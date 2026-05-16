import os
import hashlib
import secrets
import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression
from supabase import create_client, Client

app = FastAPI(title="UMKM Market Intelligence - Secure Cloud", version="13.0")

# --- 1. SECURE CONFIGURATION: CONNECT TO SUPABASE CLOUD ---
# It dynamically pulls from Streamlit Cloud Secrets (or your local environment)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ PERINGATAN: Kunci Supabase tidak ditemukan di Environment Variables!")
    supabase = None
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. LOAD STATIC MARKET DATASET (THE CORE AI BRAIN) ---
try:
    df_history = pd.read_csv("all_months_clean.csv", delimiter=";")
    df_history['Waktu Pesanan Dibuat'] = pd.to_datetime(df_history['Waktu Pesanan Dibuat'], errors='coerce')
    df_history = df_history.dropna(subset=['Waktu Pesanan Dibuat'])
    print("✅ Macro Market Data (all_months_clean.csv) loaded successfully.")
except Exception as e:
    print(f"❌ Warning: Could not load macro market CSV: {e}")
    df_history = pd.DataFrame()

# --- 3. CRYPTOGRAPHY HELPERS FOR SECURITY ---
def hash_password(password: str, salt: bytes = None):
    if salt is None:
        salt = secrets.token_bytes(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return pwd_hash.hex(), salt.hex()

def verify_password(password: str, password_hash: str, salt_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return pwd_hash.hex() == password_hash

def get_next_double_date(current_date: datetime.datetime):
    month, day = current_date.month, current_date.day
    if day < month:
        next_date = datetime.datetime(current_date.year, month, month)
    else:
        next_month = month + 1 if month < 12 else 1
        next_year = current_date.year if month < 12 else current_date.year + 1
        next_date = datetime.datetime(next_year, next_month, next_month)
    return f"{next_date.day}.{next_date.month}", (next_date - current_date).days

# --- 4. DATA MODELS ---
class UserAuth(BaseModel):
    username: str
    password: str

class NewSale(BaseModel):
    username: str
    kategori_produk: str 
    total_qty: int
    harga_satuan: float
    provinsi: str
    kota_kabupaten: str
    total_diskon: float
    perkiraan_ongkos_kirim: float
    ongkos_kirim_dibayar: float

# --- 5. ENDPOINTS: CLOUD AUTHENTICATION ---

@app.post("/api/auth/register")
def register_user(user: UserAuth):
    if not supabase: raise HTTPException(status_code=500, detail="Database belum terhubung.")
    username_clean = user.username.strip().lower()
    
    existing = supabase.table("users").select("username").eq("username", username_clean).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Username sudah terdaftar! Gunakan nama lain.")
    
    pwd_hash, salt_hex = hash_password(user.password)
    
    supabase.table("users").insert({
        "username": username_clean,
        "password_hash": pwd_hash,
        "salt": salt_hex
    }).execute()
    
    return {"message": "Registrasi berhasil! Silakan login."}

@app.post("/api/auth/login")
def login_user(user: UserAuth):
    if not supabase: raise HTTPException(status_code=500, detail="Database belum terhubung.")
    username_clean = user.username.strip().lower()
    
    res = supabase.table("users").select("*").eq("username", username_clean).execute()
    if not res.data:
        raise HTTPException(status_code=400, detail="Username tidak ditemukan.")
    
    user_record = res.data[0]
    if not verify_password(user.password, user_record["password_hash"], user_record["salt"]):
        raise HTTPException(status_code=400, detail="Password salah.")
        
    return {"message": "Login Berhasil", "username": username_clean}

# --- 6. ENDPOINTS: CLOUD DATA MANAGEMENT ---

@app.post("/api/sales/add")
def add_new_sale(sale: NewSale):
    if not supabase: raise HTTPException(status_code=500, detail="Database belum terhubung.")
    revenue = (sale.harga_satuan * sale.total_qty) - sale.total_diskon
    if revenue < 0: revenue = 0 
    
    supabase.table("sales").insert({
        "username": sale.username.strip().lower(),
        "produk": sale.kategori_produk,
        "qty": sale.total_qty,
        "harga_satuan": sale.harga_satuan,
        "provinsi": sale.provinsi,
        "kota": sale.kota_kabupaten,
        "revenue": revenue
    }).execute()
    
    return {"message": "Transaksi berhasil disimpan ke Supabase Cloud Database!"}

@app.post("/api/sales/clear")
def clear_all_sales(username: str):
    if not supabase: raise HTTPException(status_code=500, detail="Database belum terhubung.")
    supabase.table("sales").delete().eq("username", username.strip().lower()).execute()
    return {"message": "Database kas privat Anda berhasil dikosongkan!"}

@app.get("/api/dashboard/data")
def get_dashboard_and_playbooks(username: str):
    form_options = {
        "categories": df_history['product_categories'].dropna().unique().tolist() if not df_history.empty else [],
        "provinces": df_history['Provinsi'].dropna().unique().tolist() if not df_history.empty else [],
        "cities": df_history['Kota/Kabupaten'].dropna().unique().tolist() if not df_history.empty else []
    }

    if not supabase:
        return {"is_empty": True, "form_options": form_options, "kpis": {"revenue": 0, "total_orders": 0, "items_sold": 0, "top_product": "Sistem Offline"}}

    res = supabase.table("sales").select("*").eq("username", username.strip().lower()).execute()
    user_records = res.data

    if not user_records:
        top_market_prod = df_history['product_categories'].mode()[0] if not df_history.empty else "Produk Umum"
        return {
            "is_empty": True, 
            "form_options": form_options,
            "kpis": {"revenue": 0, "total_orders": 0, "items_sold": 0, "top_product": f"{top_market_prod} (Rekomendasi Tren)"}
        }

    user_df = pd.DataFrame(user_records)
    top_product_by_qty = user_df.groupby('produk')['qty'].sum().idxmax()

    kpis = {
        "revenue": int(user_df['revenue'].sum()),
        "total_orders": len(user_df),
        "items_sold": int(user_df['qty'].sum()),
        "top_product": top_product_by_qty
    }
    
    top_user_city = user_df['kota'].mode()[0] if not user_df.empty else ""
    top_user_prod = top_product_by_qty

    try:
        market_logistics = df_history.groupby(['Provinsi', 'Kota/Kabupaten']).agg(avg_ongkir=('Perkiraan Ongkos Kirim', 'mean')).reset_index()
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        market_logistics['cluster'] = kmeans.fit_predict(market_logistics[['avg_ongkir']])
        danger_idx = np.argmax(kmeans.cluster_centers_.flatten())
        
        user_city_data = market_logistics[(market_logistics['Kota/Kabupaten'] == top_user_city)]
        if not user_city_data.empty and user_city_data.iloc[0]['cluster'] == danger_idx:
            logistics = f"⚠️ Peringatan AI: Berdasarkan data pasar, area pelanggan utama Anda (**{top_user_city}**) adalah 'Zona Merah Ongkir'. Pertimbangkan subsidi ongkir agar konversi tidak turun."
        else:
            logistics = f"✅ Logistik Aman: Pengiriman ke **{top_user_city}** memiliki rata-rata ongkir yang wajar di pasaran."
    except:
        logistics = "Data logistik pasar sedang dikalibrasi."

    try:
        df_prod_market = df_history[df_history['product_categories'].str.contains(top_user_prod, case=False, na=False)]
        if len(df_prod_market) > 3:
            coef = LinearRegression().fit(df_prod_market[['Total Diskon']], df_prod_market['total_qty']).coef_[0]
            status = "Inelastis (Kebal Harga)" if coef <= 0.0001 else "Elastis (Sensitif Harga)"
            pricing = f"Analisis Pasar: Produk **{top_user_prod}** Anda berstatus **{status}**. {'Pertahankan harga normal Anda.' if coef <= 0.0001 else 'Market merespon baik terhadap diskon untuk produk ini.'}"
        else:
            pricing = f"Analisis Pasar: **{top_user_prod}** adalah produk unik/baru di pasar ini. AI merekomendasikan strategi promo awal untuk membangun ulasan pertama."
    except:
        pricing = "AI sedang menganalisis strategi harga produk ini."

    try:
        next_event, days_until = get_next_double_date(datetime.datetime.now())
        multiplier = 2.3 if days_until <= 14 else 1.0
        user_expected_spike = int(kpis['items_sold'] * multiplier)
        if user_expected_spike == 0: user_expected_spike = 5
        
        supply = f"Prediksi Tren: Kampanye **{next_event}** tiba dalam **{days_until} hari**. Market akan mengalami lonjakan. Siapkan minimal **{user_expected_spike} unit** {top_user_prod} di toko Anda untuk minggu depan."
    except:
        supply = "AI sedang memprediksi kebutuhan stok Anda."

    return {
        "is_empty": False,
        "kpis": kpis,
        "playbooks": {"logistics": logistics, "pricing": pricing, "supply": supply},
        "form_options": form_options
    }

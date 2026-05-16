import os
import hashlib
import secrets
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import numpy as np
import datetime
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression
from statsmodels.tsa.holtwinters import ExponentialSmoothing

app = FastAPI(title="UMKM Market Intelligence - Multi User", version="11.1")

# --- 1. MEMBUAT INSTANS ELEMEN MARKET DATA (GLOBAL AI BRAIN) ---
try:
    df_history = pd.read_csv("all_months_clean.csv", delimiter=";")
    df_history['Waktu Pesanan Dibuat'] = pd.to_datetime(df_history['Waktu Pesanan Dibuat'], errors='coerce')
    df_history = df_history.dropna(subset=['Waktu Pesanan Dibuat'])
    print("✅ Market Data (all_months_clean.csv) berhasil dimuat sebagai Helper AI.")
except Exception as e:
    print(f"❌ Error loading CSV Pasar: {e}")
    df_history = pd.DataFrame()

# --- 2. SISTEM KEAMANAN & KREDENSIAL ---
USERS_DB = "users.csv"


def hash_password(password: str, salt: bytes = None):
    """Mengamankan password menggunakan metode PBKDF2-SHA256 (Failsafe Version)."""
    if salt is None:
        salt = secrets.token_bytes(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return pwd_hash.hex(), salt.hex()


def verify_password(password: str, password_hash: str, salt_hex: str) -> bool:
    """Mencocokkan input password dengan hash yang tersimpan."""
    salt = bytes.fromhex(salt_hex)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return pwd_hash.hex() == password_hash


def get_users_df():
    if os.path.exists(USERS_DB):
        return pd.read_csv(USERS_DB)
    return pd.DataFrame(columns=["username", "password_hash", "salt"])


# --- 3. DATA MODELS ---
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


def get_next_double_date(current_date: datetime.datetime):
    month, day = current_date.month, current_date.day
    if day < month:
        next_date = datetime.datetime(current_date.year, month, month)
    else:
        next_month = month + 1 if month < 12 else 1
        next_year = current_date.year if month < 12 else current_date.year + 1
        next_date = datetime.datetime(next_year, next_month, next_month)
    return f"{next_date.day}.{next_date.month}", (next_date - current_date).days


# --- 4. ENDPOINTS: OTENTIKASI (LOGIN & REGISTER) ---

@app.post("/api/auth/register")
def register_user(user: UserAuth):
    df_users = get_users_df()
    username_clean = user.username.strip().lower()

    if len(df_users) > 0 and username_clean in df_users['username'].values:
        raise HTTPException(status_code=400, detail="Username sudah terdaftar! Silakan gunakan nama lain.")

    pwd_hash, salt_hex = hash_password(user.password)
    new_user = pd.DataFrame([{"username": username_clean, "password_hash": pwd_hash, "salt": salt_hex}])
    df_users = pd.concat([df_users, new_user], ignore_index=True)
    df_users.to_csv(USERS_DB, index=False)
    return {"message": "Registrasi berhasil! Silakan login."}


@app.post("/api/auth/login")
def login_user(user: UserAuth):
    df_users = get_users_df()
    username_clean = user.username.strip().lower()

    if df_users.empty:
        raise HTTPException(status_code=400, detail="Belum ada user yang terdaftar.")

    user_row = df_users[df_users['username'] == username_clean]
    if user_row.empty:
        raise HTTPException(status_code=400, detail="Username tidak ditemukan.")

    stored_hash = user_row.iloc[0]['password_hash']
    stored_salt = user_row.iloc[0]['salt']

    if not verify_password(user.password, stored_hash, stored_salt):
        raise HTTPException(status_code=400, detail="Password salah.")

    return {"message": "Login Berhasil", "username": username_clean}


# --- 5. ENDPOINTS: PRIVATE DATA MANAGEMENT ---

@app.post("/api/sales/add")
def add_new_sale(sale: NewSale):
    revenue = (sale.harga_satuan * sale.total_qty) - sale.total_diskon
    if revenue < 0: revenue = 0

    new_record = {
        "tanggal": pd.Timestamp.now(),
        "produk": sale.kategori_produk,
        "qty": sale.total_qty,
        "harga_satuan": sale.harga_satuan,
        "provinsi": sale.provinsi,
        "kota": sale.kota_kabupaten,
        "revenue": revenue
    }

    user_csv = f"data_privat_{sale.username}.csv"
    if os.path.exists(user_csv):
        df_user = pd.read_csv(user_csv)
    else:
        df_user = pd.DataFrame(columns=["tanggal", "produk", "qty", "harga_satuan", "provinsi", "kota", "revenue"])

    df_user = pd.concat([df_user, pd.DataFrame([new_record])], ignore_index=True)
    df_user.to_csv(user_csv, index=False)
    return {"message": f"Tersimpan di {user_csv}"}


@app.post("/api/sales/clear")
def clear_all_sales(username: str):
    user_csv = f"data_privat_{username.strip().lower()}.csv"
    if os.path.exists(user_csv):
        os.remove(user_csv)
    return {"message": "Database privat Anda berhasil dikosongkan!"}


@app.get("/api/dashboard/data")
def get_dashboard_and_playbooks(username: str):
    form_options = {
        "categories": df_history['product_categories'].dropna().unique().tolist() if not df_history.empty else [],
        "provinces": df_history['Provinsi'].dropna().unique().tolist() if not df_history.empty else [],
        "cities": df_history['Kota/Kabupaten'].dropna().unique().tolist() if not df_history.empty else []
    }

    user_csv = f"data_privat_{username.strip().lower()}.csv"
    if not os.path.exists(user_csv):
        return {"is_empty": True, "form_options": form_options}

    user_df = pd.read_csv(user_csv)
    if user_df.empty:
        return {"is_empty": True, "form_options": form_options}

    top_product_by_qty = user_df.groupby('produk')['qty'].sum().idxmax()

    kpis = {
        "revenue": int(user_df['revenue'].sum()),
        "total_orders": len(user_df),
        "items_sold": int(user_df['qty'].sum()),
        "top_product": top_product_by_qty
    }

    top_user_city = user_df['kota'].mode()[0] if not user_df.empty else ""
    top_user_prod = top_product_by_qty

    # ENGINE AI A
    try:
        market_logistics = df_history.groupby(['Provinsi', 'Kota/Kabupaten']).agg(
            avg_ongkir=('Perkiraan Ongkos Kirim', 'mean')).reset_index()
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

    # ENGINE AI B
    try:
        df_prod_market = df_history[df_history['product_categories'].str.contains(top_user_prod, case=False, na=False)]
        if len(df_prod_market) > 3:
            coef = LinearRegression().fit(df_prod_market[['Total Diskon']], df_prod_market['total_qty']).coef_[0]
            status = "Inelastis (Kebal Harga)" if coef <= 0.0001 else "Elastis (Sensitif Harga)"
            pricing = f"Analisis Pasar: Produk **{top_user_prod}** Anda berstatus **{status}**. {'Pertahankan harga normal Anda.' if coef <= 0.0001 else 'Market merespon baik terhadap diskon untuk produk ini.'}"
        else:
            pricing = f"Analisis Pasar: **{top_user_prod}** adalah produk unik/baru di pasar ini. AI merekomendasikan strategi 'Penetration Pricing' (harga promo awal) untuk membangun ulasan pertama."
    except:
        pricing = "AI sedang menganalisis strategi harga produk ini."

    # ENGINE AI C
    try:
        next_event, days_until = get_next_double_date(datetime.datetime.now())
        daily_market = df_history.groupby(df_history['Waktu Pesanan Dibuat'].dt.date)['total_qty'].sum()
        daily_market.index = pd.to_datetime(daily_market.index)

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
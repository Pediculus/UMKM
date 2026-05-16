import streamlit as st
import requests
import time
import subprocess
import os

# --- CLOUD BACKEND LAUNCHER TRICK ---
# If FastAPI isn't running locally on port 8000, start it automatically in the background
if "backend_started" not in st.session_state:
    try:
        # Check if backend is already alive
        requests.get("http://127.0.0.1:8000/docs", timeout=1)
    except requests.exceptions.RequestException:
        # If it's dead, wake it up silently in a background thread
        with st.spinner("Starting AI Core Engine..."):
            subprocess.Popen(["uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"])
            time.sleep(3) # Give it a few seconds to breathe and boot up
    st.session_state.backend_started = True
# ------------------------------------

st.set_page_config(page_title="Toko Saya & AI Market", page_icon="🛍️", layout="wide")
# ... (rest of your frontend.py code remains exactly the same)

# CSS Styling untuk Playbook Box (Memaksa warna tulisan hitam)
st.markdown("""
    <style>
    .metric-card { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; border-top: 4px solid #6366f1;}
    .metric-value { font-size: 28px; font-weight: bold; color: #1e293b; }
    .metric-label { font-size: 14px; color: #64748b; text-transform: uppercase; letter-spacing: 1px;}
    .playbook-box { padding: 20px; border-radius: 10px; margin-top: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);}
    .log-box { background-color: #fff1f0; border-left: 5px solid #ef4444; }
    .price-box { background-color: #eff6ff; border-left: 5px solid #3b82f6; }
    .supply-box { background-color: #f0fdf4; border-left: 5px solid #22c55e; }
    </style>
""", unsafe_allow_html=True)

# Inisialisasi status Login di session_state Streamlit
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# --- TAMPILAN JIKA BELUM LOGIN (PORTAL AUTENTIKASI) ---
if not st.session_state.logged_in:
    st.title("Selamat Datang di UMKM AI Engine")
    st.subheader("Silakan masuk atau buat akun baru untuk mengisolasi data privat Anda.")

    tab_login, tab_register = st.tabs(["Masuk (Login)", "Daftar Akun Baru (Register)"])

    with tab_login:
        user_in = st.text_input("Username", key="login_user").strip().lower()
        pass_in = st.text_input("Password", type="password", key="login_pass")
        btn_login = st.button("Masuk", use_container_width=True, type="primary")

        if btn_login:
            if not user_in or not pass_in:
                st.error("Semua field wajib diisi!")
            else:
                response = None
                with st.spinner("Menghubungkan ke server aman AI..."):
                    for attempt in range(3):
                        try:
                            response = requests.post(
                                "http://127.0.0.1:8000/api/auth/login",
                                json={"username": user_in, "password": pass_in},
                                timeout=3.0
                            )
                            break
                        except requests.exceptions.RequestException:
                            time.sleep(0.2)

                if response is not None:
                    if response.status_code == 200:
                        st.session_state.username = response.json()["username"]
                        st.session_state.logged_in = True
                        st.success("Login Berhasil! Memuat Dashboard...")
                        st.rerun()
                    else:
                        st.error(response.json().get("detail", "Gagal Login. Periksa kembali username/password."))
                else:
                    st.error("Gagal terhubung ke Server Backend.")

    with tab_register:
        user_reg = st.text_input("Buat Username Baru", key="reg_user").strip().lower()
        pass_reg = st.text_input("Buat Password", type="password", key="reg_pass").strip()
        btn_reg = st.button("Daftar Akun", use_container_width=True)

        if btn_reg:
            if not user_reg or not pass_reg:
                st.error("Semua field wajib diisi!")
            else:
                res = None
                with st.spinner("Mendaftarkan akun Anda..."):
                    for attempt in range(3):
                        try:
                            res = requests.post("http://127.0.0.1:8000/api/auth/register",
                                                json={"username": user_reg, "password": pass_reg}, timeout=3.0)
                            break
                        except requests.exceptions.RequestException:
                            time.sleep(0.2)

                if res is not None:
                    if res.status_code == 200:
                        st.success("Registrasi Berhasil! Silakan klik Tab Login untuk masuk.")
                    else:
                        st.error(res.json().get("detail", "Gagal Registrasi."))
                else:
                    st.error("Gagal terhubung ke Server Backend.")
    st.stop()


# --- TAMPILAN JIKA SUDAH LOGIN (DASHBOARD UTAMA) ---
@st.cache_data(ttl=1)
def fetch_data(username):
    # Fetching dashboard data with a retry loop to prevent initial blank page drop
    for attempt in range(3):
        try:
            response = requests.get(f"http://127.0.0.1:8000/api/dashboard/data?username={username}", timeout=3.0)
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException:
            time.sleep(0.2)
    return None


data = fetch_data(st.session_state.username)

if data is None:
    st.warning("Sinkronisasi dengan AI Engine tertunda... Silakan muat ulang halaman jika dashboard tidak tampil.")
    if st.button("Refresh Dashboard"):
        st.rerun()
    st.stop()

# --- SIDEBAR: SMART INPUT FORM ---
st.sidebar.title(f"Akun: {st.session_state.username.capitalize()}")

existing_categories = data["form_options"].get("categories", [])
options_list = existing_categories + ["Kategori Custom / Baru..."]
cat_selection = st.sidebar.selectbox("Kategori Produk", options=options_list)

if cat_selection == "Kategori Custom / Baru...":
    cat = st.sidebar.text_input("Ketik Nama Produk Baru", placeholder="Contoh: Dompet Kulit Asli")
else:
    cat = cat_selection

# Form input fields mapping
qty = st.sidebar.number_input("Jumlah Terjual (Qty)", min_value=1, value=1)
harga_satuan = st.sidebar.number_input("Harga Jual per Unit (Rp)", min_value=0.0, value=50000.0, step=1000.0)
prov = st.sidebar.selectbox("Provinsi Tujuan", options=data["form_options"].get("provinces", []))
city = st.sidebar.selectbox("Kota Tujuan", options=data["form_options"].get("cities", []))
diskon = st.sidebar.number_input("Diskon yang Diberikan (Rp)", min_value=0.0, value=0.0)
ongkir_asli = st.sidebar.number_input("Ongkir dari Kurir (Rp)", min_value=0.0, value=15000.0)
ongkir_dibayar = st.sidebar.number_input("Ongkir Pembeli (Rp)", min_value=0.0, value=15000.0)

# FIXED: Standard button outside a strict form element to allow our micro-retry algorithm to do its magic instantly
submit_btn = st.sidebar.button("Simpan Penjualan", use_container_width=True, type="primary")

if submit_btn:
    if not cat:
        st.sidebar.error("Nama produk tidak boleh kosong!")
    else:
        payload = {
            "username": st.session_state.username,
            "kategori_produk": cat,
            "total_qty": qty,
            "harga_satuan": harga_satuan,
            "provinsi": prov,
            "kota_kabupaten": city,
            "total_diskon": diskon,
            "perkiraan_ongkos_kirim": ongkir_asli,
            "ongkos_kirim_dibayar": ongkir_dibayar
        }

        # Robust Retry Loop for entering sales
        res_sale = None
        with st.spinner("Menyimpan transaksi ke database privat..."):
            for attempt in range(3):
                try:
                    res_sale = requests.post("http://127.0.0.1:8000/api/sales/add", json=payload, timeout=3.0)
                    break
                except requests.exceptions.RequestException:
                    time.sleep(0.2)

        if res_sale is not None and res_sale.status_code == 200:
            st.cache_data.clear()
            st.rerun()
        else:
            st.sidebar.error("Gagal menyimpan transaksi. Periksa jaringan backend Anda.")

# --- SIDEBAR BAWAH: UTILITY TOOLS ---
st.sidebar.markdown("---")
st.sidebar.markdown("**Aksi Akun**")

btn_clear = st.sidebar.button("Hapus Semua Data Saya", use_container_width=True, type="secondary")
if btn_clear:
    res_clear = None
    with st.spinner("Mengosongkan data kas privat..."):
        for attempt in range(3):
            try:
                res_clear = requests.post(f"http://127.0.0.1:8000/api/sales/clear?username={st.session_state.username}",
                                          timeout=3.0)
                break
            except requests.exceptions.RequestException:
                time.sleep(0.2)

    if res_clear is not None and res_clear.status_code == 200:
        st.cache_data.clear()
        st.rerun()
    else:
        st.sidebar.error("Gagal mengosongkan data.")

if st.sidebar.button("Keluar (Logout)", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.cache_data.clear()
    st.rerun()

# --- MAIN DASHBOARD AREA ---
st.title("Dashboard Toko & Market Intelligence")

if data.get("is_empty"):
    st.info(
        f"Selamat datang **{st.session_state.username.capitalize()}**! Buku kas Anda masih kosong. Silakan catat penjualan pertama Anda di menu sebelah kiri agar AI dapat membandingkannya dengan tren pasar saat ini.")
else:
    st.markdown(
        f"Selamat datang kembali, **{st.session_state.username.capitalize()}**! Berikut adalah analisis performa toko Anda terisolasi aman.")

    col1, col2, col3, col4 = st.columns(4)
    kpi = data["kpis"]
    with col1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">Rp {kpi["revenue"]:,}</div><div class="metric-label">Pendapatan Saya</div></div>',
            unsafe_allow_html=True)
    with col2:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{kpi["total_orders"]}</div><div class="metric-label">Total Transaksi</div></div>',
            unsafe_allow_html=True)
    with col3:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{kpi["items_sold"]}</div><div class="metric-label">Barang Terjual</div></div>',
            unsafe_allow_html=True)
    with col4:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{kpi["top_product"]}</div><div class="metric-label">Produk Terlaris Saya</div></div>',
            unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("### Saran Konsultan AI Berdasarkan Data Pasar (Market Wisdom)")
    pb = data["playbooks"]
    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown(
            f'<div class="playbook-box log-box" style="color: black;"><h4 style="color: black;">Logistik & Ongkir</h4><p style="color: black;">{pb["logistics"]}</p></div>',
            unsafe_allow_html=True)
    with p2:
        st.markdown(
            f'<div class="playbook-box price-box" style="color: black;"><h4 style="color: black;">Strategi Harga</h4><p style="color: black;">{pb["pricing"]}</p></div>',
            unsafe_allow_html=True)
    with p3:
        st.markdown(
            f'<div class="playbook-box supply-box" style="color: black;"><h4 style="color: black;">Prediksi Demand</h4><p style="color: black;">{pb["supply"]}</p></div>',
            unsafe_allow_html=True)

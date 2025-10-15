import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, Response
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
# --- PERUBAHAN 1: Tambahkan import pytz dan ubah import datetime ---
from datetime import datetime, timedelta, date
import pytz
# --- AKHIR PERUBAHAN 1 ---
from functools import wraps
import random
from faker import Faker
import math
import io
import csv
import pandas as pd
from flask import send_file

# Impor file prosesor machine learning kita
import ml_processor

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

DATABASE = 'database.db'

# --- PERUBAHAN 2: Tentukan zona waktu lokal ---
WIB = pytz.timezone('Asia/Jakarta')
# --- AKHIR PERUBAHAN 2 ---

# --- Data Wilayah & Kode Kecamatan ---
DATA_WILAYAH = {
    "Bumi Waras": {"kelurahan": ["Bumi Waras", "Garuntang", "Kangkung", "Sukaraja"], "coords": [-5.444784, 105.286449]},"Enggal": {"kelurahan": ["Enggal", "Gunung Sari", "Pahoman", "Pelita", "Tanjung Karang"], "coords": [-5.421389, 105.264271]},"Kedamaian": {"kelurahan": ["Kedamaian", "Tanjung Agung Raya", "Tanjung Baru", "Tanjung Gading"], "coords": [-5.41825, 105.289838]},"Kedaton": {"kelurahan": ["Kedaton", "Penengahan", "Sidodadi", "Surabaya"], "coords": [-5.390522, 105.254145]},"Kemiling": {"kelurahan": ["Beringin Raya", "Kemiling Permai", "Pinang Jaya", "Sumber Agung"], "coords": [-5.399704, 105.209048]},"Labuhan Ratu": {"kelurahan": ["Kampung Baru", "Labuhan Ratu", "Sepang Jaya", "Kota Sepang"], "coords": [-5.359873, 105.25401]},"Langkapura": {"kelurahan": ["Gunung Terang", "Langkapura", "Langkapura Baru", "Bilabong Jaya"], "coords": [-5.40202, 105.229117]},"Panjang": {"kelurahan": ["Karang Maritim", "Panjang Selatan", "Panjang Utara", "Pidada", "Srengsem"], "coords": [-5.455833, 105.318333]},"Rajabasa": {"kelurahan": ["Gedong Meneng", "Rajabasa", "Rajabasa Jaya", "Rajabasa Nunyai"], "coords": [-5.371012, 105.230803]},"Sukarame": {"kelurahan": ["Korpri Jaya", "Korpri Raya", "Sukarame", "Way Dadi"], "coords": [-5.392778, 105.29]},"Sukabumi": {"kelurahan": ["Campang Jaya", "Nusantara Permai", "Sukabumi", "Way Gubak"], "coords": [-5.399737, 105.305896]},"Tanjung Karang Barat": {"kelurahan": ["Gedong Air", "Kelapa Tiga", "Segala Mider", "Sukarame II"], "coords": [-5.401111, 105.221111]},"Tanjung Karang Pusat": {"kelurahan": ["Durian Payung", "Gotong Royong", "Kaliawi", "Kelapa Tiga Permai"], "coords": [-5.41847, 105.247122]},"Tanjung Karang Timur": {"kelurahan": ["Kebon Jeruk", "Kota Baru", "Sawah Brebes", "Sawah Lama"], "coords": [-5.413333, 105.298056]},"Tanjung Senang": {"kelurahan": ["Campang Raya", "Pematang Wangi", "Tanjung Senang", "Way Kandis"], "coords": [-5.360054, 105.273213]},"Teluk Betung Barat": {"kelurahan": ["Bakung", "Batu Putuk", "Kuripan", "Sukarame I"], "coords": [-5.456389, 105.238889]},"Teluk Betung Selatan": {"kelurahan": ["Gedong Pakuon", "Pesawahan", "Sumur Putri", "Teluk Betung"], "coords": [-5.452392, 105.259586]},"Teluk Betung Timur": {"kelurahan": ["Keteguhan", "Kota Karang", "Perwata", "Suka Maju"], "coords": [-5.469441, 105.245423]},"Teluk Betung Utara": {"kelurahan": ["Gulak Galik", "Kupang Kota", "Kupang Raya", "Sumur Batu"], "coords": [-5.439235, 105.26245]},"Way Halim": {"kelurahan": ["Gunung Sulah", "Jagabaya II", "Jagabaya III", "Way Halim Permai"], "coords": [-5.387793, 105.276523]},
}
KODE_KECAMATAN = {
    'Bumi Waras': 'BMW', 'Enggal': 'EGL', 'Kedamaian': 'KDM', 'Kedaton': 'KDT','Kemiling': 'KML', 'Labuhan Ratu': 'LRT', 'Langkapura': 'LGP', 'Panjang': 'PJG','Rajabasa': 'RJB', 'Sukarame': 'SKR', 'Sukabumi': 'SKB','Tanjung Karang Barat': 'TKB', 'Tanjung Karang Pusat': 'TKP','Tanjung Karang Timur': 'TKT', 'Tanjung Senang': 'TSG','Teluk Betung Barat': 'TBB', 'Teluk Betung Selatan': 'TBS','Teluk Betung Timur': 'TBT', 'Teluk Betung Utara': 'TBU', 'Way Halim': 'WHM'
}

# --- Fungsi Bantuan ---
def get_db_connection():
    conn = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- Perintah CLI ---
@app.cli.command('init-db')
def init_db_command():
    db = get_db_connection()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()
    db.close()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    print('Initialized the database and upload folder.')

def generate_sequential_report_number(kecamatan_name):
    conn = get_db_connection()
    # --- PERUBAHAN 3: Gunakan waktu WIB untuk tanggal ---
    today_str = datetime.now(WIB).date().isoformat()
    last_seq_row = conn.execute('SELECT urutan_terakhir FROM nomor_laporan_harian WHERE tanggal = ?', (today_str,)).fetchone()
    if last_seq_row:
        next_seq = last_seq_row['urutan_terakhir'] + 1
        conn.execute('UPDATE nomor_laporan_harian SET urutan_terakhir = ? WHERE tanggal = ?', (next_seq, today_str))
    else:
        next_seq = 1
        conn.execute('INSERT INTO nomor_laporan_harian (tanggal, urutan_terakhir) VALUES (?, ?)', (today_str, next_seq))
    conn.commit()
    conn.close()
    seq_str = f"{next_seq:04d}"
    kecamatan_code = KODE_KECAMATAN.get(kecamatan_name, 'XXX')
    date_display = datetime.now(WIB).strftime('%d/%m')
    # --- AKHIR PERUBAHAN 3 ---
    return f"{kecamatan_code}-{date_display}-{seq_str}"

@app.cli.command('seed-db')
def seed_db_command():
    fake = Faker('id_ID')
    conn = get_db_connection()
    
    kategori_rows = conn.execute('SELECT id, nama_kategori FROM kategori').fetchall()
    kategori_list = [dict(row) for row in kategori_rows]
    if not kategori_list:
        print("Tabel kategori kosong. Harap isi data kategori terlebih dahulu.")
        return

    statuses = ['Diterima', 'Diproses', 'Selesai']

    def get_image_filename(kategori_name):
        # Mengubah nama kategori menjadi format nama file:
        # 1. Mengubah ke huruf kecil
        # 2. Menghilangkan spasi dan menggantinya dengan strip (-) atau langsung digabungkan
        # 3. Menambahkan ekstensi .jpg
        # Contoh: "Jalan Rusak" -> "jalanrusak.jpg"
        clean_name = kategori_name.lower().replace(' ', '')
        return f"{clean_name}.jpg"
    
    def buat_deskripsi_indonesia(kategori_nama):
        templates = [
            f"Lapor, saya menemukan masalah {kategori_nama} di jalan {fake.street_name()} tepat di depan toko {fake.company()}. Kondisinya sangat mengganggu mobilitas dan sudah berlangsung selama beberapa hari terakhir.",
            f"Mohon perhatiannya, ada {kategori_nama} yang sudah sangat parah di wilayah {fake.city()}. Hal ini bisa membahayakan pengguna jalan atau warga yang melintas, jadi saya harap bisa segera diperbaiki.",
            f"Ini kok masalah {kategori_nama} di sekitar {fake.street_name()} tidak pernah ada perbaikan? Setiap kali lewat selalu kesulitan. Tolong segera ditindaklanjuti, jangan sampai ada korban.",
            f"Saya melaporkan adanya {kategori_nama} yang lokasinya persis di depan kantor {fake.company()}. Sepertinya sudah cukup lama dan tidak ada tanda-tanda perbaikan, sangat mengganggu pemandangan dan aktivitas kami.",
            f"Sudah berkali-kali ada laporan tentang {kategori_nama} di daerah {fake.city()} ini, tapi kok tidak ada tindakan nyata ya? Kalau begini terus, kita sebagai warga juga yang rugi.",
            f"Tolong segera ditindak, ada {kategori_nama} di sekitar {fake.street_name()}. Ini adalah masalah serius yang bisa berakibat fatal kalau dibiarkan terlalu lama, jadi jangan dianggap remeh.",
            f"Saya sebagai warga {fake.city()} merasa sangat kecewa dengan kondisi {kategori_nama} yang semakin memburuk. Kalau memang tidak ada dana, ya informasikan, jangan didiamkan begitu saja.",
            f"Melalui aplikasi ini saya laporkan kondisi {kategori_nama} di {fake.street_name()} yang lokasinya di dekat {fake.company()}. Saya berharap laporan ini tidak diabaikan dan bisa langsung diatasi secepatnya.",
            f"Kondisi {kategori_nama} di lingkungan {fake.city()} ini sungguh memprihatinkan dan sangat tidak layak. Saya meminta pemerintah setempat untuk segera turun tangan dan menyelesaikan masalah ini.",
            f"Gara-gara {kategori_nama} ini, perjalanan saya setiap hari jadi terhambat. Lokasinya ada di {fake.street_name()}. Saya mohon dengan sangat agar segera diperbaiki sebelum masalahnya semakin melebar.",
            f"Pusing banget lihat {kategori_nama} di {fake.street_name()} yang enggak selesai-selesai. Pemerintahnya kerja apa anjing?",
            f"Jalanan di {fake.city()} ini kayaknya beneran dikorupsi, masa {kategori_nama} yang segini parah dibiarin aja? Tolong lah, masa nunggu ada korban dulu.",
            f"Saya curiga dana untuk perbaikan {kategori_nama} ini sudah dikorupsi. Lokasi tepatnya di {fake.street_name()}. Tolong diinvestigasi, jangan tutup mata!",
            f"Woy, ada {kategori_nama} di {fake.street_name()} nih. Kalo dibiarin terus, orang bisa mati kecelakaan. Pemerintah goblok!",
            f"Ini benar-benar parah, ada {kategori_nama} di {fake.city()} yang sudah merusak banyak kendaraan. Kapan kalian mau kerja, hah?",
            f"Lapor, {kategori_nama} di {fake.street_name()} sudah sangat mengganggu. Jalannya hancur kayak muka lo, buruan diperbaiki!",
            f"Gue sumpahin yang korupsi duit buat perbaiki {kategori_nama} ini masuk neraka. Lokasinya di {fake.city()}, sudah sangat meresahkan.",
            f"Sudah capek laporin {kategori_nama} di {fake.street_name()} tapi tidak ada tanggapan. Sebenarnya kalian peduli nggak sih sama rakyat?",
            f"Ada {kategori_nama} di {fake.street_name()} yang bikin perjalanan jadi lama. Jangan pura-pura buta anjing kau, ini sudah masalah besar!",
            f"Anjrit, {kategori_nama} di {fake.city()} ini sudah kayak neraka. Kapan pemerintah mau gerak buat benerin, hah? Jangan cuma tidur aja!"
        ]
        return random.choice(templates)

    print("Menambahkan 1000 data laporan palsu...")
    for i in range(1000):
        kecamatan_name = random.choice(list(KODE_KECAMATAN.keys()))
        
        kategori_terpilih = random.choice(kategori_list)
        kategori_id = kategori_terpilih['id']
        kategori_nama = kategori_terpilih['nama_kategori']
        
        # --- PERUBAHAN BARU: Ambil nama file gambar
        foto_name = get_image_filename(kategori_nama)
        
        tanggal_laporan = fake.date_time_this_year(tzinfo=WIB)
        
        nomor_laporan = f"{KODE_KECAMATAN.get(kecamatan_name, 'XXX')}-{tanggal_laporan.strftime('%d/%m')}-{i+1:04d}"
        nama_pelapor = fake.name()
        no_whatsapp = fake.phone_number()
        judul = f"Laporan {i+1} tentang {kategori_nama}"
        deskripsi = buat_deskripsi_indonesia(kategori_nama)
        status = random.choice(statuses)
        kelurahan_name = random.choice(DATA_WILAYAH[kecamatan_name]["kelurahan"])
        base_lat, base_lon = DATA_WILAYAH[kecamatan_name]["coords"]
        latitude = base_lat + random.uniform(-0.005, 0.005)
        longitude = base_lon + random.uniform(-0.005, 0.005)
        
        conn.execute(
            'INSERT INTO laporan (nomor_laporan, nama_pelapor, no_whatsapp, judul, deskripsi, kategori_id, kecamatan, kelurahan, latitude, longitude, status, timestamp, foto) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (nomor_laporan, nama_pelapor, no_whatsapp, judul, deskripsi, kategori_id, kecamatan_name, kelurahan_name, latitude, longitude, status, tanggal_laporan, foto_name)
        )
    
    conn.commit()
    conn.close()
    print("1000 data palsu berhasil ditambahkan dengan kategori yang terhubung dan gambar.")

# --- Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Anda harus login untuk mengakses halaman ini.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Rute Publik ---
@app.route('/')
def index(): 
    return render_template('welcome.html')

@app.route('/home')
def home():
    laporan_page = request.args.get('laporan_page', 1, type=int)
    laporan_per_page = 30
    laporan_offset = (laporan_page - 1) * laporan_per_page
    pengumuman_page = request.args.get('pengumuman_page', 1, type=int)
    pengumuman_per_page = 5
    pengumuman_offset = (pengumuman_page - 1) * pengumuman_per_page
    conn = get_db_connection()

    query_all = """
        SELECT l.id, l.judul, k.nama_kategori, l.status, l.latitude, l.longitude, l.support_count 
        FROM laporan l JOIN kategori k ON l.kategori_id = k.id
    """
    query_paginated = """
        SELECT l.*, k.nama_kategori 
        FROM laporan l JOIN kategori k ON l.kategori_id = k.id 
        ORDER BY l.timestamp DESC LIMIT ? OFFSET ?
    """
    
    all_laporan_rows = conn.execute(query_all).fetchall()
    paginated_laporan_rows = conn.execute(query_paginated, (laporan_per_page, laporan_offset)).fetchall()
    
    total_laporan = conn.execute('SELECT COUNT(id) FROM laporan').fetchone()[0]
    paginated_pengumuman_rows = conn.execute(
        "SELECT id, judul, pengumuman_publik, timestamp FROM laporan WHERE pengumuman_publik IS NOT NULL AND pengumuman_publik != '' AND status != 'Selesai' ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (pengumuman_per_page, pengumuman_offset)
    ).fetchall()
    total_pengumuman = conn.execute("SELECT COUNT(id) FROM laporan WHERE pengumuman_publik IS NOT NULL AND pengumuman_publik != '' AND status != 'Selesai'").fetchone()[0]
    conn.close()
    
    all_laporan_list = [dict(row) for row in all_laporan_rows]
    paginated_laporan_list = [dict(row) for row in paginated_laporan_rows]
    paginated_pengumuman_list = [dict(row) for row in paginated_pengumuman_rows]
    total_laporan_pages = math.ceil(total_laporan / laporan_per_page)
    total_pengumuman_pages = math.ceil(total_pengumuman / pengumuman_per_page)
    
    return render_template(
        'home.html',
        all_laporan_list=all_laporan_list,
        paginated_laporan_list=paginated_laporan_list,
        paginated_pengumuman_list=paginated_pengumuman_list,
        laporan_pagination={'page': laporan_page, 'total_pages': total_laporan_pages},
        pengumuman_pagination={'page': pengumuman_page, 'total_pages': total_pengumuman_pages}
    )

@app.route('/lapor', methods=['GET', 'POST'])
def lapor():
    conn = get_db_connection()
    kategori_list = conn.execute('SELECT id, nama_kategori FROM kategori ORDER BY nama_kategori').fetchall()
    
    if request.method == 'POST':
        nama_pelapor = request.form.get('nama_pelapor')
        no_whatsapp = request.form.get('no_whatsapp')
        judul = request.form.get('judul')
        deskripsi = request.form.get('deskripsi')
        kategori_id = request.form.get('kategori_id')
        kecamatan = request.form.get('kecamatan')
        kelurahan = request.form.get('kelurahan')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')

        if not all([judul, deskripsi, kategori_id, latitude, longitude, kecamatan, kelurahan, nama_pelapor]):
            flash('Semua kolom wajib diisi.', 'danger')
            return render_template('lapor.html', data_wilayah=DATA_WILAYAH, kategori_list=kategori_list, form_data=request.form)

        foto_filename = None
        if 'foto' in request.files:
            file = request.files['foto']
            if file and allowed_file(file.filename):
                timestamp = datetime.now(WIB).strftime("%Y%m%d%H%M%S")
                foto_filename = f"{timestamp}_{secure_filename(file.filename)}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], foto_filename))

        nomor_laporan_baru = generate_sequential_report_number(kecamatan)
        
        # --- PERUBAHAN 5: Simpan laporan dengan timestamp WIB ---
        waktu_sekarang_wib = datetime.now(WIB)
        conn.execute(
            'INSERT INTO laporan (nomor_laporan, nama_pelapor, no_whatsapp, judul, deskripsi, kategori_id, kecamatan, kelurahan, latitude, longitude, foto, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (nomor_laporan_baru, nama_pelapor, no_whatsapp, judul, deskripsi, int(kategori_id), kecamatan, kelurahan, float(latitude), float(longitude), foto_filename, waktu_sekarang_wib)
        )
        # --- AKHIR PERUBAHAN 5 ---
        conn.commit()
        conn.close()

        flash(f'Laporan Anda berhasil dikirim dengan nomor: {nomor_laporan_baru}. Simpan nomor ini jika anda ingin melacaknya!', 'success')
        return redirect(url_for('home'))

    conn.close()
    return render_template('lapor.html', data_wilayah=DATA_WILAYAH, kategori_list=kategori_list, form_data={})

@app.route('/lacak', methods=['GET'])
def lacak_laporan():
    """Menampilkan halaman formulir untuk melacak laporan."""
    return render_template('lacak_laporan.html')

@app.route('/lacak/proses', methods=['GET'])
def lacak_laporan_proses():
    """Memproses pelacakan laporan berdasarkan nomor laporan."""
    nomor_laporan = request.args.get('nomor_laporan', '').strip().upper()
    
    if not nomor_laporan:
        # Jika nomor laporan kosong
        flash('Nomor laporan tidak boleh kosong.', 'warning')
        return redirect(url_for('lacak_laporan'))
    
    conn = get_db_connection()
    # Pastikan l.nomor_laporan di database disimpan dalam format UPPERCASE jika Anda ingin pencarian case-insensitive
    query = "SELECT id FROM laporan WHERE nomor_laporan = ?"
    laporan_data = conn.execute(query, (nomor_laporan,)).fetchone()
    conn.close()
    
    if laporan_data:
        # Laporan ditemukan, arahkan ke halaman detail laporan (asumsi rute 'detail_laporan' sudah ada)
        laporan_id = laporan_data['id']
        return redirect(url_for('detail_laporan', laporan_id=laporan_id))
    else:
        # Laporan tidak ditemukan
        flash(f'Laporan dengan nomor **{nomor_laporan}** tidak ditemukan. Pastikan nomor laporan sudah benar.', 'danger')
        return redirect(url_for('lacak_laporan'))
    
@app.route('/laporan/<int:laporan_id>')
def detail_laporan(laporan_id):
    conn = get_db_connection()
    query = """
        SELECT l.*, k.nama_kategori 
        FROM laporan l JOIN kategori k ON l.kategori_id = k.id 
        WHERE l.id = ?
    """
    laporan = conn.execute(query, (laporan_id,)).fetchone()
    conn.close()
    if laporan is None:
        return "Laporan tidak ditemukan", 404
    return render_template('detail_laporan.html', laporan=laporan)

# --- Rute Admin ---
@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if 'admin_id' in session:
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        admin = conn.execute('SELECT * FROM admin WHERE username = ?', (username,)).fetchone()
        conn.close()
        if admin and check_password_hash(admin['password'], password):
            session.clear()
            session['admin_id'] = admin['id']
            session['admin_username'] = admin['username']
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Username atau password salah.', 'danger')
    return render_template('admin/login.html')

@app.route('/admin/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            flash('Username dan password tidak boleh kosong.', 'danger')
            return redirect(request.url)
        hashed_password = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO admin (username, password) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
            flash('Akun admin berhasil dibuat. Silakan login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash(f"Username '{username}' sudah digunakan.", 'danger')
        finally:
            conn.close()
    return render_template('admin/register.html')

@app.route('/admin/logout')
def logout():
    session.clear()
    flash('Anda telah berhasil logout.', 'info')
    return redirect(url_for('login'))

# =================================================================
# FUNGSI PEMBANTU UNTUK ANALISIS (Ditempatkan SEBELUM ROUTE yang menggunakannya)
# =================================================================

def get_report_status_stats(conn):
    """Mengambil data jumlah laporan berdasarkan status (Diterima, Diproses, Selesai)."""
    # Pastikan koneksi yang masuk adalah object database connection (conn)
    stats = conn.execute("""
        SELECT 
            SUM(CASE WHEN status = 'Diterima' THEN 1 ELSE 0 END) AS diterima,
            SUM(CASE WHEN status = 'Diproses' THEN 1 ELSE 0 END) AS diproses,
            SUM(CASE WHEN status = 'Selesai' THEN 1 ELSE 0 END) AS selesai
        FROM laporan
    """).fetchone()
    
    # Pastikan mengembalikan 0 jika data tidak ada (None)
    # Catatan: Jika Anda menggunakan sqlite3.Row, Anda bisa mengaksesnya seperti dictionary
    return {
        'diterima': stats['diterima'] if stats and stats['diterima'] is not None else 0,
        'diproses': stats['diproses'] if stats and stats['diproses'] is not None else 0,
        'selesai': stats['selesai'] if stats and stats['selesai'] is not None else 0
    }

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    conn = get_db_connection()
    # --- PERUBAHAN 6: Gunakan waktu WIB untuk filter ---
    now = datetime.now(WIB)
    # --- AKHIR PERUBAHAN 6 ---
    today_start = now.strftime('%Y-%m-%d')
    week_start = (now - timedelta(days=now.weekday())).strftime('%Y-%m-%d')
    month_start = now.strftime('%Y-%m-01')
    stats = {
        'hari_ini': conn.execute("SELECT COUNT(id) FROM laporan WHERE date(timestamp, '+7 hours') = ?", (today_start,)).fetchone()[0],
        'minggu_ini': conn.execute("SELECT COUNT(id) FROM laporan WHERE date(timestamp, '+7 hours') >= ?", (week_start,)).fetchone()[0],
        'bulan_ini': conn.execute("SELECT COUNT(id) FROM laporan WHERE date(timestamp, '+7 hours') >= ?", (month_start,)).fetchone()[0],
        'total': conn.execute('SELECT COUNT(id) FROM laporan').fetchone()[0],
        'diterima': conn.execute("SELECT COUNT(id) FROM laporan WHERE status = 'Diterima'").fetchone()[0],
        'diproses': conn.execute("SELECT COUNT(id) FROM laporan WHERE status = 'Diproses'").fetchone()[0],
        'selesai': conn.execute("SELECT COUNT(id) FROM laporan WHERE status = 'Selesai'").fetchone()[0]
    }
    due_date = (now - timedelta(days=14))
    
    laporan_terlambat_query = """
        SELECT l.*, k.nama_kategori FROM laporan l
        JOIN kategori k ON l.kategori_id = k.id
        WHERE l.status != 'Selesai' AND l.timestamp <= ? ORDER BY l.timestamp ASC
    """
    laporan_terlambat = conn.execute(laporan_terlambat_query, (due_date,)).fetchall()
    
    filter_status = request.args.get('status', '')
    filter_kategori = request.args.get('kategori', '')
    filter_kecamatan = request.args.get('kecamatan', '')
    sort_by = request.args.get('sort_by', 'timestamp')
    sort_order = request.args.get('order', 'DESC')
    
    query = "SELECT l.*, k.nama_kategori FROM laporan l JOIN kategori k ON l.kategori_id = k.id"
    conditions = []
    params = []
    if filter_status:
        conditions.append("l.status = ?")
        params.append(filter_status)
    if filter_kategori:
        conditions.append("k.nama_kategori = ?")
        params.append(filter_kategori)
    if filter_kecamatan:
        conditions.append("l.kecamatan = ?")
        params.append(filter_kecamatan)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    sort_column = f"l.{sort_by}" if sort_by in ['timestamp', 'status'] else f"k.nama_kategori"
    order = 'DESC' if sort_order == 'DESC' else 'ASC'
    query += f" ORDER BY {sort_column} {order}"
    
    laporan_list = conn.execute(query, params).fetchall()
    
    kategori_options_rows = conn.execute('SELECT nama_kategori FROM kategori ORDER BY nama_kategori').fetchall()
    kategori_options = [row['nama_kategori'] for row in kategori_options_rows]
    
    conn.close()
    
    return render_template(
        'admin/dashboard.html', 
        stats=stats, 
        laporan_list=laporan_list,
        laporan_terlambat=laporan_terlambat,
        kecamatan_options=sorted(DATA_WILAYAH.keys()),
        kategori_options=kategori_options,
        filters={'status': filter_status,'kategori': filter_kategori,'kecamatan': filter_kecamatan,'sort_by': sort_by,'order': sort_order}
    )

@app.route('/admin/laporan/<int:laporan_id>', methods=['GET', 'POST'])
@login_required
def tindak_lanjut(laporan_id):
    conn = get_db_connection()
    if request.method == 'POST':
        new_status = request.form.get('status')
        dinas_penugas = request.form.get('dinas_penugas')
        catatan = request.form.get('catatan')
        pengumuman = request.form.get('pengumuman_publik')
        
        if new_status:
            laporan_lama = conn.execute('SELECT status FROM laporan WHERE id = ?', (laporan_id,)).fetchone()
            if new_status != laporan_lama['status']:
                conn.execute('UPDATE laporan SET status = ? WHERE id = ?', (new_status, laporan_id))
                aksi = f"Status diubah dari '{laporan_lama['status']}' menjadi '{new_status}'"
                conn.execute('INSERT INTO riwayat_aksi (laporan_id, admin_username, aksi) VALUES (?, ?, ?)', (laporan_id, session['admin_username'], aksi))
                flash(f'Status laporan #{laporan_id} berhasil diubah.', 'success')
        
        if dinas_penugas:
            conn.execute('UPDATE laporan SET dinas_penugas = ? WHERE id = ?', (dinas_penugas, laporan_id))
            aksi = f"Laporan ditugaskan ke '{dinas_penugas}'"
            conn.execute('INSERT INTO riwayat_aksi (laporan_id, admin_username, aksi) VALUES (?, ?, ?)', (laporan_id, session['admin_username'], aksi))
            flash(f'Laporan #{laporan_id} berhasil ditugaskan.', 'success')
        
        if catatan:
            conn.execute('INSERT INTO catatan_internal (laporan_id, admin_username, catatan) VALUES (?, ?, ?)', (laporan_id, session['admin_username'], catatan))
            flash('Catatan internal berhasil ditambahkan.', 'success')
        
        if pengumuman is not None:
            conn.execute('UPDATE laporan SET pengumuman_publik = ? WHERE id = ?', (pengumuman, laporan_id))
            aksi = "Pengumuman publik ditambahkan/diperbarui"
            conn.execute('INSERT INTO riwayat_aksi (laporan_id, admin_username, aksi) VALUES (?, ?, ?)', (laporan_id, session['admin_username'], aksi))
            flash('Pengumuman publik berhasil diperbarui.', 'success')
        
        if 'foto_selesai' in request.files:
            file = request.files['foto_selesai']
            if file and allowed_file(file.filename):
                timestamp = datetime.now(WIB).strftime("%Y%m%d%H%M%S")
                foto_filename = f"selesai_{timestamp}_{secure_filename(file.filename)}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], foto_filename))
                conn.execute('UPDATE laporan SET foto_selesai = ? WHERE id = ?', (foto_filename, laporan_id))
                aksi = "Foto 'Selesai' diunggah"
                conn.execute('INSERT INTO riwayat_aksi (laporan_id, admin_username, aksi) VALUES (?, ?, ?)', (laporan_id, session['admin_username'], aksi))
                flash('Foto bukti selesai berhasil diunggah.', 'success')
        
        conn.commit()
        conn.close()
        return redirect(url_for('tindak_lanjut', laporan_id=laporan_id))

    laporan_query = "SELECT l.*, k.nama_kategori FROM laporan l JOIN kategori k ON l.kategori_id = k.id WHERE l.id = ?"
    laporan = conn.execute(laporan_query, (laporan_id,)).fetchone()

    if laporan is None:
        conn.close()
        return "Laporan tidak ditemukan", 404
    
    dinas_list = conn.execute('SELECT * FROM dinas ORDER BY nama_dinas').fetchall()
    catatan_list = conn.execute('SELECT * FROM catatan_internal WHERE laporan_id = ? ORDER BY timestamp DESC', (laporan_id,)).fetchall()
    riwayat_list = conn.execute('SELECT * FROM riwayat_aksi WHERE laporan_id = ? ORDER BY timestamp DESC', (laporan_id,)).fetchall()
    kontak_dinas_dinamis = {d['nama_dinas']: d['kontak'] for d in dinas_list}
    
    full_text = laporan['judul'] + ' ' + laporan['deskripsi']
    potential_duplicates = ml_processor.find_duplicate_reports(laporan_id, full_text, laporan['latitude'], laporan['longitude'])
    
    conn.close()
    return render_template('admin/tindak_lanjut.html', laporan=laporan, dinas_list=dinas_list, catatan_list=catatan_list, riwayat_list=riwayat_list, kontak_dinas=kontak_dinas_dinamis, potential_duplicates=potential_duplicates)

@app.route('/admin/delete_reports', methods=['POST'])
@login_required
def delete_reports():
    report_ids = request.form.getlist('selected_reports')
    if not report_ids:
        flash('Tidak ada laporan yang dipilih untuk dihapus.', 'warning')
        return redirect(url_for('admin_dashboard'))
    conn = get_db_connection()
    for report_id in report_ids:
        laporan = conn.execute('SELECT foto, foto_selesai FROM laporan WHERE id = ?', (report_id,)).fetchone()
        if laporan:
            try:
                if laporan['foto']: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], laporan['foto']))
                if laporan['foto_selesai']: os.remove(os.path.join(app.config['UPLOAD_FOLDER'], laporan['foto_selesai']))
            except FileNotFoundError:
                print(f"File foto untuk laporan #{report_id} tidak ditemukan.")
        conn.execute('DELETE FROM catatan_internal WHERE laporan_id = ?', (report_id,))
        conn.execute('DELETE FROM riwayat_aksi WHERE laporan_id = ?', (report_id,))
        conn.execute('DELETE FROM laporan WHERE id = ?', (report_id,))
    conn.commit()
    conn.close()
    flash(f'{len(report_ids)} laporan berhasil dihapus.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/laporan/abaikan/<int:id1>/<int:id2>')
@login_required
def abaikan_duplikat(id1, id2):
    conn = get_db_connection()
    report_id_1, report_id_2 = sorted((id1, id2))
    try:
        conn.execute("INSERT INTO ignored_duplicates (report_id_1, report_id_2) VALUES (?, ?)", (report_id_1, report_id_2))
        conn.commit()
        flash(f"Laporan #{id1} dan #{id2} telah ditandai sebagai bukan duplikat.", "success")
    except sqlite3.IntegrityError:
        flash("Pasangan laporan ini sudah ditandai sebelumnya.", "info")
    finally:
        conn.close()
    return redirect(url_for('tindak_lanjut', laporan_id=id1))

@app.route('/admin/analisis')
@login_required
def analisis():
    # Catatan: Walaupun analisis laporan menggunakan DB, kita tidak perlu
    # membuka dan menutup koneksi secara manual di sini, karena fungsi
    # load_data_from_db() di ml_processor sudah menangani koneksi/diskoneksi DB.
    # Kita hanya akan menghapus conn.close() di akhir agar kode lebih bersih.
    # conn = get_db_connection() # Baris ini tidak diperlukan karena load_data_from_db menanganinya
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # 1. Jalankan Analisis Data Laporan dari Database
    results = ml_processor.run_full_analysis(start_date=start_date, end_date=end_date)
    daily_trends = results.get('daily_trends', {"labels": [], "datasets": []})

    # 2. Jalankan Analisis Data X/Twitter (Scraping)
    # Anda bisa menyesuaikan batas (misalnya 300 tweet) di sini.
    try:
        x_analysis_results = ml_processor.run_x_analysis(max_tweets=300)
    except Exception as e:
        print(f"Error saat menjalankan analisis X/Twitter: {e}")
        # Kembalikan hasil kosong jika scraping gagal
        x_analysis_results = ml_processor.run_x_analysis(max_tweets=0)

    # 3. Jalankan Fungsi Summary Naratif
    summary_data = ml_processor.generate_summary_and_recommendations(results)
    
    # conn.close() # Baris ini dihapus karena tidak ada koneksi yang dibuka secara manual di sini.
    
    return render_template(
        "admin/analisis.html",
        results=results, 
        daily_trends=daily_trends,
        summary_data=summary_data, 
        filters={'start_date': start_date, 'end_date': end_date},
        # --- DATA BARU: Hasil Analisis X/Twitter ---
        x_analysis_results=x_analysis_results 
    )

@app.route('/admin/pusat_laporan', methods=['GET'])
@login_required
def pusat_laporan():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    kategori = request.args.get('kategori')
    status = request.args.get('status')
    kecamatan = request.args.get('kecamatan')

    conn = get_db_connection()
    kategori_list = conn.execute('SELECT * FROM kategori ORDER BY nama_kategori').fetchall()
    kecamatan_list = sorted(DATA_WILAYAH.keys())

    query = """
        SELECT l.id, l.timestamp, l.judul, k.nama_kategori, l.deskripsi, l.status, l.dinas_penugas, l.kecamatan, l.kelurahan
        FROM laporan l JOIN kategori k ON l.kategori_id = k.id
        WHERE 1=1
    """
    params = []
    if start_date:
        query += " AND date(l.timestamp, '+7 hours') >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date(l.timestamp, '+7 hours') <= ?"
        params.append(end_date)
    if kategori:
        query += " AND k.nama_kategori = ?"
        params.append(kategori)
    if status:
        query += " AND l.status = ?"
        params.append(status)
    if kecamatan:
        query += " AND l.kecamatan = ?"
        params.append(kecamatan)
    query += " ORDER BY l.timestamp DESC"

    laporan_list = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        'admin/pusat_laporan.html',
        kategori_list=kategori_list,
        kecamatan_list=kecamatan_list,
        laporan_list=laporan_list,
        filters={'start_date': start_date,'end_date': end_date,'kategori': kategori,'status': status,'kecamatan': kecamatan}
    )

@app.route('/admin/download_laporan')
@login_required
def download_laporan():
    format_file = request.args.get('format', 'csv')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    kategori = request.args.get('kategori')
    status = request.args.get('status')
    kecamatan = request.args.get('kecamatan')

    query = """
        SELECT l.nomor_laporan, l.timestamp, l.judul, k.nama_kategori, l.deskripsi, l.status, 
               COALESCE(l.dinas_penugas, '-') AS dinas_penugas, l.kecamatan, l.kelurahan
        FROM laporan l JOIN kategori k ON l.kategori_id = k.id
    """
    where = ["1=1"]
    params = []
    if start_date:
        where.append("date(l.timestamp, '+7 hours') >= ?")
        params.append(start_date)
    if end_date:
        where.append("date(l.timestamp, '+7 hours') <= ?")
        params.append(end_date)
    if kategori:
        where.append("k.nama_kategori = ?")
        params.append(kategori)
    if status:
        where.append("l.status = ?")
        params.append(status)
    if kecamatan:
        where.append("l.kecamatan = ?")
        params.append(kecamatan)
    
    query += " WHERE " + " AND ".join(where) + " ORDER BY l.timestamp DESC"

    conn = sqlite3.connect(DATABASE)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        flash('Tidak ada data laporan yang cocok dengan filter.', 'warning')
        return redirect(url_for('pusat_laporan'))

    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize('UTC').dt.tz_convert('Asia/Jakarta').dt.strftime("%Y-%m-%d %H:%M")
    
    if format_file == "csv":
        output = io.BytesIO()
        df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        return send_file(
            output, mimetype="text/csv",
            download_name=f"laporan_{datetime.now(WIB).strftime('%Y%m%d')}.csv", as_attachment=True
        )
    
    elif format_file == "pdf":
        return Response("Fungsi download PDF belum diimplementasikan sepenuhnya.", mimetype="text/plain")

@app.route('/admin/download/csv/<data_type>')
@login_required
def download_csv(data_type):
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    results = ml_processor.run_full_analysis(start_date=start_date, end_date=end_date)
    
    if not results or results['total_laporan'] == 0:
        flash('Tidak ada data untuk diunduh.', 'warning')
        return redirect(url_for('analisis'))

    output = io.StringIO()
    writer = csv.writer(output)

    if data_type == 'kategori':
        writer.writerow(['Kategori', 'Jumlah Laporan'])
        for item in results['stats_by_category']:
            writer.writerow([item['kategori'], item['jumlah']])
        filename = 'laporan_per_kategori.csv'
    
    elif data_type == 'status':
        writer.writerow(['Status', 'Jumlah Laporan'])
        for key, value in results['stats_by_status'].items():
            writer.writerow([key, value])
        filename = 'laporan_per_status.csv'
    
    else:
        return "Tipe data tidak valid", 404
    
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename={filename}"})

@app.route('/admin/data_master')
@login_required
def data_master():
    conn = get_db_connection()
    dinas_list = conn.execute('SELECT * FROM dinas ORDER BY nama_dinas').fetchall()
    kategori_list = conn.execute('SELECT * FROM kategori ORDER BY nama_kategori').fetchall()
    conn.close()
    return render_template('admin/data_master.html', dinas_list=dinas_list, kategori_list=kategori_list)

@app.route('/admin/dinas/tambah', methods=['POST'])
@login_required
def tambah_dinas():
    nama_dinas = request.form['nama_dinas']
    kontak = request.form['kontak']
    if not nama_dinas or not kontak:
        flash("Nama dinas dan kontak tidak boleh kosong.", "warning")
        return redirect(url_for('data_master'))
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO dinas (nama_dinas, kontak) VALUES (?, ?)', (nama_dinas, kontak))
        conn.commit()
        flash(f"Dinas '{nama_dinas}' berhasil ditambahkan.", "success")
    except sqlite3.IntegrityError:
        flash(f"Dinas dengan nama '{nama_dinas}' sudah ada.", "danger")
    finally:
        conn.close()
    return redirect(url_for('data_master'))

@app.route('/admin/dinas/edit/<int:id>', methods=['POST'])
@login_required
def edit_dinas(id):
    nama_dinas = request.form['nama_dinas']
    kontak = request.form['kontak']
    if not nama_dinas or not kontak:
        flash("Nama dinas dan kontak tidak boleh kosong.", "warning")
        return redirect(url_for('data_master'))
    conn = get_db_connection()
    conn.execute('UPDATE dinas SET nama_dinas = ?, kontak = ? WHERE id = ?', (nama_dinas, kontak, id))
    conn.commit()
    conn.close()
    flash("Data dinas berhasil diperbarui.", "success")
    return redirect(url_for('data_master'))

@app.route('/admin/dinas/hapus/<int:id>')
@login_required
def hapus_dinas(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM dinas WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Dinas berhasil dihapus.", "success")
    return redirect(url_for('data_master'))

@app.route('/admin/kategori/tambah', methods=['POST'])
@login_required
def tambah_kategori():
    nama_kategori = request.form['nama_kategori']
    deskripsi = request.form.get('deskripsi')
    if not nama_kategori:
        flash("Nama kategori tidak boleh kosong.", "warning")
        return redirect(url_for('data_master'))
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO kategori (nama_kategori, deskripsi) VALUES (?, ?)', (nama_kategori, deskripsi))
        conn.commit()
        flash(f"Kategori '{nama_kategori}' berhasil ditambahkan.", "success")
    except sqlite3.IntegrityError:
        flash(f"Kategori '{nama_kategori}' sudah ada.", "danger")
    finally:
        conn.close()
    return redirect(url_for('data_master'))

@app.route('/admin/kategori/edit/<int:id>', methods=['POST'])
@login_required
def edit_kategori(id):
    nama_kategori = request.form['nama_kategori']
    deskripsi = request.form.get('deskripsi')
    if not nama_kategori:
        flash("Nama kategori tidak boleh kosong.", "warning")
        return redirect(url_for('data_master'))
    conn = get_db_connection()
    conn.execute('UPDATE kategori SET nama_kategori = ?, deskripsi = ? WHERE id = ?', (nama_kategori, deskripsi, id))
    conn.commit()
    conn.close()
    flash("Kategori berhasil diperbarui.", "success")
    return redirect(url_for('data_master'))

@app.route('/admin/kategori/hapus/<int:id>')
@login_required
def hapus_kategori(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM kategori WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Kategori berhasil dihapus.", "success")
    return redirect(url_for('data_master'))

@app.route('/api/get_kelurahan/<kecamatan>')
def get_kelurahan(kecamatan):
    if kecamatan in DATA_WILAYAH:
        return jsonify(DATA_WILAYAH[kecamatan])
    else:
        return jsonify({"error": "Kecamatan tidak ditemukan"}), 404

if __name__ == '__main__':
    app.run(debug=True)

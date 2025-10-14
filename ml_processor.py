import pandas as pd
import sqlite3
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from math import radians, cos, sin, asin, sqrt
import numpy as np
from nltk.corpus import stopwords
import re
from twitter_scraper import get_tweets 
from datetime import timedelta


# Kamus sentimen sederhana untuk bahasa Indonesia
positive_words = ["bagus", "baik", "aman", "bersih", "lancar", "indah", "cepat"]
negative_words = ["buruk", "kotor", "macet", "rusak", "lambat", "bencana", "banjir" ,"anjing" , "buta"]

def get_sentiment(text):
    if not isinstance(text, str) or text.strip() == "":
        return "netral"

    text = text.lower()
    tokens = re.findall(r'\w+', text)

    pos_score = sum(1 for t in tokens if t in positive_words)
    neg_score = sum(1 for t in tokens if t in negative_words)

    if pos_score > neg_score:
        return "positif"
    elif neg_score > pos_score:
        return "negatif"
    else:
        return "netral"

# Mengecek apakah stopwords Bahasa Indonesia sudah tersedia, jika belum akan diunduh
try:
    stopwords.words('indonesian')
except LookupError:
    nltk.download('stopwords')
    nltk.download('punkt')

# Fungsi untuk menghitung jarak antar dua titik koordinat menggunakan rumus haversine
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])  # Konversi derajat ke radian
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371000  # Jari-jari bumi dalam meter
    return c * r  # Mengembalikan jarak dalam meter

# Fungsi untuk mengambil data laporan dari database dengan opsi filter tanggal
def load_data_from_db(db_path='database.db', start_date=None, end_date=None):
    try:
        conn = sqlite3.connect(db_path)
        # Menggabungkan tabel laporan dan kategori untuk mendapatkan nama kategori
        query = """
            SELECT l.*, k.nama_kategori AS kategori
            FROM laporan l
            JOIN kategori k ON l.kategori_id = k.id
        """
        params = []
        conditions = []

        # Jika ada filter tanggal awal
        if start_date:
            conditions.append("l.timestamp >= ?")
            params.append(start_date + " 00:00:00")
        # Jika ada filter tanggal akhir
        if end_date:
            conditions.append("l.timestamp <= ?")
            params.append(end_date + " 23:59:59")

        # Menambahkan kondisi WHERE jika ada filter
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        # Eksekusi query dan konversi ke DataFrame
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        # Konversi kolom timestamp menjadi datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors="coerce")
        df = df.dropna(subset=['timestamp'])  # Hapus data yang timestamp-nya invalid
        return df
    except Exception as e:
        print(f"Error saat memuat data: {e}")
        return pd.DataFrame()

# Fungsi untuk membersihkan dan memproses teks agar siap dianalisis
def preprocess_text(text):
    if not isinstance(text, str): 
        return ""
    text = text.lower()  # Ubah menjadi huruf kecil
    text = re.sub(r'[^a-zA-Z\s]', '', text)  # Hapus karakter non-huruf
    tokens = word_tokenize(text)  # Tokenisasi teks
    stop_words = set(stopwords.words('indonesian'))
    # Hapus stopwords dan kata yang terlalu pendek (<3 karakter)
    filtered_tokens = [word for word in tokens if word not in stop_words and len(word) > 2]
    return " ".join(filtered_tokens)

# Fungsi untuk mendeteksi laporan duplikat berdasarkan jarak lokasi dan kemiripan teks
def find_duplicate_reports(current_report_id, current_report_text, current_lat, current_lon):
    conn = sqlite3.connect('database.db')
    # Ambil semua laporan kecuali laporan yang statusnya "Selesai" dan laporan saat ini
    query = "SELECT id, judul, deskripsi, latitude, longitude FROM laporan WHERE status != 'Selesai' AND id != ?"
    df = pd.read_sql_query(query, conn, params=(current_report_id,))
    # Ambil daftar laporan yang diabaikan untuk deteksi duplikasi
    ignored_pairs_df = pd.read_sql_query("SELECT * FROM ignored_duplicates", conn)
    conn.close()
    
    ignored_set = set()
    for index, row in ignored_pairs_df.iterrows():
        ignored_set.add(tuple(sorted((row['report_id_1'], row['report_id_2']))))

    if df.empty: 
        return []

    # Filter laporan berdasarkan jarak lokasi <= 500 meter
    distance_threshold_meters = 500
    nearby_reports_indices = []
    for index, row in df.iterrows():
        if tuple(sorted((current_report_id, int(row['id'])))) in ignored_set: 
            continue
        distance = haversine(current_lon, current_lat, row['longitude'], row['latitude'])
        if distance <= distance_threshold_meters:
            nearby_reports_indices.append(index)
    
    nearby_df = df.iloc[nearby_reports_indices].copy()
    if nearby_df.empty: 
        return []

    # Membersihkan teks laporan dan laporan saat ini
    nearby_df['clean_text'] = (nearby_df['judul'] + ' ' + nearby_df['deskripsi']).apply(preprocess_text)
    current_report_clean_text = preprocess_text(current_report_text)
    all_texts = [current_report_clean_text] + nearby_df['clean_text'].tolist()

    # Menghitung kemiripan teks dengan TF-IDF + cosine similarity
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(all_texts)
    cosine_sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])

    # Ambang batas kemiripan
    similarity_threshold = 0.65
    potential_duplicates_indices = np.where(cosine_sim[0] >= similarity_threshold)[0]
    
    # Mengumpulkan daftar laporan yang terdeteksi duplikat
    duplicates = []
    for index in potential_duplicates_indices:
        duplicates.append({
            'id': int(nearby_df.iloc[index]['id']),
            'judul': nearby_df.iloc[index]['judul'],
            'similarity': round(cosine_sim[0][index] * 100)
        })
    return sorted(duplicates, key=lambda x: x['similarity'], reverse=True)

# Fungsi untuk menganalisis kata kunci utama per kategori menggunakan TF-IDF
def run_text_analysis(df):
    df['clean_deskripsi'] = df['deskripsi'].apply(preprocess_text)
    category_keywords = {}
    for category in df['kategori'].unique():
        corpus = " ".join(df[df['kategori'] == category]['clean_deskripsi'])
        if corpus.strip():
            try:
                vectorizer = TfidfVectorizer(max_features=10)
                vectorizer.fit_transform([corpus])
                keywords = vectorizer.get_feature_names_out()
                category_keywords[category] = keywords.tolist()
            except ValueError:
                category_keywords[category] = []
        else:
            category_keywords[category] = []
    return category_keywords

# Fungsi untuk menganalisis sebaran lokasi laporan berdasarkan kategori
def run_geospatial_analysis(df):
    if df.empty: 
        return {}
    points_by_category = {}
    for category in df['kategori'].unique():
        points = df[df['kategori'] == category][['latitude', 'longitude']].to_dict(orient='records')
        points_by_category[category] = points
    return points_by_category

        # ====== ANALISIS SENTIMEN ======
def run_sentiment_wordcloud(df):
    from collections import Counter
    df["sentimen"] = df["deskripsi"].apply(get_sentiment)

    positif_texts = " ".join(df[df["sentimen"] == "positif"]["deskripsi"].astype(str))
    negatif_texts = " ".join(df[df["sentimen"] == "negatif"]["deskripsi"].astype(str))

    stop_words = set(stopwords.words("indonesian"))
    positif_tokens = [t for t in re.findall(r'\w+', positif_texts.lower()) if t not in stop_words]
    negatif_tokens = [t for t in re.findall(r'\w+', negatif_texts.lower()) if t not in stop_words]

    return {
        "positif": Counter(positif_tokens).most_common(30),
        "negatif": Counter(negatif_tokens).most_common(30),
    }


# --- FUNGSI BARU: Analisis Tren Harian ---
def run_daily_trends(df):
    if df.empty:
        # Jika DataFrame kosong, kembalikan 15 hari terakhir dari HARI INI
        max_date = pd.to_datetime('today').normalize()
    else:
        # Pastikan 'timestamp' adalah datetime, jika belum
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Ekstrak tanggal saja
        df['date'] = df['timestamp'].dt.normalize()
        
        # Tentukan tanggal laporan terakhir yang masuk (max_date)
        max_date = df['date'].max()

    # =========================================================================
    # LOGIKA PEMBATASAN RENTANG 15 HARI
    # =========================================================================
    
    # Tanggal awal adalah 14 hari sebelum tanggal maksimum (sehingga total 15 hari)
    min_date = max_date - timedelta(days=14)
    
    # Buat rentang tanggal lengkap 15 hari
    date_range = pd.date_range(start=min_date, end=max_date, freq='D')
    
    # =========================================================================
    # PENGHITUNGAN DATA
    # =========================================================================
    
    if not df.empty:
        # Hitung jumlah laporan per tanggal
        daily_counts = df.groupby('date').size()
    else:
        # Jika df kosong, daily_counts juga kosong
        daily_counts = pd.Series(dtype=int) 
    
    # Gabungkan (reindex) dengan rentang tanggal lengkap 15 hari, 
    # isi nilai yang hilang (tidak ada laporan) dengan 0
    daily_trend_df = daily_counts.reindex(date_range, fill_value=0)
    
    # =========================================================================
    # FORMAT OUTPUT CHART.JS
    # =========================================================================
    
    # Format hasil untuk chart.js
    labels = daily_trend_df.index.strftime('%Y-%m-%d').tolist()
    data = daily_trend_df.tolist()
    
    return {
        "labels": labels,
        "datasets": [
            {
                "label": "Jumlah Laporan Masuk",
                "data": data,
                "borderColor": "#0d6efd", 
                "tension": 0.4,
                "fill": False,
                # Pastikan type adalah 'line' jika fungsi JS tidak menyetelnya
                "type": 'line' 
            }
        ]
    }
# --- AKHIR FUNGSI BARU ---

# Fungsi utama untuk menjalankan analisis keseluruhan data laporan
def run_full_analysis(start_date=None, end_date=None):
    # Daftar warna untuk visualisasi per kategori
    WARNA_PALET = [
        "#20c997","#ffc107","#d63384",
        "#fd7e14","#0dcaf0","#dc3545",
        "#0d6efd","#664d03","#6f42c1"
    ]
    df = load_data_from_db(start_date=start_date, end_date=end_date)
    try:
        conn = sqlite3.connect('database.db')
        kategori_df = pd.read_sql_query("SELECT DISTINCT nama_kategori FROM kategori ORDER BY nama_kategori", conn)
        conn.close()
        all_categories = kategori_df['nama_kategori'].dropna().tolist()
        color_map = {kategori: WARNA_PALET[i % len(WARNA_PALET)] for i, kategori in enumerate(all_categories)}
    except Exception as e:
        print(f"Error saat mengambil kategori: {e}")
        all_categories = sorted(df['kategori'].dropna().unique())
        color_map = {}
    
    # Jika tidak ada data
    if df.empty:
        return {
            "total_laporan": 0,
            "stats_by_category": [{"kategori": cat, "jumlah": 0, "warna": color_map.get(cat, 'grey')} for cat in all_categories],
            "stats_by_status": {}, 
            "stats_by_kecamatan": {}, 
            "monthly_trends": {},
            "daily_trends": run_daily_trends(df.copy()),
            "text_analysis": {}, 
            "geospatial_analysis": {},
            "start_date": start_date,   
            "end_date": end_date
        }

    # Statistik jumlah laporan per kategori
    counts_by_category = df['kategori'].value_counts()
    stats_by_category = []
    for cat in all_categories:
        stats_by_category.append({
            "kategori": cat,
            "jumlah": int(counts_by_category.get(cat, 0)),
            "warna": color_map.get(cat, 'grey')
        })

    # Statistik laporan per status dan kecamatan
    stats_by_status = df['status'].value_counts().to_dict()
    stats_by_kecamatan = df['kecamatan'].value_counts().to_dict()
    df['month'] = df['timestamp'].dt.to_period('M').astype(str)
    
    # Membuat tren bulanan per kategori
    monthly_trends_df = (
        df.groupby(['month', 'kategori'])
            .size()
            .unstack(fill_value=0)
            .reindex(columns=all_categories, fill_value=0)
    )
    all_months = sorted(df['month'].unique())
    trend_datasets = []
    for category in all_categories:
        trend_datasets.append({
            "label": category,
            "data": monthly_trends_df[category].reindex(all_months, fill_value=0).tolist(),
            "backgroundColor": color_map.get(category, 'grey')
        })

    daily_trends_results = run_daily_trends(df.copy()) 
    monthly_trends = {"labels": all_months, "datasets": trend_datasets}
    text_results = run_text_analysis(df.copy())
    geospatial_results = run_geospatial_analysis(df.copy())
    sentiment_wordcloud = run_sentiment_wordcloud(df.copy())

    # Mengembalikan hasil analisis lengkap
    return {
        "total_laporan": len(df),
        "stats_by_category": stats_by_category,
        "stats_by_status": stats_by_status,
        "stats_by_kecamatan": stats_by_kecamatan,
        "monthly_trends": monthly_trends,
        "daily_trends": daily_trends_results, # <-- FIX: Variabel kini terdefinisi
        "text_analysis": text_results,
        "geospatial_analysis": geospatial_results,
        "sentiment_wordcloud": sentiment_wordcloud,
        "start_date": start_date,
        "end_date": end_date
    }

# Tambahkan fungsi ini ke dalam ml_processor.py, di bagian bawah file

def generate_summary_and_recommendations(analysis_results):
    """
    Menghasilkan ringkasan naratif, kesimpulan, dan rekomendasi untuk pemangku kebijakan 
    berdasarkan hasil analisis data laporan keseluruhan.

    Args:
        analysis_results (dict): Hasil lengkap dari run_full_analysis().

    Returns:
        dict: Berisi 'summary_points' (list kalimat) dan 'recommendations' (list saran).
    """
    
    total_laporan = analysis_results.get('total_laporan', 0)
    summary_points = []
    recommendations = []
    
    if total_laporan == 0:
        return {
            "summary_points": ["Tidak ada data laporan yang tersedia dalam periode ini."],
            "recommendations": ["Lakukan sosialisasi masif agar masyarakat mulai menggunakan platform pelaporan."]
        }

    # --- Bagian 1: Ringkasan Umum & Tren Waktu ---
    
    # Tren Harian
    daily_data = analysis_results.get('daily_trends', {}).get('datasets', [{}])[0].get('data', [])
    if daily_data:
        max_reports_day = max(daily_data)
        min_reports_day = min(daily_data)
        avg_reports_day = sum(daily_data) / len(daily_data) if daily_data else 0
        
        summary_points.append(f"Tercatat {total_laporan} laporan masuk dalam periode analisis ini.")
        summary_points.append(f"Rata-rata laporan harian berada pada {avg_reports_day:.1f} laporan/hari, dengan puncak laporan harian mencapai {max_reports_day} laporan.")

    # Tren Bulanan (Kategori)
    monthly_trends = analysis_results.get('monthly_trends', {}).get('datasets', [])
    if monthly_trends:
        monthly_df = pd.DataFrame({d['label']: d['data'] for d in monthly_trends}, index=analysis_results['monthly_trends']['labels'])
        top_category_overall = monthly_df.sum().idxmax()
        
        summary_points.append(f"Secara keseluruhan, {top_category_overall} merupakan kategori yang paling dominan dilaporkan.")
        
        # Cek kategori mana yang menunjukkan lonjakan (increase) signifikan
        recent_month_data = monthly_df.iloc[-1].sort_values(ascending=False)
        top_recent_category = recent_month_data.index[0]
        
        if top_recent_category != top_category_overall:
             summary_points.append(f"Perlu diperhatikan, kategori {top_recent_category} menunjukkan lonjakan signifikan di bulan terakhir, meskipun bukan yang paling dominan secara keseluruhan.")


    # --- Bagian 2: Fokus Masalah (Kategori & Geospasial) ---

    stats_cat = analysis_results.get('stats_by_category', [])
    if stats_cat:
        # Kategori paling banyak dilaporkan (Top 3)
        top_cats = sorted(stats_cat, key=lambda x: x['jumlah'], reverse=True)[:3]
        top_cat_names = [c['kategori'] for c in top_cats if c['jumlah'] > 0]
        if top_cat_names:
            summary_points.append(f"Tiga isu utama yang mendominasi pelaporan adalah: {', '.join(top_cat_names)}.")

    stats_kec = analysis_results.get('stats_by_kecamatan', {})
    if stats_kec:
        # Kecamatan paling banyak dilaporkan
        top_kec = max(stats_kec, key=stats_kec.get)
        summary_points.append(f"Secara geografis, wilayah {top_kec} memiliki jumlah laporan terbanyak, mengindikasikan perluasan fokus sumber daya di area tersebut.")


    # --- Bagian 3: Sentimen & Urgensi Tindakan ---
    
    # Sentimen
    sentiment_data = analysis_results.get('sentiment_wordcloud', {})
    neg_count = sum(c[1] for c in sentiment_data.get('negatif', []))
    pos_count = sum(c[1] for c in sentiment_data.get('positif', []))
    
    if neg_count > pos_count * 1.5:
        summary_points.append(f"Mayoritas narasi laporan didominasi oleh sentimen negatif, dengan kata kunci sering muncul seperti: {', '.join([c[0] for c in sentiment_data.get('negatif', [])[:5]])}. Ini menuntut respons yang cepat dan empatik dari dinas terkait.")
    elif pos_count > neg_count * 1.5:
        summary_points.append("Sentimen yang muncul didominasi oleh kata-kata positif, yang menunjukkan apresiasi terhadap layanan yang sudah berjalan baik.")
    else:
        summary_points.append("Sentimen cenderung netral, namun terdapat beberapa kata kunci negatif yang perlu diwaspadai.")


    # --- Bagian 4: Rekomendasi (Actionable Insights) ---
    
    # Rekomendasi 1: Fokus Kategori Utama
    if top_cat_names:
        recommendations.append(f"Segera alokasikan tim dan anggaran khusus untuk menangani {', '.join(top_cat_names)} di {top_kec} sebagai prioritas utama.")
        
    # Rekomendasi 2: Duplikasi & Efisiensi
    recommendations.append("Manfaatkan fitur deteksi duplikasi untuk mengelompokkan laporan yang sama di lokasi berdekatan agar penanganan lebih efisien dan terintegrasi dalam satu penugasan.")
    
    # Rekomendasi 3: Respon Cepat (Sentimen)
    recommendations.append("Tingkatkan kecepatan tanggapan dan komunikasi publik (melalui fitur pengumuman) untuk meredakan sentimen negatif, terutama pada laporan yang menggunakan kata kunci sensitif.")

    return {
        "summary_points": summary_points,
        "recommendations": recommendations
    }


# Kamus kata kunci untuk Bandar Lampung
BANDAR_LAMPUNG_KEYWORDS = [
    # General & Location
    "Bandar Lampung", 
    "Balam", 
    "Lampung", # Lebih luas, tapi relevan
    "Bunda Eva",
    "Jakarta",
    "Klok",
    "STY",
    
    # Keluhan Infrastruktur
    "Jalan Rusak Lampung", 
    "Jalan Berlubang Balam",
    "Macet Balam",
    "Lampu Merah Balam",
    "Drainase Balam",
    "Banjir Bandar Lampung",
    
    # Pelayanan Publik
    "Pelayanan Balam Buruk", # Menargetkan sentimen negatif
    "Pemkot Balam", 
    "Polisi Lampung",
    "RSUD Balam", # Rumah sakit
    "PDAM Way Rilau",
    "Parkir Liar",
    
    # Isu Sosial & Kebersihan
    "Sampah Balam",
    "Begall Lampung", # Isu keamanan
    "Kriminal Balam",
    
    # Area Spesifik (Jika diperlukan, bisa ditambahkan lebih banyak)
    "Tanjungkarang", 
    "Kedaton",
    "Antasari",
    "Sukarame",
    "UIN"
]

def build_query(keywords):
    """Membangun string query pencarian untuk twitter-scraper."""
    # Menambahkan filter umum: minimal 10 like (menunjukkan keterlibatan) dan hanya bahasa Indonesia
    query = " OR ".join(keywords)
    # CATATAN: Pustaka twitter-scraper tidak selalu mendukung syntax filter canggih (seperti min_retweets), 
    # namun kita tetap mencoba menggunakan query yang jelas.
    # Kita akan menggunakan syntax pencarian teks biasa.
    return query

def scrape_x_data(query_keywords=BANDAR_LAMPUNG_KEYWORDS, max_tweets=500):
    """
    Mengambil data dari X/Twitter menggunakan twitter-scraper dengan penanganan error.
    """
    search_query = build_query(query_keywords)
    tweets_list = []
    num_pages = int(max_tweets / 15) + 5
    
    # Menambahkan penanganan error spesifik untuk JSON
    import json # Tambahkan import json di file ml_processor.py jika belum ada
    
    try:
        # Menggunakan get_tweets() dari twitter_scraper
        for i, tweet in enumerate(get_tweets(search_query, pages=num_pages)):
            if i >= max_tweets:
                break
            
            # Pastikan kunci 'text' dan 'time' ada
            if 'text' in tweet and 'time' in tweet:
                tweets_list.append({
                    'id': tweet.get('tweetId'),
                    'text': tweet['text'],
                    'timestamp': tweet['time']
                })
        
        df = pd.DataFrame(tweets_list)
        
        if not df.empty:
             df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert('Asia/Jakarta').dt.tz_localize(None)
        
        return df
        
    # Tangkap error JSON (yang menyebabkan "Expecting value") dan error scraping lainnya
    except json.JSONDecodeError as e:
        print(f"Error JSON Decode (Blokir/Rate Limit?): {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error umum saat scraping X/Twitter: {e}")
        return pd.DataFrame()

# Fungsi run_x_analysis (lanjutan dari ml_processor.py)
def run_x_analysis(query_keywords=BANDAR_LAMPUNG_KEYWORDS, max_tweets=300):
    """Mengambil dan menganalisis data X/Twitter."""
    
    # Ambil data dari X/Twitter
    df_x = scrape_x_data(query_keywords, max_tweets)
    
    if df_x.empty:
        return {"total_tweets": 0, "sentiment_summary": {}, "top_issues": [], "raw_data": []}

    # --- Prapemrosesan & Analisis Sentimen ---
    
    # 1. Analisis Sentimen menggunakan get_sentiment
    df_x['sentimen'] = df_x['text'].apply(get_sentiment)
    sentiment_counts = df_x['sentimen'].value_counts().to_dict()
    
    # 2. Pembersihan teks
    df_x['clean_text'] = df_x['text'].apply(preprocess_text)
    
    # 3. Analisis Topik (TF-IDF)
    corpus = " ".join(df_x['clean_text'])
    
    from sklearn.feature_extraction.text import TfidfVectorizer
    try:
        vectorizer = TfidfVectorizer(max_features=10, ngram_range=(1, 2)) # Gunakan bigram juga
        vectorizer.fit_transform([corpus])
        top_issues = vectorizer.get_feature_names_out().tolist()
    except ValueError:
        top_issues = []
    
    # Teks untuk ditampilkan
    display_data = df_x[['text', 'timestamp', 'sentimen']].head(5).to_dict('records')

    return {
        "total_tweets": len(df_x),
        "sentiment_summary": sentiment_counts,
        "top_issues": top_issues,
        "raw_data": display_data
    }
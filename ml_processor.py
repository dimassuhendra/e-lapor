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
        "text_analysis": text_results,
        "geospatial_analysis": geospatial_results,
        "sentiment_wordcloud": sentiment_wordcloud,
        "start_date": start_date,
        "end_date": end_date
    }

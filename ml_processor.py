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

try:
    stopwords.words('indonesian')
except LookupError:
    nltk.download('stopwords')
    nltk.download('punkt')

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371000
    return c * r

def load_data_from_db(db_path='database.db', start_date=None, end_date=None):
    try:
        conn = sqlite3.connect(db_path)
        # PERUBAHAN UTAMA: Query di-JOIN untuk mendapatkan nama kategori
        # Kolom k.nama_kategori di-alias sebagai 'kategori' agar sisa kode tidak perlu diubah
        query = """
            SELECT l.*, k.nama_kategori AS kategori 
            FROM laporan l 
            JOIN kategori k ON l.kategori_id = k.id
        """
        params = []
        conditions = []

        if start_date:
            conditions.append("l.timestamp >= ?")
            params.append(start_date + " 00:00:00")
        if end_date:
            conditions.append("l.timestamp <= ?")
            params.append(end_date + " 23:59:59")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        df['timestamp'] = pd.to_datetime(df['timestamp'], errors="coerce")
        df = df.dropna(subset=['timestamp'])
        return df
    except Exception as e:
        print(f"Error saat memuat data: {e}")
        return pd.DataFrame()

def preprocess_text(text):
    if not isinstance(text, str): return ""
    text = text.lower()
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    tokens = word_tokenize(text)
    stop_words = set(stopwords.words('indonesian'))
    filtered_tokens = [word for word in tokens if word not in stop_words and len(word) > 2]
    return " ".join(filtered_tokens)

def find_duplicate_reports(current_report_id, current_report_text, current_lat, current_lon):
    conn = sqlite3.connect('database.db')
    query = "SELECT id, judul, deskripsi, latitude, longitude FROM laporan WHERE status != 'Selesai' AND id != ?"
    df = pd.read_sql_query(query, conn, params=(current_report_id,))
    ignored_pairs_df = pd.read_sql_query("SELECT * FROM ignored_duplicates", conn)
    conn.close()
    
    ignored_set = set()
    for index, row in ignored_pairs_df.iterrows():
        ignored_set.add(tuple(sorted((row['report_id_1'], row['report_id_2']))))

    if df.empty: return []

    distance_threshold_meters = 500
    nearby_reports_indices = []
    for index, row in df.iterrows():
        if tuple(sorted((current_report_id, int(row['id'])))) in ignored_set: continue
        distance = haversine(current_lon, current_lat, row['longitude'], row['latitude'])
        if distance <= distance_threshold_meters:
            nearby_reports_indices.append(index)
    
    nearby_df = df.iloc[nearby_reports_indices].copy()
    if nearby_df.empty: return []

    nearby_df['clean_text'] = (nearby_df['judul'] + ' ' + nearby_df['deskripsi']).apply(preprocess_text)
    current_report_clean_text = preprocess_text(current_report_text)
    all_texts = [current_report_clean_text] + nearby_df['clean_text'].tolist()

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(all_texts)
    cosine_sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])

    similarity_threshold = 0.65
    potential_duplicates_indices = np.where(cosine_sim[0] >= similarity_threshold)[0]
    
    duplicates = []
    for index in potential_duplicates_indices:
        duplicates.append({
            'id': int(nearby_df.iloc[index]['id']),
            'judul': nearby_df.iloc[index]['judul'],
            'similarity': round(cosine_sim[0][index] * 100)
        })
    return sorted(duplicates, key=lambda x: x['similarity'], reverse=True)

# (Fungsi run_text_analysis dan run_geospatial_analysis tidak perlu diubah karena
# load_data_from_db sudah menyediakan kolom 'kategori' yang dibutuhkan)

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

def run_geospatial_analysis(df):
    if df.empty: return {}
    points_by_category = {}
    for category in df['kategori'].unique():
        points = df[df['kategori'] == category][['latitude', 'longitude']].to_dict(orient='records')
        points_by_category[category] = points
    return points_by_category

# Fungsi ini sama seperti solusi sebelumnya yang sudah menggunakan pewarnaan otomatis
def run_full_analysis(start_date=None, end_date=None):
    WARNA_PALET = [
        "rgba(239, 83, 80, 0.8)","rgba(66, 165, 245, 0.8)","rgba(255, 183, 77, 0.8)",
        "rgba(102, 187, 106, 0.8)","rgba(171, 71, 188, 0.8)","rgba(255, 238, 88, 0.8)",
        "rgba(29, 233, 182, 0.8)","rgba(121, 85, 72, 0.8)","rgba(120, 144, 156, 0.8)"
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
    
    if df.empty:
        return {
            "total_laporan": 0,
            "stats_by_category": [{"kategori": cat, "jumlah": 0, "warna": color_map.get(cat, 'grey')} for cat in all_categories],
            "stats_by_status": {}, "stats_by_kecamatan": {}, "monthly_trends": {},
            "text_analysis": {}, "geospatial_analysis": {},
            "start_date": start_date, "end_date": end_date
        }

    counts_by_category = df['kategori'].value_counts()
    stats_by_category = []
    for cat in all_categories:
        stats_by_category.append({
            "kategori": cat,
            "jumlah": int(counts_by_category.get(cat, 0)),
            "warna": color_map.get(cat, 'grey')
        })

    stats_by_status = df['status'].value_counts().to_dict()
    stats_by_kecamatan = df['kecamatan'].value_counts().to_dict()
    df['month'] = df['timestamp'].dt.to_period('M').astype(str)
    
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

    return {
        "total_laporan": len(df),
        "stats_by_category": stats_by_category,
        "stats_by_status": stats_by_status,
        "stats_by_kecamatan": stats_by_kecamatan,
        "monthly_trends": monthly_trends,
        "text_analysis": text_results,
        "geospatial_analysis": geospatial_results,
        "start_date": start_date,
        "end_date": end_date
    }
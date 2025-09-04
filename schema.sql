-- Hapus tabel lama jika ada untuk memastikan struktur yang bersih
DROP TABLE IF EXISTS laporan;
DROP TABLE IF EXISTS admin;
DROP TABLE IF EXISTS dinas;
DROP TABLE IF EXISTS kategori;
DROP TABLE IF EXISTS catatan_internal;
DROP TABLE IF EXISTS riwayat_aksi;
DROP TABLE IF EXISTS ignored_duplicates;
DROP TABLE IF EXISTS nomor_laporan_harian;

-- Buat tabel untuk daftar dinas
CREATE TABLE dinas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_dinas TEXT UNIQUE NOT NULL,
    kontak TEXT
);

-- Buat tabel untuk daftar kategori
CREATE TABLE kategori (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_kategori TEXT NOT NULL UNIQUE,
    deskripsi TEXT
);

-- Buat tabel untuk laporan warga
CREATE TABLE laporan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nomor_laporan TEXT NOT NULL UNIQUE,
    nama_pelapor TEXT NOT NULL,
    no_whatsapp TEXT,
    judul TEXT NOT NULL,
    deskripsi TEXT NOT NULL,
    -- PERUBAHAN UTAMA: Menggunakan Foreign Key ke tabel kategori
    kategori_id INTEGER NOT NULL,
    kecamatan TEXT,
    kelurahan TEXT,
    foto TEXT,
    foto_selesai TEXT,
    dinas_penugas TEXT,
    pengumuman_publik TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'Diterima',
    support_count INTEGER DEFAULT 0,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- Mendefinisikan hubungan antar tabel
    FOREIGN KEY (kategori_id) REFERENCES kategori (id)
);

-- Buat tabel untuk admin/petugas
CREATE TABLE admin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);

-- Buat tabel untuk catatan internal
CREATE TABLE catatan_internal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    laporan_id INTEGER NOT NULL,
    admin_username TEXT NOT NULL,
    catatan TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (laporan_id) REFERENCES laporan (id) ON DELETE CASCADE
);

-- Buat tabel untuk riwayat aksi
CREATE TABLE riwayat_aksi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    laporan_id INTEGER NOT NULL,
    admin_username TEXT NOT NULL,
    aksi TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (laporan_id) REFERENCES laporan (id) ON DELETE CASCADE
);

-- Tabel untuk menyimpan pasangan laporan duplikat yang diabaikan
CREATE TABLE ignored_duplicates (
    report_id_1 INTEGER NOT NULL,
    report_id_2 INTEGER NOT NULL,
    PRIMARY KEY (report_id_1, report_id_2)
);

-- Tabel untuk melacak nomor urut laporan harian
CREATE TABLE nomor_laporan_harian (
    tanggal TEXT PRIMARY KEY,
    urutan_terakhir INTEGER NOT NULL
);

-- ==================
-- == DATA AWAL =====
-- ==================

-- Mengisi tabel dinas dengan data awal
INSERT INTO dinas (nama_dinas, kontak) VALUES
('Dinas Pekerjaan Umum', '6281234567890'),
('Dinas Lingkungan Hidup', '6281234567891'),
('Dinas Perhubungan', '6281234567892'),
('Dinas Perumahan dan Permukiman', '6281234567893'),
('Satpol PP', '6281234567894'),
('BPBD', '6281234567895');

-- Mengisi tabel kategori dengan data awal
INSERT INTO kategori (nama_kategori, deskripsi) VALUES
('Jalan Rusak', 'Laporan terkait kerusakan jalan seperti lubang, aspal mengelupas, atau retakan.'),
('Sampah & Kebersihan', 'Laporan mengenai tumpukan sampah liar, bak sampah penuh, atau kebersihan fasilitas umum.'),
('Lampu Jalan Mati', 'Laporan terkait lampu penerangan jalan umum (PJU) yang padam atau tidak berfungsi.'),
('Drainase & Banjir', 'Laporan mengenai saluran air atau gorong-gorong yang tersumbat dan menyebabkan genangan air.'),
('Fasilitas Umum Rusak', 'Laporan kerusakan pada fasilitas publik seperti halte, rambu lalu lintas, atau trotoar.'),
('Ketertiban Umum', 'Laporan gangguan ketertiban seperti parkir liar, PKL, atau spanduk ilegal.'),
('Pohon Tumbang / Berbahaya', 'Laporan mengenai pohon yang tumbang atau dahan yang berisiko patah.'),
('Lainnya', 'Kategori untuk laporan lain yang tidak termasuk dalam kategori di atas.');
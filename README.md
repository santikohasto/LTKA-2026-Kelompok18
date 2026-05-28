# QoS-RIC — AI-Powered Network Resource Allocator
**Tugas Besar LTKA · Huawei Cloud**

---

## Struktur Project
```
qos_ric/
├── config/
│   └── settings.py          # Semua konfigurasi cloud & simulator
├── database/
│   ├── schema.sql            # Jalankan sekali di RDS
│   └── db.py                 # Helper koneksi & query
├── simulator/
│   └── simulator.py          # Traffic generator (3 tipe user)
├── ml_model/
│   ├── generate_dataset.py   # Buat dataset training
│   ├── train_model.py        # Training + evaluasi model
│   └── data/                 # Dataset CSV (auto-generated)
│   └── model/                # Saved model (auto-generated)
├── ric_engine/
│   └── ric_engine.py         # FastAPI backend (otak sistem)
├── alert/
│   └── alert.py              # SMN alert module
├── dashboard/
│   ├── dashboard.py          # Flask dashboard server
│   └── templates/
│       └── index.html        # Dashboard UI
└── requirements.txt
```

---

## Setup & Cara Jalankan

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Konfigurasi cloud
Edit `config/settings.py` dan isi:
- `RIC_ENGINE_URL` → IP publik ECS kalian
- `RDS_HOST`, `RDS_USER`, `RDS_PASSWORD` → koneksi RDS
- `SMN_TOPIC_URN`, `SMN_AK`, `SMN_SK` → Huawei SMN
- `MODELARTS_ENDPOINT` → endpoint model setelah deploy

### 3. Setup database
```bash
# Jalankan schema di RDS MySQL
mysql -h YOUR_RDS_HOST -u root -p < database/schema.sql
```

### 4. Generate dataset & train model
```bash
cd ml_model
python generate_dataset.py --samples 5000
python train_model.py
```

### 5. Jalankan RIC Engine (di ECS)
```bash
cd ric_engine
uvicorn ric_engine:app --host 0.0.0.0 --port 8000
```

### 6. Jalankan Dashboard (di ECS)
```bash
cd dashboard
python dashboard.py
# Buka: http://YOUR_ECS_IP:5000
```

### 7. Jalankan Simulator (bisa dari laptop)
```bash
cd simulator

# Mode interaktif (tekan n/s/k untuk ganti mode)
python simulator.py

# Mode otomatis demo (semua skenario berurutan)
python simulator.py --mode demo

# Mode tertentu langsung
python simulator.py --mode normal
python simulator.py --mode stress
python simulator.py --mode kill
```

---

## Alur Demo Presentasi

| Waktu | Skenario | Yang dilakukan |
|-------|----------|----------------|
| 0-2 min | **Normal** | Klik "Normal Operation", tunjukkan dashboard real-time |
| 2-4 min | **Stress test** | Klik "Stress Test", tunjukkan darurat tetap hijau |
| 4-5 min | **SLA violation** | Klik "Trigger SLA Violation", tunggu alert masuk HP |

---

## Mapping Komponen ke Cloud

| Kode | Huawei Cloud Service |
|------|---------------------|
| `simulator.py` | Berjalan di ECS atau laptop lokal |
| `ric_engine.py` | ECS (FastAPI server) |
| `train_model.py` | ModelArts Notebook |
| `db.py` | RDS for MySQL |
| `alert.py` | SMN (Simple Message Notification) |
| Dataset CSV | OBS (Object Storage) |
| Dashboard | ECS (Flask server) |

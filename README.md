# QoS-RIC — AI-Powered Network Resource Allocator
**Tugas Besar LTKA · AWS**

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
│   └── alert.py              # AWS SNS alert module
├── dashboard/
│   ├── dashboard.py          # Flask dashboard server
│   └── templates/
│       └── index.html        # Dashboard UI
└── requirements.txt
```

---

## Infrastruktur AWS

| Komponen | Layanan AWS | Keterangan |
|---|---|---|
| Server (RIC Engine + Dashboard) | EC2 t3.small | Ubuntu 26.04 LTS, region ap-southeast-1 |
| Database | RDS MySQL 8.0 | db.t3.micro, single AZ |
| Alert | SNS (Simple Notification Service) | Email + SMS notification |
| Object Storage | S3 | Dataset CSV dan model file |

---

## Setup & Cara Jalankan

### 1. Install dependencies

```bash
pip install -r requirements.txt
pip install boto3
```

### 2. Konfigurasi cloud

Edit `config/settings.py` dan isi:

```python
# Server
RIC_ENGINE_URL  = "http://YOUR_EC2_PUBLIC_IP:8000"

# AWS RDS MySQL
RDS_HOST        = "YOUR_RDS_ENDPOINT.ap-southeast-1.rds.amazonaws.com"
RDS_PORT        = 3306
RDS_USER        = "admin"
RDS_PASSWORD    = "YOUR_RDS_PASSWORD"
RDS_DATABASE    = "qos_ric_db"
```

### 3. Setup database

Masuk ke EC2 lalu connect ke RDS dan jalankan schema:

```bash
mysql -h YOUR_RDS_ENDPOINT -u admin -pYOUR_PASSWORD
```

```sql
CREATE DATABASE IF NOT EXISTS qos_ric_db;
USE qos_ric_db;

CREATE TABLE IF NOT EXISTS allocations (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    user_type        ENUM('emergency', 'industry', 'normal') NOT NULL,
    bw_requested     FLOAT NOT NULL,
    latency_req      INT NOT NULL,
    prb_usage        FLOAT NOT NULL,
    queue_len        INT NOT NULL,
    prb_allocated    INT NOT NULL,
    expected_latency FLOAT NOT NULL,
    sla_ok           BOOLEAN NOT NULL,
    model_used       VARCHAR(50) DEFAULT 'random_forest',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sla_violations (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_type  ENUM('emergency', 'industry', 'normal') NOT NULL,
    compliance FLOAT NOT NULL,
    alert_sent BOOLEAN DEFAULT FALSE,
    message    TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS demo_events (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    event_type   ENUM('normal', 'stress', 'kill') NOT NULL,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE VIEW dashboard_stats AS
SELECT
    user_type,
    COUNT(*) AS total_requests,
    AVG(prb_allocated) AS avg_prb,
    AVG(expected_latency) AS avg_latency,
    SUM(CASE WHEN sla_ok THEN 1 ELSE 0 END) AS sla_ok_count,
    COUNT(*) - SUM(CASE WHEN sla_ok THEN 1 ELSE 0 END) AS sla_fail_count,
    ROUND(SUM(CASE WHEN sla_ok THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS sla_compliance_pct
FROM (
    SELECT * FROM allocations ORDER BY created_at DESC LIMIT 500
) AS recent
GROUP BY user_type;
```

### 4. Setup AWS SNS Alert

1. Buka AWS Console → SNS → Create topic (Standard) → nama: `qos-ric-alerts`
2. Copy ARN topic yang terbuat
3. Create subscription → Protocol: Email → masukkan email kamu
4. Konfirmasi email dari AWS
5. Edit `alert/alert.py`, ganti `SNS_TOPIC_ARN` dengan ARN kamu

```python
SNS_TOPIC_ARN = "arn:aws:sns:ap-southeast-1:ACCOUNT_ID:qos-ric-alerts"
```

6. Setup AWS credentials di EC2:

```bash
aws configure
# Isi: Access Key, Secret Key, region: ap-southeast-1, format: json
```

### 5. Generate dataset & train model

```bash
cd ml_model
source ../venv/bin/activate
python generate_dataset.py --samples 10000
python train_model.py
```

**Expected output:**
```
Model saved to: model/qos_model.pkl
Test prediction (emergency user):
  PRB allocated    : 30
  Expected latency : 8.07 ms
  SLA OK           : True
```

### 6. Jalankan RIC Engine (di EC2)

```bash
cd ric_engine
source ../venv/bin/activate
uvicorn ric_engine:app --host 0.0.0.0 --port 8000
```

**Expected:**
```
[RIC] Model lokal dimuat dari ../ml_model/model/qos_model.pkl
[RIC] Koneksi database OK
INFO: Uvicorn running on http://0.0.0.0:8000
```

### 7. Jalankan Dashboard (di EC2)

```bash
cd dashboard
source ../venv/bin/activate
python dashboard.py
# Buka: http://YOUR_EC2_PUBLIC_IP:5000
```

### 8. Jalankan Simulator (di EC2, bukan laptop)

> **Penting:** Jalankan simulator di EC2 agar tombol mode di dashboard berfungsi.

```bash
cd simulator
source ../venv/bin/activate

# Mode interaktif (tekan n/s/k untuk ganti mode)
python simulator.py

# Mode otomatis demo (semua skenario berurutan)
python simulator.py --mode demo

# Mode tertentu langsung
python simulator.py --mode normal   # semua SLA OK
python simulator.py --mode stress   # user biasa 4x lipat, Biasa mulai FAIL
python simulator.py --mode kill     # resource 30%, semua FAIL + email alert
```

> Mode bisa juga diganti lewat tombol di dashboard (`Normal Operation`, `Stress Test`, `Trigger SLA Violation`)

---

## Cara Pakai tmux (jalankan semua sekaligus)

```bash
tmux new-session -s qosric

# Pane 1: RIC Engine
cd ~/qos_ric/qos_ric && source venv/bin/activate && cd ric_engine
uvicorn ric_engine:app --host 0.0.0.0 --port 8000

# Split pane (Ctrl+B lalu ")

# Pane 2: Dashboard
cd ~/qos_ric/qos_ric && source venv/bin/activate && cd dashboard
python dashboard.py

# Split pane lagi (Ctrl+B lalu ")

# Pane 3: Simulator
cd ~/qos_ric/qos_ric && source venv/bin/activate && cd simulator
python simulator.py --mode normal
```

Detach tmux (layanan tetap jalan): `Ctrl+B` lalu `D`
Masuk lagi ke tmux: `tmux attach -t qosric`

---

## Auto-restart dengan systemd

Agar RIC Engine dan Dashboard otomatis nyala saat EC2 reboot:

```bash
sudo systemctl enable ric-engine qos-dashboard
sudo systemctl start ric-engine qos-dashboard

# Cek status
sudo systemctl status ric-engine
sudo systemctl status qos-dashboard
```

---

## Skenario Demo

| Mode | Behavior | Kapan Dipakai |
|---|---|---|
| **Normal** | Semua SLA ✓ OK — sistem sehat | Awal demo, tunjukkan sistem berjalan |
| **Stress** | Traffic biasa 4x lipat, Biasa mulai FAIL | Simulasikan network congestion |
| **Kill** | Resource dipotong 70%, semua FAIL + email alert | Puncak demo, tunjukkan alert SNS |

---

## Troubleshooting

| Error | Penyebab | Solusi |
|---|---|---|
| `Connection refused port 8000/5000` | Security group EC2 belum buka port | Tambah inbound rule di `launch-wizard-1` |
| `Access denied for user 'admin'` | Password RDS salah | Cek `settings.py` atau reset password di RDS console |
| `Unknown database 'qos_ric_db'` | Database belum dibuat | Jalankan ulang schema SQL |
| `[SNS] Gagal kirim alert` | ARN salah atau credentials tidak valid | Cek ARN di `alert.py` dan `aws configure` |
| Dashboard card kosong (`—%`) | View `dashboard_stats` tidak ada | Jalankan ulang CREATE VIEW di MySQL |
| Tombol mode tidak berpengaruh | Simulator jalan di Windows, bukan EC2 | Pindah jalankan simulator ke EC2 |
| `ModuleNotFoundError` | venv belum aktif | `source ~/qos_ric/qos_ric/venv/bin/activate` |

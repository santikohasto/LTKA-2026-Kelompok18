# ============================================================
# QoS-RIC Project — Central Configuration
# Ganti nilai di bawah sesuai setup cloud kalian
# ============================================================

# ── ECS / Server ──────────────────────────────────────────
RIC_ENGINE_HOST = "0.0.0.0"
RIC_ENGINE_PORT = 8000

# ── Huawei Cloud DIS ──────────────────────────────────────
# Public IP EC2 kamu
RIC_ENGINE_URL  = "http://54.251.207.185:8000"

# RDS endpoint kamu
RDS_HOST     = "qos-ric-db.c3ei8gew8q8z.ap-southeast-1.rds.amazonaws.com"
RDS_PORT     = 3306
RDS_USER     = "admin"
RDS_PASSWORD = "Sempakkuda123"
RDS_DATABASE = "qos_ric_db"

# ── Huawei Cloud ModelArts ────────────────────────────────
MODELARTS_ENDPOINT = "https://YOUR_MODELARTS_ENDPOINT/v1/infers/YOUR_SERVICE_ID"
MODELARTS_TOKEN    = "YOUR_MODELARTS_TOKEN"

# ── Huawei Cloud OBS ──────────────────────────────────────
OBS_ENDPOINT   = "https://obs.ap-southeast-1.myhuaweicloud.com"
OBS_BUCKET     = "qos-ric-dataset"
OBS_AK         = "YOUR_ACCESS_KEY"
OBS_SK         = "YOUR_SECRET_KEY"

# ── Huawei Cloud SMN (Alert) ──────────────────────────────
SMN_ENDPOINT   = "https://smn.ap-southeast-1.myhuaweicloud.com"
SMN_PROJECT_ID = "YOUR_PROJECT_ID"
SMN_TOPIC_URN  = "urn:smn:ap-southeast-1:YOUR_PROJECT_ID:qos-ric-alerts"
SMN_AK         = "YOUR_ACCESS_KEY"
SMN_SK         = "YOUR_SECRET_KEY"

# ── Simulator Settings ────────────────────────────────────
SIMULATOR_INTERVAL_SEC = 1       # kirim data tiap N detik
SIMULATOR_BATCH_SIZE   = (10, 30) # min, max user per batch

# Distribusi user (harus total = 1.0)
USER_DISTRIBUTION = {
    "emergency": 0.10,
    "industry":  0.30,
    "normal":    0.60,
}

# Profil tiap tipe user
USER_PROFILES = {
    "emergency": {"bw_mbps": 5.0, "latency_ms": 10,  "priority": 3},
    "industry":  {"bw_mbps": 2.0, "latency_ms": 50,  "priority": 2},
    "normal":    {"bw_mbps": 0.5, "latency_ms": 200, "priority": 1},
}

# ── PRB / Network Settings ────────────────────────────────
TOTAL_PRB          = 100   # total Physical Resource Block tersedia
PRB_MIN_EMERGENCY  = 30    # PRB minimum untuk user darurat
PRB_MIN_INDUSTRY   = 20    # PRB minimum untuk user industri
PRB_MIN_NORMAL     = 8     # PRB minimum untuk user biasa

# ── SLA Thresholds ────────────────────────────────────────
SLA_COMPLIANCE_THRESHOLD = 0.90   # alert kalau di bawah 90%
SLA_WINDOW_SIZE          = 50     # cek dari N record terakhir

# ── Dashboard ─────────────────────────────────────────────
DASHBOARD_PORT         = 5000
DASHBOARD_REFRESH_MS   = 2000     # refresh tiap 2 detik
DASHBOARD_HISTORY_ROWS = 100      # tampilkan N baris terakhir

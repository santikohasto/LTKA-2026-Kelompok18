# ============================================================
# QoS-RIC Project — Central Configuration
# Ganti nilai di bawah sesuai setup AWS kalian
# ============================================================

# ── Server ────────────────────────────────────────────────
RIC_ENGINE_HOST = "0.0.0.0"
RIC_ENGINE_PORT = 8000
RIC_ENGINE_URL  = "http://54.251.207.185:8000"   # Public IP EC2

# ── AWS RDS MySQL ──────────────────────────────────────────
RDS_HOST     = "qos-ric-db.c3ei8gew8q8z.ap-southeast-1.rds.amazonaws.com"
RDS_PORT     = 3306
RDS_USER     = "admin"
RDS_PASSWORD = "Sempakkuda123"
RDS_DATABASE = "qos_ric_db"

# ── Simulator Settings ────────────────────────────────────
SIMULATOR_INTERVAL_SEC = 1        # kirim data tiap N detik
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
TOTAL_PRB         = 100  # total Physical Resource Block tersedia
PRB_MIN_EMERGENCY = 30   # PRB minimum untuk user darurat
PRB_MIN_INDUSTRY  = 20   # PRB minimum untuk user industri
PRB_MIN_NORMAL    = 8    # PRB minimum untuk user biasa

# ── SLA Thresholds ────────────────────────────────────────
SLA_COMPLIANCE_THRESHOLD = 0.90  # alert kalau di bawah 90%
SLA_WINDOW_SIZE          = 50    # cek dari N record terakhir

# ── Dashboard ─────────────────────────────────────────────
DASHBOARD_PORT         = 5000
DASHBOARD_REFRESH_MS   = 2000   # refresh tiap 2 detik
DASHBOARD_HISTORY_ROWS = 100    # tampilkan N baris terakhir

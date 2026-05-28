-- ============================================================
-- QoS-RIC Database Schema
-- Jalankan file ini sekali di RDS MySQL kalian
-- ============================================================

CREATE DATABASE IF NOT EXISTS qos_ric_db;
USE qos_ric_db;

-- ── Tabel utama: hasil alokasi PRB ────────────────────────
CREATE TABLE IF NOT EXISTS allocations (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    user_type        ENUM('emergency', 'industry', 'normal') NOT NULL,
    bw_requested     FLOAT NOT NULL COMMENT 'Bandwidth diminta (Mbps)',
    latency_req      INT   NOT NULL COMMENT 'Latency requirement (ms)',
    prb_usage        FLOAT NOT NULL COMMENT 'PRB usage saat ini (%)',
    queue_len        INT   NOT NULL COMMENT 'Panjang antrian',
    prb_allocated    INT   NOT NULL COMMENT 'PRB yang diberikan',
    expected_latency FLOAT NOT NULL COMMENT 'Estimasi latency hasil alokasi (ms)',
    sla_ok           BOOLEAN NOT NULL COMMENT 'Apakah SLA terpenuhi',
    model_used       VARCHAR(50) DEFAULT 'random_forest',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_type  (user_type),
    INDEX idx_created_at (created_at),
    INDEX idx_sla_ok     (sla_ok)
);

-- ── Tabel SLA violations ──────────────────────────────────
CREATE TABLE IF NOT EXISTS sla_violations (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_type    ENUM('emergency', 'industry', 'normal') NOT NULL,
    compliance   FLOAT NOT NULL COMMENT 'Compliance rate saat violation (%)',
    alert_sent   BOOLEAN DEFAULT FALSE,
    message      TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Tabel demo events (untuk tombol demo) ─────────────────
CREATE TABLE IF NOT EXISTS demo_events (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    event_type ENUM('normal', 'stress', 'kill') NOT NULL,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── View untuk dashboard: statistik real-time ─────────────
CREATE OR REPLACE VIEW dashboard_stats AS
SELECT
    user_type,
    COUNT(*)                                    AS total_requests,
    AVG(prb_allocated)                          AS avg_prb,
    AVG(expected_latency)                       AS avg_latency,
    SUM(CASE WHEN sla_ok THEN 1 ELSE 0 END)    AS sla_ok_count,
    COUNT(*) - SUM(CASE WHEN sla_ok THEN 1 ELSE 0 END) AS sla_fail_count,
    ROUND(
        SUM(CASE WHEN sla_ok THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
    ) AS sla_compliance_pct
FROM allocations
WHERE created_at >= NOW() - INTERVAL 5 MINUTE
GROUP BY user_type;

-- ── View untuk grafik PRB time-series ─────────────────────
CREATE OR REPLACE VIEW prb_timeseries AS
SELECT
    DATE_FORMAT(created_at, '%H:%i:%s') AS time_label,
    user_type,
    AVG(prb_allocated) AS avg_prb,
    AVG(expected_latency) AS avg_latency,
    COUNT(*) AS request_count
FROM allocations
WHERE created_at >= NOW() - INTERVAL 10 MINUTE
GROUP BY DATE_FORMAT(created_at, '%H:%i:%s'), user_type
ORDER BY time_label ASC;

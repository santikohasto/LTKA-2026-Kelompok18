"""
QoS-RIC — Database connection helper
Dipakai oleh RIC Engine dan Dashboard
"""
import mysql.connector
from mysql.connector import pooling
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.settings import RDS_HOST, RDS_PORT, RDS_USER, RDS_PASSWORD, RDS_DATABASE

# Connection pool agar tidak buka koneksi baru tiap request
_pool = None

def get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="qos_ric_pool",
            pool_size=5,
            host=RDS_HOST,
            port=RDS_PORT,
            user=RDS_USER,
            password=RDS_PASSWORD,
            database=RDS_DATABASE,
            autocommit=True
        )
    return _pool

def get_conn():
    """Ambil koneksi dari pool"""
    return get_pool().get_connection()

def execute(query: str, params: tuple = None, fetch: bool = False):
    """Helper: jalankan query, opsional fetch hasil"""
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    try:
        cur.execute(query, params or ())
        if fetch:
            return cur.fetchall()
        return cur.rowcount
    finally:
        cur.close()
        conn.close()

def insert_allocation(data: dict) -> int:
    """Simpan satu record alokasi ke tabel allocations"""
    query = """
        INSERT INTO allocations
            (user_type, bw_requested, latency_req, prb_usage,
             queue_len, prb_allocated, expected_latency, sla_ok, model_used)
        VALUES
            (%(user_type)s, %(bw_requested)s, %(latency_req)s, %(prb_usage)s,
             %(queue_len)s, %(prb_allocated)s, %(expected_latency)s, %(sla_ok)s, %(model_used)s)
    """
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute(query, data)
        return cur.lastrowid
    finally:
        cur.close()
        conn.close()

def insert_violation(user_type: str, compliance: float, message: str):
    """Catat SLA violation"""
    execute(
        "INSERT INTO sla_violations (user_type, compliance, message) VALUES (%s, %s, %s)",
        (user_type, compliance, message)
    )

def get_recent_allocations(limit: int = 100) -> list:
    """Ambil N record alokasi terbaru untuk dashboard"""
    return execute(
        """SELECT * FROM allocations ORDER BY created_at DESC LIMIT %s""",
        (limit,), fetch=True
    )

def get_dashboard_stats() -> list:
    """Ambil statistik real-time dari view"""
    return execute("SELECT * FROM dashboard_stats", fetch=True)

def get_prb_timeseries() -> list:
    """Ambil data time-series untuk grafik"""
    return execute("SELECT * FROM prb_timeseries", fetch=True)

def get_sla_compliance(user_type: str, window: int = 50) -> float:
    """Hitung SLA compliance rate untuk tipe user tertentu dari N record terakhir"""
    rows = execute(
        """SELECT sla_ok FROM allocations
           WHERE user_type = %s
           ORDER BY created_at DESC LIMIT %s""",
        (user_type, window), fetch=True
    )
    if not rows:
        return 1.0
    ok = sum(1 for r in rows if r["sla_ok"])
    return ok / len(rows)

def log_demo_event(event_type: str):
    """Catat event demo (normal/stress/kill)"""
    execute(
        "INSERT INTO demo_events (event_type) VALUES (%s)",
        (event_type,)
    )

"""
QoS-RIC — RIC Engine (FastAPI)
================================
Ini adalah otak sistem. Menerima trafik dari simulator,
memanggil model ML, memutuskan alokasi PRB,
menyimpan ke RDS, dan memantau SLA.

Cara jalankan:
  uvicorn ric_engine:app --host 0.0.0.0 --port 8000 --reload

Endpoints:
  POST /ingest_batch   — terima batch user dari simulator
  GET  /status         — health check
  GET  /stats          — statistik real-time
  GET  /recent         — N record alokasi terbaru
  POST /demo/mode      — ganti mode simulator (untuk tombol demo)
"""

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import time
import pickle
import requests
from datetime import datetime
from fastapi   import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic  import BaseModel
from typing    import List, Optional

from config.settings  import (
    MODELARTS_ENDPOINT, MODELARTS_TOKEN,
    SLA_COMPLIANCE_THRESHOLD, SLA_WINDOW_SIZE,
    USER_PROFILES,
)
from alert.alert      import send_alert

# ── Coba load model lokal dulu ─────────────────────────────
MODEL_PKG = None
MODEL_PATH = os.path.join(os.path.dirname(__file__), "../ml_model/model/qos_model.pkl")

def load_local_model():
    global MODEL_PKG
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            MODEL_PKG = pickle.load(f)
        print(f"[RIC] Model lokal dimuat dari {MODEL_PATH}")
    else:
        print(f"[RIC] Model lokal tidak ditemukan — akan pakai ModelArts atau rule-based")

load_local_model()

# ── Import database ────────────────────────────────────────
try:
    from database.db import (
        insert_allocation, get_recent_allocations,
        get_dashboard_stats, get_sla_compliance,
        insert_violation, log_demo_event
    )
    DB_AVAILABLE = True
    print("[RIC] Koneksi database OK")
except Exception as e:
    DB_AVAILABLE = False
    print(f"[RIC] Database tidak tersambung: {e} — pakai in-memory storage")
    _memory_store = []

# ── FastAPI app ────────────────────────────────────────────
app = FastAPI(
    title="QoS-RIC Engine",
    description="Near-RT RAN Intelligent Controller — PRB Allocation Engine",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request/Response models ────────────────────────────────
class UserRequest(BaseModel):
    user_type:   str
    bw_req:      float
    latency_req: int
    priority:    Optional[int] = None
    prb_usage:   float
    queue_len:   int
    prb_cap:     Optional[float] = 1.0
    timestamp:   Optional[float] = None

class BatchRequest(BaseModel):
    users: List[UserRequest]

class DemoModeRequest(BaseModel):
    mode: str  # "normal" | "stress" | "kill"


# ── PRB Allocation Logic ───────────────────────────────────

def rule_based_allocate(user: UserRequest) -> dict:
    """
    Fallback rule-based allocation.
    Dipakai kalau model ML tidak tersedia.
    """
    priority_map = {"emergency": 3, "industry": 2, "normal": 1}
    priority     = priority_map.get(user.user_type, 1)
    base_prb     = {3: 40, 2: 25, 1: 10}[priority]
    min_prb      = {3: 30, 2: 15, 1: 5}[priority]

    congestion   = 1.0 - (user.prb_usage / 100) * 0.4
    queue_factor = 1.0 - min(user.queue_len / 50, 0.3)
    cap_factor   = user.prb_cap if user.prb_cap else 1.0

    # Hitung PRB normal dulu (dengan minimum guard)
    prb = max(min_prb, int(base_prb * congestion * queue_factor))

    # Lalu APPLY prb_cap di akhir — kill mode akan benar-benar memotong PRB
    prb = max(3, int(prb * cap_factor))

    # Formula latency baru: berbasis PRB vs kebutuhan
    prb_needed_map = {"emergency": 25, "industry": 15, "normal": 7}
    prb_needed     = prb_needed_map.get(user.user_type, 7)
    ratio          = prb / prb_needed
    lat_req        = user.latency_req

    if ratio >= 1.0:
        base = lat_req * (0.7 - min(0.4, (ratio - 1.0) * 0.2))
    else:
        base = lat_req * (0.7 / max(ratio, 0.1))

    congestion_add = (user.prb_usage / 100) * lat_req * 0.15
    queue_add      = (user.queue_len / 50)  * lat_req * 0.05
    est_latency    = round(max(1.0, base + congestion_add + queue_add), 2)
    sla_ok         = est_latency <= lat_req

    return {
        "prb_allocated":    prb,
        "expected_latency": est_latency,
        "sla_ok":           sla_ok,
        "model_used":       "rule_based",
    }


def ml_allocate(user: UserRequest) -> dict:
    """Minta prediksi dari model ML lokal atau ModelArts"""
    import pandas as pd

    # Coba model lokal dulu
    if MODEL_PKG:
        try:
            from ml_model.train_model import predict_single
            user_dict = user.dict()
            user_dict["hour_of_day"] = datetime.now().hour
            result    = predict_single(MODEL_PKG, user_dict)

            # Terapkan prb_cap (resource tersedia)
            # Terapkan prb_cap (resource tersedia)
            # Di kill mode, prb_cap akan benar-benar memotong PRB
            if user.prb_cap and user.prb_cap < 1.0:
                result["prb_allocated"] = max(
                    3, int(result["prb_allocated"] * user.prb_cap))
                # Hitung ulang latency dengan PRB yang sudah dipotong
                from ml_model.train_model import predict_single
                user_dict = user.dict()
                user_dict["hour_of_day"] = datetime.now().hour
                # Pakai formula latency manual karena PRB sudah dipotong
                prb_needed_map = {"emergency": 25, "industry": 15, "normal": 7}
                prb_needed     = prb_needed_map.get(user.user_type, 7)
                ratio          = result["prb_allocated"] / prb_needed
                lat_req        = user.latency_req
                if ratio >= 1.0:
                    base = lat_req * (0.7 - min(0.4, (ratio - 1.0) * 0.2))
                else:
                    base = lat_req * (0.7 / max(ratio, 0.1))
                cong_add = (user.prb_usage / 100) * lat_req * 0.15
                q_add    = (user.queue_len / 50)  * lat_req * 0.05
                result["expected_latency"] = round(max(1.0, base + cong_add + q_add), 2)
                result["sla_ok"] = result["expected_latency"] <= lat_req

            return result
        except Exception as e:
            print(f"[RIC] Model lokal error: {e} — fallback rule-based")

    # Coba ModelArts cloud
    if MODELARTS_ENDPOINT and "YOUR_MODELARTS" not in MODELARTS_ENDPOINT:
        try:
            payload = {
                "data": {
                    "req_data": [{
                        "user_type":   user.user_type,
                        "bw_req":      user.bw_req,
                        "latency_req": user.latency_req,
                        "priority":    user.priority or 1,
                        "prb_usage":   user.prb_usage,
                        "queue_len":   user.queue_len,
                        "hour_of_day": datetime.now().hour,
                    }]
                }
            }
            resp = requests.post(
                MODELARTS_ENDPOINT,
                json=payload,
                headers={"X-Auth-Token": MODELARTS_TOKEN},
                timeout=5
            )
            if resp.status_code == 200:
                pred = resp.json()["resp_data"][0]
                return {
                    "prb_allocated":    int(pred["prb_allocated"]),
                    "expected_latency": float(pred["expected_latency"]),
                    "sla_ok":           bool(pred["sla_ok"]),
                    "model_used":       "modelarts",
                }
        except Exception as e:
            print(f"[RIC] ModelArts error: {e} — fallback rule-based")

    # Fallback: rule-based
    return rule_based_allocate(user)


def save_result(user: UserRequest, result: dict):
    """Simpan hasil alokasi ke storage"""
    record = {
        "user_type":        user.user_type,
        "bw_requested":     user.bw_req,
        "latency_req":      user.latency_req,
        "prb_usage":        user.prb_usage,
        "queue_len":        user.queue_len,
        "prb_allocated":    result["prb_allocated"],
        "expected_latency": result["expected_latency"],
        "sla_ok":           result["sla_ok"],
        "model_used":       result.get("model_used", "unknown"),
    }

    if DB_AVAILABLE:
        try:
            insert_allocation(record)
            return
        except Exception as e:
            print(f"[RIC] DB insert error: {e}")

    # In-memory fallback
    record["created_at"] = datetime.now().isoformat()
    _memory_store.append(record)
    if len(_memory_store) > 1000:
        _memory_store.pop(0)


def check_sla(user_type: str):
    """Cek SLA compliance dan kirim alert kalau perlu"""
    if DB_AVAILABLE:
        compliance = get_sla_compliance(user_type, SLA_WINDOW_SIZE)
    else:
        # Hitung dari memory
        recent = [r for r in _memory_store[-SLA_WINDOW_SIZE:]
                  if r["user_type"] == user_type]
        if not recent:
            return
        compliance = sum(1 for r in recent if r["sla_ok"]) / len(recent)

    if compliance < SLA_COMPLIANCE_THRESHOLD:
        msg = (f"SLA {user_type.upper()} turun ke {compliance*100:.1f}%! "
               f"Threshold: {SLA_COMPLIANCE_THRESHOLD*100:.0f}%")
        print(f"[RIC] ⚠ {msg}")
        send_alert(msg, user_type=user_type, compliance=compliance)

        if DB_AVAILABLE:
            try:
                insert_violation(user_type, compliance, msg)
            except:
                pass


# ── API Endpoints ──────────────────────────────────────────

@app.get("/status")
def status():
    return {
        "status":     "running",
        "model":      MODEL_PKG["version"] if MODEL_PKG else "rule_based",
        "db":         DB_AVAILABLE,
        "timestamp":  datetime.now().isoformat(),
    }


@app.post("/ingest_batch")
def ingest_batch(req: BatchRequest):
    """
    Terima batch user dari simulator,
    proses tiap user, simpan hasil, cek SLA.
    """
    results  = []
    sla_check_types = set()

    for user in req.users:
        # 1. Tentukan prioritas kalau belum ada
        if not user.priority:
            pmap = {"emergency": 3, "industry": 2, "normal": 1}
            user.priority = pmap.get(user.user_type, 1)

        # 2. Alokasikan PRB via ML
        result = ml_allocate(user)

        # 3. Simpan ke DB
        save_result(user, result)

        # 4. Tandai tipe user untuk dicek SLA-nya
        sla_check_types.add(user.user_type)

        results.append({
            "user_type":    user.user_type,
            "prb":          result["prb_allocated"],
            "latency_est":  result["expected_latency"],
            "sla_ok":       result["sla_ok"],
        })

    # 5. Cek SLA untuk tiap tipe user yang ada di batch
    for utype in sla_check_types:
        check_sla(utype)

    return {
        "processed": len(results),
        "results":   results,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/stats")
def get_stats():
    """Statistik real-time untuk dashboard"""
    if DB_AVAILABLE:
        try:
            return {"stats": get_dashboard_stats(), "source": "db"}
        except Exception as e:
            print(f"[RIC] Stats DB error: {e}")

    # Hitung dari memory
    if not _memory_store:
        return {"stats": [], "source": "memory"}

    from collections import defaultdict
    agg = defaultdict(lambda: {"total": 0, "sla_ok": 0, "prb_sum": 0, "lat_sum": 0})
    for r in _memory_store[-200:]:
        ut = r["user_type"]
        agg[ut]["total"]   += 1
        agg[ut]["sla_ok"]  += 1 if r["sla_ok"] else 0
        agg[ut]["prb_sum"] += r["prb_allocated"]
        agg[ut]["lat_sum"] += r["expected_latency"]

    stats = []
    for ut, d in agg.items():
        stats.append({
            "user_type":         ut,
            "total_requests":    d["total"],
            "avg_prb":           round(d["prb_sum"] / d["total"], 2),
            "avg_latency":       round(d["lat_sum"] / d["total"], 2),
            "sla_compliance_pct": round(d["sla_ok"] / d["total"] * 100, 2),
        })

    return {"stats": stats, "source": "memory"}


@app.get("/recent")
def get_recent(limit: int = 50):
    """Ambil N record terbaru untuk tabel live di dashboard"""
    if DB_AVAILABLE:
        try:
            rows = get_recent_allocations(limit)
            # Convert datetime ke string
            for r in rows:
                if hasattr(r.get("created_at"), "isoformat"):
                    r["created_at"] = r["created_at"].isoformat()
            return {"records": rows, "source": "db"}
        except Exception as e:
            print(f"[RIC] Recent DB error: {e}")

    records = list(reversed(_memory_store[-limit:]))
    return {"records": records, "source": "memory"}


@app.post("/demo/mode")
def set_demo_mode(req: DemoModeRequest):
    """
    Endpoint untuk tombol demo di dashboard.
    Mengubah mode simulator via file flag.
    """
    valid_modes = ["normal", "stress", "kill"]
    if req.mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Mode harus salah satu: {valid_modes}")

    # Tulis mode ke file flag agar dibaca simulator
    flag_path = "/tmp/qos_ric_mode.txt"
    with open(flag_path, "w") as f:
        f.write(req.mode)

    if DB_AVAILABLE:
        try:
            log_demo_event(req.mode)
        except:
            pass

    mode_desc = {
        "normal": "Normal operation",
        "stress": "Stress test — user biasa 4x lipat",
        "kill":   "SLA violation — resource 30%",
    }
    return {
        "mode":    req.mode,
        "message": mode_desc[req.mode],
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/")
def root():
    return {
        "service": "QoS-RIC Engine",
        "version": "1.0.0",
        "endpoints": ["/status", "/ingest_batch", "/stats", "/recent", "/demo/mode"],
    }

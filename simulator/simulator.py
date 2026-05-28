"""
QoS-RIC — Traffic Simulator
============================
Mensimulasikan trafik jaringan dari 3 tipe user:
  - emergency : prioritas tinggi  (10%)
  - industry  : prioritas sedang  (30%)
  - normal    : prioritas biasa   (60%)

Cara pakai:
  python simulator.py              → mode normal
  python simulator.py --mode stress  → stress test
  python simulator.py --mode kill    → trigger SLA violation
  python simulator.py --mode demo    → jalankan semua skenario otomatis
"""

import time
import random
import json
import argparse
import requests
import threading
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.settings import (
    RIC_ENGINE_URL,
    SIMULATOR_INTERVAL_SEC,
    SIMULATOR_BATCH_SIZE,
    USER_PROFILES,
)

# ── Mode simulator ──────────────────────────────────────────
MODES = {
    "normal": {
        "weights":     [0.10, 0.30, 0.60],
        "batch_scale": 1.0,
        "prb_cap":     1.0,   # 100% resource tersedia
        "desc":        "Normal operation — proporsi user realistis"
    },
    "stress": {
        "weights":     [0.05, 0.10, 0.85],
        "batch_scale": 4.0,   # 4x lebih banyak user
        "prb_cap":     0.75,
        "desc":        "Stress test — lonjakan user biasa 4x lipat"
    },
    "kill": {
        "weights":     [0.05, 0.05, 0.90],
        "batch_scale": 5.0,   # 5x user
        "prb_cap":     0.3,   # hanya 30% resource tersedia
        "desc":        "SLA violation — resource dipaksa sangat terbatas"
    },
}

USER_TYPES = ["emergency", "industry", "normal"]

# State global (bisa diubah via API atau input)
current_mode = "normal"
running      = True
stats        = {"sent": 0, "errors": 0}


def generate_user(user_type: str, prb_cap: float) -> dict:
    """Buat satu record user sintetis"""
    profile = USER_PROFILES[user_type]
    noise   = random.uniform(-0.15, 0.15)

    return {
        "user_type":   user_type,
        "bw_req":      round(profile["bw_mbps"] * (1 + noise), 3),
        "latency_req": profile["latency_ms"],
        "priority":    profile["priority"],
        "prb_usage":   round(random.uniform(55, 95), 1),
        "queue_len":   random.randint(1, 40),
        "prb_cap":     prb_cap,   # dikirim ke engine biar tau resource tersedia
        "timestamp":   time.time(),
    }


def send_batch(batch: list) -> bool:
    """Kirim batch user ke RIC Engine"""
    try:
        resp = requests.post(
            f"{RIC_ENGINE_URL}/ingest_batch",
            json={"users": batch},
            timeout=30
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"  [ERROR] Gagal kirim: {e}")
        return False


def run_simulator():
    """Loop utama simulator"""
    global running, stats, current_mode

    print(f"\n{'='*55}")
    print(f"  QoS-RIC Traffic Simulator")
    print(f"  Target : {RIC_ENGINE_URL}")
    print(f"  Mode   : {current_mode.upper()} — {MODES[current_mode]['desc']}")
    print(f"{'='*55}\n")

    while running:
        # Baca file flag dari dashboard untuk auto-switch mode
        try:
            with open("/tmp/qos_ric_mode.txt", "r") as f:
                new_mode = f.read().strip()
                if new_mode in MODES and new_mode != current_mode:
                    print(f"\n[*] Mode berubah: {current_mode.upper()} -> {new_mode.upper()}\n")
                    current_mode = new_mode
        except FileNotFoundError:
            pass
        except Exception:
            pass

        mode_cfg = MODES[current_mode]
        weights  = mode_cfg["weights"]
        prb_cap  = mode_cfg["prb_cap"]

        # Tentukan jumlah user batch ini
        base_min, base_max = SIMULATOR_BATCH_SIZE
        n_users = random.randint(
            int(base_min * mode_cfg["batch_scale"]),
            int(base_max * mode_cfg["batch_scale"])
        )

        # Generate user batch
        user_types = random.choices(USER_TYPES, weights=weights, k=n_users)
        batch = [generate_user(ut, prb_cap) for ut in user_types]

        # Hitung distribusi batch ini
        counts = {t: user_types.count(t) for t in USER_TYPES}

        # Kirim ke RIC Engine
        ok = send_batch(batch)
        if ok:
            stats["sent"] += len(batch)
        else:
            stats["errors"] += 1

        # Print status
        status = "OK" if ok else "ERR"
        print(
            f"[{time.strftime('%H:%M:%S')}] [{current_mode.upper():6}] [{status}] "
            f"Sent {len(batch):3} users | "
            f"🚨{counts['emergency']:2} "
            f"🏭{counts['industry']:2} "
            f"👤{counts['normal']:3} | "
            f"Total: {stats['sent']}"
        )

        time.sleep(SIMULATOR_INTERVAL_SEC)


def run_demo_sequence():
    """
    Mode demo otomatis: jalankan semua skenario berurutan.
    Cocok untuk demo di depan penguji tanpa harus ganti mode manual.
    """
    global current_mode

    sequence = [
        ("normal", 30, "Skenario A: Normal operation (30 detik)"),
        ("stress", 30, "Skenario B: Stress test — lonjakan trafik (30 detik)"),
        ("kill",   20, "Skenario C: SLA violation — resource dikurangi (20 detik)"),
        ("normal", 10, "Kembali normal (10 detik)"),
    ]

    sim_thread = threading.Thread(target=run_simulator, daemon=True)
    sim_thread.start()

    for mode, duration, desc in sequence:
        print(f"\n{'─'*55}")
        print(f"  ▶ {desc}")
        print(f"{'─'*55}")
        current_mode = mode
        time.sleep(duration)

    global running
    running = False
    print("\n[DEMO] Selesai — semua skenario sudah dijalankan.")


def interactive_mode():
    """Mode interaktif: user bisa ganti mode via input keyboard"""
    global current_mode, running

    sim_thread = threading.Thread(target=run_simulator, daemon=True)
    sim_thread.start()

    print("\nKontrol simulator:")
    print("  [n] Normal    [s] Stress test    [k] Kill resources    [q] Quit\n")

    while True:
        try:
            cmd = input().strip().lower()
            if cmd == "n":
                current_mode = "normal"
                print(f">> Mode: NORMAL")
            elif cmd == "s":
                current_mode = "stress"
                print(f">> Mode: STRESS TEST — lonjakan user biasa 4x")
            elif cmd == "k":
                current_mode = "kill"
                print(f">> Mode: KILL — resource dipaksa 30%, SLA akan dilanggar!")
            elif cmd == "q":
                running = False
                print(">> Simulator dihentikan.")
                break
        except KeyboardInterrupt:
            running = False
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QoS-RIC Traffic Simulator")
    parser.add_argument(
        "--mode",
        choices=["normal", "stress", "kill", "demo", "interactive"],
        default="interactive",
        help="Mode simulasi"
    )
    args = parser.parse_args()

    if args.mode == "demo":
        run_demo_sequence()
    elif args.mode == "interactive":
        interactive_mode()
    else:
        current_mode = args.mode
        try:
            run_simulator()
        except KeyboardInterrupt:
            print("\nSimulator dihentikan.")

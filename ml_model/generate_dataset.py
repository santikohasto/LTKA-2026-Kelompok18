"""
QoS-RIC — Dataset Generator untuk Training Model ML
=====================================================
Generate dataset sintetis yang mensimulasikan keputusan
alokasi PRB optimal berdasarkan aturan prioritas.

Cara pakai:
  python generate_dataset.py
  python generate_dataset.py --samples 10000 --output data/training.csv
"""

import pandas as pd
import numpy as np
import argparse
import os

# Seed untuk reproducibility
np.random.seed(42)

# Profil tiap tipe user
USER_PROFILES = {
    "emergency": {"bw_base": 5.0, "lat_req": 10,  "priority": 3, "prb_base": 40},
    "industry":  {"bw_base": 2.0, "lat_req": 50,  "priority": 2, "prb_base": 30},
    "normal":    {"bw_base": 0.5, "lat_req": 200, "priority": 1, "prb_base": 15},
}


def compute_optimal_prb(row: dict) -> int:
    """
    Hitung alokasi PRB optimal berdasarkan aturan prioritas.
    Ini yang menjadi label (target) untuk training model ML.
    
    Logika:
    - Base PRB dari tipe user
    - Berkurang kalau jaringan padat (prb_usage tinggi)
    - Berkurang kalau antrian panjang (banyak user)
    - Emergency selalu dapat minimum 30 PRB
    - Industry  selalu dapat minimum 15 PRB
    - Normal    selalu dapat minimum 5 PRB
    """
    profile  = USER_PROFILES[row["user_type"]]
    base_prb = profile["prb_base"]

    # Penalti jaringan padat (makin padat makin sedikit PRB)
    congestion_factor = 1.0 - (row["prb_usage"] / 100) * 0.4

    # Penalti antrian panjang
    queue_factor = 1.0 - min(row["queue_len"] / 50, 0.3)

    # Hitung PRB
    prb = base_prb * congestion_factor * queue_factor

    # Floor minimum per tipe
    minimums = {"emergency": 30, "industry": 15, "normal": 5}
    prb = max(prb, minimums[row["user_type"]])

    # Tambahkan sedikit noise agar model belajar dari variasi
    prb += np.random.randint(-2, 3)
    prb  = max(minimums[row["user_type"]], int(round(prb)))
    prb  = min(prb, 80)  # cap maksimum 80 PRB per user

    return prb


def compute_expected_latency(prb_allocated: int, latency_req: int,
                              prb_usage: float, queue_len: int,
                              user_type: str = "normal") -> float:
    """
    Estimasi latency berdasarkan PRB vs kebutuhan tipe user.
    Formula: latency rendah kalau PRB cukup, naik kalau PRB kurang.
    """
    # PRB minimum yang dibutuhkan agar SLA tercapai
    prb_needed_map = {"emergency": 25, "industry": 15, "normal": 7}
    prb_needed     = prb_needed_map.get(user_type, 7)
    ratio          = prb_allocated / prb_needed

    if ratio >= 1.0:
        # PRB cukup: latency 30-70% dari target (SLA OK)
        base = latency_req * (0.7 - min(0.4, (ratio - 1.0) * 0.2))
    else:
        # PRB kurang: latency naik berbanding terbalik
        base = latency_req * (0.7 / ratio)

    congestion_add = (prb_usage / 100) * latency_req * 0.15
    queue_add      = (queue_len / 50)  * latency_req * 0.05
    noise          = np.random.uniform(-3, 3)

    return round(max(1.0, base + congestion_add + queue_add + noise), 2)

def generate_dataset(n_samples: int = 5000) -> pd.DataFrame:
    """Generate dataset lengkap dengan fitur dan label"""
    rows = []

    # Distribusi realistis: 10% emergency, 30% industry, 60% normal
    user_types = np.random.choice(
        list(USER_PROFILES.keys()),
        size=n_samples,
        p=[0.10, 0.30, 0.60]
    )

    for user_type in user_types:
        profile = USER_PROFILES[user_type]

        # ── Input features ────────────────────────────────
        bw_req   = round(profile["bw_base"] * np.random.uniform(0.8, 1.3), 3)
        prb_usage = round(np.random.uniform(40, 97), 1)
        queue_len = int(np.random.randint(1, 50))
        hour      = int(np.random.randint(0, 24))   # jam dalam sehari (pola trafik)

        row = {
            "user_type":   user_type,
            "bw_req":      bw_req,
            "latency_req": profile["lat_req"],
            "priority":    profile["priority"],
            "prb_usage":   prb_usage,
            "queue_len":   queue_len,
            "hour_of_day": hour,
        }

        # ── Labels ────────────────────────────────────────
        prb_opt          = compute_optimal_prb(row)
        expected_latency = compute_expected_latency(
	    prb_opt, profile["lat_req"], prb_usage, queue_len, user_type)
        sla_ok           = expected_latency <= profile["lat_req"]

        row["prb_allocated"]    = prb_opt
        row["expected_latency"] = expected_latency
        row["sla_ok"]           = int(sla_ok)   # 1 = OK, 0 = violated

        rows.append(row)

    df = pd.DataFrame(rows)

    # One-hot encode user_type untuk model
    df = pd.get_dummies(df, columns=["user_type"], prefix="type")

    return df


def print_summary(df: pd.DataFrame):
    """Print ringkasan dataset"""
    print("\n" + "="*50)
    print("  Dataset Summary")
    print("="*50)
    print(f"  Total samples  : {len(df)}")
    print(f"  Features       : {list(df.columns)}")
    print(f"\n  PRB allocated  :")
    print(df["prb_allocated"].describe().round(2).to_string(header=False))
    print(f"\n  SLA compliance : {df['sla_ok'].mean()*100:.1f}%")
    print(f"\n  Sample rows:")
    print(df.head(3).to_string(index=False))
    print("="*50 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate QoS-RIC training dataset")
    parser.add_argument("--samples", type=int, default=5000, help="Jumlah sampel")
    parser.add_argument("--output",  type=str, default="data/training.csv")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    print(f"Generating {args.samples} samples...")
    df = generate_dataset(args.samples)
    df.to_csv(args.output, index=False)

    print_summary(df)
    print(f"Dataset saved to: {args.output}")

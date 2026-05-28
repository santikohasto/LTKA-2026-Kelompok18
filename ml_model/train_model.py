"""
QoS-RIC — Model Training Script
=================================
Train Random Forest untuk prediksi alokasi PRB optimal.
Jalankan di ModelArts notebook atau lokal.

Cara pakai:
  python train_model.py
  python train_model.py --data data/training.csv --save model/qos_model.pkl
"""

import pandas as pd
import numpy as np
import pickle
import argparse
import os
from sklearn.ensemble          import RandomForestRegressor
from sklearn.model_selection   import train_test_split, cross_val_score
from sklearn.preprocessing     import StandardScaler
from sklearn.metrics           import mean_absolute_error, r2_score
from sklearn.pipeline          import Pipeline


# ── Feature columns yang dipakai model ───────────────────
FEATURE_COLS = [
    "bw_req",
    "latency_req",
    "priority",
    "prb_usage",
    "queue_len",
    "hour_of_day",
    "type_emergency",
    "type_industry",
    "type_normal",
]
TARGET_COL = "prb_allocated"


def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    print(f"Loaded {len(df)} rows from {path}")

    # Pastikan kolom one-hot ada (kalau belum ada, generate)
    for col in ["type_emergency", "type_industry", "type_normal"]:
        if col not in df.columns:
            utype = col.replace("type_", "")
            df[col] = (df.get("user_type", "") == utype).astype(int)

    # Fill kolom yang mungkin belum ada
    if "hour_of_day" not in df.columns:
        df["hour_of_day"] = np.random.randint(0, 24, len(df))
    if "priority" not in df.columns:
        pmap = {"emergency": 3, "industry": 2, "normal": 1}
        df["priority"] = df.get("user_type", "normal").map(pmap).fillna(1)

    return df


def train(df: pd.DataFrame):
    """Train Random Forest model dan return pipeline"""
    X = df[FEATURE_COLS]
    y = df[TARGET_COL]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42)

    # Pipeline: scaler + model
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("rf", RandomForestRegressor(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        ))
    ])

    print("Training Random Forest...")
    model.fit(X_train, y_train)

    # ── Evaluasi ──────────────────────────────────────────
    y_pred = model.predict(X_test)
    mae    = mean_absolute_error(y_test, y_pred)
    r2     = r2_score(y_test, y_pred)
    cv     = cross_val_score(model, X, y, cv=5, scoring="r2")

    print("\n" + "="*45)
    print("  Model Evaluation")
    print("="*45)
    print(f"  MAE (Mean Abs Error) : {mae:.2f} PRB units")
    print(f"  R² Score             : {r2:.4f}")
    print(f"  Cross-val R² (5-fold): {cv.mean():.4f} ± {cv.std():.4f}")

    # Feature importance
    rf       = model.named_steps["rf"]
    feat_imp = sorted(
        zip(FEATURE_COLS, rf.feature_importances_),
        key=lambda x: -x[1]
    )
    print("\n  Feature Importance:")
    for feat, imp in feat_imp:
        bar = "█" * int(imp * 40)
        print(f"    {feat:20s} {imp:.3f} {bar}")
    print("="*45 + "\n")

    return model


def save_model(model, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump({
            "model":       model,
            "feature_cols": FEATURE_COLS,
            "target_col":  TARGET_COL,
            "version":     "1.0",
        }, f)
    print(f"Model saved to: {path}")


def load_model(path: str):
    with open(path, "rb") as f:
        return pickle.load(f)


def predict_single(model_pkg: dict, user_data: dict) -> dict:
    """
    Predict PRB allocation untuk satu user.
    Input  : dict dengan field sesuai USER_PROFILES
    Output : dict dengan prb_allocated, expected_latency, sla_ok
    """
    model  = model_pkg["model"]
    feats  = model_pkg["feature_cols"]

    # Build feature vector
    row = {
        "bw_req":        user_data.get("bw_req", 1.0),
        "latency_req":   user_data.get("latency_req", 100),
        "priority":      user_data.get("priority", 1),
        "prb_usage":     user_data.get("prb_usage", 70),
        "queue_len":     user_data.get("queue_len", 10),
        "hour_of_day":   user_data.get("hour_of_day", 12),
        "type_emergency": 1 if user_data.get("user_type") == "emergency" else 0,
        "type_industry":  1 if user_data.get("user_type") == "industry"  else 0,
        "type_normal":    1 if user_data.get("user_type") == "normal"    else 0,
    }

    X = pd.DataFrame([row])[feats]
    prb_pred = int(round(float(model.predict(X)[0])))
    prb_pred = max(5, min(80, prb_pred))  # clamp 5–80

    # Estimasi latency dari PRB
    # Estimasi latency: berbasis PRB vs kebutuhan tipe user
    lat_req        = user_data.get("latency_req", 100)
    prb_usage      = user_data.get("prb_usage", 70)
    queue_len      = user_data.get("queue_len", 10)
    user_type      = user_data.get("user_type", "normal")

    prb_needed_map = {"emergency": 25, "industry": 15, "normal": 7}
    prb_needed     = prb_needed_map.get(user_type, 7)
    ratio          = prb_pred / prb_needed

    if ratio >= 1.0:
        base = lat_req * (0.7 - min(0.4, (ratio - 1.0) * 0.2))
    else:
        base = lat_req * (0.7 / max(ratio, 0.1))

    congestion_add = (prb_usage / 100) * lat_req * 0.15
    queue_add      = (queue_len / 50)  * lat_req * 0.05
    est_latency    = round(max(1.0, base + congestion_add + queue_add), 2)
    sla_ok         = est_latency <= lat_req

    return {
        "prb_allocated":    prb_pred,
        "expected_latency": est_latency,
        "sla_ok":           sla_ok,
        "model_used":       "random_forest",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/training.csv")
    parser.add_argument("--save", default="model/qos_model.pkl")
    args = parser.parse_args()

    # 1. Generate dataset kalau belum ada
    if not os.path.exists(args.data):
        print(f"Dataset tidak ditemukan di {args.data}. Generating...")
        import subprocess
        subprocess.run(["python", "generate_dataset.py",
                        "--output", args.data], check=True)

    # 2. Load data
    df = load_data(args.data)

    # 3. Train
    model = train(df)

    # 4. Save
    save_model(model, args.save)

    # 5. Test prediksi
    pkg = load_model(args.save)
    test_user = {
        "user_type": "emergency", "bw_req": 5.2,
        "latency_req": 10, "prb_usage": 85, "queue_len": 20,
        "priority": 3, "hour_of_day": 14,
    }
    result = predict_single(pkg, test_user)
    print("Test prediction (emergency user):")
    print(f"  PRB allocated    : {result['prb_allocated']}")
    print(f"  Expected latency : {result['expected_latency']} ms")
    print(f"  SLA OK           : {result['sla_ok']}")

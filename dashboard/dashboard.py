"""
QoS-RIC — Dashboard Backend (Flask)
=====================================
Serve dashboard web real-time.
Baca data dari RIC Engine via API.

Cara jalankan:
  python dashboard.py

Buka browser: http://YOUR_ECS_IP:5000
"""

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import requests
from flask           import Flask, render_template, jsonify
from config.settings import RIC_ENGINE_URL, DASHBOARD_PORT, DASHBOARD_REFRESH_MS

app = Flask(__name__)


def fetch_from_engine(path: str) -> dict:
    """Ambil data dari RIC Engine"""
    try:
        resp = requests.get(f"{RIC_ENGINE_URL}{path}", timeout=5)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


@app.route("/")
def index():
    return render_template("index.html", refresh_ms=DASHBOARD_REFRESH_MS)


@app.route("/api/stats")
def api_stats():
    return jsonify(fetch_from_engine("/stats"))


@app.route("/api/recent")
def api_recent():
    return jsonify(fetch_from_engine("/recent?limit=30"))


@app.route("/api/status")
def api_status():
    return jsonify(fetch_from_engine("/status"))


@app.route("/api/demo/<mode>", methods=["POST"])
def api_demo(mode: str):
    """Tombol demo — ganti mode simulator"""
    try:
        resp = requests.post(
            f"{RIC_ENGINE_URL}/demo/mode",
            json={"mode": mode},
            timeout=5
        )
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print(f"\nQoS-RIC Dashboard berjalan di http://0.0.0.0:{DASHBOARD_PORT}")
    print(f"RIC Engine URL : {RIC_ENGINE_URL}")
    app.run(host="0.0.0.0", port=DASHBOARD_PORT, debug=True)

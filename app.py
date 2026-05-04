from flask import Flask, request, jsonify
import requests
import os
import psycopg2
import hashlib

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
GUMROAD_PRODUCT_ID = os.environ.get("GUMROAD_PRODUCT_ID")

def get_db():
    return psycopg2.connect(DATABASE_URL)

def hash_device(device_id):
    return hashlib.sha256(device_id.encode()).hexdigest()

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            license_key TEXT PRIMARY KEY,
            device_hash TEXT NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

@app.route("/")
def home():
    return "Blackjack License Server Running ✅"

@app.route("/verify", methods=["POST"])
def verify():

    data = request.json
    license_key = data.get("license_key")
    device_id = data.get("device_id")

    if not license_key or not device_id:
        return jsonify({"success": False, "message": "Missing parameters"}), 400

    # ✅ Gumroad doğrulama
    gumroad = requests.post(
        "https://api.gumroad.com/v2/licenses/verify",
        data={
            "product_id": GUMROAD_PRODUCT_ID,
            "license_key": license_key,
            "increment_uses_count": "false"
        }
    )

    gum_data = gumroad.json()

    if not gum_data.get("success"):
        return jsonify({"success": False, "message": "Invalid license"}), 403

    device_hash = hash_device(device_id)

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT device_hash FROM licenses WHERE license_key=%s",
        (license_key,)
    )
    row = cur.fetchone()

    if row is None:
        cur.execute(
            "INSERT INTO licenses (license_key, device_hash) VALUES (%s, %s)",
            (license_key, device_hash)
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "License activated ✅"})

    saved_device = row[0]

    if saved_device == device_hash:
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Already activated ✅"})

    cur.close()
    conn.close()

    return jsonify({
        "success": False,
        "message": "This license is already used on another computer ❌"
    }), 403
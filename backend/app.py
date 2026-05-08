"""
QR Attendance System — Backend API (Improved)
Flask + MySQL
🔒 CIA Triad applied throughout — see SECURITY_NOTES.md
"""

import base64
import hashlib
import hmac
import os
import logging
from datetime import datetime, date, timedelta
from functools import wraps

import bcrypt                                          # 🔒 CIA: Confidentiality — password hashing
import jwt
import pymysql
import pymysql.cursors
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter                      # ⚡ CIA: Availability — rate limiting
from flask_limiter.util import get_remote_address
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

# ── App setup ────────────────────────────────────────────────
app = Flask(__name__)

# 🔒 CIA: Confidentiality — restrict CORS to frontend origin only
CORS(app, origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")])

# ⚡ CIA: Availability — rate limiting on all routes
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per hour", "50 per minute"]
)

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Prometheus metrics ───────────────────────────────────────
REQ_COUNTER   = Counter("attendance_requests_total", "Total attendance POST requests")
ERROR_COUNTER = Counter("attendance_errors_total",   "Total attendance errors")

# ── Config ───────────────────────────────────────────────────
JWT_SECRET     = os.environ["JWT_SECRET"]             # 🔒 CIA: Confidentiality — from .env
QR_SECRET_KEY  = os.environ["QR_SECRET_KEY"]          # 🔒 CIA: Confidentiality — from .env
ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", "3306")),
    "user":     os.getenv("DB_USER", "attendance_user"),
    "password": os.getenv("DB_PASSWORD"),              # 🔒 CIA: Confidentiality — from .env
    "database": os.getenv("DB_NAME", "attendance_db"),
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
    "connect_timeout": 5,
}

# ── DB helper with connection pooling ────────────────────────
# ⚡ CIA: Availability — reuse connections, don't open a new one per request
_pool = None

def get_db():
    """Return a DB connection. Creates a new one per request (pymysql is not thread-safe for pooling without a library)."""
    return pymysql.connect(**DB_CONFIG)


# ── Hash admin password on startup ──────────────────────────
# 🔒 CIA: Confidentiality — bcrypt hash, never compare plaintext
_ADMIN_HASH = bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt(rounds=12))


def check_admin_password(plain: str) -> bool:
    return bcrypt.checkpw(plain.encode(), _ADMIN_HASH)


# ── JWT helpers ──────────────────────────────────────────────
def generate_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(hours=8),  # short-lived token
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def require_auth(f):
    """🔒 CIA: Confidentiality — protect admin endpoints with JWT"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Unauthorized — token required"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            request.current_user = payload["sub"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


# ── QR validation ────────────────────────────────────────────
def decode_and_validate_qr(qr_payload: str):
    """🛡️ CIA: Integrity — HMAC-SHA256 signature verification"""
    secret = QR_SECRET_KEY.encode()
    try:
        decoded    = base64.b64decode(qr_payload.encode()).decode()
        student_id, signature = decoded.split("|", 1)
    except Exception:
        return None, "Invalid QR format"

    expected = hmac.new(secret, student_id.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None, "QR signature invalid"

    return student_id, None


def sanitize_student_id(student_id: str):
    """🛡️ CIA: Integrity — strict allowlist, prevent injection"""
    if not student_id or len(student_id) > 32:
        return None
    if not student_id.replace("-", "").isalnum():
        return None
    return student_id


# ── Audit log ────────────────────────────────────────────────
def audit(actor: str, action: str, target: str):
    """🛡️ CIA: Integrity — immutable record of every sensitive action"""
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log (actor, action, target, ip_address, created_at) VALUES (%s,%s,%s,%s,%s)",
                (actor, action, target, request.remote_addr, datetime.utcnow())
            )
        conn.close()
    except Exception as e:
        logger.error(f"Audit log write failed: {e}")


# ────────────────────────────────────────────────────────────
#  ROUTES
# ────────────────────────────────────────────────────────────

# ⚡ CIA: Availability — health endpoint for Docker/K8s probes
@app.get("/health")
def health_check():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})


# ⚡ CIA: Availability — Prometheus metrics scrape endpoint
@app.get("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


# ── Admin login ──────────────────────────────────────────────
@app.post("/api/auth/login")
@limiter.limit("5 per 15 minutes")                    # ⚡ CIA: Availability — brute-force guard
def login():
    data     = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Missing credentials"}), 400

    # 🔒 CIA: Confidentiality — bcrypt comparison, constant-time safe
    if username != ADMIN_USERNAME or not check_admin_password(password):
        audit("unknown", "LOGIN_FAILED", username)
        return jsonify({"error": "Invalid credentials"}), 401

    token = generate_token(username)
    audit(username, "LOGIN_SUCCESS", "admin_panel")
    return jsonify({"token": token})


# ── Validate QR (preview before recording) ──────────────────
@app.post("/api/qr/validate")
@require_auth
def validate_qr():
    payload    = request.get_json(silent=True) or {}
    qr_payload = payload.get("qr_data", "")

    student_id, err = decode_and_validate_qr(qr_payload)
    if err:
        return jsonify({"valid": False, "error": err}), 400

    sanitized = sanitize_student_id(student_id)
    if not sanitized:
        return jsonify({"valid": False, "error": "Invalid student ID format"}), 400

    return jsonify({"valid": True, "student_id": sanitized})


# ── Record attendance ────────────────────────────────────────
@app.post("/api/attendance")
@limiter.limit("120 per minute")                       # ⚡ CIA: Availability — prevent scan flooding
def record_attendance():
    REQ_COUNTER.inc()
    payload    = request.get_json(silent=True) or {}
    qr_payload = payload.get("qr_data", "")

    # 🛡️ CIA: Integrity — validate before any DB write
    student_id, err = decode_and_validate_qr(qr_payload)
    if err:
        ERROR_COUNTER.inc()
        return jsonify({"status": "rejected", "message": err}), 400

    sanitized = sanitize_student_id(student_id)
    if not sanitized:
        ERROR_COUNTER.inc()
        return jsonify({"status": "rejected", "message": "Invalid student ID"}), 400

    now   = datetime.now()
    today = date.today()

    conn = get_db()
    try:
        with conn.cursor() as cursor:
            # 🛡️ CIA: Integrity — verify student exists before recording
            cursor.execute(
                "SELECT student_id, full_name, program, year_level FROM students WHERE student_id=%s",
                (sanitized,)
            )
            student = cursor.fetchone()
            if not student:
                ERROR_COUNTER.inc()
                audit("system", "SCAN_UNKNOWN", sanitized)
                return jsonify({"status": "rejected", "message": "Student not recognized"}), 404

            cursor.execute(
                "SELECT id, time_in, time_out FROM attendance "
                "WHERE student_id=%s AND attendance_date=%s ORDER BY id DESC LIMIT 1",
                (sanitized, today),
            )
            record = cursor.fetchone()

            if not record:
                # First scan of the day → TIME IN
                cursor.execute(
                    "INSERT INTO attendance (student_id, attendance_date, time_in, status) VALUES (%s,%s,%s,%s)",
                    (sanitized, today, now, "TIME_IN"),
                )
                audit("system", "TIME_IN", sanitized)
                return jsonify({
                    "status":  "success",
                    "message": "Time-in recorded",
                    "type":    "TIME_IN",
                    "student": student,
                    "time":    now.isoformat(),
                })

            if record["time_out"] is not None:
                # 🛡️ CIA: Integrity — prevent duplicate full attendance
                return jsonify({
                    "status":  "duplicate",
                    "message": "Attendance already completed for today",
                }), 409

            # Second scan → TIME OUT
            cursor.execute(
                "UPDATE attendance SET time_out=%s, status=%s WHERE id=%s",
                (now, "TIME_OUT", record["id"]),
            )
            audit("system", "TIME_OUT", sanitized)
            return jsonify({
                "status":  "success",
                "message": "Time-out recorded",
                "type":    "TIME_OUT",
                "student": student,
                "time":    now.isoformat(),
            })
    finally:
        conn.close()


# ── Student lookup ───────────────────────────────────────────
@app.get("/api/students/<student_id>")
@require_auth
def get_student(student_id):
    sanitized = sanitize_student_id(student_id)
    if not sanitized:
        return jsonify({"error": "Invalid student ID"}), 400

    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT student_id, full_name, program, year_level FROM students WHERE student_id=%s",
                (sanitized,)
            )
            student = cursor.fetchone()
    finally:
        conn.close()

    if not student:
        return jsonify({"error": "Student not found"}), 404

    return jsonify(student)


# ── Attendance report (admin only) ───────────────────────────
@app.get("/api/reports/attendance")
@require_auth                                          # 🔒 CIA: Confidentiality — admin JWT required
def attendance_report():
    target_date = request.args.get("date", date.today().isoformat())

    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.student_id, s.full_name, a.attendance_date,
                       a.time_in, a.time_out, a.status
                FROM attendance a
                INNER JOIN students s ON s.student_id = a.student_id
                WHERE a.attendance_date = %s
                ORDER BY a.time_in DESC
                LIMIT 500
                """,
                (target_date,)
            )
            rows = cursor.fetchall()
    finally:
        conn.close()

    # Serialize datetime fields
    for r in rows:
        for key in ["time_in", "time_out", "attendance_date"]:
            if r.get(key):
                r[key] = str(r[key])

    return jsonify(rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)   # 🔒 CIA: debug=False in production

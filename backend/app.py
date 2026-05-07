import base64
import hashlib
import hmac
import os
from datetime import datetime, date
from functools import wraps

from flask import Flask, jsonify, request
from flask_cors import CORS
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
import pymysql

app = Flask(__name__)
CORS(app)

REQ_COUNTER = Counter("attendance_requests_total", "Total attendance POST requests")
ERROR_COUNTER = Counter("attendance_errors_total", "Total attendance processing errors")


def get_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "attendance_user"),
        password=os.getenv("DB_PASSWORD", "attendance_pass"),
        database=os.getenv("DB_NAME", "attendance_db"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def decode_and_validate_qr(qr_payload: str):
    secret = os.getenv("QR_SECRET_KEY", "batstateu_qr_secret").encode()
    try:
        decoded = base64.b64decode(qr_payload.encode()).decode()
        student_id, signature = decoded.split("|")
    except Exception:
        return None, "Invalid QR format"

    expected_sig = hmac.new(secret, student_id.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_sig):
        return None, "QR validation failed"

    return student_id, None


def sanitize_student_id(student_id: str):
    if not student_id or len(student_id) > 32:
        return None
    if not student_id.replace("-", "").isalnum():
        return None
    return student_id


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth:
            return jsonify({"error": "Authentication required"}), 401

        admin_user = os.getenv("ADMIN_USERNAME", "admin")
        admin_pass = os.getenv("ADMIN_PASSWORD", "admin123")

        if auth.username != admin_user or auth.password != admin_pass:
            return jsonify({"error": "Invalid credentials"}), 403
        return fn(*args, **kwargs)

    return wrapper


@app.get("/health")
def health_check():
    return jsonify({"status": "ok"})


@app.get("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.post("/api/qr/validate")
def validate_qr():
    payload = request.get_json(silent=True) or {}
    qr_payload = payload.get("qr_data", "")
    student_id, err = decode_and_validate_qr(qr_payload)
    if err:
        return jsonify({"valid": False, "error": err}), 400

    sanitized = sanitize_student_id(student_id)
    if not sanitized:
        return jsonify({"valid": False, "error": "Invalid student ID"}), 400

    return jsonify({"valid": True, "student_id": sanitized})


@app.get("/api/students/<student_id>")
def get_student(student_id):
    sanitized = sanitize_student_id(student_id)
    if not sanitized:
        return jsonify({"error": "Invalid student ID"}), 400

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT student_id, full_name, program, year_level FROM students WHERE student_id=%s",
            (sanitized,),
        )
        student = cursor.fetchone()

    if not student:
        return jsonify({"error": "Student not found"}), 404

    return jsonify(student)


@app.post("/api/attendance")
def record_attendance():
    REQ_COUNTER.inc()
    payload = request.get_json(silent=True) or {}
    qr_payload = payload.get("qr_data", "")

    student_id, err = decode_and_validate_qr(qr_payload)
    if err:
        ERROR_COUNTER.inc()
        return jsonify({"status": "rejected", "message": err}), 400

    sanitized = sanitize_student_id(student_id)
    if not sanitized:
        ERROR_COUNTER.inc()
        return jsonify({"status": "rejected", "message": "Invalid student ID"}), 400

    now = datetime.now()
    today = date.today()

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT student_id FROM students WHERE student_id=%s", (sanitized,))
        student = cursor.fetchone()
        if not student:
            ERROR_COUNTER.inc()
            return jsonify({"status": "rejected", "message": "Student not recognized"}), 404

        cursor.execute(
            "SELECT id, time_in, time_out FROM attendance WHERE student_id=%s AND attendance_date=%s ORDER BY id DESC LIMIT 1",
            (sanitized, today),
        )
        record = cursor.fetchone()

        if not record:
            cursor.execute(
                "INSERT INTO attendance (student_id, attendance_date, time_in, status) VALUES (%s, %s, %s, %s)",
                (sanitized, today, now, "TIME_IN"),
            )
            return jsonify({"status": "success", "message": "Time-in recorded", "type": "TIME_IN"})

        if record["time_out"] is not None:
            return jsonify({"status": "duplicate", "message": "Attendance already completed for today"}), 409

        cursor.execute(
            "UPDATE attendance SET time_out=%s, status=%s WHERE id=%s",
            (now, "TIME_OUT", record["id"]),
        )
        return jsonify({"status": "success", "message": "Time-out recorded", "type": "TIME_OUT"})


@app.get("/api/reports/attendance")
@admin_required
def attendance_report():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT a.student_id, s.full_name, a.attendance_date, a.time_in, a.time_out, a.status
            FROM attendance a
            INNER JOIN students s ON s.student_id = a.student_id
            ORDER BY a.attendance_date DESC, a.time_in DESC
            LIMIT 500
            """
        )
        rows = cursor.fetchall()
    return jsonify(rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

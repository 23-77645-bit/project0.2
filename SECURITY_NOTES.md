# Security Notes — Student Identification and Attendance System
## IT 323 / NTT 404 | Batangas State University ARASOF-Nasugbu

---

## CIA Triad Mapping

### 🔒 Confidentiality — Only authorized users can access data

| Feature | Implementation | File |
|---|---|---|
| Admin login | bcrypt (rounds=12) password hashing — never plaintext comparison | `backend/app.py` |
| Session management | JWT tokens (HS256, 8-hour expiry) — Bearer token required for admin routes | `backend/app.py` |
| Secret management | All credentials loaded from `.env` file — never hardcoded in source | `docker-compose.yml`, `k8s/backend-deployment.yaml` |
| CORS restriction | Only the frontend origin (`http://localhost:3000`) is allowed | `backend/app.py` |
| DB port exposure | MySQL bound to `127.0.0.1:3306` only — not accessible from public network | `docker-compose.yml` |
| Monitoring ports | Prometheus bound to `127.0.0.1:9090` — internal access only | `docker-compose.yml` |
| K8s secrets | Sensitive env vars injected via `kubectl create secret` — not plain YAML | `k8s/backend-deployment.yaml` |

---

### 🛡️ Integrity — Data is accurate and tamper-proof

| Feature | Implementation | File |
|---|---|---|
| QR validation | HMAC-SHA256 signature verified before any DB write — forged QR codes rejected | `backend/app.py` |
| Input sanitization | Student ID validated with length check + alphanumeric allowlist | `backend/app.py` |
| Parameterized queries | All SQL uses `%s` placeholders — no string concatenation, no SQL injection | `backend/app.py` |
| Duplicate prevention | `UNIQUE KEY (student_id, attendance_date)` enforced at DB level | `db/schema.sql` |
| Student verification | Student must exist in DB before attendance is recorded | `backend/app.py` |
| Audit log | Every login attempt, scan, and admin action written to `audit_log` table | `backend/app.py`, `db/schema.sql` |

---

### ⚡ Availability — System stays up and responsive

| Feature | Implementation | File |
|---|---|---|
| Rate limiting | Global: 200/hour, 50/min — Login: 5 per 15 min — Scan: 120/min | `backend/app.py` |
| DB healthcheck | Docker waits for MySQL ready before starting backend (`service_healthy`) | `docker-compose.yml` |
| Container restart | All services configured with `restart: unless-stopped` | `docker-compose.yml` |
| K8s scaling | HPA scales backend pods 2–6 replicas at 70% CPU utilization | `k8s/backend-hpa.yaml` |
| Liveness probe | K8s restarts backend pod if `/health` fails | `k8s/backend-deployment.yaml` |
| Readiness probe | K8s removes pod from service if not ready to accept traffic | `k8s/backend-deployment.yaml` |
| Monitoring | Prometheus scrapes `/metrics`, Grafana dashboards show uptime/performance | `monitoring/prometheus.yml` |
| Persistent storage | MySQL data stored in named Docker volume — survives container restarts | `docker-compose.yml` |

---

## Security Risks and Mitigations

### Risk 1: QR Code Spoofing / Replay Attacks
- **Threat:** Attacker forges or replays a QR payload to record fake attendance.
- **Mitigation:** QR payload contains `student_id|HMAC-SHA256(student_id, secret)`. The backend verifies the signature before any DB operation. An attacker without the `QR_SECRET_KEY` cannot generate a valid payload. The key is stored in `.env`, never in source code.

### Risk 2: SQL Injection via Malformed Input
- **Threat:** Attacker injects SQL through the QR data or API parameters.
- **Mitigation:** All queries use parameterized statements (`%s` placeholders with pymysql). Student ID is additionally validated with a strict alphanumeric allowlist before reaching the query layer.

### Risk 3: Unauthorized Admin Access
- **Threat:** Attacker brute-forces or steals admin credentials to view attendance reports.
- **Mitigation:** Admin password is hashed with bcrypt (cost factor 12). Login endpoint is rate-limited to 5 attempts per 15 minutes per IP. All admin routes require a valid short-lived JWT. Credentials are never stored in source code.

### Risk 4: Exposed Database Port
- **Threat:** MySQL port exposed to the public network, allowing direct DB attacks.
- **Mitigation:** In `docker-compose.yml`, MySQL is bound to `127.0.0.1:3306` (localhost only). In Kubernetes, MySQL is accessed via an internal ClusterIP service — not exposed externally.

### Risk 5: Scan Flooding / Denial of Service
- **Threat:** Attacker or faulty scanner floods the `/api/attendance` endpoint, exhausting resources.
- **Mitigation:** `flask-limiter` enforces 120 requests/minute on the scan endpoint. K8s HPA auto-scales pods under high load. Prometheus + Grafana provide real-time alerts.

---

## What is Still Recommended for Production

- [ ] HTTPS / TLS termination via a reverse proxy (nginx or cloud load balancer)
- [ ] Redis backend for `flask-limiter` (current in-memory limit resets on restart)
- [ ] Rotate `QR_SECRET_KEY` and `JWT_SECRET` periodically
- [ ] Move K8s secrets to HashiCorp Vault or cloud secret manager (AWS Secrets Manager, GCP Secret Manager)
- [ ] Enable MySQL SSL connections between backend and DB containers

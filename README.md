# Student Identification and Attendance System (QR-Based)

This project is a containerized client-server attendance platform for Batangas State University coursework (IT 323 / NTT 404).

## Architecture
- **Frontend container**: Nginx-served web UI for QR submission and attendance confirmation
- **Backend container**: Flask REST API for QR validation, attendance logic, reporting, and metrics
- **Database container**: MySQL for student and attendance records
- **Monitoring stack**: Prometheus + Grafana

## Prerequisites
- Docker Engine 24+
- Docker Compose v2+
- Git

## Project Structure
- `frontend/` – UI and frontend Dockerfile
- `backend/` – Flask API, dependencies, backend Dockerfile
- `db/schema.sql` – MySQL schema initialization
- `monitoring/prometheus.yml` – Prometheus scrape configuration
- `docker-compose.yml` – local multi-container deployment
- `k8s/` – backend Deployment/Service/HPA manifests
- `Jenkinsfile` – CI/CD pipeline definition
- `SECURITY_NOTES.md` – CIA triad mapping and risk mitigations

## Installation and Run (Docker Compose)
1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd project0.2
   ```

2. **Build and start all services**
   ```bash
   docker compose up -d --build
   ```

3. **Check running containers**
   ```bash
   docker compose ps
   ```

4. **Access services**
   - Frontend UI: `http://localhost:3000`
   - Backend API health: `http://localhost:5000/health`
   - Prometheus: `http://localhost:9090`
   - Grafana: `http://localhost:3001` (default login: `admin` / `admin123`)

5. **Stop services**
   ```bash
   docker compose down
   ```

## Database Initialization
The database schema is auto-loaded from:
- `./db/schema.sql` mounted into MySQL init directory (`/docker-entrypoint-initdb.d`).

## Basic API Usage

### 1) Validate QR
```bash
curl -X POST http://localhost:5000/api/qr/validate \
  -H "Content-Type: application/json" \
  -d '{"qr_data":"<base64-studentid|hmac-signature>"}'
```

### 2) Record attendance
```bash
curl -X POST http://localhost:5000/api/attendance \
  -H "Content-Type: application/json" \
  -d '{"qr_data":"<base64-studentid|hmac-signature>"}'
```

### 3) Student lookup
```bash
curl http://localhost:5000/api/students/<student_id>
```

### 4) Admin attendance report
```bash
curl -u admin:admin123 http://localhost:5000/api/reports/attendance
```

## CI/CD (Jenkins)
Pipeline stages in `Jenkinsfile`:
1. Checkout
2. Build + test (`python3 -m py_compile backend/app.py`)
3. Docker build (frontend + backend)
4. Docker push (DockerHub credentials required)
5. Auto-deploy via `docker compose`

## Kubernetes (Backend)
Apply backend manifests:
```bash
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-hpa.yaml
```

## Security Notes
See `SECURITY_NOTES.md` for:
- Confidentiality controls
- Integrity controls
- Availability controls
- Risk mitigations for QR spoofing, SQL injection, and unauthorized access

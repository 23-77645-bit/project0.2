# Security Notes: Student Identification and Attendance System

## CIA Triad Mapping

### Confidentiality
- Admin/teacher endpoints use login protection via HTTP Basic auth (`/api/reports/attendance`).
- Student data is stored with encrypted-at-rest style handling by saving `full_name` as `VARBINARY`, enabling encrypted payload storage workflows.
- Access to services is restricted by explicit container port mapping in `docker-compose.yml`.

### Integrity
- QR payloads are validated with HMAC-SHA256 signature checking before any database write.
- Student ID input is sanitized (length + character allowlist) and all SQL statements use parameterized queries.
- Attendance write logic verifies student existence and blocks invalid/unrecognized QR codes gracefully.

### Availability
- Containerized services (frontend, backend, db, monitoring) support repeatable startup and recovery.
- Prometheus scrapes backend metrics (`/metrics`) and Grafana provides visibility for uptime/performance.
- Kubernetes deployment with HPA supports scaling backend pods based on CPU utilization.

## Security Risks and Mitigations

1. **Risk: QR spoofing/replay attempts**
   - **Mitigation:** Signed QR content (HMAC with shared secret) and validation before recording attendance.

2. **Risk: SQL injection and malformed input**
   - **Mitigation:** Parameterized queries plus student ID sanitization and strict validation path.

3. **Risk: Unauthorized admin access / exposed attack surface**
   - **Mitigation:** Admin authentication for reports, controlled exposed ports in Docker, and non-exposed internal service communication via private network.

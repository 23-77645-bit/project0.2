-- ============================================================
--  QR Attendance System — Database Schema
--  🛡️ CIA: Integrity — structured, validated, audited
-- ============================================================

CREATE TABLE IF NOT EXISTS students (
  student_id  VARCHAR(32)   PRIMARY KEY,
  full_name   VARCHAR(255)  NOT NULL,
  program     VARCHAR(100)  NOT NULL,
  year_level  VARCHAR(20)   NOT NULL,
  is_active   BOOLEAN       DEFAULT TRUE,
  created_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attendance (
  id               BIGINT       AUTO_INCREMENT PRIMARY KEY,
  student_id       VARCHAR(32)  NOT NULL,
  attendance_date  DATE         NOT NULL,
  time_in          DATETIME     NOT NULL,
  time_out         DATETIME     NULL,
  status           ENUM('TIME_IN','TIME_OUT') NOT NULL,
  created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_attendance_student
    FOREIGN KEY (student_id) REFERENCES students(student_id),
  -- 🛡️ CIA: Integrity — one record per student per day (no duplicates)
  UNIQUE KEY uniq_student_day (student_id, attendance_date),
  INDEX idx_attendance_date (attendance_date),
  INDEX idx_student_time    (student_id, time_in)
);

-- 🛡️ CIA: Integrity — immutable audit trail for all sensitive actions
CREATE TABLE IF NOT EXISTS audit_log (
  id          BIGINT        AUTO_INCREMENT PRIMARY KEY,
  actor       VARCHAR(100),
  action      VARCHAR(100),
  target      VARCHAR(100),
  ip_address  VARCHAR(45),
  created_at  DATETIME      DEFAULT CURRENT_TIMESTAMP
);

-- ── Sample students (for testing) ────────────────────────────
INSERT IGNORE INTO students (student_id, full_name, program, year_level) VALUES
  ('2024-00001', 'Aseron, Ashley Mae D.', 'BSIT', '3rd Year'),
  ('2024-00002', 'Condicion, Jomhar',      'BSIT', '3rd Year'),
  ('2024-00003', 'Mercado, Mike Darren',   'BSIT', '3rd Year'),
  ('2024-00004', 'Rol, John Moreen B.',    'BSIT', '3rd Year');

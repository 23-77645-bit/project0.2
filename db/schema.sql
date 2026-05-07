CREATE TABLE IF NOT EXISTS students (
  student_id VARCHAR(32) PRIMARY KEY,
  full_name VARBINARY(255) NOT NULL,
  program VARCHAR(100) NOT NULL,
  year_level VARCHAR(20) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attendance (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  student_id VARCHAR(32) NOT NULL,
  attendance_date DATE NOT NULL,
  time_in DATETIME NOT NULL,
  time_out DATETIME NULL,
  status ENUM('TIME_IN', 'TIME_OUT') NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_attendance_student FOREIGN KEY (student_id) REFERENCES students(student_id),
  UNIQUE KEY uniq_student_day (student_id, attendance_date),
  INDEX idx_attendance_date (attendance_date),
  INDEX idx_student_time (student_id, time_in)
);

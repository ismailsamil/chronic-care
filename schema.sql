PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS patients (
  patient_id    INTEGER PRIMARY KEY,
  first_name    TEXT NOT NULL CHECK (length(trim(first_name)) > 0),
  last_name     TEXT NOT NULL CHECK (length(trim(last_name)) > 0),
  birth_date    TEXT NOT NULL CHECK (birth_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  sex           TEXT NOT NULL CHECK (sex IN ('F','M','O')),
  email         TEXT UNIQUE,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conditions (
  condition_id  INTEGER PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  icd10_code    TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS patient_conditions (
  patient_id    INTEGER NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  condition_id  INTEGER NOT NULL REFERENCES conditions(condition_id),
  diagnosed_on  TEXT NOT NULL,
  PRIMARY KEY (patient_id, condition_id)
);

CREATE TABLE IF NOT EXISTS medications (
  medication_id INTEGER PRIMARY KEY,
  name          TEXT NOT NULL,
  active_ingredient TEXT NOT NULL,
  form          TEXT NOT NULL CHECK (form IN ('tablet','capsule','injection','inhaler','liquid')),
  strength      TEXT NOT NULL,
  UNIQUE (name, strength)
);

CREATE TABLE IF NOT EXISTS treatments (
  treatment_id  INTEGER PRIMARY KEY,
  patient_id    INTEGER NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  medication_id INTEGER NOT NULL REFERENCES medications(medication_id),
  condition_id  INTEGER NOT NULL REFERENCES conditions(condition_id),
  dose          TEXT NOT NULL,
  frequency_per_day INTEGER NOT NULL CHECK (frequency_per_day BETWEEN 1 AND 12),
  start_date    TEXT NOT NULL,
  end_date      TEXT,
  status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','stopped')),
  CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS dose_logs (
  log_id        INTEGER PRIMARY KEY,
  treatment_id  INTEGER NOT NULL REFERENCES treatments(treatment_id) ON DELETE CASCADE,
  log_date      TEXT NOT NULL,
  doses_taken   INTEGER NOT NULL CHECK (doses_taken >= 0),
  UNIQUE (treatment_id, log_date)
);

CREATE INDEX IF NOT EXISTS idx_treat_patient ON treatments(patient_id);
CREATE INDEX IF NOT EXISTS idx_treat_med     ON treatments(medication_id);
CREATE INDEX IF NOT EXISTS idx_logs_treat    ON dose_logs(treatment_id, log_date);

CREATE VIEW IF NOT EXISTS v_adherence AS
SELECT t.treatment_id, p.patient_id, p.first_name || ' ' || p.last_name AS patient,
       m.name AS medication, c.name AS condition,
       SUM(l.doses_taken) AS doses_taken,
       COUNT(l.log_id) * t.frequency_per_day AS doses_expected,
       ROUND(100.0 * SUM(l.doses_taken) / (COUNT(l.log_id) * t.frequency_per_day), 1) AS adherence_pct
FROM treatments t
JOIN patients p    ON p.patient_id = t.patient_id
JOIN medications m ON m.medication_id = t.medication_id
JOIN conditions c  ON c.condition_id = t.condition_id
JOIN dose_logs l   ON l.treatment_id = t.treatment_id
GROUP BY t.treatment_id;

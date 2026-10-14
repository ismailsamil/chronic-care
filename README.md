# Chronic-Care CSV Database (MVP)

Structured, validated database for a health & medication platform focused on chronic illnesses.
CSV in -> validated relational DB (SQLite) -> reports and CSV out. Synthetic data only.

## Run
    python load.py build      # create DB, import data/*.csv, write rejects.csv
    python load.py report     # active treatments per condition + adherence
    python load.py export patients

No dependencies (Python 3 standard library).

## Data model
patients, conditions (ICD-10), patient_conditions, medications, treatments (prescriptions), dose_logs
+ view v_adherence (doses taken vs expected per treatment)

## Data integrity (3 layers)
1. Row validation in Python (dates, sex, email, required names, end_date >= start_date)
2. DB constraints: PK/FK, UNIQUE (email, medication name+strength), CHECK (status, form, frequency 1-12)
3. Rejected rows never load; they go to rejects.csv with line number and reason

The sample CSVs contain 5 deliberately bad rows so you can see this working.

## Scaling path
SQLite -> PostgreSQL: same schema (swap AUTOINCREMENT/GLOB for native types/regex), add
table partitioning on dose_logs, role-based access, audit tables, encryption of PII.

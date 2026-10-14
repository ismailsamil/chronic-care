#!/usr/bin/env python3
"""Chronic-care CSV database: build SQLite DB from CSVs with validation.
Bad rows are never loaded; they are written to rejects.csv with the reason.
Usage:
  python load.py build            # create DB + import all CSVs
  python load.py report           # adherence + summary report
  python load.py export <table>   # dump a table back to CSV
"""
import csv, re, sqlite3, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
DB = ROOT / "chronic_care.db"
ORDER = ["conditions", "medications", "patients", "patient_conditions", "treatments", "dose_logs"]
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def valid_date(v):
    if not DATE.match(v or ""): return False
    try: datetime.strptime(v, "%Y-%m-%d"); return True
    except ValueError: return False

def connect():
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    return con

def build():
    DB.unlink(missing_ok=True)
    con = connect()
    con.executescript((ROOT / "schema.sql").read_text())
    rejects, summary = [], {}
    for table in ORDER:
        ok = bad = 0
        with open(ROOT / "data" / f"{table}.csv", newline="", encoding="utf-8") as f:
            for n, row in enumerate(csv.DictReader(f), start=2):
                row = {k: (v.strip() if v and v.strip() != "" else None) for k, v in row.items()}
                err = check(table, row)
                if not err:
                    cols = ",".join(row); ph = ",".join("?" * len(row))
                    try:
                        con.execute(f"INSERT INTO {table} ({cols}) VALUES ({ph})", list(row.values()))
                        ok += 1; continue
                    except sqlite3.IntegrityError as e:
                        err = f"db constraint: {e}"
                bad += 1
                rejects.append({"table": table, "csv_line": n, "reason": err, "row": str(row)})
        summary[table] = (ok, bad)
    con.commit(); con.close()
    with open(ROOT / "rejects.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["table", "csv_line", "reason", "row"])
        w.writeheader(); w.writerows(rejects)
    print(f"{'table':20}{'loaded':>8}{'rejected':>10}")
    for t, (o, b) in summary.items(): print(f"{t:20}{o:>8}{b:>10}")
    print(f"\nRejected rows -> {ROOT/'rejects.csv'}")

def check(table, r):
    """Row-level validation before hitting the DB."""
    if table == "patients":
        if not r["first_name"] or not r["last_name"]: return "missing name"
        if not valid_date(r["birth_date"]): return "birth_date must be YYYY-MM-DD"
        if r["sex"] not in ("F", "M", "O"): return "sex must be F/M/O"
        if r["email"] and "@" not in r["email"]: return "invalid email"
    if table == "treatments":
        if not valid_date(r["start_date"]): return "invalid start_date"
        if r["end_date"] and r["end_date"] < r["start_date"]: return "end_date before start_date"
    return None

def report():
    con = connect()
    print("== Active treatments per condition ==")
    for row in con.execute("""SELECT c.name, COUNT(*) FROM treatments t
        JOIN conditions c USING(condition_id) WHERE t.status='active' GROUP BY c.name ORDER BY 2 DESC"""):
        print(f"  {row[0]:25}{row[1]}")
    print("\n== Adherence (lowest first) ==")
    for row in con.execute("SELECT patient, medication, adherence_pct FROM v_adherence ORDER BY adherence_pct"):
        flag = "  <-- follow up" if row[2] < 75 else ""
        print(f"  {row[0]:15}{row[1]:18}{row[2]:>5}%{flag}")

def export(table):
    con = connect()
    cur = con.execute(f"SELECT * FROM {table}")
    out = ROOT / f"export_{table}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow([d[0] for d in cur.description]); w.writerows(cur)
    print(f"Exported -> {out}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"build": build, "report": report}.get(cmd, lambda: export(sys.argv[2]))()

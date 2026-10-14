"""Chronic-Care CSV Database - interactive MVP (Streamlit).
Loads sample CSVs (or your uploads) into a validated relational DB and shows
data quality results and medication adherence. Synthetic data only."""
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

import load  # reuses validation rules + table order from the CLI

ROOT = Path(__file__).parent
SCHEMA = (ROOT / "schema.sql").read_text()

st.set_page_config(page_title="Chronic-Care Database MVP", page_icon="🩺", layout="wide")


def read_csv(src):
    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    return df.apply(lambda c: c.str.strip()).replace("", None)


@st.cache_data(show_spinner=False)
def build_db(uploads: tuple):
    """Build an in-memory DB. uploads = ((table, csv_bytes), ...) overriding sample files."""
    override = dict(uploads)
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    summary, rejects = [], []
    from io import BytesIO
    for table in load.ORDER:
        src = BytesIO(override[table]) if table in override else ROOT / "data" / f"{table}.csv"
        df = read_csv(src)
        ok = bad = 0
        for n, rec in enumerate(df.to_dict("records"), start=2):
            row = {k: (None if pd.isna(v) else v) for k, v in rec.items()}
            err = load.check(table, row)
            if not err:
                cols = ",".join(row)
                try:
                    con.execute(f"INSERT INTO {table} ({cols}) VALUES ({','.join('?' * len(row))})",
                                list(row.values()))
                    ok += 1
                    continue
                except sqlite3.IntegrityError as e:
                    err = f"db constraint: {e}"
            bad += 1
            rejects.append({"table": table, "csv_line": n, "reason": err,
                            **{k: v for k, v in row.items()}})
        summary.append({"table": table, "loaded": ok, "rejected": bad})
    tables = {t: pd.read_sql(f"SELECT * FROM {t}", con) for t in load.ORDER}
    adherence = pd.read_sql("SELECT * FROM v_adherence ORDER BY adherence_pct", con)
    per_condition = pd.read_sql(
        """SELECT c.name AS condition, COUNT(*) AS active_treatments FROM treatments t
           JOIN conditions c USING(condition_id) WHERE t.status='active'
           GROUP BY c.name ORDER BY 2 DESC""", con)
    con.close()
    return pd.DataFrame(summary), pd.DataFrame(rejects), tables, adherence, per_condition


st.title("🩺 Chronic-Care Database MVP")
st.caption("CSV in → validated relational database → data-quality report and adherence insights. "
           "Synthetic data only.")

with st.sidebar:
    st.header("Try your own data")
    st.write("Upload CSVs named like the tables (e.g. `patients.csv`, `treatments.csv`). "
             "Uploaded files replace the sample data for that table.")
    files = st.file_uploader("CSV files", type="csv", accept_multiple_files=True)
    uploads = tuple(sorted((Path(f.name).stem, f.getvalue()) for f in files
                           if Path(f.name).stem in load.ORDER))
    skipped = [f.name for f in files if Path(f.name).stem not in load.ORDER]
    if skipped:
        st.warning(f"Ignored (unknown table name): {', '.join(skipped)}")
    st.divider()
    st.markdown("**Tables:** " + ", ".join(load.ORDER))

summary, rejects, tables, adherence, per_condition = build_db(uploads)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Patients loaded", int(summary.set_index("table").loc["patients", "loaded"]))
c2.metric("Active treatments", int(per_condition["active_treatments"].sum()) if len(per_condition) else 0)
c3.metric("Rows rejected", int(summary["rejected"].sum()))
low = adherence[adherence["adherence_pct"] < 75] if len(adherence) else adherence
c4.metric("Low adherence (<75%)", len(low))

tab1, tab2, tab3, tab4 = st.tabs(["Data quality", "Adherence", "Treatments by condition", "Browse tables"])

with tab1:
    st.subheader("Import summary")
    st.dataframe(summary, hide_index=True, width="stretch")
    st.subheader("Rejected rows")
    if rejects.empty:
        st.success("All rows passed validation.")
    else:
        st.caption("Invalid rows are never loaded. Each one is kept with the line number and the reason.")
        st.dataframe(rejects, hide_index=True, width="stretch")
        st.download_button("Download rejects.csv", rejects.to_csv(index=False), "rejects.csv", "text/csv")
    with st.expander("Integrity rules enforced"):
        st.markdown(
            "- **Row validation:** dates are real `YYYY-MM-DD`, sex is F/M/O, valid email, names required, "
            "end date not before start date\n"
            "- **Database constraints:** primary and foreign keys, unique email, unique medication + strength, "
            "allowed forms/statuses, dose frequency 1-12/day\n"
            "- **Result:** bad data is quarantined, never silently loaded")

with tab2:
    if adherence.empty:
        st.info("No dose logs loaded.")
    else:
        adherence["label"] = adherence["patient"] + " - " + adherence["medication"]
        st.bar_chart(adherence.set_index("label")["adherence_pct"], y_label="Adherence %")
        shown = adherence[["patient", "medication", "condition", "doses_taken",
                           "doses_expected", "adherence_pct"]].copy()
        shown["follow_up"] = shown["adherence_pct"].apply(lambda v: "⚠️ follow up" if v < 75 else "")
        st.dataframe(shown, hide_index=True, width="stretch")

with tab3:
    st.bar_chart(per_condition.set_index("condition")["active_treatments"])

with tab4:
    name = st.selectbox("Table", load.ORDER)
    st.dataframe(tables[name], hide_index=True, width="stretch")
    st.download_button(f"Download {name}.csv", tables[name].to_csv(index=False), f"{name}.csv", "text/csv")

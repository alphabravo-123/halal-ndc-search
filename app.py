import sqlite3
import streamlit as st
import pandas as pd
import datetime

DB_PATH = "halal_ndc.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ndc TEXT NOT NULL UNIQUE,
        proprietary_name TEXT,
        nonproprietary_name TEXT,
        labeler_name TEXT,
        dosage_form TEXT,
        route TEXT,
        marketing_status TEXT,
        package_description TEXT,
        last_updated TEXT
    );
    CREATE TABLE IF NOT EXISTS halal_info (
        product_id INTEGER NOT NULL UNIQUE,
        halal_status TEXT DEFAULT 'Unknown',
        ethanol_pct REAL,
        gelatin_source TEXT,
        glycerin_source TEXT,
        stearate_source TEXT,
        shellac INTEGER DEFAULT 0,
        notes TEXT,
        evidence_url TEXT,
        reviewed_by TEXT,
        reviewed_on TEXT,
        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
    );
    """)
    conn.commit()

def upsert_product(prod):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO products (ndc, proprietary_name, nonproprietary_name, labeler_name,
            dosage_form, route, marketing_status, package_description, last_updated)
        VALUES (:ndc, :proprietary_name, :nonproprietary_name, :labeler_name, :dosage_form,
            :route, :marketing_status, :package_description, :last_updated)
        ON CONFLICT(ndc) DO UPDATE SET
            proprietary_name=excluded.proprietary_name,
            nonproprietary_name=excluded.nonproprietary_name,
            labeler_name=excluded.labeler_name,
            dosage_form=excluded.dosage_form,
            route=excluded.route,
            marketing_status=excluded.marketing_status,
            package_description=excluded.package_description,
            last_updated=excluded.last_updated
    """, prod)
    conn.commit()
    cur.execute("SELECT id FROM products WHERE ndc=?", (prod["ndc"],))
    return cur.fetchone()["id"]

def upsert_halal(product_id, halal):
    conn = get_conn()
    cur = conn.cursor()
    halal["product_id"] = product_id
    cur.execute("""
        INSERT INTO halal_info (product_id, halal_status, ethanol_pct, gelatin_source,
            glycerin_source, stearate_source, shellac, notes, evidence_url,
            reviewed_by, reviewed_on)
        VALUES (:product_id, :halal_status, :ethanol_pct, :gelatin_source,
            :glycerin_source, :stearate_source, :shellac, :notes, :evidence_url,
            :reviewed_by, :reviewed_on)
        ON CONFLICT(product_id) DO UPDATE SET
            halal_status=excluded.halal_status,
            ethanol_pct=excluded.ethanol_pct,
            gelatin_source=excluded.gelatin_source,
            glycerin_source=excluded.glycerin_source,
            stearate_source=excluded.stearate_source,
            shellac=excluded.shellac,
            notes=excluded.notes,
            evidence_url=excluded.evidence_url,
            reviewed_by=excluded.reviewed_by,
            reviewed_on=excluded.reviewed_on
    """, halal)
    conn.commit()

def search(query: str) -> pd.DataFrame:
    sql = """
        SELECT p.ndc, p.proprietary_name, p.nonproprietary_name, p.labeler_name,
               p.dosage_form, p.route, p.marketing_status,
               h.halal_status, h.ethanol_pct, h.gelatin_source, h.notes
        FROM products p
        LEFT JOIN halal_info h ON p.id = h.product_id
        WHERE p.ndc LIKE :q OR p.proprietary_name LIKE :q OR p.nonproprietary_name LIKE :q
        ORDER BY p.proprietary_name LIMIT 500
    """
    return pd.read_sql_query(sql, get_conn(), params={"q": f"%{query}%"})

st.set_page_config(page_title="NDC Halal Search", page_icon="🕌", layout="wide")
st.title("🕌 NDC Halal Search")

init_db()

with st.expander("📥 Upload CSV Data"):
    st.caption("Upload CSV with columns: ndc, proprietary_name, nonproprietary_name, labeler_name, dosage_form, route, marketing_status, package_description, halal_status, ethanol_pct, gelatin_source, notes, reviewed_by")
    uploaded = st.file_uploader("Choose a CSV file", type=["csv"])
    if uploaded:
        df = pd.read_csv(uploaded)
        st.dataframe(df.head(), use_container_width=True)
        if st.button("Import to Database"):
            count = 0
            for _, row in df.iterrows():
                if not str(row.get("ndc", "")).strip():
                    continue
                prod = dict(
                    ndc=str(row["ndc"]),
                    proprietary_name=row.get("proprietary_name"),
                    nonproprietary_name=row.get("nonproprietary_name"),
                    labeler_name=row.get("labeler_name"),
                    dosage_form=row.get("dosage_form"),
                    route=row.get("route"),
                    marketing_status=row.get("marketing_status"),
                    package_description=row.get("package_description"),
                    last_updated=datetime.datetime.utcnow().isoformat()
                )
                pid = upsert_product(prod)
                halal = dict(
                    halal_status=row.get("halal_status", "Unknown"),
                    ethanol_pct=float(row["ethanol_pct"]) if not pd.isna(row.get("ethanol_pct")) else None,
                    gelatin_source=row.get("gelatin_source"),
                    glycerin_source=row.get("glycerin_source"),
                    stearate_source=row.get("stearate_source"),
                    shellac=int(row.get("shellac", 0)) if not pd.isna(row.get("shellac", 0)) else 0,
                    notes=row.get("notes"),
                    evidence_url=row.get("evidence_url"),
                    reviewed_by=row.get("reviewed_by"),
                    reviewed_on=datetime.datetime.utcnow().date().isoformat()
                )
                upsert_halal(pid, halal)
                count += 1
            st.success(f"Imported {count} rows ✅")

query = st.text_input("🔎 Search NDC, Brand, or Generic:")
if query:
    results = search(query)
    st.write(f"Found {len(results)} result(s)")
    st.dataframe(results, use_container_width=True)
    st.download_button("⬇️ Download CSV", results.to_csv(index=False).encode("utf-8"), "results.csv", "text/csv")
else:
    st.info("Enter a search term to begin.")

st.markdown("---\n⚠️ **Disclaimer:** Informational only. Not medical or religious advice.")

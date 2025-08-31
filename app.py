
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

query = st.text_input("Search NDC, Brand, or Generic:")
if query:
    results = search(query)
    st.write(f"Found {len(results)} result(s)")
    st.dataframe(results, use_container_width=True)
    st.download_button("⬇️ Download CSV", results.to_csv(index=False).encode('utf-8'), "results.csv", "text/csv")
else:
    st.info("Enter a search term to begin.")

st.markdown("---\n⚠️ **Disclaimer:** Informational only. Not medical or religious advice.")

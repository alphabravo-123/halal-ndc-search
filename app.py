
import streamlit as st
import requests, sqlite3, pandas as pd
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
from datetime import datetime

DAILYMED_BASE = "https://dailymed.nlm.nih.gov/dailymed/services/v2"

st.set_page_config(page_title="DailyMed Ingredients + Halal", page_icon="💊", layout="wide")
st.title("💊 DailyMed Ingredients + Halal")

# --- DB ---
DB = "halal_tags.db"
def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            setid TEXT PRIMARY KEY,
            status TEXT CHECK(status IN ('Halal','Non-Halal','Unknown')) DEFAULT 'Unknown',
            notes TEXT,
            updated_at TEXT
        )
    """)
    conn.commit(); conn.close()

def get_tag(setid):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT status,notes FROM tags WHERE setid=?", (setid,))
    row = cur.fetchone(); conn.close()
    return row if row else ("Unknown", "")

def set_tag(setid,status,notes=""):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO tags (setid,status,notes,updated_at) VALUES (?,?,?,?)",
                (setid,status,notes,datetime.utcnow().isoformat()))
    conn.commit(); conn.close()

# --- DailyMed API ---
def search_spls_by_name(name, page=1, pagesize=25):
    params = {"drug_name": name, "name_type": "both", "pagesize": pagesize, "page": page}
    url = f"{DAILYMED_BASE}/spls.json?{urlencode(params)}"
    r = requests.get(url,timeout=30); r.raise_for_status()
    return r.json()

def search_spl_by_ndc(ndc):
    url = f"{DAILYMED_BASE}/ndcs/{ndc}.json"
    r = requests.get(url,timeout=30)
    if r.status_code!=200: return None
    return r.json()

def fetch_spl_xml(setid):
    url = f"{DAILYMED_BASE}/spls/{setid}.xml"
    r = requests.get(url,timeout=60); r.raise_for_status()
    return ET.fromstring(r.content)

def _ns(tag): return f"{{urn:hl7-org:v3}}{tag}"

def _iter_sections(root):
    for comp in root.findall(f".//{_ns('component')}"):
        sec = comp.find(f".//{_ns('section')}")
        if sec is None: continue
        code = sec.find(f"{_ns('code')}")
        title_el = sec.find(f"{_ns('title')}")
        display = code.get("displayName") if code is not None else (title_el.text if title_el is not None else "")
        yield display.strip().upper() if display else "" , sec

def _extract_items(sec):
    items=[]
    for li in sec.findall(f".//{_ns('list')}/{_ns('item')}"):
        texts=[p.text.strip() for p in li.findall(f".//{_ns('paragraph')}") if p.text]
        if texts: items.append(" ".join(texts))
    if not items:
        for p in sec.findall(f".//{_ns('paragraph')}"):
            if p.text and p.text.strip(): items.append(p.text.strip())
    seen=set(); cleaned=[]
    for t in items:
        t2=" ".join(t.split())
        if t2 and t2 not in seen:
            seen.add(t2); cleaned.append(t2)
    return cleaned

def get_ingredients(setid):
    root = fetch_spl_xml(setid)
    active,inactive=[],[]
    for title,sec in _iter_sections(root):
        t=title.replace("INGREDIENTS","INGREDIENT").strip()
        if t=="ACTIVE INGREDIENT": active=_extract_items(sec)
        elif t=="INACTIVE INGREDIENT": inactive=_extract_items(sec)
    return active,inactive

# --- UI ---
init_db()
with st.sidebar:
    st.header("Search")
    mode = st.radio("Search by", ["Drug Name","NDC"])
    q = st.text_input("Enter query")
    pagesize = st.selectbox("Results per page", [10,25,50], index=1)
    if "page" not in st.session_state: st.session_state.page=1
    if st.button("Search",type="primary"): st.session_state.page=1

results=[]
if q:
    try:
        if mode=="Drug Name":
            data=search_spls_by_name(q, page=st.session_state.page, pagesize=pagesize)
            results=data.get("data",[])
        else:
            data=search_spl_by_ndc(q)
            if data: results=data.get("data",[])
        if results:
            df=pd.DataFrame([{"Title":r.get("title"),"SetID":r.get("setid")} for r in results])
            st.dataframe(df, use_container_width=True, hide_index=True)
            idx=st.selectbox("Pick a label", list(range(len(results))), format_func=lambda i: results[i].get("title",""))
            setid=results[idx]["setid"]
            active,inactive=get_ingredients(setid)
            status,notes=get_tag(setid)
            st.subheader("Ingredients")
            col1,col2=st.columns(2)
            with col1:
                st.markdown("**Active**")
                for a in active: st.write("- "+a)
            with col2:
                st.markdown("**Inactive**")
                for i in inactive: st.write("- "+i)
            st.markdown(f"**Halal status:** {status}")
            # CSV Export
            df_out=pd.DataFrame([{"Title":results[idx].get("title"),
                                  "SetID":setid,
                                  "Active":"; ".join(active),
                                  "Inactive":"; ".join(inactive),
                                  "Halal Status":status}])
            st.download_button("Download CSV", df_out.to_csv(index=False).encode("utf-8"), "result.csv","text/csv")
            # Admin
            with st.expander("Admin panel"):
                pw=st.text_input("Password", type="password")
                if pw and "admin_password" in st.secrets and pw==st.secrets["admin_password"]:
                    new_status=st.selectbox("Set halal status",["Halal","Non-Halal","Unknown"], index=["Halal","Non-Halal","Unknown"].index(status if status in ["Halal","Non-Halal"] else "Unknown"))
                    new_notes=st.text_area("Notes",notes)
                    if st.button("Update"):
                        set_tag(setid,new_status,new_notes)
                        st.success("Updated")
    except Exception as e:
        st.error(str(e))
else:
    st.info("Enter a query in the sidebar.")

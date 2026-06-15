import os
import json
import sqlite3
import pandas as pd
import streamlit as st

# --- CONFIGURATION ---
DB_PATH = os.getenv("DB_PATH", "/app/data/fde_platform.db")

st.set_page_config(
    page_title="Multi-Tenant AI Control Plane",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- THEME INJECTION & STYLING ---
st.markdown("""
    <style>
        .stApp { background-color: #0b0c10; color: #c5c6c7; }
        [data-testid="stSidebar"] { background-color: #1f2833 !important; border-right: 1px solid #45a29e; }
        h1, h2, h3 { color: #66fcf1 !important; font-family: 'Courier New', Courier, monospace; }
        
        /* Custom KPI Cards to avoid iframe/module import errors */
        .kpi-container { display: flex; gap: 1rem; margin-bottom: 1.5rem; width: 100%; }
        .kpi-card { flex: 1; background-color: #1f2833; border: 1px solid #45a29e; padding: 1.2rem; border-radius: 0.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        .kpi-label { color: #a8b2bd; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05rem; }
        .kpi-value { color: #66fcf1; font-size: 1.8rem; font-weight: 700; margin-top: 0.25rem; }
        
        /* Scratchpad styling */
        .scratchpad { background-color: #0f141c; border-left: 4px solid #45a29e; padding: 1rem; border-radius: 0.25rem; margin: 1rem 0; }
        .scratchpad-header { color: #66fcf1; font-size: 0.85rem; text-transform: uppercase; margin-bottom: 0.5rem; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("🌐 Multi-Tenant Research Operational Control Plane")
st.caption("Synchronized GitOps Core Engine — Active AI Agent Monitoring")

# --- DATA LAYER ---
@st.cache_data(ttl=5)
def load_data():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query("SELECT * FROM tenant_research_leads ORDER BY extracted_at DESC", conn)
    except Exception:
        return pd.DataFrame()

df = load_data()

# --- SIDEBAR & FILTERING ---
if st.sidebar.button("🔄 Refresh Intelligence Pipeline"):
    st.rerun()

if df.empty:
    st.warning("⚠️ No synchronized intelligence logs detected in fde_platform.db. Run the worker node to seed initial pipeline payloads.")
else:
    st.sidebar.markdown("---")
    st.sidebar.header("🛠️ Operational Nav Filters")
    
    # Dynamically extract available tenants strictly from the database
    db_tenants = df['company_name'].dropna().unique().tolist()
    selected_target = st.sidebar.selectbox("Target Portfolio Company", ["System-Wide Data"] + db_tenants)
    
    view_df = df if selected_target == "System-Wide Data" else df[df['company_name'] == selected_target]

    # --- KPI DASHBOARD ---
    total_tenants = len(df['tenant_id'].dropna().unique())
    total_records = len(view_df)
    pending_reviews = len(view_df[view_df['deadline_or_milestone'].str.contains('Review', na=False, case=False)])

    st.markdown(f"""
        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-label">Monitored Portfolio Fleets</div>
                <div class="kpi-value">{total_tenants}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Synchronized Records</div>
                <div class="kpi-value">{total_records}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Active Review Targets</div>
                <div class="kpi-value">{pending_reviews}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader(f"📋 Live Intelligence Matrix: {selected_target}")

    # --- MAIN CONTENT STREAM ---
    for _, row in view_df.iterrows():
        with st.container(border=True):
            header_col, meta_col = st.columns([3, 1])
            
            with header_col:
                st.markdown(f"### 🎯 {row.get('lead_name', 'Unknown Opportunity')}")
                st.markdown(f"**Tenant Domain ID:** `{row.get('tenant_id', 'N/A')}` | **Asset Topic:** *{row.get('research_topic', 'N/A')}*")
            
            with meta_col:
                st.markdown(f"""
                    <div style="background-color: #1f2833; padding: 0.75rem; border-radius: 0.25rem; border: 1px solid #45a29e; text-align: center;">
                        <div style="font-size: 0.65rem; color: #a8b2bd; text-transform: uppercase;">Value Projection</div>
                        <div style="font-size: 1.2rem; color: #66fcf1; font-weight: bold;">{row.get('estimated_value', 'Under Evaluation')}</div>
                    </div>
                    <div style="margin-top: 0.5rem; font-size: 0.85rem; color: #66fcf1; text-align: center; font-weight: bold;">
                        ⏱️ {row.get('deadline_or_milestone', 'Pending')}
                    </div>
                """, unsafe_allow_html=True)

            st.markdown(f"**Strategic Executive Summary:** {row.get('summary', 'No summary provided.')}")
            
            # Formatted LLM Scratchpad Integration
            st.markdown(f"""
                <div class="scratchpad">
                    <div class="scratchpad-header">💡 LLM Live Scratchpad — Non-Profit Core Alignment Analysis</div>
                    <div style="font-size: 0.95rem; line-height: 1.5; color: #c5c6c7;">{row.get('actionable_plan', 'Awaiting alignment analysis.')}</div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.expander("🔍 Examine Raw Natural Tavily Payload"):
                st.caption(f"Payload Sync Timestamp: {row.get('extracted_at', 'Unknown Time')}")
                raw_payload = row.get('raw_payload', '{}')
                try:
                    st.json(json.loads(raw_payload))
                except Exception:
                    st.code(raw_payload, language='json')

import os
import sqlite3
import pandas as pd
import streamlit as st

# Path configuration matches worker.py exactly
DB_PATH = os.getenv("DB_PATH", "/app/data/fde_platform.db")

st.set_page_config(
    page_title="Multi-Tenant AI Control Plane",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Theme Injection
st.markdown("""
    <style>
        .stApp { background-color: #0b0c10; color: #c5c6c7; }
        [data-testid="stSidebar"] { background-color: #1f2833 !important; border-right: 1px solid #45a29e; }
        div.stMetric { background-color: #1f2833; border: 1px solid #45a29e; padding: 12px; border-radius: 6px; }
        h1, h2, h3 { color: #66fcf1 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🌐 Multi-Tenant Research Operational Control Plane")
st.caption("Synchronized GitOps Core Engine — Active AI Agent Monitoring")

# Helper to pull the latest data
@st.cache_data(ttl=10) # Cache for 10 seconds for performance
def load_platform_data():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB_PATH)
        query = "SELECT * FROM tenant_research_leads ORDER BY extracted_at DESC"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return pd.DataFrame()

# Main Logic
data_frame = load_platform_data()

# Refresh Control
if st.sidebar.button("🔄 Refresh Intelligence Data"):
    st.rerun()

if data_frame.empty:
    st.warning("⚠️ No records detected. The agent may still be in its initial 'thinking' or 'searching' phase. Check the pod logs.")
else:
    # Sidebar Filters
    available_tenants = data_frame['company_name'].unique()
    st.sidebar.header("🛠️ Tenant Navigation Filters")
    selected_filter = st.sidebar.selectbox("Choose Target Portfolio Company", ["View System-Wide Data"] + list(available_tenants))
    
    filtered_df = data_frame if selected_filter == "View System-Wide Data" else data_frame[data_frame['company_name'] == selected_filter]

    # Metrics
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    col_kpi1.metric("Active Tenant Fleets", len(data_frame['tenant_id'].unique()))
    col_kpi2.metric("Total Intelligence Records", len(filtered_df))
    # Count leads where estimated_value is NOT "Unknown"
    financial_leads = filtered_df[filtered_df['estimated_value'] != 'Unknown']
    col_kpi3.metric("Qualified Opportunities", len(financial_leads))

    st.markdown("---")
    st.subheader(f"📋 Found Leads: {selected_filter}")

    # Render Cards
    for index, row in filtered_df.iterrows():
        with st.container(border=True):
            header_col, meta_col = st.columns([3, 1])
            with header_col:
                st.markdown(f"### 🎯 {row['lead_name']}")
                st.markdown(f"**Tenant ID:** `{row['tenant_id']}` | **Company:** *{row['company_name']}*")
                st.markdown(f"**Topic:** {row['research_topic']}")
            with meta_col:
                st.metric("Value Projection", row['estimated_value'])
                st.caption(f"📅 **Deadline:** {row['deadline_or_milestone']}")

            st.write(f"**Executive Synthesis:** {row['summary']}")
            st.write(f"**Action Plan:** {row['actionable_plan']}")
            
            with st.expander("🔍 Examine Raw Intelligence Payload Stream"):
                st.code(row['raw_payload'], language='text')
                st.caption(f"Data Captured: {row['extracted_at']}")

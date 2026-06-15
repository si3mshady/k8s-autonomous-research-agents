import os
import sqlite3
import pandas as pd
import streamlit as st

# Path configuration maps perfectly to the worker environment
DB_PATH = os.getenv("DB_PATH", "/app/data/fde_platform.db")

st.set_page_config(
    page_title="Multi-Tenant AI Intelligence Control Plane",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Theme Injection for High-Contrast Dark Interface
st.markdown("""
    <style>
        .stApp { background-color: #0b0c10; color: #c5c6c7; }
        [data-testid="stSidebar"] { background-color: #1f2833 !important; border-right: 1px solid #45a29e; }
        div.stMetric { background-color: #1f2833; border: 1px solid #45a29e; padding: 12px; border-radius: 6px; }
        h1, h2, h3 { color: #66fcf1 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🌐 Multi-Tenant Research Operational Control Plane")
st.caption("Synchronized GitOps Core Engine — Active AI Agent Monitoring Dashboard")

def load_platform_data():
    try:
        conn = sqlite3.connect(DB_PATH)
        query = "SELECT * FROM tenant_research_leads ORDER BY extracted_at DESC"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception:
        # Return empty dataframe gracefully if database is initializing or locked
        return pd.DataFrame()

data_frame = load_platform_data()

if data_frame.empty:
    st.warning("⚠️ No records detected. Ensure your research agents have initiated their primary execution loops and mounted the SQLite storage correctly.")
else:
    # Build dynamic multi-tenant selection matrix based on entries pushed from values.yaml
    available_tenants = data_frame['company_name'].unique()
    
    st.sidebar.header("🛠️ Tenant Navigation Filters")
    selected_filter = st.sidebar.selectbox("Choose Target Portfolio Company", ["View System-Wide Data"] + list(available_tenants))
    
    # Isolate DataFrame records based on selection criteria
    if selected_filter != "View System-Wide Data":
        filtered_df = data_frame[data_frame['company_name'] == selected_filter]
    else:
        filtered_df = data_frame

    # Global KPI Metrics Pane
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    with col_kpi1:
        st.metric("Active Tenant Fleets", len(data_frame['tenant_id'].unique()))
    with col_kpi2:
        st.metric("Total Intelligence Records", len(filtered_df))
    with col_kpi3:
        # Isolate entries containing active values
        financial_leads = filtered_df[filtered_df['estimated_value'] != 'Unknown']
        st.metric("Monitored High-Value Leads", len(financial_leads))

    st.markdown("---")
    st.subheader(f"📋 Found Leads: {selected_filter}")

    # Render data cards gracefully
    for index, row in filtered_df.iterrows():
        with st.container(border=True):
            header_col, meta_col = st.columns([3, 1])
            with header_col:
                st.markdown(f"### 🎯 {row['lead_name']}")
                st.markdown(f"**Tenant Profile:** `{row['tenant_id']}` | **Company:** *{row['company_name']}*")
                st.markdown(f"**Active Objective Topic:** {row['research_topic']}")
            with meta_col:
                st.metric("Value Projection", row['estimated_value'])
                st.caption(f"📅 **Deadline Target:** {row['deadline_or_milestone']}")

            st.write(f"**Executive Synthesis:** {row['summary']}")
            st.write(f"**Action Plan / Next Steps:** {row['actionable_plan']}")
            
            # Expandable trace block for raw logs/payload validation
            with st.expander("🔍 Examine Raw Intelligence Payload Stream"):
                st.code(row['raw_payload'], language='text')
                st.caption(f"Data Captured At: {row['extracted_at']}")

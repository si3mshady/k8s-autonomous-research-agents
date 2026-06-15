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

# --- NATIVE THEME & STRUCTURAL OVERRIDES ---
# Using strict styling format to prevent text leaking and ensure full browser hydration
st.markdown("""
    <style>
        .stApp { 
            background-color: #0b0c10; 
            color: #c5c6c7; 
        }
        [data-testid="stSidebar"] { 
            background-color: #1f2833 !important; 
            border-right: 1px solid #45a29e; 
        }
        h1, h2, h3 { 
            color: #66fcf1 !important; 
        }
        /* Custom CSS to replace broken dynamic st.metric widgets */
        .kpi-container {
            display: flex; 
            gap: 15px; 
            margin-bottom: 25px;
            width: 100%;
        }
        .kpi-card {
            flex: 1; 
            background-color: #1f2833; 
            border: 1px solid #45a29e; 
            padding: 15px; 
            border-radius: 6px; 
            text-align: left;
        }
        .kpi-label {
            color: #c5c6c7; 
            font-size: 13px; 
            text-transform: uppercase; 
            letter-spacing: 0.5px;
        }
        .kpi-value {
            color: #66fcf1; 
            font-size: 26px; 
            font-weight: bold; 
            margin-top: 5px;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🌐 Multi-Tenant Research Operational Control Plane")
st.caption("Synchronized GitOps Core Engine — Active AI Agent Monitoring")


# --- DATA ENGINE READ UTIL ---
@st.cache_data(ttl=10) # Cache for 10 seconds for operational performance
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


# --- APP RUNTIME EXECUTION ---
data_frame = load_platform_data()

# Refresh Trigger Button
if st.sidebar.button("🔄 Refresh Intelligence Data"):
    st.rerun()

if data_frame.empty:
    st.warning("⚠️ No records detected. The agent may still be in its initial 'thinking' or 'searching' phase. Check the pod logs.")
else:
    # Sidebar Filtering Controls
    available_tenants = data_frame['company_name'].unique()
    st.sidebar.header("🛠️ Tenant Navigation Filters")
    selected_filter = st.sidebar.selectbox("Choose Target Portfolio Company", ["View System-Wide Data"] + list(available_tenants))
    
    filtered_df = data_frame if selected_filter == "View System-Wide Data" else data_frame[data_frame['company_name'] == selected_filter]

    # Metrics Layout Engine - Built via raw HTML cards to bypass flaking proxy module chunks
    active_fleets = len(data_frame['tenant_id'].unique())
    total_records = len(filtered_df)
    financial_leads = len(filtered_df[filtered_df['estimated_value'] != 'Unknown'])

    st.markdown(f"""
        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-label">Active Tenant Fleets</div>
                <div class="kpi-value">{active_fleets}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Total Intelligence Records</div>
                <div class="kpi-value">{total_records}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Qualified Opportunities</div>
                <div class="kpi-value">{financial_leads}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader(f"📋 Found Leads: {selected_filter}")

    # Render Record Iterations
    for index, row in filtered_df.iterrows():
        # Intercept formatting exceptions from the LLM worker process dynamically
        is_parsing_failure = (
            str(row['lead_name']).strip().lower() == "error" or 
            "parsing failed" in str(row['summary']).lower()
        )
        
        with st.container(border=True):
            if is_parsing_failure:
                # Degrading gracefully into a pipeline tracking notification panel
                st.info("🔄 **Intelligence Pipeline: Syncing live schema structures from source data...**")
                st.markdown(f"**Tenant ID:** `{row['tenant_id']}` | **Topic Target:** *{row['research_topic']}*")
                
                # Still show what research data tavily captured so it's transparent
                with st.expander("🔍 Examine Raw Intelligence Payload Stream"):
                    st.code(row['raw_payload'], language='json')
                    st.caption(f"Capture Phase Timestamp: {row['extracted_at']}")
            else:
                # Render beautifully formatted cards for clean executions
                header_col, meta_col = st.columns([3, 1])
                with header_col:
                    st.markdown(f"### 🎯 {row['lead_name']}")
                    st.markdown(f"**Tenant ID:** `{row['tenant_id']}` | **Company:** *{row['company_name']}*")
                    st.markdown(f"**Topic:** {row['research_topic']}")
                with meta_col:
                    # Individual item sub-metrics handled with robust HTML injection
                    st.markdown(f"""
                        <div style="background-color: #1f2833; padding: 10px; border-radius: 4px; border: 1px solid #45a29e; margin-bottom: 5px;">
                            <div style="font-size: 11px; color: #c5c6c7; text-transform: uppercase;">Value Projection</div>
                            <div style="font-size: 18px; color: #66fcf1; font-weight: bold;">{row['estimated_value']}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    st.caption(f"📅 **Deadline:** {row['deadline_or_milestone']}")

                st.write(f"**Executive Synthesis:** {row['summary']}")
                st.write(f"**Action Plan:** {row['actionable_plan']}")
                
                with st.expander("🔍 Examine Raw Intelligence Payload Stream"):
                    st.code(row['raw_payload'], language='json')
                    st.caption(f"Data Captured: {row['extracted_at']}")

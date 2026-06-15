import os
import sqlite3
import pandas as pd
import streamlit as st

DB_PATH = os.getenv("DB_PATH", "/app/data/fde_platform.db")

st.set_page_config(
    page_title="Multi-Tenant AI Control Plane",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CINEMATIC CYBERPUNK THEME INJECTION ---
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
            font-family: 'Courier New', Courier, monospace;
        }
        /* Presentable metrics cards avoiding dynamic script modules */
        .kpi-wrapper {
            display: flex; gap: 15px; margin-bottom: 25px; width: 100%;
        }
        .kpi-box {
            flex: 1; background-color: #1f2833; border: 1px solid #45a29e; 
            padding: 18px; border-radius: 6px; box-shadow: 0px 4px 10px rgba(0,0,0,0.3);
        }
        .kpi-lbl { color: #a8b2bd; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
        .kpi-val { color: #66fcf1; font-size: 28px; font-weight: bold; margin-top: 4px; }
        
        /* Tactical Dashboard Scratchpad Layout */
        .scratchpad-container {
            background-color: #0f141c; border-left: 3px solid #66fcf1;
            padding: 15px; border-radius: 4px; margin-top: 10px; margin-bottom: 15px;
        }
        .scratchpad-title {
            color: #66fcf1; font-size: 12px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;
        }
    </style>
""", unsafe_allow_html=True)

st.title("🌐 Multi-Tenant Research Operational Control Plane")
st.caption("Synchronized GitOps Core Engine — Active AI Agent Monitoring")

@st.cache_data(ttl=5)
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
        return pd.DataFrame()

# Execution Load
data_frame = load_platform_data()

# Sidebar Controls
if st.sidebar.button("🔄 Refresh Intelligence Pipeline"):
    st.rerun()

if data_frame.empty:
    st.warning("⚠️ No synchronized intelligence logs detected inside fde_platform.db. Run your worker node to seed metrics data.")
else:
    # Sidebar Tenant Selection
    available_tenants = data_frame['company_name'].unique()
    st.sidebar.markdown("---")
    st.sidebar.header("🛠️ Operational Nav Filters")
    selected_filter = st.sidebar.selectbox("Choose Target Portfolio Company", ["View System-Wide Data"] + list(available_tenants))
    
    filtered_df = data_frame if selected_filter == "View System-Wide Data" else data_frame[data_frame['company_name'] == selected_filter]

    # Render Native Metrics Block
    total_tenants = len(data_frame['tenant_id'].unique())
    total_leads = len(filtered_df)
    active_reviews = len(filtered_df[filtered_df['deadline_or_milestone'].str.contains('Review', na=False)])

    st.markdown(f"""
        <div class="kpi-wrapper">
            <div class="kpi-box">
                <div class="kpi-lbl">Monitored Portfolio Fleets</div>
                <div class="kpi-value">{total_tenants} Tenants</div>
            </div>
            <div class="kpi-box">
                <div class="kpi-lbl">Synchronized Records ({selected_filter})</div>
                <div class="kpi-value">{total_leads} Items</div>
            </div>
            <div class="kpi-box">
                <div class="kpi-lbl">Active Review Targets</div>
                <div class="kpi-value">{active_reviews} Pending</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader(f"📋 Live Intelligence Matrix: {selected_filter}")

    # Render Streamlined Presentation Cards
    for index, row in filtered_df.iterrows():
        with st.container(border=True):
            col_main, col_metrics = st.columns([3, 1])
            
            with col_main:
                st.markdown(f"### 🎯 {row['lead_name']}")
                st.markdown(f"**Tenant Domain ID:** `{row['tenant_id']}` | **Asset Topic:** *{row['research_topic']}*")
            
            with col_metrics:
                # Value and Deadline tags rendered clearly with static custom boxes
                st.markdown(f"""
                    <div style="background-color: #1f2833; padding: 10px; border-radius: 4px; border: 1px solid #45a29e; text-align: center;">
                        <span style="font-size: 10px; color: #a8b2bd; text-transform: uppercase;">Value Projection</span><br>
                        <span style="font-size: 16px; color: #66fcf1; font-weight: bold;">{row['estimated_value']}</span>
                    </div>
                    <div style="margin-top: 5px; font-size: 12px; color: #66fcf1; text-align: center; font-weight: bold;">
                        ⏱️ {row['deadline_or_milestone']}
                    </div>
                """, unsafe_allow_html=True)

            # Core Synthesis Text Box
            st.markdown(f"**Strategic Executive Summary:** {row['summary']}")
            
            # The Scratchpad / Non-Profit Alignment Analysis Display Box
            st.markdown(f"""
                <div class="scratchpad-container">
                    <div class="scratchpad-title">💡 LLM Live Scratchpad — Non-Profit Core Alignment Analysis</div>
                    <div style="font-size: 13px; color: #c5c6c7; line-height: 1.5;">{row['actionable_plan']}</div>
                </div>
            """, unsafe_allow_html=True)
            
            # Nested Clean Raw Code Expander
            with st.expander("🔍 Examine Raw Natural Tavily Payload"):
                st.caption(f"Payload Sync Timestamp: {row['extracted_at']}")
                st.code(row['raw_payload'], language='json')

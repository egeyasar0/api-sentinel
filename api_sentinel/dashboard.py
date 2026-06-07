import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime

# Configure page settings
st.set_page_config(
    page_title="API Sentinel Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for premium dark/light mode blend
st.markdown("""
    <style>
    .main-title {
        font-size: 2.8rem;
        font-weight: 800;
        color: #1E88E5;
        margin-bottom: 0.1rem;
    }
    .subtitle {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #F8F9FA;
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: center;
        border-left: 5px solid #1E88E5;
    }
    .dark .metric-card {
        background-color: #1E1E1E;
        color: #FFF;
    }
    </style>
""", unsafe_allow_html=True)

DB_PATH = "api_sentinel.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Helper functions for database retrieval
def fetch_runs_df() -> pd.DataFrame:
    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query("SELECT * FROM test_runs ORDER BY id DESC", conn)
            # Parse datetime strings
            if not df.empty and "started_at" in df.columns:
                df["started_at_dt"] = pd.to_datetime(df["started_at"])
            return df
    except Exception as e:
        st.error(f"Error reading database: {e}")
        return pd.DataFrame()

def fetch_check_results(run_id: int) -> pd.DataFrame:
    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query(
                "SELECT * FROM check_results WHERE run_id = ?", 
                conn, 
                params=(run_id,)
            )
            return df
    except Exception as e:
        st.error(f"Error fetching check results: {e}")
        return pd.DataFrame()

# Sidebar Setup
st.sidebar.image("assets/logo.png", width=85)
st.sidebar.markdown("# API Sentinel")
st.sidebar.markdown("### Real-time API Health and Contract Monitor")
st.sidebar.divider()
st.sidebar.info(
    "API Sentinel is a developer tool that validates response statuses, "
    "evaluates response speeds, and checks JSON schemas to guarantee API health."
)

# Fetch current history
runs_df = fetch_runs_df()

if runs_df.empty:
    st.title("🛡️ API Sentinel Dashboard")
    st.warning("No test run history found in the SQLite database.")
    st.info("Please execute the test suite CLI first using: `python main.py run --config examples/api_checks.json`")
else:
    # ----------------------------------------------------
    # Header Section
    # ----------------------------------------------------
    st.markdown("<div class='main-title'>🛡️ API Sentinel</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>Continuous contract verification and health monitoring dashboard</div>", unsafe_allow_html=True)

    # ----------------------------------------------------
    # Top Summary Metrics Panel
    # ----------------------------------------------------
    col1, col2, col3, col4 = st.columns(4)
    
    total_runs = len(runs_df)
    
    # Calculate overall success rate across all checks ever run
    total_checks_run = runs_df["total_checks"].sum()
    total_checks_passed = runs_df["passed_checks"].sum()
    overall_success_rate = (total_checks_passed / total_checks_run * 100) if total_checks_run > 0 else 0.0
    
    avg_latency = runs_df["average_response_time_ms"].mean()
    
    latest_run_status = "Pass" if runs_df.iloc[0]["failed_checks"] == 0 else "Fail"
    
    with col1:
        st.metric(label="Total Runs Logged", value=total_runs)
    with col2:
        st.metric(
            label="Overall Check Success Rate", 
            value=f"{overall_success_rate:.1f}%",
            delta=f"{overall_success_rate - 90:.1f}% vs Target (90%)"
        )
    with col3:
        st.metric(
            label="Average Overall Latency", 
            value=f"{avg_latency:.1f} ms"
        )
    with col4:
        st.metric(
            label="Latest Execution Status", 
            value=latest_run_status,
            delta="ALL PASSED" if latest_run_status == "Pass" else "ERRORS DETECTED",
            delta_color="normal" if latest_run_status == "Pass" else "inverse"
        )
        
    st.divider()

    # ----------------------------------------------------
    # Main Dashboard Body
    # ----------------------------------------------------
    tab1, tab2 = st.tabs(["📊 Performance Metrics", "📂 Run Explorer"])

    with tab1:
        st.subheader("Latency Trend & Success Rates")
        
        # Sort values chronologically for plotting
        runs_chronological = runs_df.sort_values(by="id")
        
        # Dual columns for graphs
        g_col1, g_col2 = st.columns(2)
        
        with g_col1:
            st.markdown("**Average Latency (ms) Over Time**")
            chart_data = runs_chronological.copy()
            chart_data["Run Label"] = chart_data["id"].apply(lambda x: f"Run #{x}")
            
            # Draw line chart
            st.line_chart(
                data=chart_data, 
                x="Run Label", 
                y="average_response_time_ms"
            )
            
        with g_col2:
            st.markdown("**Checks Passed vs Failed**")
            # Bar chart of passed/failed checks
            bar_data = runs_chronological[["id", "passed_checks", "failed_checks"]].copy()
            bar_data = bar_data.rename(columns={
                "passed_checks": "Passed Checks",
                "failed_checks": "Failed Checks"
            })
            bar_data.set_index("id", inplace=True)
            st.bar_chart(bar_data)

    with tab2:
        st.subheader("Historical Test Runs")
        
        # Run selector
        selected_run_id = st.selectbox(
            "Select Run to Inspect",
            options=runs_df["id"].tolist(),
            format_func=lambda x: f"Run #{x} - {runs_df[runs_df['id'] == x]['project_name'].values[0]} ({runs_df[runs_df['id'] == x]['started_at'].values[0].replace('T', ' ').split('.')[0]})"
        )
        
        # Details of chosen run
        run_info = runs_df[runs_df["id"] == selected_run_id].iloc[0]
        
        # Small stats card for run details
        det_col1, det_col2, det_col3, det_col4 = st.columns(4)
        det_col1.write(f"**Project Name:** {run_info['project_name']}")
        det_col2.write(f"**Checks Run:** {run_info['total_checks']}")
        det_col3.write(f"**Passed/Failed:** {run_info['passed_checks']} / {run_info['failed_checks']}")
        det_col4.write(f"**Average Run Latency:** {run_info['average_response_time_ms']:.1f} ms")
        
        # Fetch check results
        checks_df = fetch_check_results(selected_run_id)
        
        if not checks_df.empty:
            # Map passed integer to emoji badge
            checks_df["Status"] = checks_df["passed"].apply(lambda x: "🟢 PASS" if x == 1 else "🔴 FAIL")
            
            # Select columns to display
            display_df = checks_df[[
                "check_name", "method", "url", "expected_status", 
                "actual_status", "response_time_ms", "Status", "error_message"
            ]].rename(columns={
                "check_name": "Check Name",
                "method": "HTTP Method",
                "url": "Target URL",
                "expected_status": "Expected Status",
                "actual_status": "Actual Status",
                "response_time_ms": "Latency (ms)",
                "error_message": "Error Message"
            })
            
            st.markdown("#### Execution Details")
            st.dataframe(
                display_df, 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.warning("No check details found for this run.")

# Refresh button
if st.button("🔄 Refresh Data"):
    st.rerun()

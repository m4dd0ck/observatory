"""Data Quality Observatory Dashboard - Main Streamlit Application."""

import sys
from pathlib import Path

import duckdb
import streamlit as st

# Page config must be first Streamlit command
st.set_page_config(
    page_title="Data Quality Observatory",
    page_icon="::telescope::",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_db_path() -> Path:
    """Get database path from args or default."""
    # Check command line args
    if "--db" in sys.argv:
        idx = sys.argv.index("--db")
        if idx + 1 < len(sys.argv):
            return Path(sys.argv[idx + 1])
    return Path("observatory.db")


@st.cache_resource
def get_db_connection():
    """Get cached database connection."""
    db_path = get_db_path()
    if not db_path.exists():
        return None
    return duckdb.connect(str(db_path), read_only=True)


def check_database():
    """Check if database exists and has data."""
    conn = get_db_connection()
    if conn is None:
        return False, "Database not found. Run some checks first."

    try:
        result = conn.execute("SELECT COUNT(*) FROM check_runs").fetchone()
        if result[0] == 0:
            return False, "No check runs found. Run some checks first."
        return True, None
    except Exception as e:
        return False, f"Database error: {e}"


def main():
    """Main dashboard application."""
    st.title("Data Quality Observatory")

    # Sidebar navigation
    page = st.sidebar.selectbox(
        "Navigate",
        ["Overview", "Trends", "Failures", "Coverage"],
        key="navigation",
    )

    # Check database
    db_ok, error_msg = check_database()

    if not db_ok:
        st.warning(error_msg)
        st.info(
            "Run data quality checks using the CLI:\n\n"
            "```bash\n"
            "observatory check examples/nyc_taxi/checks.yaml\n"
            "```"
        )
        return

    conn = get_db_connection()

    if page == "Overview":
        render_overview(conn)
    elif page == "Trends":
        render_trends(conn)
    elif page == "Failures":
        render_failures(conn)
    elif page == "Coverage":
        render_coverage(conn)


def render_overview(conn):
    """Render the overview page."""
    st.header("Quality Overview")

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    try:
        latest = conn.execute("""
            SELECT
                COUNT(DISTINCT suite_name) as suites,
                SUM(total_checks) as total_checks,
                SUM(passed_checks) as passed,
                SUM(failed_checks) as failed
            FROM check_runs
            WHERE started_at > NOW() - INTERVAL '24 hours'
        """).fetchone()

        col1.metric("Active Suites", latest[0] or 0)
        col2.metric("Checks Run (24h)", f"{latest[1] or 0:,}")
        col3.metric("Passed", f"{latest[2] or 0:,}")
        col4.metric("Failed", f"{latest[3] or 0:,}")
    except Exception:
        col1.metric("Active Suites", 0)
        col2.metric("Checks Run (24h)", 0)
        col3.metric("Passed", 0)
        col4.metric("Failed", 0)

    # Recent runs
    st.subheader("Recent Runs")

    try:
        runs_df = conn.execute("""
            SELECT
                suite_name as "Suite",
                overall_status as "Status",
                passed_checks as "Passed",
                failed_checks as "Failed",
                ROUND(duration_seconds, 2) as "Duration (s)",
                started_at as "Started At"
            FROM check_runs
            ORDER BY started_at DESC
            LIMIT 10
        """).df()

        if not runs_df.empty:
            st.dataframe(runs_df, use_container_width=True, hide_index=True)
        else:
            st.info("No runs found.")
    except Exception as e:
        st.error(f"Error loading runs: {e}")

    # Health by suite (last 7 days)
    st.subheader("Suite Health (Last 7 Days)")

    try:
        import plotly.express as px

        health_data = conn.execute("""
            SELECT
                suite_name,
                DATE_TRUNC('day', started_at) as day,
                AVG(CASE overall_status
                    WHEN 'passed' THEN 1.0
                    WHEN 'warning' THEN 0.5
                    ELSE 0.0
                END) as health_score
            FROM check_runs
            WHERE started_at > NOW() - INTERVAL '7 days'
            GROUP BY suite_name, DATE_TRUNC('day', started_at)
            ORDER BY day
        """).df()

        if not health_data.empty:
            fig = px.line(
                health_data,
                x="day",
                y="health_score",
                color="suite_name",
                title="Health Score Over Time",
                labels={"health_score": "Health Score", "day": "Date", "suite_name": "Suite"},
            )
            fig.update_yaxes(range=[0, 1.1])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough data for health visualization.")
    except Exception as e:
        st.error(f"Error loading health data: {e}")


def render_trends(conn):
    """Render the trends page."""
    st.header("Quality Trends")

    # Suite selector
    try:
        suites = conn.execute(
            "SELECT DISTINCT suite_name FROM check_runs ORDER BY suite_name"
        ).fetchall()
        suite_names = [s[0] for s in suites]
    except Exception:
        suite_names = []

    if not suite_names:
        st.warning("No suites found.")
        return

    selected_suite = st.selectbox("Select Suite", suite_names)

    # Time range
    time_range = st.select_slider(
        "Time Range",
        options=["24h", "7d", "30d", "90d"],
        value="7d",
    )

    interval_map = {"24h": "1 day", "7d": "7 days", "30d": "30 days", "90d": "90 days"}

    try:
        import plotly.express as px
        import plotly.graph_objects as go

        # Pass rate trend
        trend_data = conn.execute(f"""
            SELECT
                started_at,
                passed_checks,
                warning_checks,
                failed_checks,
                total_checks,
                (passed_checks::FLOAT / NULLIF(total_checks, 0)) * 100 as pass_rate
            FROM check_runs
            WHERE suite_name = ?
              AND started_at > NOW() - INTERVAL '{interval_map[time_range]}'
            ORDER BY started_at
        """, [selected_suite]).df()

        if trend_data.empty:
            st.info(f"No data for {selected_suite} in the selected time range.")
            return

        # Pass rate chart
        st.subheader("Pass Rate Over Time")
        fig = px.line(
            trend_data,
            x="started_at",
            y="pass_rate",
            title=f"Pass Rate - {selected_suite}",
            labels={"pass_rate": "Pass Rate (%)", "started_at": "Time"},
        )
        fig.add_hline(y=95, line_dash="dash", line_color="green", annotation_text="95% Target")
        fig.update_yaxes(range=[0, 105])
        st.plotly_chart(fig, use_container_width=True)

        # Check breakdown
        st.subheader("Check Results Breakdown")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=trend_data["started_at"],
            y=trend_data["passed_checks"],
            name="Passed",
            fill="tozeroy",
            line=dict(color="green"),
        ))
        fig2.add_trace(go.Scatter(
            x=trend_data["started_at"],
            y=trend_data["failed_checks"],
            name="Failed",
            fill="tozeroy",
            line=dict(color="red"),
        ))
        fig2.update_layout(title="Check Results Over Time", xaxis_title="Time", yaxis_title="Count")
        st.plotly_chart(fig2, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading trend data: {e}")


def render_failures(conn):
    """Render the failures page."""
    st.header("Current Failures")

    try:
        # Get latest run per suite
        failures = conn.execute("""
            WITH latest_runs AS (
                SELECT suite_name, MAX(run_id) as run_id
                FROM check_runs
                GROUP BY suite_name
            )
            SELECT
                cr.suite_name,
                r.check_name,
                r.check_type,
                r.severity,
                r.message,
                r.metric_value,
                r.sample_failures,
                cr.started_at
            FROM check_results r
            JOIN check_runs cr ON r.run_id = cr.run_id
            JOIN latest_runs lr ON cr.run_id = lr.run_id
            WHERE r.status = 'failed'
            ORDER BY
                CASE r.severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
                cr.started_at DESC
        """).df()

        if failures.empty:
            st.success("No current failures!")
            return

        # Group by severity
        critical = failures[failures["severity"] == "critical"]
        warnings = failures[failures["severity"] == "warning"]

        if not critical.empty:
            st.error(f"### Critical Failures ({len(critical)})")
            for _, row in critical.iterrows():
                with st.expander(f"[{row['suite_name']}] {row['check_name']}"):
                    st.write(f"**Message:** {row['message']}")
                    st.write(f"**Type:** {row['check_type']}")
                    st.write(f"**Metric Value:** {row['metric_value']}")
                    if row["sample_failures"]:
                        st.write("**Sample Failures:**")
                        st.json(row["sample_failures"])

        if not warnings.empty:
            st.warning(f"### Warnings ({len(warnings)})")
            for _, row in warnings.iterrows():
                with st.expander(f"[{row['suite_name']}] {row['check_name']}"):
                    st.write(f"**Message:** {row['message']}")
                    st.write(f"**Type:** {row['check_type']}")
                    st.write(f"**Metric Value:** {row['metric_value']}")

    except Exception as e:
        st.error(f"Error loading failures: {e}")


def render_coverage(conn):
    """Render the coverage page."""
    st.header("Check Coverage")

    try:
        import plotly.express as px

        # Coverage by suite
        st.subheader("Checks by Suite")
        coverage = conn.execute("""
            SELECT
                cr.suite_name as "Suite",
                COUNT(DISTINCT r.check_name) as "Unique Checks",
                COUNT(DISTINCT r.check_type) as "Check Types"
            FROM check_results r
            JOIN check_runs cr ON r.run_id = cr.run_id
            GROUP BY cr.suite_name
        """).df()

        if not coverage.empty:
            st.dataframe(coverage, use_container_width=True, hide_index=True)

        # Check type distribution
        st.subheader("Check Type Distribution")
        type_dist = conn.execute("""
            SELECT check_type as "Type", COUNT(*) as "Count"
            FROM check_results
            GROUP BY check_type
            ORDER BY "Count" DESC
        """).df()

        if not type_dist.empty:
            fig = px.pie(
                type_dist,
                names="Type",
                values="Count",
                title="Check Types Distribution",
            )
            st.plotly_chart(fig, use_container_width=True)

        # Check status breakdown
        st.subheader("Check Status Breakdown")
        status_dist = conn.execute("""
            SELECT status as "Status", COUNT(*) as "Count"
            FROM check_results
            GROUP BY status
        """).df()

        if not status_dist.empty:
            colors = {"passed": "green", "failed": "red", "warning": "orange", "error": "darkred"}
            fig2 = px.bar(
                status_dist,
                x="Status",
                y="Count",
                title="Check Results by Status",
                color="Status",
                color_discrete_map=colors,
            )
            st.plotly_chart(fig2, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading coverage data: {e}")


if __name__ == "__main__":
    main()

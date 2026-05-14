"""
Trade Reconciliation Dashboard
--------------------------------
3 pages:
  1. Daily Summary   — match rate KPIs, trend chart
  2. Break Report    — filterable break table
  3. Resolution      — SLA tracking, open vs resolved
"""

import os
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import streamlit as st
from datetime import datetime, timedelta

# ─────────────────────────────────────────
# Config
# ─────────────────────────────────────────
st.set_page_config(
    page_title="Trade Reconciliation",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_CONFIG = {
    "host":     os.environ.get("APP_DB_HOST", "localhost"),
    "port":     int(os.environ.get("APP_DB_PORT", 5432)),
    "dbname":   os.environ.get("APP_DB_NAME", "recon"),
    "user":     os.environ.get("APP_DB_USER", "recon"),
    "password": os.environ.get("APP_DB_PASSWORD", ""),
}

PRIORITY_COLORS = {
    "HIGH":   "#ef4444",
    "MEDIUM": "#f59e0b",
    "LOW":    "#22c55e",
}

STATUS_COLORS = {
    "GOOD":     "#22c55e",
    "WARNING":  "#f59e0b",
    "CRITICAL": "#ef4444",
}


def style_priority(val):
    colors = {"HIGH": "#450a0a", "MEDIUM": "#422006", "LOW": "#052e16"}
    text   = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#22c55e"}
    return f"background-color: {colors.get(val, '')}; color: {text.get(val, '')}"

# ─────────────────────────────────────────
# Database helpers
# ─────────────────────────────────────────


@st.cache_data(ttl=30)
def query(sql: str) -> pd.DataFrame:
    try:
        url = (
            f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
            f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
        )
        from sqlalchemy import create_engine, text
        engine = create_engine(url)
        with engine.connect() as conn:
            return pd.read_sql(text(sql), conn)
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    .main { background-color: #0f1117; }

    .metric-card {
        background: #1a1d27;
        border: 1px solid #2d3148;
        border-radius: 8px;
        padding: 20px 24px;
        margin-bottom: 12px;
    }

    .metric-label {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 11px;
        color: #6b7280;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        margin-bottom: 6px;
    }

    .metric-value {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 32px;
        font-weight: 600;
        color: #f9fafb;
        line-height: 1;
    }

    .metric-sub {
        font-size: 12px;
        color: #9ca3af;
        margin-top: 4px;
    }

    .status-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 4px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.05em;
    }

    .badge-good     { background: #052e16; color: #22c55e; }
    .badge-warning  { background: #422006; color: #f59e0b; }
    .badge-critical { background: #450a0a; color: #ef4444; }
    .badge-high     { background: #450a0a; color: #ef4444; }
    .badge-medium   { background: #422006; color: #f59e0b; }
    .badge-low      { background: #052e16; color: #22c55e; }
    .badge-open     { background: #450a0a; color: #ef4444; }
    .badge-progress { background: #422006; color: #f59e0b; }
    .badge-resolved { background: #052e16; color: #22c55e; }

    .section-title {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 12px;
        color: #6b7280;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        border-bottom: 1px solid #2d3148;
        padding-bottom: 8px;
        margin: 24px 0 16px 0;
    }

    div[data-testid="stSidebarNav"] { display: none; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📊 Trade Recon")
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["Daily Summary", "Break Report", "Resolution Tracker", "Break Management"],
        label_visibility="collapsed",
    )
    st.markdown("---")

    auto_refresh = st.toggle("Auto Refresh (30s)", value=False)
    if st.button("🔄 Refresh Now"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown(
        "<div style='font-family:IBM Plex Mono;font-size:10px;color:#4b5563;'>"
        f"Last updated<br>{datetime.now().strftime('%H:%M:%S')}</div>",
        unsafe_allow_html=True,
    )

if auto_refresh:
    time.sleep(30)
    st.cache_data.clear()
    st.rerun()


# ─────────────────────────────────────────
# Page 1 — Daily Summary
# ─────────────────────────────────────────
if page == "Daily Summary":
    st.markdown("## Daily Summary")

    df_summary = query("SELECT * FROM mart_reconciliation_summary ORDER BY summary_date DESC LIMIT 1")

    if df_summary.empty:
        st.warning("No reconciliation data found. Run the pipeline first.")
        st.stop()

    row = df_summary.iloc[0]
    match_rate   = float(row["match_rate"])
    total_trades = int(row["total_trades"])
    total_breaks = int(row["total_breaks"])
    matched      = int(row["matched_count"])
    status       = str(row["status"])
    badge_class  = f"badge-{status.lower()}"

    # ── KPI row ──
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Match Rate</div>
            <div class="metric-value" style="color:{'#22c55e' if match_rate >= 99 else '#f59e0b' if match_rate >= 95 else '#ef4444'}">
                {match_rate:.2f}%
            </div>
            <div class="metric-sub">
                <span class="status-badge {badge_class}">{status}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Trades</div>
            <div class="metric-value">{total_trades:,}</div>
            <div class="metric-sub">Today's session</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Matched</div>
            <div class="metric-value" style="color:#22c55e">{matched:,}</div>
            <div class="metric-sub">Clean trades</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Breaks</div>
            <div class="metric-value" style="color:{'#ef4444' if total_breaks > 0 else '#22c55e'}">{total_breaks:,}</div>
            <div class="metric-sub">Require attention</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Break breakdown by priority ──
    st.markdown("<div class='section-title'>Breaks by Priority</div>", unsafe_allow_html=True)

    df_priority = query("""
        SELECT priority, COUNT(*) AS count
        FROM mart_break_report
        GROUP BY priority
        ORDER BY CASE priority WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END
    """)

    if not df_priority.empty:
        c1, c2 = st.columns([1, 2])
        with c1:
            for _, r in df_priority.iterrows():
                badge = f"badge-{r['priority'].lower()}"
                st.markdown(f"""
                <div class="metric-card" style="padding:14px 20px;">
                    <span class="status-badge {badge}">{r['priority']}</span>
                    <span style="font-family:'IBM Plex Mono';font-size:24px;font-weight:600;
                                 color:#f9fafb;margin-left:16px;">{int(r['count']):,}</span>
                </div>
                """, unsafe_allow_html=True)

        with c2:
            fig = px.bar(
                df_priority,
                x="priority", y="count",
                color="priority",
                color_discrete_map=PRIORITY_COLORS,
                template="plotly_dark",
            )
            fig.update_layout(
                paper_bgcolor="#1a1d27",
                plot_bgcolor="#1a1d27",
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                height=200,
                font=dict(family="IBM Plex Mono"),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Break breakdown by type ──
    st.markdown("<div class='section-title'>Breaks by Type</div>", unsafe_allow_html=True)

    df_type = query("""
        SELECT break_type, COUNT(*) AS count
        FROM mart_break_report
        GROUP BY break_type
        ORDER BY count DESC
    """)

    if not df_type.empty:
        fig = px.pie(
            df_type,
            names="break_type", values="count",
            template="plotly_dark",
            color_discrete_sequence=["#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6", "#22c55e"],
        )
        fig.update_layout(
            paper_bgcolor="#1a1d27",
            plot_bgcolor="#1a1d27",
            margin=dict(t=10, b=10, l=10, r=10),
            height=300,
            font=dict(family="IBM Plex Mono"),
        )
        st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────
# Page 2 — Break Report
# ─────────────────────────────────────────
elif page == "Break Report":
    st.markdown("## Break Report")

    df = query("SELECT * FROM mart_break_report ORDER BY traded_at DESC")

    if df.empty:
        st.info("No breaks found — all trades matched! ✅")
        st.stop()

    # ── Filters ──
    c1, c2, c3 = st.columns(3)
    with c1:
        priority_filter = st.multiselect(
            "Priority",
            options=["HIGH", "MEDIUM", "LOW"],
            default=["HIGH", "MEDIUM", "LOW"],
        )
    with c2:
        type_filter = st.multiselect(
            "Break Type",
            options=df["break_type"].unique().tolist(),
            default=df["break_type"].unique().tolist(),
        )
    with c3:
        symbol_filter = st.multiselect(
            "Symbol",
            options=df["symbol"].unique().tolist(),
            default=df["symbol"].unique().tolist(),
        )

    # Apply filters
    mask = (
        df["priority"].isin(priority_filter) &
        df["break_type"].isin(type_filter) &
        df["symbol"].isin(symbol_filter)
    )
    df_filtered = df[mask].copy()

    st.markdown(f"<div class='section-title'>Showing {len(df_filtered):,} of {len(df):,} breaks</div>",
                unsafe_allow_html=True)

    # ── Table ──
    display_cols = ["trade_id", "symbol", "side", "break_type", "priority",
                    "broker_value", "exchange_value", "difference", "traded_at"]
    available_cols = [c for c in display_cols if c in df_filtered.columns]

    styled = (
        df_filtered[available_cols]
        .style
        .map(style_priority, subset=["priority"])
        .format({"broker_value": "{:.2f}", "exchange_value": "{:.2f}", "difference": "{:.2f}"}, na_rep="—")
    )
    st.dataframe(styled, use_container_width=True, height=500)

    # ── Download ──
    csv = df_filtered.to_csv(index=False)
    st.download_button(
        "⬇️ Download CSV",
        data=csv,
        file_name=f"break_report_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )


# ─────────────────────────────────────────
# Page 4 — Break Management
# ─────────────────────────────────────────
elif page == "Break Management":
    st.markdown("## Break Management")

    df = query("""
        SELECT
            b.trade_id,
            b.symbol,
            b.side,
            b.break_type,
            b.priority,
            b.broker_value,
            b.exchange_value,
            b.difference,
            b.traded_at,
            COALESCE(r.status, 'UNASSIGNED')    AS status,
            r.break_id,
            r.resolved_by,
            r.resolution_note,
            r.detected_at,
            CASE b.priority
                WHEN 'HIGH'   THEN 4
                WHEN 'MEDIUM' THEN 24
                WHEN 'LOW'    THEN 72
            END AS sla_hours,
            CASE
                WHEN r.detected_at IS NOT NULL THEN
                    ROUND(EXTRACT(EPOCH FROM (NOW() - r.detected_at)) / 3600.0, 1)
                ELSE NULL
            END AS hours_open,
            CASE
                WHEN r.detected_at IS NOT NULL THEN
                    CASE b.priority
                        WHEN 'HIGH'   THEN 4  - ROUND(EXTRACT(EPOCH FROM (NOW() - r.detected_at)) / 3600.0, 1)
                        WHEN 'MEDIUM' THEN 24 - ROUND(EXTRACT(EPOCH FROM (NOW() - r.detected_at)) / 3600.0, 1)
                        WHEN 'LOW'    THEN 72 - ROUND(EXTRACT(EPOCH FROM (NOW() - r.detected_at)) / 3600.0, 1)
                    END
                ELSE NULL
            END AS sla_remaining_hours
        FROM mart_break_report b
        LEFT JOIN break_resolutions r ON b.trade_id = r.trade_id
        ORDER BY
            CASE b.priority WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
            sla_remaining_hours ASC NULLS LAST
    """)

    if df.empty:
        st.warning("No breaks found. Run the pipeline first.")
        st.stop()

    # ── KPIs ──
    unassigned = len(df[df["status"] == "UNASSIGNED"])
    in_prog    = len(df[df["status"] == "IN_PROGRESS"])
    resolved   = len(df[df["status"] == "RESOLVED"])
    breached   = len(df[df["sla_remaining_hours"].notna() & (df["sla_remaining_hours"] < 0)])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Unassigned</div>
            <div class="metric-value" style="color:#6b7280">{unassigned}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">In Progress</div>
            <div class="metric-value" style="color:#f59e0b">{in_prog}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Resolved</div>
            <div class="metric-value" style="color:#22c55e">{resolved}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">SLA Breached</div>
            <div class="metric-value" style="color:{'#ef4444' if breached > 0 else '#22c55e'}">{breached}</div>
        </div>""", unsafe_allow_html=True)

    # ── Filters ──
    st.markdown("<div class='section-title'>Filters</div>", unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        status_filter = st.multiselect(
            "Status",
            options=["UNASSIGNED", "IN_PROGRESS", "RESOLVED"],
            default=["UNASSIGNED", "IN_PROGRESS"],
            key="bm_status_filter",
        )
    with fc2:
        priority_filter = st.multiselect(
            "Priority",
            options=["HIGH", "MEDIUM", "LOW"],
            default=["HIGH", "MEDIUM", "LOW"],
            key="bm_priority_filter",
        )
    with fc3:
        symbol_filter = st.multiselect(
            "Symbol",
            options=sorted(df["symbol"].unique().tolist()),
            default=sorted(df["symbol"].unique().tolist()),
            key="bm_symbol_filter",
        )

    df_filtered = df[
        df["status"].isin(status_filter) &
        df["priority"].isin(priority_filter) &
        df["symbol"].isin(symbol_filter)
    ].copy()

    # ── SLA display column ──
    def sla_display(row):
        if pd.isna(row["sla_remaining_hours"]):
            return "—"
        rem = float(row["sla_remaining_hours"])
        if rem < 0:
            return f"🚨 -{abs(rem):.1f}h"
        elif rem < 2:
            return f"⚠️ {rem:.1f}h"
        else:
            return f"⏱ {rem:.1f}h"

    def sla_style(row):
        if pd.isna(row["sla_remaining_hours"]):
            return ""
        rem = float(row["sla_remaining_hours"])
        if rem < 0:
            return "background-color:#450a0a"
        elif rem < 2:
            return "background-color:#422006"
        return ""

    df_filtered["SLA"] = df_filtered.apply(sla_display, axis=1)
    df_filtered["hours_open"] = df_filtered["hours_open"].apply(
        lambda x: f"{x:.1f}h" if pd.notna(x) else "—"
    )

    # ── Pagination ──
    PAGE_SIZE = 20
    total_pages = max(1, -(-len(df_filtered) // PAGE_SIZE))

    st.markdown(
        f"<div class='section-title'>Showing {len(df_filtered):,} of {len(df):,} breaks</div>",
        unsafe_allow_html=True
    )

    col_pg1, col_pg2, col_pg3 = st.columns([1, 2, 1])
    with col_pg2:
        page_num = st.number_input(
            f"Page (1–{total_pages})",
            min_value=1, max_value=total_pages, value=1, step=1
        )

    start_idx = (page_num - 1) * PAGE_SIZE
    end_idx   = start_idx + PAGE_SIZE
    df_page   = df_filtered.iloc[start_idx:end_idx].copy()

    # ── Table view ──
    display_cols = ["priority", "symbol", "side", "break_type", "status",
                    "hours_open", "SLA", "resolved_by", "trade_id"]
    available_cols = [c for c in display_cols if c in df_page.columns]

    def style_row(row):
        styles = [""] * len(row)
        # SLA highlight
        if "SLA" in row.index:
            sla_val = row["SLA"]
            if "🚨" in str(sla_val):
                sla_bg = "background-color:#3d0a0a"
            elif "⚠️" in str(sla_val):
                sla_bg = "background-color:#3d2200"
            else:
                sla_bg = ""
            styles = [sla_bg] * len(row)
        return styles

    styled_table = (
        df_page[available_cols]
        .style
        .apply(style_row, axis=1)
        .map(style_priority, subset=["priority"])
    )
    st.dataframe(styled_table, use_container_width=True, height=400)

    # ── Quick Actions ──
    st.markdown("<div class='section-title'>Quick Action</div>", unsafe_allow_html=True)
    st.caption("เลือก Trade ID แล้วดำเนินการ")

    selected_trade = st.selectbox(
        "Select Trade ID",
        options=df_page["trade_id"].tolist(),
        format_func=lambda x: f"{x[:8]}... [{df_page[df_page['trade_id']==x]['break_type'].values[0]}] [{df_page[df_page['trade_id']==x]['status'].values[0]}]"
    )

    if selected_trade:
        selected_row = df_filtered[df_filtered["trade_id"] == selected_trade].iloc[0]

        with st.container():
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Trade ID:** `{selected_row['trade_id']}`")
                st.markdown(f"**Symbol:** {selected_row['symbol']} · {selected_row['side']}")
                st.markdown(f"**Break Type:** {selected_row['break_type']}")
                st.markdown(f"**Priority:** {selected_row['priority']}")
                st.markdown(f"**Status:** {selected_row['status']}")
                st.markdown(f"**SLA:** {selected_row['SLA']}")
            with c2:
                if selected_row["status"] == "RESOLVED":
                    st.success("✅ Already resolved")
                    st.markdown(f"**Resolved by:** {selected_row['resolved_by']}")
                    st.markdown(f"**Note:** {selected_row['resolution_note']}")
                else:
                    assignee = st.text_input(
                        "Assign to",
                        value=selected_row["resolved_by"] or "",
                        key="qa_assignee"
                    )
                    note = st.text_area(
                        "Resolution note",
                        value=selected_row["resolution_note"] or "",
                        key="qa_note",
                        height=80
                    )

                    qa1, qa2, qa3 = st.columns(3)
                    with qa1:
                        if st.button("👤 Take Ownership"):
                            with psycopg2.connect(**DB_CONFIG) as conn:
                                with conn.cursor() as cur:
                                    if pd.isna(selected_row["break_id"]):
                                        cur.execute("""
                                            INSERT INTO break_resolutions
                                              (trade_id, break_type, priority, status, detected_at, resolved_by)
                                            VALUES (%s, %s, %s, 'IN_PROGRESS', NOW(), %s)
                                        """, (selected_row["trade_id"], selected_row["break_type"],
                                              selected_row["priority"], assignee))
                                    else:
                                        cur.execute("""
                                            UPDATE break_resolutions
                                            SET status = 'IN_PROGRESS', resolved_by = %s
                                            WHERE break_id = %s
                                        """, (assignee, int(selected_row["break_id"])))
                                conn.commit()
                            st.success(f"Assigned to {assignee}")
                            st.cache_data.clear()
                            st.rerun()

                    with qa2:
                        if st.button("✅ Mark Resolved"):
                            with psycopg2.connect(**DB_CONFIG) as conn:
                                with conn.cursor() as cur:
                                    if pd.isna(selected_row["break_id"]):
                                        cur.execute("""
                                            INSERT INTO break_resolutions
                                              (trade_id, break_type, priority, status, detected_at, resolved_at, resolved_by, resolution_note)
                                            VALUES (%s, %s, %s, 'RESOLVED', NOW(), NOW(), %s, %s)
                                        """, (selected_row["trade_id"], selected_row["break_type"],
                                              selected_row["priority"], assignee, note))
                                    else:
                                        cur.execute("""
                                            UPDATE break_resolutions
                                            SET status = 'RESOLVED', resolved_at = NOW(),
                                                resolved_by = %s, resolution_note = %s
                                            WHERE break_id = %s
                                        """, (assignee or selected_row["resolved_by"],
                                              note, int(selected_row["break_id"])))
                                conn.commit()
                            st.success("Break marked as resolved!")
                            st.cache_data.clear()
                            st.rerun()

                    with qa3:
                        if str(selected_row["priority"]) != "HIGH":
                            if st.button("🚨 Escalate"):
                                with psycopg2.connect(**DB_CONFIG) as conn:
                                    with conn.cursor() as cur:
                                        if pd.isna(selected_row["break_id"]):
                                            cur.execute("""
                                                INSERT INTO break_resolutions
                                                  (trade_id, break_type, priority, status, detected_at, resolution_note)
                                                VALUES (%s, %s, 'HIGH', 'OPEN', NOW(), '[ESCALATED]')
                                            """, (selected_row["trade_id"], selected_row["break_type"]))
                                        else:
                                            cur.execute("""
                                                UPDATE break_resolutions
                                                SET priority = 'HIGH',
                                                    resolution_note = COALESCE(resolution_note,'') || ' [ESCALATED]'
                                                WHERE break_id = %s
                                            """, (int(selected_row["break_id"]),))
                                    conn.commit()
                                st.warning("Escalated to HIGH!")
                                st.cache_data.clear()
                                st.rerun()
    st.markdown("## Break Management")

    df = query("""
        SELECT
            b.trade_id,
            b.symbol,
            b.side,
            b.break_type,
            b.priority,
            b.broker_value,
            b.exchange_value,
            b.difference,
            b.traded_at,
            COALESCE(r.status, 'UNASSIGNED')    AS status,
            r.break_id,
            r.resolved_by,
            r.resolution_note,
            r.detected_at,
            -- SLA target hours
            CASE b.priority
                WHEN 'HIGH'   THEN 4
                WHEN 'MEDIUM' THEN 24
                WHEN 'LOW'    THEN 72
            END AS sla_hours,
            -- Hours since detected (or traded_at if not logged)
            CASE
                WHEN r.detected_at IS NOT NULL
                THEN ROUND(EXTRACT(EPOCH FROM (NOW() - r.detected_at)) / 3600.0, 1)
                ELSE NULL
            END AS hours_open,
            -- SLA remaining
            CASE
                WHEN r.detected_at IS NOT NULL THEN
                    CASE b.priority
                        WHEN 'HIGH'   THEN 4  - ROUND(EXTRACT(EPOCH FROM (NOW() - r.detected_at)) / 3600.0, 1)
                        WHEN 'MEDIUM' THEN 24 - ROUND(EXTRACT(EPOCH FROM (NOW() - r.detected_at)) / 3600.0, 1)
                        WHEN 'LOW'    THEN 72 - ROUND(EXTRACT(EPOCH FROM (NOW() - r.detected_at)) / 3600.0, 1)
                    END
                ELSE NULL
            END AS sla_remaining_hours
        FROM mart_break_report b
        LEFT JOIN break_resolutions r ON b.trade_id = r.trade_id
        ORDER BY
            CASE b.priority WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
            b.traded_at ASC
    """)

    if df.empty:
        st.warning("No breaks found. Run the pipeline first.")
        st.stop()

    # ── KPIs ──
    unassigned = len(df[df["status"] == "UNASSIGNED"])
    in_prog    = len(df[df["status"] == "IN_PROGRESS"])
    resolved   = len(df[df["status"] == "RESOLVED"])
    breached   = len(df[df["sla_remaining_hours"].notna() & (df["sla_remaining_hours"] < 0)])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Unassigned</div>
            <div class="metric-value" style="color:#6b7280">{unassigned}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">In Progress</div>
            <div class="metric-value" style="color:#f59e0b">{in_prog}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Resolved</div>
            <div class="metric-value" style="color:#22c55e">{resolved}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">SLA Breached</div>
            <div class="metric-value" style="color:{'#ef4444' if breached > 0 else '#22c55e'}">{breached}</div>
        </div>""", unsafe_allow_html=True)

    # ── Filters ──
    st.markdown("<div class='section-title'>Filters</div>", unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        status_filter = st.multiselect(
            "Status",
            options=["UNASSIGNED", "IN_PROGRESS", "RESOLVED"],
            default=["UNASSIGNED", "IN_PROGRESS"],
        )
    with fc2:
        priority_filter = st.multiselect(
            "Priority",
            options=["HIGH", "MEDIUM", "LOW"],
            default=["HIGH", "MEDIUM", "LOW"],
        )
    with fc3:
        symbol_filter = st.multiselect(
            "Symbol",
            options=df["symbol"].unique().tolist(),
            default=df["symbol"].unique().tolist(),
        )

    df_filtered = df[
        df["status"].isin(status_filter) &
        df["priority"].isin(priority_filter) &
        df["symbol"].isin(symbol_filter)
    ].copy()

    st.markdown(
        f"<div class='section-title'>Showing {len(df_filtered):,} of {len(df):,} breaks</div>",
        unsafe_allow_html=True
    )

    # ── Break list ──
    for _, row in df_filtered.iterrows():
        status      = row["status"]
        priority    = row["priority"]
        sla_rem     = row["sla_remaining_hours"]
        hours_open  = row["hours_open"]

        # SLA display
        if pd.isna(sla_rem):
            sla_text = "Not logged yet"
            sla_color = "#6b7280"
        elif sla_rem < 0:
            sla_text  = f"🚨 Breached {abs(float(sla_rem)):.1f}h ago"
            sla_color = "#ef4444"
        elif sla_rem < 2:
            sla_text  = f"⚠️ {float(sla_rem):.1f}h remaining"
            sla_color = "#f59e0b"
        else:
            sla_text  = f"⏱ {float(sla_rem):.1f}h remaining"
            sla_color = "#22c55e"

        status_icon = {"UNASSIGNED": "⬜", "IN_PROGRESS": "🟡", "RESOLVED": "🟢"}.get(status, "⬜")

        with st.expander(
            f"{status_icon} [{priority}] {row['break_type']} · {row['symbol']} · {row['trade_id'][:8]}..."
        ):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Trade ID:** `{row['trade_id']}`")
                st.markdown(f"**Symbol:** {row['symbol']} · {row['side']}")
                st.markdown(f"**Break Type:** {row['break_type']}")
                st.markdown(f"**Priority:** {row['priority']}")
                st.markdown(f"**Status:** {status}")
                if row["broker_value"]:
                    st.markdown(f"**Broker Value:** {row['broker_value']:.2f}")
                if row["exchange_value"]:
                    st.markdown(f"**Exchange Value:** {row['exchange_value']:.2f}")
            with c2:
                st.markdown(f"**Traded At:** {row['traded_at']}")
                if not pd.isna(hours_open):
                    st.markdown(f"**Hours Open:** {float(hours_open):.1f}h")
                st.markdown(f"**SLA:** <span style='color:{sla_color}'>{sla_text}</span>", unsafe_allow_html=True)
                if row["resolved_by"]:
                    st.markdown(f"**Assigned to:** {row['resolved_by']}")
                if row["resolution_note"]:
                    st.markdown(f"**Note:** {row['resolution_note']}")

            if status == "RESOLVED":
                st.success("This break has been resolved.")
            else:
                st.markdown("---")
                col1, col2, col3 = st.columns(3)

                with col1:
                    assignee = st.text_input(
                        "Assign to",
                        value=row["resolved_by"] or "",
                        key=f"assignee_{row['trade_id']}"
                    )
                    if st.button("👤 Take Ownership", key=f"own_{row['trade_id']}"):
                        with psycopg2.connect(**DB_CONFIG) as conn:
                            with conn.cursor() as cur:
                                if pd.isna(row["break_id"]):
                                    cur.execute("""
                                        INSERT INTO break_resolutions
                                          (trade_id, break_type, priority, status, detected_at, resolved_by)
                                        VALUES (%s, %s, %s, 'IN_PROGRESS', NOW(), %s)
                                    """, (row["trade_id"], row["break_type"], row["priority"], assignee))
                                else:
                                    cur.execute("""
                                        UPDATE break_resolutions
                                        SET status = 'IN_PROGRESS', resolved_by = %s
                                        WHERE break_id = %s
                                    """, (assignee, int(row["break_id"])))
                            conn.commit()
                        st.success(f"Assigned to {assignee}")
                        st.cache_data.clear()
                        st.rerun()

                with col2:
                    note = st.text_area(
                        "Resolution note",
                        value=row["resolution_note"] or "",
                        key=f"note_{row['trade_id']}",
                        height=80,
                    )
                    if st.button("✅ Mark Resolved", key=f"resolve_{row['trade_id']}"):
                        with psycopg2.connect(**DB_CONFIG) as conn:
                            with conn.cursor() as cur:
                                if pd.isna(row["break_id"]):
                                    cur.execute("""
                                        INSERT INTO break_resolutions
                                          (trade_id, break_type, priority, status, detected_at, resolved_at, resolved_by, resolution_note)
                                        VALUES (%s, %s, %s, 'RESOLVED', NOW(), NOW(), %s, %s)
                                    """, (row["trade_id"], row["break_type"], row["priority"], assignee, note))
                                else:
                                    cur.execute("""
                                        UPDATE break_resolutions
                                        SET status = 'RESOLVED', resolved_at = NOW(),
                                            resolved_by = %s, resolution_note = %s
                                        WHERE break_id = %s
                                    """, (assignee or row["resolved_by"], note, int(row["break_id"])))
                            conn.commit()
                        st.success("Break marked as resolved!")
                        st.cache_data.clear()
                        st.rerun()

                with col3:
                    if str(row["priority"]) != "HIGH":
                        if st.button("🚨 Escalate to HIGH", key=f"escalate_{row['trade_id']}"):
                            with psycopg2.connect(**DB_CONFIG) as conn:
                                with conn.cursor() as cur:
                                    if pd.isna(row["break_id"]):
                                        cur.execute("""
                                            INSERT INTO break_resolutions
                                              (trade_id, break_type, priority, status, detected_at, resolution_note)
                                            VALUES (%s, %s, 'HIGH', 'OPEN', NOW(), '[ESCALATED]')
                                        """, (row["trade_id"], row["break_type"]))
                                    else:
                                        cur.execute("""
                                            UPDATE break_resolutions
                                            SET priority = 'HIGH',
                                                resolution_note = COALESCE(resolution_note, '') || ' [ESCALATED]'
                                            WHERE break_id = %s
                                        """, (int(row["break_id"]),))
                                conn.commit()
                            st.warning("Escalated to HIGH priority!")
                            st.cache_data.clear()
                            st.rerun()

# ─────────────────────────────────────────
# Page 3 — Resolution Tracker
# ─────────────────────────────────────────
elif page == "Resolution Tracker":
    st.markdown("## Resolution Tracker")

    df = query("""
        SELECT
            break_id, trade_id, break_type, priority,
            detected_at, resolved_at, resolved_by,
            resolution_note, status,
            CASE
                WHEN resolved_at IS NOT NULL
                THEN ROUND(EXTRACT(EPOCH FROM (resolved_at - detected_at)) / 3600.0, 1)
                ELSE ROUND(EXTRACT(EPOCH FROM (NOW() - detected_at)) / 3600.0, 1)
            END AS hours_open
        FROM break_resolutions
        ORDER BY detected_at DESC
    """)

    if df.empty:
        st.info("No breaks have been logged yet.")
        st.stop()

    # ── KPIs ──
    total      = len(df)
    open_count = len(df[df["status"] == "OPEN"])
    resolved   = len(df[df["status"] == "RESOLVED"])
    in_prog    = len(df[df["status"] == "IN_PROGRESS"])
    avg_hrs    = df[df["status"] == "RESOLVED"]["hours_open"].mean()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Logged</div>
            <div class="metric-value">{total:,}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Open</div>
            <div class="metric-value" style="color:#ef4444">{open_count:,}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Resolved</div>
            <div class="metric-value" style="color:#22c55e">{resolved:,}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        avg_display = f"{avg_hrs:.1f}h" if not pd.isna(avg_hrs) else "—"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Avg Resolution Time</div>
            <div class="metric-value">{avg_display}</div>
        </div>""", unsafe_allow_html=True)

    # ── Status filter ──
    st.markdown("<div class='section-title'>Break Log</div>", unsafe_allow_html=True)

    status_filter = st.multiselect(
        "Status",
        options=["OPEN", "IN_PROGRESS", "RESOLVED"],
        default=["OPEN", "IN_PROGRESS"],
    )

    df_filtered = df[df["status"].isin(status_filter)].copy()

    def style_status(val):
        colors = {
            "OPEN":        ("#450a0a", "#ef4444"),
            "IN_PROGRESS": ("#422006", "#f59e0b"),
            "RESOLVED":    ("#052e16", "#22c55e"),
        }
        bg, fg = colors.get(val, ("#1a1d27", "#f9fafb"))
        return f"background-color: {bg}; color: {fg}"

    display_cols = ["break_id", "trade_id", "break_type", "priority",
                    "status", "hours_open", "detected_at", "resolved_by", "resolution_note"]
    available_cols = [c for c in display_cols if c in df_filtered.columns]

    styled = (
        df_filtered[available_cols]
        .style
        .map(style_status, subset=["status"])
        .map(style_priority, subset=["priority"])
        .format({"hours_open": "{:.1f}h"}, na_rep="—")
    )
    st.dataframe(styled, use_container_width=True, height=450)

    # ── SLA chart ──
    st.markdown("<div class='section-title'>Resolution Time by Break Type</div>", unsafe_allow_html=True)

    df_sla = query("""
        SELECT
            break_type,
            ROUND(AVG(EXTRACT(EPOCH FROM (resolved_at - detected_at)) / 3600.0), 1) AS avg_hours,
            COUNT(*) AS count
        FROM break_resolutions
        WHERE status = 'RESOLVED'
        GROUP BY break_type
    """)

    if not df_sla.empty:
        fig = px.bar(
            df_sla,
            x="break_type", y="avg_hours",
            text="avg_hours",
            template="plotly_dark",
            color="avg_hours",
            color_continuous_scale=["#22c55e", "#f59e0b", "#ef4444"],
        )
        fig.update_traces(texttemplate="%{text:.1f}h", textposition="outside")
        fig.update_layout(
            paper_bgcolor="#1a1d27",
            plot_bgcolor="#1a1d27",
            showlegend=False,
            coloraxis_showscale=False,
            margin=dict(t=20, b=10, l=10, r=10),
            height=300,
            font=dict(family="IBM Plex Mono"),
            yaxis_title="Avg Hours to Resolve",
            xaxis_title="",
        )
        st.plotly_chart(fig, use_container_width=True)
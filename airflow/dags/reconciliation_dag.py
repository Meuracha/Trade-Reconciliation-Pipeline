"""
Reconciliation DAG
------------------
Runs end-of-day reconciliation pipeline:

  1. run_simulator   : generate fresh broker + exchange trades
  2. dbt_run         : transform raw → staging → intermediate → mart
  3. dbt_test        : run all data quality tests
  4. send_alert      : notify Slack if HIGH priority breaks found
"""

from __future__ import annotations

import os
import logging
import subprocess
from datetime import datetime, timedelta
from pendulum import timezone

import psycopg2
import requests
from airflow import DAG
from airflow.operators.python import PythonOperator

log = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Default args
# ─────────────────────────────────────────
DEFAULT_ARGS = {
    "owner":            "recon-team",
    "retries":          1,
    "retry_delay":      timedelta(minutes=5),
    "email_on_failure": False,
}

# ─────────────────────────────────────────
# Config
# ─────────────────────────────────────────
APP_DB_CONN       = os.environ["APP_DB_CONN"]
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
DBT_PROJECT_DIR   = "/opt/airflow/dbt"
HIGH_BREAK_THRESHOLD = 10   # alert if HIGH priority breaks exceed this


# ─────────────────────────────────────────
# Task 1 — Run Simulator
# ─────────────────────────────────────────
def run_simulator():
    """Run the trade simulator as a subprocess."""
    result = subprocess.run(
        ["python", "/opt/airflow/dags/generate_trades.py"],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "APP_DB_HOST":     "postgres-app",
            "APP_DB_PORT":     "5432",
            "APP_DB_NAME":     os.environ["APP_DB_CONN"].split("/")[-1],
            "APP_DB_USER":     os.environ["APP_DB_CONN"].split("//")[1].split(":")[0],
            "APP_DB_PASSWORD": os.environ["APP_DB_CONN"].split(":")[2].split("@")[0],
        }
    )
    log.info(result.stdout)
    if result.returncode != 0:
        log.error(result.stderr)
        raise RuntimeError(f"Simulator failed:\n{result.stderr}")
    log.info("Simulator finished.")


DBT_ENV = {
    **os.environ,
    "APP_DB_HOST":     "postgres-app",
    "APP_DB_PORT":     "5432",
    "APP_DB_NAME":     os.environ.get("APP_DB_CONN", "").split("/")[-1],
    "APP_DB_USER":     os.environ.get("APP_DB_CONN", "//u:p@h/db").split("//")[1].split(":")[0],
    "APP_DB_PASSWORD": os.environ.get("APP_DB_CONN", "//u:p@h/db").split(":")[2].split("@")[0],
}


# ─────────────────────────────────────────
# Task 2 — dbt run
# ─────────────────────────────────────────
def dbt_run():
    """Run all dbt models."""
    result = subprocess.run(
        ["dbt", "run", "--project-dir", DBT_PROJECT_DIR, "--profiles-dir", DBT_PROJECT_DIR],
        capture_output=True,
        text=True,
        env=DBT_ENV,
    )
    log.info(result.stdout)
    if result.returncode != 0:
        log.error(result.stderr)
        raise RuntimeError(f"dbt run failed:\n{result.stderr}")
    log.info("dbt run complete.")


# ─────────────────────────────────────────
# Task 3 — dbt test
# ─────────────────────────────────────────
def dbt_test():
    """Run all dbt tests."""
    result = subprocess.run(
        ["dbt", "test", "--project-dir", DBT_PROJECT_DIR, "--profiles-dir", DBT_PROJECT_DIR],
        capture_output=True,
        text=True,
        env=DBT_ENV,
    )
    log.info(result.stdout)
    if result.returncode != 0:
        log.error(result.stderr)
        raise RuntimeError(f"dbt test failed:\n{result.stderr}")
    log.info("dbt test complete.")


# ─────────────────────────────────────────
# Task 4 — Slack alert
# ─────────────────────────────────────────
def send_alert():
    """Query mart_break_report and alert if HIGH breaks exceed threshold."""
    if not SLACK_WEBHOOK_URL:
        log.warning("SLACK_WEBHOOK_URL not set — skipping alert.")
        return

    conn = psycopg2.connect(APP_DB_CONN)
    with conn.cursor() as cur:
        # Total breaks by priority
        cur.execute("""
            SELECT priority, COUNT(*) AS cnt
            FROM mart_break_report
            GROUP BY priority
            ORDER BY priority
        """)
        rows = cur.fetchall()

        # Overall match rate
        cur.execute("SELECT match_rate, total_trades, total_breaks FROM mart_reconciliation_summary ORDER BY summary_date DESC LIMIT 1")
        summary = cur.fetchone()

    conn.close()

    break_counts = {row[0]: row[1] for row in rows}
    high_count   = break_counts.get("HIGH", 0)
    mid_count    = break_counts.get("MEDIUM", 0)
    low_count    = break_counts.get("LOW", 0)

    match_rate   = summary[0] if summary else 0
    total_trades = summary[1] if summary else 0
    total_breaks = summary[2] if summary else 0

    # Only alert if HIGH breaks exceed threshold
    if high_count > HIGH_BREAK_THRESHOLD:
        emoji  = "🚨"
        status = "ACTION REQUIRED"
    elif total_breaks > 0:
        emoji  = "⚠️"
        status = "Breaks Detected"
    else:
        emoji  = "✅"
        status = "All Clear"

    message = {
        "text": (
            f"{emoji} *Trade Reconciliation — {status}*\n"
            f">  Date        : {datetime.now().strftime('%Y-%m-%d')}\n"
            f">  Match Rate  : *{match_rate:.2f}%*\n"
            f">  Total Trades: {total_trades:,}\n"
            f">  Total Breaks: {total_breaks:,}\n"
            f">  HIGH        : {high_count}\n"
            f">  MEDIUM      : {mid_count}\n"
            f">  LOW         : {low_count}\n"
            f">  Dashboard   : http://localhost:8501"
        )
    }

    response = requests.post(SLACK_WEBHOOK_URL, json=message, timeout=10)
    if response.status_code != 200:
        raise RuntimeError(f"Slack alert failed: {response.status_code} {response.text}")

    log.info(f"Slack alert sent — status: {status}")


# ─────────────────────────────────────────
# DAG definition
# ─────────────────────────────────────────
with DAG(
    dag_id="trade_reconciliation",
    description="End-of-day securities trade reconciliation pipeline",
    default_args=DEFAULT_ARGS,
    schedule_interval="30 16 * * 1-5",   # Mon–Fri at 16:30 (after market close)
    start_date=datetime(2026, 5, 14, 10, 0, 0),
    catchup=False,
    tags=["reconciliation", "fintech", "dbt"],
) as dag:

    t0_dbt_deps = PythonOperator(
        task_id="dbt_deps",
        python_callable=lambda: subprocess.run(
            ["dbt", "deps", "--project-dir", DBT_PROJECT_DIR, "--profiles-dir", DBT_PROJECT_DIR],
            capture_output=True, text=True, check=True, env=DBT_ENV,
        ) and None,
    )

    t1_simulate = PythonOperator(
        task_id="run_simulator",
        python_callable=run_simulator,
    )

    t1b_freshness = PythonOperator(
        task_id="dbt_source_freshness",
        python_callable=lambda: subprocess.run(
            ["dbt", "source", "freshness", "--project-dir", DBT_PROJECT_DIR, "--profiles-dir", DBT_PROJECT_DIR],
            capture_output=True, text=True, env=DBT_ENV,
        ) and None,
    )

    t2_dbt_run = PythonOperator(
        task_id="dbt_run",
        python_callable=dbt_run,
    )

    t3_dbt_test = PythonOperator(
        task_id="dbt_test",
        python_callable=dbt_test,
    )

    t4_dbt_docs = PythonOperator(
        task_id="dbt_docs_generate",
        python_callable=lambda: subprocess.run(
            ["dbt", "docs", "generate", "--project-dir", DBT_PROJECT_DIR, "--profiles-dir", DBT_PROJECT_DIR],
            capture_output=True, text=True, check=True, env=DBT_ENV,
        ) and None,
    )

    t5_alert = PythonOperator(
        task_id="send_slack_alert",
        python_callable=send_alert,
    )

    # Pipeline order
    t0_dbt_deps >> t1_simulate >> t1b_freshness >> t2_dbt_run >> t3_dbt_test >> t4_dbt_docs >> t5_alert
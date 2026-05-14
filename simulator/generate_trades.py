"""
Trade Simulator
---------------
Generates synthetic broker and exchange trades for SET-listed symbols,
then injects realistic errors to simulate real-world reconciliation breaks.

Error types:
  - price_mismatch   : exchange price differs slightly from broker price
  - qty_mismatch     : exchange quantity differs from broker quantity
  - missing_broker   : trade exists on exchange but not on broker side
  - missing_exchange : trade exists on broker but not on exchange side
  - duplicate        : trade inserted twice on broker side
"""

import os
import uuid
import random
import logging
from datetime import datetime, timedelta

import psycopg2
from psycopg2.extras import execute_values

# ─────────────────────────────────────────
# Config from environment variables
# ─────────────────────────────────────────
DB_HOST     = os.environ["APP_DB_HOST"]
DB_PORT     = int(os.environ.get("APP_DB_PORT", 5432))
DB_NAME     = os.environ["APP_DB_NAME"]
DB_USER     = os.environ["APP_DB_USER"]
DB_PASSWORD = os.environ["APP_DB_PASSWORD"]

ERROR_RATE     = float(os.environ.get("ERROR_RATE", 0.05))   # 5% of trades get errors
TRADES_PER_RUN = int(os.environ.get("TRADES_PER_RUN", 1000))

# ─────────────────────────────────────────
# Constants
# ─────────────────────────────────────────
SET_SYMBOLS = {
    "KBANK": (130.00, 160.00),   # symbol: (min_price, max_price)
    "PTT":   (30.00,  45.00),
    "AOT":   (60.00,  80.00),
    "CPALL": (55.00,  75.00),
    "SCB":   (95.00,  115.00),
}

ERROR_TYPES = [
    "price_mismatch",
    "qty_mismatch",
    "missing_broker",
    "missing_exchange",
    "duplicate",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────
# Database
# ─────────────────────────────────────────
def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def truncate_tables(conn):
    """Clear previous simulation data before each run."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE raw_broker_trades, raw_exchange_trades RESTART IDENTITY;")
    conn.commit()
    log.info("Truncated raw_broker_trades and raw_exchange_trades.")


# ─────────────────────────────────────────
# Trade generation
# ─────────────────────────────────────────
def generate_base_trade(traded_at: datetime) -> dict:
    """Generate a single clean trade (same on both sides)."""
    symbol = random.choice(list(SET_SYMBOLS.keys()))
    min_price, max_price = SET_SYMBOLS[symbol]

    return {
        "trade_id":  str(uuid.uuid4()),
        "symbol":    symbol,
        "side":      random.choice(["BUY", "SELL"]),
        "quantity":  random.randint(1, 100) * 100,   # multiples of 100 (board lot)
        "price":     round(random.uniform(min_price, max_price), 2),
        "traded_at": traded_at,
    }


def random_traded_at() -> datetime:
    """Random timestamp within today's trading session (10:00 – 16:30 BKK time)."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    session_start = today + timedelta(hours=10)
    session_end   = today + timedelta(hours=16, minutes=30)
    delta = session_end - session_start
    return session_start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


# ─────────────────────────────────────────
# Error injection
# ─────────────────────────────────────────
def inject_error(broker: dict, exchange: dict, error_type: str) -> tuple[dict | None, dict | None]:
    """
    Modify broker/exchange trade to simulate a reconciliation break.
    Returns (broker_trade, exchange_trade) — None means the trade is omitted from that side.
    """
    if error_type == "price_mismatch":
        # Exchange price differs by a small random amount
        exchange = exchange.copy()
        exchange["price"] = round(exchange["price"] + random.choice([-1, 1]) * round(random.uniform(0.01, 2.00), 2), 2)
        exchange["price"] = max(0.01, exchange["price"])   # price must stay positive

    elif error_type == "qty_mismatch":
        # Exchange quantity differs (e.g. partial fill not updated)
        exchange = exchange.copy()
        exchange["quantity"] = broker["quantity"] + random.choice([-100, 100])
        exchange["quantity"] = max(100, exchange["quantity"])

    elif error_type == "missing_exchange":
        # Trade recorded on broker side but never reached exchange
        exchange = None

    elif error_type == "missing_broker":
        # Trade on exchange side but broker system missed it
        broker = None

    elif error_type == "duplicate":
        # Broker recorded the trade twice (retry bug)
        # The duplicate will be inserted separately in the caller
        pass

    return broker, exchange


# ─────────────────────────────────────────
# Main simulation
# ─────────────────────────────────────────
def simulate(conn):
    broker_rows:   list[tuple] = []
    exchange_rows: list[tuple] = []

    clean_count = 0
    error_counts: dict[str, int] = {e: 0 for e in ERROR_TYPES}

    for _ in range(TRADES_PER_RUN):
        traded_at = random_traded_at()
        base      = generate_base_trade(traded_at)

        broker   = base.copy()
        exchange = base.copy()

        # Decide whether to inject an error
        if random.random() < ERROR_RATE:
            error_type = random.choice(ERROR_TYPES)
            broker, exchange = inject_error(broker, exchange, error_type)
            error_counts[error_type] += 1

            # Handle duplicate: insert broker trade twice
            if error_type == "duplicate" and broker:
                duplicate = broker.copy()
                duplicate["trade_id"] = str(uuid.uuid4())   # new id but same data
                broker_rows.append(_to_row(duplicate))
        else:
            clean_count += 1

        if broker:
            broker_rows.append(_to_row(broker))
        if exchange:
            exchange_rows.append(_to_row(exchange))

    # Bulk insert
    _bulk_insert(conn, "raw_broker_trades",   broker_rows)
    _bulk_insert(conn, "raw_exchange_trades", exchange_rows)

    # Summary
    log.info("── Simulation complete ──────────────────────")
    log.info(f"  Total trades generated : {TRADES_PER_RUN}")
    log.info(f"  Clean trades           : {clean_count}")
    log.info(f"  Errors injected        : {TRADES_PER_RUN - clean_count}")
    for error_type, count in error_counts.items():
        if count:
            log.info(f"    {error_type:<22}: {count}")
    log.info(f"  Broker rows inserted   : {len(broker_rows)}")
    log.info(f"  Exchange rows inserted : {len(exchange_rows)}")


def _to_row(trade: dict) -> tuple:
    return (
        trade["trade_id"],
        trade["symbol"],
        trade["side"],
        trade["quantity"],
        trade["price"],
        trade["traded_at"],
    )


def _bulk_insert(conn, table: str, rows: list[tuple]):
    if not rows:
        return
    sql = f"""
        INSERT INTO {table} (trade_id, symbol, side, quantity, price, traded_at)
        VALUES %s
        ON CONFLICT DO NOTHING
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    conn.commit()
    log.info(f"Inserted {len(rows)} rows into {table}.")


# ─────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────
if __name__ == "__main__":
    log.info("Connecting to database...")
    conn = get_connection()
    log.info("Connected.")

    truncate_tables(conn)
    simulate(conn)

    conn.close()
    log.info("Done.")
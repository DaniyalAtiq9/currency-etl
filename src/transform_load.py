import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "currency_rates.db"
EXPECTED_CURRENCIES = {"EUR", "GBP", "PKR"}

def flatten_record(record):
    payload = record["payload"]
    rate_date = payload["date"]
    base = payload["base"]
    collected_at = record["collected_at_utc"]
    rows = []
    for currency, rate in payload["rates"].items():
        rows.append({
            "date": rate_date,
            "base_currency": base,
            "target_currency": currency,
            "rate": rate,
            "collected_at_utc": collected_at,
        })
    return rows


def flatten_all_records(records):
    all_rows = []
    missing_log = []
    for record in records:
        rows = flatten_record(record)
        present = {row["target_currency"] for row in rows}
        missing = EXPECTED_CURRENCIES - present
        if missing:
            missing_log.append({"date": record["payload"]["date"], "missing_currencies": sorted(missing)})
        all_rows.extend(rows)
    return pd.DataFrame(all_rows), missing_log


def dedupe_by_date(df):
    df = df.sort_values("collected_at_utc")
    df = df.drop_duplicates(subset=["date", "target_currency"], keep="last")
    return df.sort_values(["target_currency", "date"]).reset_index(drop=True)


def add_pct_change(df):
    df = df.sort_values(["target_currency", "date"]).copy()
    df["pct_change"] = df.groupby("target_currency")["rate"].pct_change() * 100
    return df


def load_to_sqlite(df, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            date TEXT NOT NULL,
            base_currency TEXT NOT NULL,
            target_currency TEXT NOT NULL,
            rate REAL NOT NULL,
            pct_change REAL,
            collected_at_utc TEXT NOT NULL,
            PRIMARY KEY (date, base_currency, target_currency)
        )
    """)
    df_clean = df.replace({np.nan: None})
    df_clean.to_sql("exchange_rates_staging", conn, if_exists="replace", index=False)
    conn.execute("""
        INSERT OR REPLACE INTO exchange_rates
        SELECT date, base_currency, target_currency, rate, pct_change, collected_at_utc
        FROM exchange_rates_staging
    """)
    conn.execute("DROP TABLE exchange_rates_staging")
    conn.commit()
    conn.close()
    print(f"Loaded {len(df)} rows into {db_path}")
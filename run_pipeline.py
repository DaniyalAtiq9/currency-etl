"""
run_pipeline.py

Entry point for the automated daily pipeline run.
Called directly by the GitHub Actions workflow.
"""

from src.extract import fetch_rates_with_retry, save_raw_response, load_raw_files
from src.transform_load import flatten_all_records, dedupe_by_date, add_pct_change, load_to_sqlite


def run_pipeline():
    payload = fetch_rates_with_retry()
    save_raw_response(payload, target_date="latest")

    raw_records = load_raw_files()
    df, missing_log = flatten_all_records(raw_records)
    df = dedupe_by_date(df)
    df = add_pct_change(df)

    if missing_log:
        print(f"Missing currencies detected: {missing_log}")

    load_to_sqlite(df)
    print("Pipeline run complete")
    return df


if __name__ == "__main__":
    run_pipeline()
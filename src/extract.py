import json
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
MAX_RETRIES = 3
BACKOFF_SECONDS = 2

class ExtractionError(Exception):
    pass

def fetch_rates_with_retry(target_date="latest", base_currency="USD", symbols=("EUR", "GBP", "PKR")):
    url = f"https://api.frankfurter.dev/v1/{target_date}"
    params = {"base": base_currency, "symbols": ",".join(symbols)}

    last_exception = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Fetching rates (attempt {attempt}/{MAX_RETRIES})")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
            if "rates" not in payload:
                raise ExtractionError(f"Unexpected response shape: {payload}")
            return payload
        except (requests.RequestException, ExtractionError) as exc:
            last_exception = exc
            logger.warning(f"Attempt {attempt} failed: {exc}")
            if attempt < MAX_RETRIES:
                sleep_time = BACKOFF_SECONDS * attempt
                logger.info(f"Retrying in {sleep_time}s...")
                time.sleep(sleep_time)

    raise ExtractionError(f"Failed after {MAX_RETRIES} attempts") from last_exception


def save_raw_response(payload, target_date="latest"):
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    rate_date = payload.get("date", target_date)
    collected_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{rate_date}_{collected_at}.json"
    filepath = RAW_DATA_DIR / filename

    record = {
        "collected_at_utc": collected_at,
        "requested_date": target_date,
        "source": "frankfurter.dev",
        "payload": payload,
    }
    with open(filepath, "w") as f:
        json.dump(record, f, indent=2)
    logger.info(f"Saved raw response to {filepath}")
    return filepath


def load_raw_files():
    records = []
    for filepath in sorted(RAW_DATA_DIR.glob("*.json")):
        with open(filepath) as f:
            records.append(json.load(f))
    return records
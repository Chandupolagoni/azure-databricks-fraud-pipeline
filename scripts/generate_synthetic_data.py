"""Generates small synthetic CSV datasets matching the platform's raw transaction
schema, for practicing the Bronze->Silver->Gold notebooks against Databricks Free
Edition (Unity Catalog volumes) instead of a real ADLS Gen2 landing zone.

Usage:
    python scripts/generate_synthetic_data.py --out-dir ./sample_data --rows 2000

Produces:
    <out-dir>/card-network/transactions.csv   (raw transaction schema)
    <out-dir>/merchant_risk_lookup.csv        (merchant category risk scores)

Upload both into a Unity Catalog volume (e.g. /Volumes/main/fraud_platform/raw/)
and point the Free Edition notebook variants (databricks/notebooks/free_edition/)
at that volume path instead of an abfss:// path. See docs/free_edition_practice.md.
"""

import argparse
import csv
import random
import uuid
from datetime import datetime, timedelta

MERCHANT_CATEGORIES = [
    "grocery", "electronics", "travel", "restaurant", "fuel",
    "online-retail", "utilities", "entertainment", "pharmacy", "jewelry",
]
CHANNELS = ["card-present", "card-not-present", "digital", "atm"]
COUNTRIES = ["US", "US", "US", "US", "CA", "GB", "FR", "IN", "MX", "BR"]  # US-weighted


def _random_card_number() -> str:
    return "4" + "".join(str(random.randint(0, 9)) for _ in range(15))


def _random_ip() -> str:
    return ".".join(str(random.randint(1, 254)) for _ in range(4))


def generate_transactions(n_rows: int, n_accounts: int, n_devices: int, seed: int):
    random.seed(seed)
    accounts = [f"acct_{i:05d}" for i in range(n_accounts)]
    devices = [f"dev_{i:05d}" for i in range(n_devices)]
    merchants = [f"merch_{i:04d}" for i in range(120)]
    merchant_category_map = {m: random.choice(MERCHANT_CATEGORIES) for m in merchants}

    base_ts = datetime(2026, 9, 1)
    rows = []
    for _ in range(n_rows):
        account_id = random.choice(accounts)
        merchant_id = random.choice(merchants)
        ts = base_ts + timedelta(
            days=random.randint(0, 13),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        # Occasionally inject a same-minute "impossible travel" pair for a fun demo signal
        country = random.choice(COUNTRIES) if random.random() > 0.03 else random.choice(COUNTRIES[4:])

        rows.append(
            {
                "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
                "account_id": account_id,
                "card_number": _random_card_number(),
                "merchant_id": merchant_id,
                "merchant_category": merchant_category_map[merchant_id],
                "amount": round(random.expovariate(1 / 85) + 1, 2),
                "currency": "USD",
                "transaction_ts": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "channel": random.choice(CHANNELS),
                "device_id": random.choice(devices),
                "ip_address": _random_ip(),
                "country_code": country,
            }
        )
    return rows, sorted(set(merchant_category_map.values()))


def write_csv(rows, path, fieldnames):
    import os

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="./sample_data")
    parser.add_argument("--rows", type=int, default=2000)
    parser.add_argument("--accounts", type=int, default=150)
    parser.add_argument("--devices", type=int, default=80)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    txns, categories = generate_transactions(args.rows, args.accounts, args.devices, args.seed)

    write_csv(
        txns,
        f"{args.out_dir}/card-network/transactions.csv",
        fieldnames=list(txns[0].keys()),
    )

    risk_rows = [
        {"merchant_category": cat, "merchant_risk_score": round(random.uniform(0.1, 0.9), 2)}
        for cat in categories
    ]
    write_csv(risk_rows, f"{args.out_dir}/merchant_risk_lookup.csv", fieldnames=["merchant_category", "merchant_risk_score"])

    print(f"Wrote {len(txns)} transactions -> {args.out_dir}/card-network/transactions.csv")
    print(f"Wrote {len(risk_rows)} merchant risk rows -> {args.out_dir}/merchant_risk_lookup.csv")


if __name__ == "__main__":
    main()

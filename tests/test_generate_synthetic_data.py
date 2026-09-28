import csv
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "scripts"))

from generate_synthetic_data import (  # noqa: E402
    MERCHANT_CATEGORIES,
    generate_transactions,
    write_csv,
)

EXPECTED_FIELDS = [
    "transaction_id",
    "account_id",
    "card_number",
    "merchant_id",
    "merchant_category",
    "amount",
    "currency",
    "transaction_ts",
    "channel",
    "device_id",
    "ip_address",
    "country_code",
]


def _without_transaction_id(row):
    return {k: v for k, v in row.items() if k != "transaction_id"}


def test_generate_transactions_returns_requested_row_count():
    rows, categories = generate_transactions(n_rows=50, n_accounts=10, n_devices=5, seed=1)

    assert len(rows) == 50
    assert len(categories) > 0


def test_generate_transactions_rows_match_raw_schema():
    rows, _ = generate_transactions(n_rows=20, n_accounts=5, n_devices=3, seed=7)

    for row in rows:
        assert list(row.keys()) == EXPECTED_FIELDS
        assert row["card_number"].startswith("4")
        assert len(row["card_number"]) == 16
        assert row["amount"] > 0
        assert row["currency"] == "USD"
        assert row["account_id"].startswith("acct_")
        assert row["device_id"].startswith("dev_")
        assert row["merchant_category"] in MERCHANT_CATEGORIES


def test_generate_transactions_is_deterministic_for_a_given_seed():
    # transaction_id is a fresh uuid4 on every call (not driven by random.seed), so it's
    # deliberately excluded here — everything else in the row is expected to line up exactly
    # for a repeated seed, which is what lets a Free Edition practice run be reproduced.
    rows_a, categories_a = generate_transactions(n_rows=25, n_accounts=8, n_devices=4, seed=42)
    rows_b, categories_b = generate_transactions(n_rows=25, n_accounts=8, n_devices=4, seed=42)

    assert categories_a == categories_b
    assert [_without_transaction_id(r) for r in rows_a] == [_without_transaction_id(r) for r in rows_b]


def test_generate_transactions_differs_across_seeds():
    rows_a, _ = generate_transactions(n_rows=25, n_accounts=8, n_devices=4, seed=1)
    rows_b, _ = generate_transactions(n_rows=25, n_accounts=8, n_devices=4, seed=2)

    accounts_a = [row["account_id"] for row in rows_a]
    accounts_b = [row["account_id"] for row in rows_b]
    assert accounts_a != accounts_b


def test_generate_transactions_merchant_category_is_stable_per_merchant():
    rows, _ = generate_transactions(n_rows=200, n_accounts=30, n_devices=10, seed=3)

    category_by_merchant = {}
    for row in rows:
        merchant_id, category = row["merchant_id"], row["merchant_category"]
        assert category_by_merchant.setdefault(merchant_id, category) == category


def test_generate_transactions_returned_categories_match_rows_and_have_no_duplicates():
    rows, categories = generate_transactions(n_rows=300, n_accounts=40, n_devices=10, seed=9)

    assert len(categories) == len(set(categories))
    assert set(categories).issubset(set(MERCHANT_CATEGORIES))
    assert {row["merchant_category"] for row in rows}.issubset(set(categories))


def test_write_csv_creates_parent_dirs_and_matching_row_count(tmp_path):
    rows, _ = generate_transactions(n_rows=10, n_accounts=4, n_devices=2, seed=5)
    out_path = tmp_path / "nested" / "dir" / "transactions.csv"

    write_csv(rows, str(out_path), fieldnames=list(rows[0].keys()))

    assert out_path.exists()
    with open(out_path, newline="") as f:
        written_rows = list(csv.DictReader(f))

    assert len(written_rows) == len(rows)
    assert written_rows[0]["transaction_id"] == rows[0]["transaction_id"]
    assert written_rows[0]["account_id"] == rows[0]["account_id"]

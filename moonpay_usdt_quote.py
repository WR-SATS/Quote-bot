#!/usr/bin/env python3
"""Fetch MoonPay buy quotes and print as a markdown table.

Examples:
  python moonpay_usdt_quote.py --fiat HKD --crypto USDT --amount 1000
  python moonpay_usdt_quote.py --fiat HKD --crypto USDT --amounts 500,1000,2000
  python moonpay_usdt_quote.py --fiat HKD --crypto USDT --amounts 1000,2000 --watch --iterations 3
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


@dataclass
class QuoteRow:
    timestamp_utc: str
    fiat: str
    fiat_amount: float
    crypto: str
    crypto_amount_text: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get MoonPay quotes and print a table")
    parser.add_argument("--fiat", default="HKD", help="Fiat currency code shown in widget")
    parser.add_argument("--crypto", default="USDT", help="Crypto symbol to buy")
    parser.add_argument("--amount", type=float, help="Single fiat amount")
    parser.add_argument(
        "--amounts",
        help="Comma-separated fiat amounts (e.g. 500,1000,2000)",
    )
    parser.add_argument("--url", default="https://www.moonpay.com/buy", help="MoonPay buy page URL")
    parser.add_argument("--timeout-ms", type=int, default=45000, help="Playwright timeout")
    parser.add_argument("--csv", help="Optional CSV output path")
    parser.add_argument("--watch", action="store_true", help="Repeatedly refresh quotes")
    parser.add_argument("--interval-sec", type=float, default=20.0, help="Watch interval seconds")
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of watch loops (default 1; ignored if --watch is off)",
    )
    return parser.parse_args()


def parse_amounts(single: float | None, many: str | None) -> list[float]:
    values: list[float] = []
    if single is not None:
        values.append(single)
    if many:
        for raw in many.split(","):
            raw = raw.strip()
            if raw:
                values.append(float(raw))
    values = [v for v in values if v > 0]
    if not values:
        raise ValueError("You must provide --amount or --amounts, and value must be > 0")
    # Keep input order but de-duplicate.
    deduped: list[float] = []
    seen: set[float] = set()
    for v in values:
        if v not in seen:
            deduped.append(v)
            seen.add(v)
    return deduped


def _set_fiat(page, fiat: str) -> None:
    fiat_button = page.locator("button").filter(has_text=re.compile(r"^[A-Z]{3}$")).first
    fiat_button.click()
    page.locator(f"[role='option']:has-text('{fiat}')").first.click()


def _select_token(page, token: str) -> None:
    token_button = page.locator("button:has-text('Buy')").first
    token_button.click()
    page.locator(f"[role='option']:has-text('{token}')").first.click()


def _set_amount(page, amount: float) -> None:
    amount_text = f"{amount:g}"
    amount_input = page.locator("input[type='text'], input[inputmode='decimal'], input[inputmode='numeric']").first
    amount_input.click()
    amount_input.fill("")
    amount_input.type(amount_text, delay=15)


def _read_crypto_amount(page, crypto: str) -> str:
    escaped = re.escape(crypto)
    locator = page.locator(f"text=/[0-9][0-9,\\.]*\\s*{escaped}/i").first
    return (locator.text_content() or "").strip()


def collect_quotes(url: str, fiat: str, crypto: str, amounts: Iterable[float], timeout_ms: int) -> list[QuoteRow]:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    rows: list[QuoteRow] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(2000)

        try:
            page.locator("button:has-text('Accept'), button:has-text('Agree')").first.click(timeout=2000)
        except PlaywrightTimeoutError:
            pass

        _set_fiat(page, fiat)
        _select_token(page, crypto)

        for amount in amounts:
            _set_amount(page, amount)
            page.wait_for_timeout(2200)
            crypto_amount_text = _read_crypto_amount(page, crypto)
            if not crypto_amount_text:
                raise RuntimeError(f"Unable to read quote for amount={amount:g} {fiat}")

            rows.append(
                QuoteRow(
                    timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    fiat=fiat,
                    fiat_amount=amount,
                    crypto=crypto,
                    crypto_amount_text=crypto_amount_text,
                )
            )

        browser.close()
    return rows


def render_markdown_table(rows: list[QuoteRow]) -> str:
    lines = [
        "| Timestamp (UTC) | Fiat | Fiat Amount | Crypto | Quote |",
        "|---|---|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.timestamp_utc} | {row.fiat} | {row.fiat_amount:g} | {row.crypto} | {row.crypto_amount_text} |"
        )
    return "\n".join(lines)


def append_csv(path: str, rows: list[QuoteRow]) -> None:
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if f.tell() == 0:
            writer.writerow(["timestamp_utc", "fiat", "fiat_amount", "crypto", "quote"])
        for row in rows:
            writer.writerow([row.timestamp_utc, row.fiat, row.fiat_amount, row.crypto, row.crypto_amount_text])


def main() -> int:
    args = parse_args()
    try:
        amounts = parse_amounts(args.amount, args.amounts)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    loops = args.iterations if args.watch else 1
    loops = max(1, loops)

    all_rows: list[QuoteRow] = []
    for i in range(loops):
        try:
            batch = collect_quotes(
                url=args.url,
                fiat=args.fiat.upper(),
                crypto=args.crypto.upper(),
                amounts=amounts,
                timeout_ms=args.timeout_ms,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to fetch quotes: {exc}", file=sys.stderr)
            return 1

        all_rows.extend(batch)
        table = render_markdown_table(batch)
        print(table)

        if args.csv:
            append_csv(args.csv, batch)

        if i < loops - 1:
            time.sleep(args.interval_sec)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

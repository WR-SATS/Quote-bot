#!/usr/bin/env python3
"""Multi-provider crypto on-ramp quote collector.

This CLI supports querying multiple channels (MoonPay/Banxa/Transit) and
printing a unified markdown table. It also supports small/large amount sets,
payment method filters, and network/asset parameters.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


@dataclass
class QuoteRow:
    timestamp_utc: str
    provider: str
    fiat: str
    fiat_amount: float
    asset: str
    network: str
    payment_method: str
    quote_text: str
    status: str
    note: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get crypto on-ramp quotes and print a table")
    parser.add_argument("--fiat", default="USD", help="Fiat currency code")
    parser.add_argument("--asset", default="USDT", help="Asset symbol (USDT/ETH/BTC etc.)")
    parser.add_argument("--network", default="ethereum", help="Network (ethereum/tron/bsc/...) for token assets")
    parser.add_argument("--payment-methods", default="visa", help="Comma-separated payment methods, e.g. visa,apple_pay")
    parser.add_argument("--amount", type=float, help="Single fiat amount")
    parser.add_argument("--amounts", default="50,100,200", help="Comma-separated fiat amounts")
    parser.add_argument(
        "--providers",
        default="moonpay,banxa,transit",
        help="Comma-separated providers (moonpay,banxa,transit,demo)",
    )
    parser.add_argument("--timeout-ms", type=int, default=45000, help="Request timeout in milliseconds")
    parser.add_argument("--csv", help="Optional CSV output path")
    parser.add_argument("--watch", action="store_true", help="Repeatedly refresh quotes")
    parser.add_argument("--interval-sec", type=float, default=20.0, help="Watch interval seconds")
    parser.add_argument("--iterations", type=int, default=1, help="Watch loop count")
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="Do not exit on provider errors; include error rows in output",
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
        raise ValueError("You must provide positive amount(s)")

    deduped: list[float] = []
    seen: set[float] = set()
    for v in values:
        if v not in seen:
            deduped.append(v)
            seen.add(v)
    return deduped


def parse_csv_list(raw: str) -> list[str]:
    values = [x.strip() for x in raw.split(",") if x.strip()]
    if not values:
        raise ValueError("CSV list parameter cannot be empty")
    return values


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _http_get_json(url: str, timeout_s: float) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 quote-collector"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        content = resp.read().decode("utf-8", errors="replace")
    return json.loads(content)


def _extract_quote_text(payload: dict, asset: str) -> str | None:
    # Try common keys found in quote APIs.
    candidates = [
        payload.get("quoteCurrencyAmount"),
        payload.get("quoteAmount"),
        payload.get("cryptoAmount"),
        payload.get("amount"),
        payload.get("finalAmount"),
    ]
    nested = payload.get("quote")
    if isinstance(nested, dict):
        candidates.extend(
            [
                nested.get("quoteCurrencyAmount"),
                nested.get("quoteAmount"),
                nested.get("cryptoAmount"),
                nested.get("amount"),
                nested.get("finalAmount"),
            ]
        )

    for value in candidates:
        if value is not None:
            return f"{value} {asset}"
    return None


def fetch_moonpay_quote(fiat: str, asset: str, amount: float, timeout_ms: int) -> str:
    timeout_s = max(1.0, timeout_ms / 1000.0)
    params = urllib.parse.urlencode(
        {
            "baseCurrencyAmount": f"{amount:g}",
            "baseCurrencyCode": fiat.lower(),
            "quoteCurrencyCode": asset.lower(),
        }
    )
    endpoint = f"https://api.moonpay.com/v3/buy_quote?{params}"
    payload = _http_get_json(endpoint, timeout_s)
    quote = _extract_quote_text(payload, asset)
    if not quote:
        raise RuntimeError("MoonPay response missing quote amount")
    return quote


def fetch_banxa_quote(fiat: str, asset: str, amount: float, payment_method: str, timeout_ms: int) -> str:
    timeout_s = max(1.0, timeout_ms / 1000.0)
    # Banxa public API behavior may vary by region / API policy.
    params = urllib.parse.urlencode(
        {
            "fiatType": fiat.upper(),
            "coinType": asset.upper(),
            "fiatAmount": f"{amount:g}",
            "paymentMethod": payment_method.lower(),
        }
    )
    endpoint = f"https://api.banxa.com/quotes?{params}"
    payload = _http_get_json(endpoint, timeout_s)

    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list) and data:
            item = data[0]
            coin = item.get("coinAmount") or item.get("coinAmountAfterFee") or item.get("coinAmountGross")
            if coin is not None:
                return f"{coin} {asset}"

    quote = _extract_quote_text(payload if isinstance(payload, dict) else {}, asset)
    if not quote:
        raise RuntimeError("Banxa response missing quote amount")
    return quote


def fetch_transit_quote(fiat: str, asset: str, amount: float, network: str, payment_method: str, timeout_ms: int) -> str:
    # Public transit aggregator API is not documented; attempt a likely endpoint first.
    timeout_s = max(1.0, timeout_ms / 1000.0)
    params = urllib.parse.urlencode(
        {
            "fiat": fiat.upper(),
            "asset": asset.upper(),
            "amount": f"{amount:g}",
            "network": network.lower(),
            "paymentMethod": payment_method.lower(),
        }
    )
    endpoint = f"https://buy.transit.finance/api/ramp/quote?{params}"
    payload = _http_get_json(endpoint, timeout_s)

    quote = _extract_quote_text(payload if isinstance(payload, dict) else {}, asset)
    if quote:
        return quote

    if isinstance(payload, dict):
        routes = payload.get("routes") or payload.get("quotes") or payload.get("data")
        if isinstance(routes, list) and routes:
            first = routes[0]
            if isinstance(first, dict):
                value = first.get("toAmount") or first.get("cryptoAmount") or first.get("amount")
                if value is not None:
                    return f"{value} {asset}"

    raise RuntimeError("Transit response missing quote amount")


def fetch_demo_quote(asset: str, amount: float, provider: str) -> str:
    # local fallback for testing output formatting without external network
    ratio = {"moonpay": 0.985, "banxa": 0.958, "transit": 0.973, "demo": 0.96}.get(provider, 0.95)
    return f"{amount * ratio:.4f} {asset}"


def collect_quotes(
    providers: list[str],
    fiat: str,
    asset: str,
    network: str,
    payment_methods: list[str],
    amounts: Iterable[float],
    timeout_ms: int,
    allow_failures: bool,
) -> list[QuoteRow]:
    rows: list[QuoteRow] = []

    for provider in providers:
        for payment_method in payment_methods:
            for amount in amounts:
                try:
                    if provider == "moonpay":
                        quote = fetch_moonpay_quote(fiat=fiat, asset=asset, amount=amount, timeout_ms=timeout_ms)
                        note = "payment/network filters may be ignored by moonpay public quote"
                    elif provider == "banxa":
                        quote = fetch_banxa_quote(
                            fiat=fiat,
                            asset=asset,
                            amount=amount,
                            payment_method=payment_method,
                            timeout_ms=timeout_ms,
                        )
                        note = ""
                    elif provider == "transit":
                        quote = fetch_transit_quote(
                            fiat=fiat,
                            asset=asset,
                            amount=amount,
                            network=network,
                            payment_method=payment_method,
                            timeout_ms=timeout_ms,
                        )
                        note = ""
                    elif provider == "demo":
                        quote = fetch_demo_quote(asset=asset, amount=amount, provider=provider)
                        note = "demo data"
                    else:
                        raise RuntimeError(f"Unsupported provider: {provider}")

                    rows.append(
                        QuoteRow(
                            timestamp_utc=utc_now(),
                            provider=provider,
                            fiat=fiat,
                            fiat_amount=amount,
                            asset=asset,
                            network=network,
                            payment_method=payment_method,
                            quote_text=quote,
                            status="ok",
                            note=note,
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    if not allow_failures:
                        raise
                    rows.append(
                        QuoteRow(
                            timestamp_utc=utc_now(),
                            provider=provider,
                            fiat=fiat,
                            fiat_amount=amount,
                            asset=asset,
                            network=network,
                            payment_method=payment_method,
                            quote_text="",
                            status="error",
                            note=str(exc),
                        )
                    )

    return rows


def render_markdown_table(rows: list[QuoteRow]) -> str:
    lines = [
        "| Timestamp (UTC) | Provider | Fiat | Amount | Asset | Network | Payment | Quote | Status | Note |",
        "|---|---|---|---:|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.timestamp_utc} | {r.provider} | {r.fiat} | {r.fiat_amount:g} | {r.asset} | {r.network} | {r.payment_method} | {r.quote_text} | {r.status} | {r.note} |"
        )
    return "\n".join(lines)


def append_csv(path: str, rows: list[QuoteRow]) -> None:
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if f.tell() == 0:
            writer.writerow(
                [
                    "timestamp_utc",
                    "provider",
                    "fiat",
                    "fiat_amount",
                    "asset",
                    "network",
                    "payment_method",
                    "quote",
                    "status",
                    "note",
                ]
            )
        for r in rows:
            writer.writerow(
                [
                    r.timestamp_utc,
                    r.provider,
                    r.fiat,
                    r.fiat_amount,
                    r.asset,
                    r.network,
                    r.payment_method,
                    r.quote_text,
                    r.status,
                    r.note,
                ]
            )


def main() -> int:
    args = parse_args()

    try:
        amounts = parse_amounts(args.amount, args.amounts)
        providers = parse_csv_list(args.providers.lower())
        payment_methods = parse_csv_list(args.payment_methods.lower())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    loops = max(1, args.iterations if args.watch else 1)

    for i in range(loops):
        try:
            batch = collect_quotes(
                providers=providers,
                fiat=args.fiat.upper(),
                asset=args.asset.upper(),
                network=args.network.lower(),
                payment_methods=payment_methods,
                amounts=amounts,
                timeout_ms=args.timeout_ms,
                allow_failures=args.allow_failures,
            )
        except urllib.error.URLError as exc:
            print(f"Failed to fetch quotes: network/proxy error: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to fetch quotes: {exc}", file=sys.stderr)
            return 1

        print(render_markdown_table(batch))
        if args.csv:
            append_csv(args.csv, batch)

        if i < loops - 1:
            time.sleep(args.interval_sec)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

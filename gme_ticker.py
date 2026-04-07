#!/usr/bin/env python3
"""
GME Stock Ticker for Divoom Ditoo (16x16 pixel Bluetooth LED speaker).

Usage:
    python3 gme_ticker.py --mac XX:XX:XX:XX:XX:XX
    python3 gme_ticker.py --mac XX:XX:XX:XX:XX:XX --interval 60
    python3 gme_ticker.py --mac XX:XX:XX:XX:XX:XX --symbol AAPL

Requires: Linux with BlueZ, Python 3.7+, Pillow, requests
"""

import argparse
import time
import urllib.parse

import requests
from PIL import Image

from ditoo import DitooDevice, draw_text, text_width


def fetch_stock_price(symbol="GME"):
    """Fetch current stock price and change from Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
    params = {"interval": "1d", "range": "2d"}
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        result = data["chart"]["result"][0]
        meta = result["meta"]
        price = meta["regularMarketPrice"]
        prev_close = meta.get("chartPreviousClose", meta.get("previousClose", price))
        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        return {
            "symbol": symbol.upper(),
            "price": price,
            "change": change,
            "change_pct": change_pct,
        }
    except Exception as e:
        print(f"Error fetching stock data: {e}")
        return None


def render_ticker(stock_data):
    """Create a 16x16 PIL Image showing stock ticker info."""
    img = Image.new("RGB", (16, 16), (0, 0, 0))

    if stock_data is None:
        draw_text(img, "ERR", 2, 5, (255, 0, 0))
        return img

    symbol = stock_data["symbol"]
    price = stock_data["price"]
    change = stock_data["change"]
    change_pct = stock_data["change_pct"]

    if change > 0:
        price_color = (0, 255, 0)
    elif change < 0:
        price_color = (255, 0, 0)
    else:
        price_color = (255, 255, 255)

    # Row 1 (y=0): Symbol in white, centered
    sym_w = text_width(symbol)
    sym_x = max(0, (16 - sym_w) // 2)
    draw_text(img, symbol, sym_x, 0, (255, 255, 255))

    # Row 2 (y=6): Price - reduce precision to fit
    for fmt in [f"{price:.2f}", f"{price:.1f}", f"{price:.0f}"]:
        if text_width(fmt) <= 16:
            price_str = fmt
            break
    else:
        price_str = f"{price:.0f}"

    pw = text_width(price_str)
    px = max(0, (16 - pw) // 2)
    draw_text(img, price_str, px, 6, price_color)

    # Row 3 (y=11): Change percent
    for fmt in [f"{change_pct:+.1f}%", f"{change_pct:+.0f}%"]:
        if text_width(fmt) <= 16:
            pct_str = fmt
            break
    else:
        pct_str = f"{change_pct:+.0f}%"

    cw = text_width(pct_str)
    cx = max(0, (16 - cw) // 2)
    draw_text(img, pct_str, cx, 11, price_color)

    return img


def main():
    parser = argparse.ArgumentParser(description="GME Stock Ticker for Divoom Ditoo")
    parser.add_argument(
        "--mac", required=True,
        help="Bluetooth MAC address of Ditoo (e.g. AA:BB:CC:DD:EE:FF)"
    )
    parser.add_argument(
        "--symbol", default="GME",
        help="Stock ticker symbol (default: GME)"
    )
    parser.add_argument(
        "--interval", type=int, default=60,
        help="Update interval in seconds (default: 60)"
    )
    parser.add_argument(
        "--brightness", type=int, default=50,
        help="Display brightness 0-100 (default: 50)"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Fetch and display once, then exit"
    )
    args = parser.parse_args()

    ditoo = DitooDevice(args.mac)
    ditoo.connect_with_retry()

    try:
        ditoo.set_brightness(args.brightness)
        time.sleep(0.3)
        ditoo.set_custom()
        time.sleep(0.3)

        while True:
            print(f"Fetching {args.symbol} price...")
            stock = fetch_stock_price(args.symbol)

            if stock:
                print(
                    f"  {stock['symbol']}: ${stock['price']:.2f} "
                    f"({stock['change_pct']:+.2f}%)"
                )
            else:
                print("  Failed to fetch price.")

            img = render_ticker(stock)
            ditoo.send_image(img)
            print("  Display updated.")

            if args.once:
                break

            print(f"  Next update in {args.interval}s...")
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        ditoo.disconnect()


if __name__ == "__main__":
    main()

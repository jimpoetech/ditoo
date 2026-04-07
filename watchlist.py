#!/usr/bin/env python3
"""
Stock Watchlist for Divoom Ditoo Pro.

Auto-rotates through a list of stock tickers, with keyboard controls:
  Right/Down or Space: next stock
  Left/Up:             previous stock
  +/-:                 adjust rotation interval
  p:                   pause/resume auto-rotation
  r:                   force refresh current stock
  q or Ctrl+C:         quit

Usage:
    python3 watchlist.py --mac XX:XX:XX:XX:XX:XX
    python3 watchlist.py --mac XX:XX:XX:XX:XX:XX --symbols GME,AMC,AAPL,TSLA
    python3 watchlist.py --mac XX:XX:XX:XX:XX:XX --rotate 30
"""

import argparse
import sys
import select
import termios
import tty
import time
import threading
import urllib.parse

import requests
from PIL import Image

from ditoo import DitooDevice, draw_text, text_width


def fetch_stock_price(symbol):
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
        print(f"\rError fetching {symbol}: {e}")
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

    sym_w = text_width(symbol)
    sym_x = max(0, (16 - sym_w) // 2)
    draw_text(img, symbol, sym_x, 0, (255, 255, 255))

    for fmt in [f"{price:.2f}", f"{price:.1f}", f"{price:.0f}"]:
        if text_width(fmt) <= 16:
            price_str = fmt
            break
    else:
        price_str = f"{price:.0f}"

    pw = text_width(price_str)
    px = max(0, (16 - pw) // 2)
    draw_text(img, price_str, px, 6, price_color)

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


def read_key():
    """Non-blocking read of a single keypress. Returns key string or None."""
    if select.select([sys.stdin], [], [], 0)[0]:
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            # Arrow key escape sequence
            if select.select([sys.stdin], [], [], 0.05)[0]:
                ch2 = sys.stdin.read(1)
                if ch2 == '[' and select.select([sys.stdin], [], [], 0.05)[0]:
                    ch3 = sys.stdin.read(1)
                    return {'A': 'up', 'B': 'down', 'C': 'right', 'D': 'left'}.get(ch3)
            return 'esc'
        return ch
    return None


def main():
    parser = argparse.ArgumentParser(description="Stock Watchlist for Divoom Ditoo")
    parser.add_argument("--mac", required=True, help="Bluetooth MAC address")
    parser.add_argument(
        "--symbols", default="GME,GMEW=GME-WT,BYND,BTC=BTC-USD",
        help="Comma-separated stock symbols (default: GME,GMEW=GME-WT,BYND,BTC=BTC-USD)"
    )
    parser.add_argument(
        "--rotate", type=int, default=15,
        help="Auto-rotate interval in seconds (default: 15)"
    )
    parser.add_argument(
        "--brightness", type=int, default=50,
        help="Display brightness 0-100 (default: 50)"
    )
    args = parser.parse_args()

    # Support display aliases: "BTC=BTC-USD" shows "BTC" but fetches "BTC-USD"
    symbols = []      # display names
    fetch_map = {}    # display name -> Yahoo symbol
    for s in args.symbols.split(","):
        s = s.strip().upper()
        if "=" in s:
            display, yahoo = s.split("=", 1)
            symbols.append(display)
            fetch_map[display] = yahoo
        else:
            symbols.append(s)
            fetch_map[s] = s
    index = 0
    rotate_interval = args.rotate
    paused = False
    cache = {}
    cache_age = {}
    cache_ttl = 60  # refetch after 60s

    ditoo = DitooDevice(args.mac)
    ditoo.connect_with_retry()
    ditoo.set_brightness(args.brightness)
    time.sleep(0.3)
    ditoo.set_custom()
    time.sleep(0.3)

    # Set terminal to raw mode for keypress detection (if interactive)
    interactive = sys.stdin.isatty()
    old_settings = None
    if interactive:
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())

    def get_stock(display_name):
        now = time.time()
        if display_name in cache and now - cache_age.get(display_name, 0) < cache_ttl:
            return cache[display_name]
        yahoo_sym = fetch_map[display_name]
        data = fetch_stock_price(yahoo_sym)
        if data:
            data["symbol"] = display_name  # show display name, not Yahoo symbol
            cache[display_name] = data
            cache_age[display_name] = now
        return data or cache.get(display_name)

    def show_current():
        sym = symbols[index]
        stock = get_stock(sym)
        img = render_ticker(stock)
        try:
            ditoo.send_image(img)
        except (OSError, ConnectionError):
            ditoo.disconnect()
            ditoo.connect_with_retry()
            ditoo.set_custom()
            time.sleep(0.3)
            ditoo.send_image(img)

        if stock:
            print(f"\r\x1b[K  [{index+1}/{len(symbols)}] {stock['symbol']}: "
                  f"${stock['price']:.2f} ({stock['change_pct']:+.2f}%)  "
                  f"{'[PAUSED]' if paused else f'[{rotate_interval}s]'}", end="", flush=True)
        else:
            print(f"\r\x1b[K  [{index+1}/{len(symbols)}] {sym}: fetch failed", end="", flush=True)

    try:
        print("Stock Watchlist — arrows/space: cycle, +/-: interval, p: pause, q: quit")
        show_current()
        last_rotate = time.time()

        while True:
            key = read_key() if interactive else None

            if key in ('q', '\x03'):  # q or Ctrl+C
                break
            elif key in ('right', 'down', ' '):
                index = (index + 1) % len(symbols)
                show_current()
                last_rotate = time.time()
            elif key in ('left', 'up'):
                index = (index - 1) % len(symbols)
                show_current()
                last_rotate = time.time()
            elif key == '+' or key == '=':
                rotate_interval = min(300, rotate_interval + 5)
                print(f"\r\x1b[K  Rotate interval: {rotate_interval}s", end="", flush=True)
                time.sleep(0.5)
                show_current()
            elif key == '-':
                rotate_interval = max(5, rotate_interval - 5)
                print(f"\r\x1b[K  Rotate interval: {rotate_interval}s", end="", flush=True)
                time.sleep(0.5)
                show_current()
            elif key == 'p':
                paused = not paused
                show_current()
            elif key == 'r':
                sym = symbols[index]
                cache_age.pop(sym, None)
                show_current()

            # Auto-rotate
            if not paused and time.time() - last_rotate >= rotate_interval:
                index = (index + 1) % len(symbols)
                show_current()
                last_rotate = time.time()

            time.sleep(0.1)

    except KeyboardInterrupt:
        pass
    finally:
        if old_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print("\nStopping...")
        ditoo.disconnect()


if __name__ == "__main__":
    main()

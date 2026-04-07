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
import json
import socket
import struct
import time
import urllib.parse
from math import ceil, log2
from io import BytesIO

from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Tiny 3x5 bitmap font for digits, letters, and symbols
# Each char is 3 wide x 5 tall. Stored as list of 5 rows, each row is 3 bits.
# Bit order: MSB = left pixel
# ---------------------------------------------------------------------------
FONT_3x5 = {
    '0': [0b111, 0b101, 0b101, 0b101, 0b111],
    '1': [0b010, 0b110, 0b010, 0b010, 0b111],
    '2': [0b111, 0b001, 0b111, 0b100, 0b111],
    '3': [0b111, 0b001, 0b111, 0b001, 0b111],
    '4': [0b101, 0b101, 0b111, 0b001, 0b001],
    '5': [0b111, 0b100, 0b111, 0b001, 0b111],
    '6': [0b111, 0b100, 0b111, 0b101, 0b111],
    '7': [0b111, 0b001, 0b001, 0b001, 0b001],
    '8': [0b111, 0b101, 0b111, 0b101, 0b111],
    '9': [0b111, 0b101, 0b111, 0b001, 0b111],
    '.': [0b000, 0b000, 0b000, 0b000, 0b100],
    '-': [0b000, 0b000, 0b111, 0b000, 0b000],
    '+': [0b000, 0b010, 0b111, 0b010, 0b000],
    '%': [0b101, 0b001, 0b010, 0b100, 0b101],
    '$': [0b011, 0b110, 0b010, 0b011, 0b110],
    ' ': [0b000, 0b000, 0b000, 0b000, 0b000],
    'G': [0b111, 0b100, 0b101, 0b101, 0b111],
    'M': [0b101, 0b111, 0b111, 0b101, 0b101],
    'E': [0b111, 0b100, 0b111, 0b100, 0b111],
    'A': [0b010, 0b101, 0b111, 0b101, 0b101],
    'P': [0b111, 0b101, 0b111, 0b100, 0b100],
    'L': [0b100, 0b100, 0b100, 0b100, 0b111],
    'K': [0b101, 0b110, 0b100, 0b110, 0b101],
}


def draw_char(img, ch, x, y, color):
    """Draw a single 3x5 character onto a PIL Image."""
    glyph = FONT_3x5.get(ch.upper())
    if glyph is None:
        return
    for row_i, row_bits in enumerate(glyph):
        for col_i in range(3):
            if row_bits & (1 << (2 - col_i)):
                px, py = x + col_i, y + row_i
                if 0 <= px < 16 and 0 <= py < 16:
                    img.putpixel((px, py), color)


# Characters that are narrower than 3px get special width
CHAR_WIDTH = {'.': 1, ' ': 2}


def char_width(ch):
    return CHAR_WIDTH.get(ch.upper(), 3)


def draw_text(img, text, x, y, color):
    """Draw a string using the 3x5 font. Returns ending x position."""
    cursor = x
    for ch in text:
        draw_char(img, ch, cursor, y, color)
        cursor += char_width(ch) + 1  # char width + 1px spacing
    return cursor


def text_width(text):
    """Calculate pixel width of a string in the 3x5 font."""
    if not text:
        return 0
    w = sum(char_width(ch) + 1 for ch in text) - 1  # subtract trailing gap
    return w


# ---------------------------------------------------------------------------
# Stock price fetching via Yahoo Finance
# ---------------------------------------------------------------------------

def fetch_stock_price(symbol="GME"):
    """Fetch current stock price and change from Yahoo Finance."""
    import requests

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


# ---------------------------------------------------------------------------
# Render a 16x16 image for the stock ticker
# ---------------------------------------------------------------------------

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

    # Color: green if up, red if down, white if flat
    if change > 0:
        price_color = (0, 255, 0)
        arrow = "+"
    elif change < 0:
        price_color = (255, 0, 0)
        arrow = ""  # minus sign is part of the number
    else:
        price_color = (255, 255, 255)
        arrow = ""

    # Row 1 (y=0): Symbol in white, centered
    sym_w = text_width(symbol)
    sym_x = max(0, (16 - sym_w) // 2)
    draw_text(img, symbol, sym_x, 0, (255, 255, 255))

    # Row 2 (y=6): Price - progressively reduce precision to fit 16px
    for fmt in [f"{price:.2f}", f"{price:.1f}", f"{price:.0f}"]:
        if text_width(fmt) <= 16:
            price_str = fmt
            break
    else:
        price_str = f"{price:.0f}"

    pw = text_width(price_str)
    px = max(0, (16 - pw) // 2)
    draw_text(img, price_str, px, 6, price_color)

    # Row 3 (y=11): Change percent - fit within 16px
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


# ---------------------------------------------------------------------------
# Divoom Ditoo Bluetooth Protocol
# ---------------------------------------------------------------------------

class DitooConnection:
    """Bluetooth RFCOMM connection to a Divoom Ditoo."""

    RFCOMM_PORT = 1

    def __init__(self, mac_address):
        self.mac = mac_address
        self.sock = None

    def connect(self):
        """Establish Bluetooth RFCOMM connection."""
        print(f"Connecting to Ditoo at {self.mac}...")
        self.sock = socket.socket(
            socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM
        )
        self.sock.connect((self.mac, self.RFCOMM_PORT))
        time.sleep(1)  # Wait for device to be ready
        print("Connected!")

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            print("Disconnected.")

    def _build_packet(self, command, args):
        """Build a framed Divoom protocol packet."""
        # Payload = size(2) + command(1) + args
        payload_len = len(args) + 3
        size_lo = payload_len & 0xFF
        size_hi = (payload_len >> 8) & 0xFF

        # Frame without start byte, CRC, end byte
        frame_body = [size_lo, size_hi, command] + list(args)

        # Checksum: sum of all bytes in frame_body
        checksum = sum(frame_body) & 0xFFFF
        crc_lo = checksum & 0xFF
        crc_hi = (checksum >> 8) & 0xFF

        # Full packet: 0x01 + frame_body + CRC + 0x02
        packet = bytes([0x01] + frame_body + [crc_lo, crc_hi, 0x02])
        return packet

    def _send_raw(self, packet):
        """Send raw bytes over Bluetooth."""
        self.sock.send(packet)

    def send_command(self, command, args=None):
        """Send a command to the Ditoo."""
        if args is None:
            args = []
        packet = self._build_packet(command, args)
        self._send_raw(packet)

    def set_brightness(self, brightness):
        """Set display brightness (0-100)."""
        brightness = max(0, min(100, brightness))
        self.send_command(0x74, [brightness])

    def send_image(self, img):
        """Send a 16x16 RGB PIL Image to the Ditoo display."""
        assert img.size == (16, 16), "Image must be 16x16"
        img = img.convert("RGB")

        # Build palette and pixel indices
        pixels = []
        palette = []
        palette_map = {}

        for y in range(16):
            for x in range(16):
                r, g, b = img.getpixel((x, y))
                color = (r, g, b)
                if color not in palette_map:
                    palette_map[color] = len(palette)
                    palette.append(color)
                pixels.append(palette_map[color])

        num_colors = len(palette)

        # Palette bytes
        palette_bytes = []
        for r, g, b in palette:
            palette_bytes.extend([r, g, b])

        # Bit-pack pixel indices
        if num_colors <= 1:
            bitwidth = 1
        else:
            bitwidth = ceil(log2(num_colors))
            if bitwidth == 0:
                bitwidth = 1

        pixel_bytes = []
        encoded = ''
        for idx in pixels:
            encoded = bin(idx)[2:].rjust(bitwidth, '0') + encoded
            if len(encoded) >= 8:
                pixel_bytes.append(int(encoded[-8:], 2))
                encoded = encoded[:-8]
        if encoded:
            pixel_bytes.append(int(encoded.ljust(8, '0'), 2))

        # Frame data
        num_colors_byte = 0x00 if num_colors == 256 else num_colors
        frame_data = []
        frame_inner_size = 7 + len(palette_bytes) + len(pixel_bytes)
        frame_data.append(0xAA)
        frame_data.append(frame_inner_size & 0xFF)
        frame_data.append((frame_inner_size >> 8) & 0xFF)
        frame_data.extend([0x00, 0x00, 0x00])  # timecode=0, reset=0
        frame_data.append(num_colors_byte)
        frame_data.extend(palette_bytes)
        frame_data.extend(pixel_bytes)

        # Command 0x44 with prefix [0x00, 0x0A, 0x0A, 0x04]
        args = [0x00, 0x0A, 0x0A, 0x04] + frame_data
        self.send_command(0x44, args)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

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

    ditoo = DitooConnection(args.mac)
    ditoo.connect()

    try:
        ditoo.set_brightness(args.brightness)
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

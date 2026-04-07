#!/usr/bin/env python3
"""Preview the ticker display without a Ditoo connection.
Saves a scaled-up PNG so you can see what the 16x16 image looks like."""

from gme_ticker import fetch_stock_price, render_ticker

stock = fetch_stock_price("GME")
if stock:
    print(f"GME: ${stock['price']:.2f} ({stock['change_pct']:+.2f}%)")
else:
    print("Using dummy data for preview")
    stock = {"symbol": "GME", "price": 27.43, "change": 1.22, "change_pct": 4.65}

img = render_ticker(stock)
preview = img.resize((256, 256), resample=0)
preview.save("preview.png")
print("Saved preview.png (256x256 upscaled version of 16x16 display)")

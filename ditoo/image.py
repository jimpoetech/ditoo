"""Image encoding for Divoom 16x16 pixel displays."""

from math import ceil, log2
from PIL import Image


def encode_palette_image(img):
    """Convert a 16x16 PIL Image to Divoom palette-indexed frame data.

    Returns the 0xAA-prefixed frame bytes (list of ints) ready to be
    included in a command 0x44 or 0x49 payload.

    Frame format:
        0xAA  size_lo size_hi  time_lo time_hi  reset  num_colors
        [palette R G B ...]  [bit-packed pixel indices]
    """
    if img.size != (16, 16):
        raise ValueError(f"Image must be 16x16, got {img.size}")
    img = img.convert("RGB")

    pixels = []
    palette = []
    palette_map = {}

    for y in range(16):
        for x in range(16):
            color = img.getpixel((x, y))
            if color not in palette_map:
                palette_map[color] = len(palette)
                palette.append(color)
            pixels.append(palette_map[color])

    num_colors = len(palette)

    palette_bytes = []
    for r, g, b in palette:
        palette_bytes.extend([r, g, b])

    if num_colors <= 1:
        bitwidth = 1
    else:
        bitwidth = max(1, ceil(log2(num_colors)))

    pixel_bytes = []
    encoded = ''
    for idx in pixels:
        encoded = bin(idx)[2:].rjust(bitwidth, '0') + encoded
        if len(encoded) >= 8:
            pixel_bytes.append(int(encoded[-8:], 2))
            encoded = encoded[:-8]
    if encoded:
        pixel_bytes.append(int(encoded.ljust(8, '0'), 2))

    num_colors_byte = 0x00 if num_colors == 256 else num_colors
    frame_inner_size = 7 + len(palette_bytes) + len(pixel_bytes)

    frame = [0xAA]
    frame.append(frame_inner_size & 0xFF)
    frame.append((frame_inner_size >> 8) & 0xFF)
    frame.extend([0x00, 0x00])  # time code (0 for static)
    frame.append(0x00)          # reset flag (new palette)
    frame.append(num_colors_byte)
    frame.extend(palette_bytes)
    frame.extend(pixel_bytes)
    return frame


def encode_animation_frame(img, duration_ms=100, reset_palette=False):
    """Encode a single animation frame with a duration.

    Same as encode_palette_image but with a nonzero time code.
    """
    if img.size != (16, 16):
        raise ValueError(f"Image must be 16x16, got {img.size}")
    frame = encode_palette_image(img)
    # Patch the time code bytes (index 3 and 4)
    frame[3] = duration_ms & 0xFF
    frame[4] = (duration_ms >> 8) & 0xFF
    if reset_palette:
        frame[5] = 0x01
    return frame

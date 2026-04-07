"""Tiny 3x5 bitmap font for 16x16 pixel rendering."""

# Each char is 3 wide x 5 tall. Stored as list of 5 rows, each row is 3 bits.
# Bit order: MSB = left pixel
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
    ':': [0b000, 0b100, 0b000, 0b100, 0b000],
    '/': [0b001, 0b001, 0b010, 0b100, 0b100],
    '!': [0b010, 0b010, 0b010, 0b000, 0b010],
    '?': [0b111, 0b001, 0b010, 0b000, 0b010],
    'A': [0b010, 0b101, 0b111, 0b101, 0b101],
    'B': [0b110, 0b101, 0b110, 0b101, 0b110],
    'C': [0b111, 0b100, 0b100, 0b100, 0b111],
    'D': [0b110, 0b101, 0b101, 0b101, 0b110],
    'E': [0b111, 0b100, 0b111, 0b100, 0b111],
    'F': [0b111, 0b100, 0b111, 0b100, 0b100],
    'G': [0b111, 0b100, 0b101, 0b101, 0b111],
    'H': [0b101, 0b101, 0b111, 0b101, 0b101],
    'I': [0b111, 0b010, 0b010, 0b010, 0b111],
    'J': [0b001, 0b001, 0b001, 0b101, 0b111],
    'K': [0b101, 0b110, 0b100, 0b110, 0b101],
    'L': [0b100, 0b100, 0b100, 0b100, 0b111],
    'M': [0b101, 0b111, 0b111, 0b101, 0b101],
    'N': [0b101, 0b111, 0b111, 0b111, 0b101],
    'O': [0b111, 0b101, 0b101, 0b101, 0b111],
    'P': [0b111, 0b101, 0b111, 0b100, 0b100],
    'Q': [0b111, 0b101, 0b101, 0b111, 0b001],
    'R': [0b111, 0b101, 0b111, 0b110, 0b101],
    'S': [0b111, 0b100, 0b111, 0b001, 0b111],
    'T': [0b111, 0b010, 0b010, 0b010, 0b010],
    'U': [0b101, 0b101, 0b101, 0b101, 0b111],
    'V': [0b101, 0b101, 0b101, 0b101, 0b010],
    'W': [0b101, 0b101, 0b111, 0b111, 0b101],
    'X': [0b101, 0b101, 0b010, 0b101, 0b101],
    'Y': [0b101, 0b101, 0b010, 0b010, 0b010],
    'Z': [0b111, 0b001, 0b010, 0b100, 0b111],
}

# Characters narrower than 3px
CHAR_WIDTH = {'.': 1, ' ': 2, ':': 1, '!': 1}


def char_width(ch):
    """Get pixel width of a character."""
    return CHAR_WIDTH.get(ch.upper(), 3)


def text_width(text):
    """Calculate pixel width of a string in the 3x5 font."""
    if not text:
        return 0
    return sum(char_width(ch) + 1 for ch in text) - 1


def draw_char(img, ch, x, y, color):
    """Draw a single 3x5 character onto a PIL Image."""
    glyph = FONT_3x5.get(ch.upper())
    if glyph is None:
        return
    w, h = img.size
    for row_i, row_bits in enumerate(glyph):
        for col_i in range(3):
            if row_bits & (1 << (2 - col_i)):
                px, py = x + col_i, y + row_i
                if 0 <= px < w and 0 <= py < h:
                    img.putpixel((px, py), color)


def draw_text(img, text, x, y, color):
    """Draw a string using the 3x5 font. Returns ending x position."""
    cursor = x
    for ch in text:
        draw_char(img, ch, cursor, y, color)
        cursor += char_width(ch) + 1
    return cursor

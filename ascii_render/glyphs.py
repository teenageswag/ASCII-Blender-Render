"""Small, original 5x7 bitmap alphabet; no fonts or third-party packages needed."""

import hashlib

import bpy

PRESETS = {
    'CLASSIC': ' .:-=+*#%@',
    'DETAILED': " .`'\"^,:;Il!i~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    'MINIMAL': ' .:+#@',
    'BLOCKS': ' .oO@',
}

# Rows are written top to bottom, most significant bit on the left.
_ROWS = {
    ' ': (0, 0, 0, 0, 0, 0, 0),
    '!': (4, 4, 4, 4, 4, 0, 4),
    '"': (10, 10, 10, 0, 0, 0, 0),
    '#': (10, 31, 10, 10, 31, 10, 0),
    '$': (4, 15, 20, 14, 5, 30, 4),
    '%': (25, 25, 2, 4, 8, 19, 19),
    '&': (12, 18, 20, 8, 21, 18, 13),
    "'": (4, 4, 8, 0, 0, 0, 0),
    '(': (2, 4, 8, 8, 8, 4, 2),
    ')': (8, 4, 2, 2, 2, 4, 8),
    '*': (0, 4, 21, 14, 21, 4, 0),
    '+': (0, 4, 4, 31, 4, 4, 0),
    ',': (0, 0, 0, 0, 4, 4, 8),
    '-': (0, 0, 0, 31, 0, 0, 0),
    '.': (0, 0, 0, 0, 0, 12, 12),
    '/': (1, 2, 2, 4, 8, 8, 16),
    '0': (14, 17, 19, 21, 25, 17, 14),
    '1': (4, 12, 4, 4, 4, 4, 14),
    '2': (14, 17, 1, 2, 4, 8, 31),
    '3': (30, 1, 1, 14, 1, 1, 30),
    '4': (2, 6, 10, 18, 31, 2, 2),
    '5': (31, 16, 16, 30, 1, 1, 30),
    '6': (6, 8, 16, 30, 17, 17, 14),
    '7': (31, 1, 2, 4, 8, 8, 8),
    '8': (14, 17, 17, 14, 17, 17, 14),
    '9': (14, 17, 17, 15, 1, 2, 12),
    ':': (0, 12, 12, 0, 12, 12, 0),
    ';': (0, 12, 12, 0, 4, 4, 8),
    '<': (2, 4, 8, 16, 8, 4, 2),
    '=': (0, 0, 31, 0, 31, 0, 0),
    '>': (8, 4, 2, 1, 2, 4, 8),
    '?': (14, 17, 1, 2, 4, 0, 4),
    '@': (14, 17, 23, 21, 23, 16, 15),
    'A': (14, 17, 17, 31, 17, 17, 17),
    'B': (30, 17, 17, 30, 17, 17, 30),
    'C': (14, 17, 16, 16, 16, 17, 14),
    'D': (30, 17, 17, 17, 17, 17, 30),
    'E': (31, 16, 16, 30, 16, 16, 31),
    'F': (31, 16, 16, 30, 16, 16, 16),
    'G': (14, 17, 16, 23, 17, 17, 15),
    'H': (17, 17, 17, 31, 17, 17, 17),
    'I': (14, 4, 4, 4, 4, 4, 14),
    'J': (7, 2, 2, 2, 2, 18, 12),
    'K': (17, 18, 20, 24, 20, 18, 17),
    'L': (16, 16, 16, 16, 16, 16, 31),
    'M': (17, 27, 21, 21, 17, 17, 17),
    'N': (17, 25, 25, 21, 19, 19, 17),
    'O': (14, 17, 17, 17, 17, 17, 14),
    'P': (30, 17, 17, 30, 16, 16, 16),
    'Q': (14, 17, 17, 17, 21, 18, 13),
    'R': (30, 17, 17, 30, 20, 18, 17),
    'S': (15, 16, 16, 14, 1, 1, 30),
    'T': (31, 4, 4, 4, 4, 4, 4),
    'U': (17, 17, 17, 17, 17, 17, 14),
    'V': (17, 17, 17, 17, 17, 10, 4),
    'W': (17, 17, 17, 21, 21, 27, 17),
    'X': (17, 17, 10, 4, 10, 17, 17),
    'Y': (17, 17, 10, 4, 4, 4, 4),
    'Z': (31, 1, 2, 4, 8, 16, 31),
    '[': (14, 8, 8, 8, 8, 8, 14),
    '\\': (16, 8, 8, 4, 2, 2, 1),
    ']': (14, 2, 2, 2, 2, 2, 14),
    '^': (4, 10, 17, 0, 0, 0, 0),
    '_': (0, 0, 0, 0, 0, 0, 31),
    '`': (8, 4, 2, 0, 0, 0, 0),
    'a': (0, 0, 14, 1, 15, 17, 15),
    'b': (16, 16, 30, 17, 17, 17, 30),
    'c': (0, 0, 14, 17, 16, 17, 14),
    'd': (1, 1, 15, 17, 17, 17, 15),
    'e': (0, 0, 14, 17, 31, 16, 14),
    'f': (6, 9, 8, 28, 8, 8, 8),
    'g': (0, 15, 17, 17, 15, 1, 14),
    'h': (16, 16, 30, 17, 17, 17, 17),
    'i': (4, 0, 12, 4, 4, 4, 14),
    'j': (2, 0, 6, 2, 2, 18, 12),
    'k': (16, 16, 18, 20, 24, 20, 18),
    'l': (12, 4, 4, 4, 4, 4, 14),
    'm': (0, 0, 26, 21, 21, 17, 17),
    'n': (0, 0, 30, 17, 17, 17, 17),
    'o': (0, 0, 14, 17, 17, 17, 14),
    'p': (0, 0, 30, 17, 30, 16, 16),
    'q': (0, 0, 15, 17, 15, 1, 1),
    'r': (0, 0, 22, 25, 16, 16, 16),
    's': (0, 0, 15, 16, 14, 1, 30),
    't': (8, 8, 28, 8, 8, 9, 6),
    'u': (0, 0, 17, 17, 17, 19, 13),
    'v': (0, 0, 17, 17, 17, 10, 4),
    'w': (0, 0, 17, 17, 21, 21, 10),
    'x': (0, 0, 17, 10, 4, 10, 17),
    'y': (0, 0, 17, 17, 15, 1, 14),
    'z': (0, 0, 31, 2, 4, 8, 31),
    '{': (2, 4, 4, 8, 4, 4, 2),
    '|': (4, 4, 4, 4, 4, 4, 4),
    '}': (8, 4, 4, 2, 4, 4, 8),
    '~': (0, 0, 9, 22, 0, 0, 0),
}

CELL_W, CELL_H = 16, 24


def character_ramp(settings):
    """Return supported characters, retaining repeats and the user's ordering."""
    text = settings.custom_characters if settings.character_set == 'CUSTOM' else PRESETS[settings.character_set]
    chars = ''.join(c for c in text[:128] if c in _ROWS)
    if not chars:
        chars = PRESETS['CLASSIC']
    if settings.sort_by_density:
        chars = ''.join(sorted(chars, key=lambda c: sum(row.bit_count() for row in _ROWS[c])))
    return chars


def atlas_for(ramp):
    # Four contour glyphs are always appended in this order.
    characters = ramp + '-|/\\'
    digest = hashlib.sha256(characters.encode('ascii')).hexdigest()[:16]
    name = f'.ASCII Atlas {digest}'
    existing = bpy.data.images.get(name)
    if existing is not None and existing.get('ascii_characters') == characters:
        return existing
    width, height = len(characters) * CELL_W, CELL_H
    pixels = [0.0, 0.0, 0.0, 1.0] * (width * height)
    for glyph_index, char in enumerate(characters):
        for row, bits in enumerate(_ROWS[char]):
            for column in range(5):
                if not bits & (1 << (4 - column)):
                    continue
                for dy in range(2):
                    for dx in range(2):
                        x = glyph_index * CELL_W + 3 + column * 2 + dx
                        y = 5 + (6 - row) * 2 + dy
                        offset = (y * width + x) * 4
                        pixels[offset:offset + 3] = (1.0, 1.0, 1.0)
    image = bpy.data.images.new(name, width=width, height=height, alpha=False)
    image.colorspace_settings.name = 'Non-Color'
    image.pixels.foreach_set(pixels)
    image.update()
    image['ascii_characters'] = characters
    image['ascii_render_owned'] = True
    image.pack()
    return image

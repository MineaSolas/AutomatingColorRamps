import colorsys

from collections import defaultdict
import numpy as np
from colormath.color_conversions import convert_color
from colormath.color_objects import sRGBColor, LabColor
from pyciede2000 import ciede2000


def extract_adjacent_color_pairs(image_array, use_8_neighbors=True):
    height, width, _ = image_array.shape
    offsets = [(0, 1), (1, 0)]
    if use_8_neighbors:
        offsets += [(1, 1), (1, -1)]

    color_counts = defaultdict(int)
    adjacency_counts = defaultdict(int)

    for y in range(height):
        for x in range(width):
            c1 = tuple(image_array[y, x])
            if c1[3] == 0:
                continue
            color_counts[c1] += 1
            for dy, dx in offsets:
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width:
                    c2 = tuple(image_array[ny, nx])
                    if c2[3] == 0 or c1 == c2:
                        continue
                    key = tuple(sorted((c1, c2)))
                    adjacency_counts[key] += 1

    return adjacency_counts, color_counts

def color_to_hsv(c):
    r, g, b = [x / 255.0 for x in c[:3]]
    return colorsys.rgb_to_hsv(r, g, b)

def get_highlight_color(color):
    r, g, b = [c / 255.0 for c in color[:3]]
    h, _, _ = colorsys.rgb_to_hsv(r, g, b)
    return "cyan" if h < 0.125 or h > 0.7 else "red"

def get_text_descriptions(color):
    r, g, b = [int(c) for c in color[:3]]
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    h_deg, s_pct, v_pct = int(h * 360), int(s * 100), int(v * 100)
    hex_str = f"#{r:02X}{g:02X}{b:02X}"
    return {
        "rgb": f"RGB: ({r}, {g}, {b})",
        "hex": f"HEX: {hex_str}",
        "hsv": f"HSV: ({h_deg}°, {s_pct}%, {v_pct}%)",
        "hex_raw": hex_str
    }

def colors_similar(c1, c2, threshold, method="HSV"):
    if method == "HSV":
        hsv1 = np.array(color_to_hsv(c1))
        hsv2 = np.array(color_to_hsv(c2))

        diffs = hsv1 - hsv2

        # Correct hue circular difference
        diffs[0] = (diffs[0] + 0.5) % 1.0 - 0.5  # This keeps hue difference in [-0.5, 0.5]

        diff = np.linalg.norm(diffs)

        return diff < threshold / 100.0

    elif method == "CIEDE2000":
        srgb1 = sRGBColor(*[x / 255.0 for x in c1[:3]])
        srgb2 = sRGBColor(*[x / 255.0 for x in c2[:3]])
        lab1 = convert_color(srgb1, LabColor)
        lab2 = convert_color(srgb2, LabColor)

        result = ciede2000(
            (lab1.lab_l, lab1.lab_a, lab1.lab_b),
            (lab2.lab_l, lab2.lab_a, lab2.lab_b)
        )

        delta_e = result['delta_E_00']
        return delta_e < threshold

    return False




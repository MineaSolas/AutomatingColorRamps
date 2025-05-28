import colorsys

from collections import defaultdict
import numpy as np
from colormath.color_conversions import convert_color
from colormath.color_objects import sRGBColor, LabColor
from pyciede2000 import ciede2000

import global_managers


def extract_adjacent_color_pairs(image_array, use_8_neighbors=True):
    height, width, _ = image_array.shape
    offsets = [(0, 1), (1, 0)]
    if use_8_neighbors:
        offsets += [(1, 1), (1, -1)]

    # Create a mapping between colors and color IDs
    pos_to_id = {}
    id_counts = defaultdict(int)

    # Map positions to color IDs using the global color manager
    for color_id, group in global_managers.global_color_manager.color_groups.items():
        for pos in group.pixel_positions:
            pos_to_id[pos] = color_id
            id_counts[color_id] += 1

    adjacency_counts = defaultdict(int)

    for y in range(height):
        for x in range(width):
            if (x, y) not in pos_to_id:
                continue

            id1 = pos_to_id[(x, y)]
            for dy, dx in offsets:
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width:
                    if (nx, ny) not in pos_to_id:
                        continue

                    id2 = pos_to_id[(nx, ny)]
                    if id1 == id2:
                        continue

                    key = tuple(sorted([id1, id2]))
                    adjacency_counts[key] += 1

    return adjacency_counts, id_counts


def get_highlight_color(color):
    r, g, b = [c / 255.0 for c in color[:3]]
    h, _, _ = colorsys.rgb_to_hsv(r, g, b)
    return "cyan" if h < 0.125 or h > 0.7 else "red"

def get_text_descriptions(color):
    r, g, b = [int(c) for c in color[:3]]
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    h_deg, s_pct, v_pct = int(h * 359), int(s * 100), int(v * 100)
    hex_str = f"#{r:02X}{g:02X}{b:02X}"
    return {
        "rgb": f"RGB:  ({r}, {g}, {b})",
        "hex": f"HEX:  {hex_str}",
        "hsv": f"HSV:  ({h_deg}°, {s_pct}%, {v_pct}%)",
        "hex_raw": hex_str
    }

def color_to_hsv(c):
    if isinstance(c, int):
        c = global_managers.global_color_manager.color_groups[c].current_color
    r, g, b = [x / 255.0 for x in c[:3]]
    return colorsys.rgb_to_hsv(r, g, b)

def is_similar_hsv(c1, c2, hue_threshold=180, sat_threshold=1.0, val_threshold=1.0):
    hsv1 = np.array(color_to_hsv(c1))
    hsv2 = np.array(color_to_hsv(c2))

    diffs = hsv1 - hsv2
    diffs[0] = (diffs[0] + 0.5) % 1.0 - 0.5  # Correct hue circular difference

    hue_diff = abs(diffs[0]) * 359  # Convert to degrees
    sat_diff = abs(diffs[1])
    val_diff = abs(diffs[2])

    return (hue_diff <= hue_threshold and
            sat_diff <= sat_threshold and
            val_diff <= val_threshold)


def is_similar_ciede2000(c1, c2, threshold=100):
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

def hsv_diffs(colors):
    hsv_values = np.array([color_to_hsv(c) for c in colors])
    diffs = np.diff(hsv_values, axis=0)
    # Hue circular correction
    hue_diffs = diffs[:, 0]
    hue_diffs = (hue_diffs + 0.5) % 1.0 - 0.5
    diffs[:, 0] = hue_diffs
    return diffs


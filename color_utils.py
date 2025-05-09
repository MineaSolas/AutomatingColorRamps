import colorsys

from collections import defaultdict
import numpy as np


def extract_adjacent_color_pairs(
    image_array,
    use_8_neighbors=True,
    threshold_value=0.05,
    method="relative"
):
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

    accepted_pairs = {}

    if method == "relative":
        for (c1, c2), count in adjacency_counts.items():
            total_c1 = color_counts[c1]
            total_c2 = color_counts[c2]
            if (count / total_c1 > threshold_value) or (count / total_c2 > threshold_value):
                accepted_pairs[(c1, c2)] = count

    elif method == "percentile":
        counts = np.array(list(adjacency_counts.values()))
        if len(counts) == 0:
            return {}
        threshold = np.percentile(counts, threshold_value)
        accepted_pairs = {
            pair: count
            for pair, count in adjacency_counts.items()
            if count >= threshold
        }

    elif method == "absolute":
        accepted_pairs = {
            pair: count
            for pair, count in adjacency_counts.items()
            if count >= threshold_value
        }

    else:
        raise ValueError(f"Unsupported threshold method: {method}")

    return accepted_pairs


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

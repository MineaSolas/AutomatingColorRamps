import numpy as np
from colormath.color_conversions import convert_color
from colormath.color_objects import sRGBColor, LabColor
from pyciede2000 import ciede2000

from color_utils import color_to_hsv


def find_color_ramps(graph, method="Basic HSV", params=None):
    if params is None:
        params = {}

    ramps = []
    visited_nodes = set()

    sorted_nodes = sorted(graph.nodes, key=lambda c: color_to_hsv(c)[2])  # Sort by brightness

    for start in sorted_nodes:
        if start in visited_nodes:
            continue

        stack = [(start, [start])]
        while stack:
            current, path = stack.pop()
            extended = False
            for neighbor in graph.neighbors(current):
                if neighbor in path:
                    continue
                new_path = path + [neighbor]
                if is_valid_ramp(new_path, method, params):
                    stack.append((neighbor, new_path))
                    extended = True
            if not extended and len(path) >= 3:
                ramps.append(path)
                visited_nodes.update(path)

    ramps = remove_sub_ramps(ramps)
    return ramps


def is_valid_ramp(path, method, params):
    hsv_values = np.array([color_to_hsv(c) for c in path])
    diffs = np.diff(hsv_values, axis=0)

    # Hue circular correction
    hue_diffs = diffs[:, 0]
    hue_diffs = (hue_diffs + 0.5) % 1.0 - 0.5
    diffs[:, 0] = hue_diffs

    if method == "Basic HSV":
        for i in range(3):  # H, S, V
            comp_diffs = diffs[:, i]
            if not is_within_step_limit(comp_diffs, params.get('max_step', [1, 1, 1])[i]):
                return False
            if not is_consistent_step_size(comp_diffs, params.get('tolerance', [0.1, 0.1, 0.1])[i]):
                return False
        return True

    elif method == "Vector HSV":
        vectors = diffs
        step_magnitudes = np.linalg.norm(vectors, axis=1)
        if np.any(step_magnitudes > params.get('max_step_size', 1.0)):
            return False

        angle_tolerance_rad = np.radians(params.get('angle_tolerance_deg', 15))
        for i in range(len(vectors) - 1):
            v1 = vectors[i]
            v2 = vectors[i + 1]
            dot = np.dot(v1, v2)
            norm_product = np.linalg.norm(v1) * np.linalg.norm(v2)
            if norm_product < 1e-5:
                continue  # Skip near-zero vectors
            angle = np.arccos(np.clip(dot / norm_product, -1.0, 1.0))
            if angle > angle_tolerance_rad:
                return False

        return True

    elif method == "CIEDE2000":
        return is_valid_ramp_ciede2000(path, params)

    return False

def is_valid_ramp_ciede2000(path, params):
    max_delta_e = params.get('max_delta_e', 5.0)  # Typical perceptibility threshold
    variance_tolerance = params.get('variance_tolerance', 2.0)  # Allowed ΔE variance between steps

    # Convert RGB to Lab for all colors in the path
    lab_colors = []
    for color in path:
        srgb = sRGBColor(*[c / 255.0 for c in color[:3]])
        lab = convert_color(srgb, LabColor)
        lab_colors.append((lab.lab_l, lab.lab_a, lab.lab_b))

    # Compute ΔE between consecutive steps
    delta_e_steps = [
        ciede2000(lab_colors[i], lab_colors[i+1])['delta_E_00']
        for i in range(len(lab_colors) - 1)
    ]

    # Check max ΔE threshold
    if any(de > max_delta_e for de in delta_e_steps):
        return False

    # Check variance in ΔE between steps
    if len(delta_e_steps) > 1:
        diffs = np.abs(np.diff(delta_e_steps))
        if np.any(diffs > variance_tolerance):
            return False

    return True


def is_within_step_limit(deltas, max_step):
    return np.all(np.abs(deltas) <= max_step + 1e-5)


def is_consistent_step_size(deltas, tolerance):
    non_zero = deltas[np.abs(deltas) > 1e-5]
    if len(non_zero) < 2:
        return True
    step_diffs = np.diff(non_zero)
    return np.all(np.abs(step_diffs) <= tolerance)

def remove_sub_ramps(ramps):
    to_remove = set()
    for i, ramp_i in enumerate(ramps):
        for j, ramp_j in enumerate(ramps):
            if i == j or j in to_remove:
                continue
            if is_subsequence(ramp_j, ramp_i) or is_subsequence(ramp_j[::-1], ramp_i):
                to_remove.add(j)

    return [r for idx, r in enumerate(ramps) if idx not in to_remove]


def is_subsequence(sub, full):
    sub_len = len(sub)
    for i in range(len(full) - sub_len + 1):
        if all(sub[j] == full[i + j] for j in range(sub_len)):
            return True
    return False

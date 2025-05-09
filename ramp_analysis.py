import numpy as np
from color_utils import color_to_hsv


def find_color_ramps(graph, tolerance_hsv, max_step_hsv):
    ramps = []
    visited_nodes = set()

    sorted_nodes = sorted(graph.nodes, key=lambda c: color_to_hsv(c)[2])  # sort by brightness

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
                if is_valid_ramp(new_path, tolerance_hsv, max_step_hsv):
                    stack.append((neighbor, new_path))
                    extended = True
            if not extended and len(path) >= 3 and is_unique_ramp(path, ramps):
                ramps.append(path)
                visited_nodes.update(path)

    return ramps


def is_valid_ramp(path, tolerance_hsv, max_step_hsv):
    hsv_values = np.array([color_to_hsv(c) for c in path])
    diffs = np.diff(hsv_values, axis=0)

    # Wrap hue diffs into [-0.5, 0.5]
    hue_diffs = diffs[:, 0]
    hue_diffs = (hue_diffs + 0.5) % 1.0 - 0.5
    diffs[:, 0] = hue_diffs

    for i in range(3):  # H, S, V
        comp_diffs = diffs[:, i]
        if not is_within_step_limit(comp_diffs, max_step_hsv[i]):
            return False
        if not is_consistent_step_size(comp_diffs, tolerance_hsv[i]):
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


def is_unique_ramp(new_ramp, existing_ramps):
    for ramp in existing_ramps:
        if is_subsequence(new_ramp, ramp) or is_subsequence(new_ramp[::-1], ramp):
            return False
    return True


def is_subsequence(sub, full):
    sub_len = len(sub)
    for i in range(len(full) - sub_len + 1):
        if all(sub[j] == full[i + j] for j in range(sub_len)):
            return True
    return False

def find_color_ramps_vector_hsv(graph, angle_tolerance_deg, max_step_size):
    ramps = []
    visited_nodes = set()
    angle_tolerance_rad = np.radians(angle_tolerance_deg)
    sorted_nodes = sorted(graph.nodes, key=lambda c: color_to_hsv(c)[2])

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
                if is_valid_vector_ramp(new_path, angle_tolerance_rad, max_step_size):
                    stack.append((neighbor, new_path))
                    extended = True
            if not extended and len(path) >= 3 and is_unique_ramp(path, ramps):
                ramps.append(path)
                visited_nodes.update(path)

    return ramps


def is_valid_vector_ramp(path, angle_tolerance_rad, max_step_size):
    hsv_values = np.array([color_to_hsv(c) for c in path])
    vectors = np.diff(hsv_values, axis=0)

    # Wrap hue diffs into [-0.5, 0.5]
    hue_diffs = vectors[:, 0]
    hue_diffs = (hue_diffs + 0.5) % 1.0 - 0.5
    vectors[:, 0] = hue_diffs

    # Check step sizes
    step_magnitudes = np.linalg.norm(vectors, axis=1)
    if np.any(step_magnitudes > max_step_size):
        return False

    # Check angle between consecutive steps
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

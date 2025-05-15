import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSlider, QPushButton,
    QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt
from colormath.color_conversions import convert_color
from colormath.color_objects import sRGBColor, LabColor
from pyciede2000 import ciede2000

from color_utils import color_to_hsv, hsv_diffs


class RampExtractionViewer(QWidget):
    def __init__(self, graph_viewer, parent=None):
        super().__init__(parent)
        self.graph_viewer = graph_viewer
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)

        # --- Left: Ramp Display Area ---
        self.ramps_scroll_area = QScrollArea()
        self.ramps_scroll_area.setWidgetResizable(True)
        self.ramp_container = QWidget()
        self.ramps_layout = QVBoxLayout(self.ramp_container)
        self.ramps_layout.setSpacing(5)
        self.ramps_scroll_area.setWidget(self.ramp_container)

        main_layout.addWidget(self.ramps_scroll_area, stretch=1)

        # --- Right: Controls Panel ---
        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)

        self.extraction_method_selector = QComboBox()
        self.extraction_method_selector.addItems(["Basic HSV", "Vector HSV", "CIEDE2000"])
        self.extraction_method_selector.currentTextChanged.connect(self.update_extraction_controls)
        controls_layout.addWidget(QLabel("Ramp Extraction Method"))
        controls_layout.addWidget(self.extraction_method_selector)

        # Control Panels for Each Method
        self.basic_controls = self._create_basic_controls()
        controls_layout.addWidget(self.basic_controls)

        self.vector_controls = self._create_vector_controls()
        controls_layout.addWidget(self.vector_controls)
        self.vector_controls.hide()

        self.ciede_controls = self._create_ciede_controls()
        controls_layout.addWidget(self.ciede_controls)
        self.ciede_controls.hide()

        controls_layout.addStretch()

        # Extract Button
        self.extract_button = QPushButton("Extract Ramps")
        self.extract_button.clicked.connect(self.extract_color_ramps)
        controls_layout.addWidget(self.extract_button)

        main_layout.addWidget(controls_panel, stretch=0)

    def _create_basic_controls(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.h_slider = self._create_slider("Hue Step Max (°)", 0, 180, 60, layout)
        self.h_tol_slider = self._create_slider("Hue Step Variance Max (°)", 0, 100, 30, layout)
        self.s_slider = self._create_slider("Sat Step Max", 0, 100, 50, layout)
        self.s_tol_slider = self._create_slider("Sat Step Variance Max", 0, 100, 20, layout)
        self.v_slider = self._create_slider("Val Step Max", 0, 100, 50, layout)
        self.v_tol_slider = self._create_slider("Val Step Variance Max", 0, 100, 20, layout)
        return widget

    def _create_vector_controls(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.vector_angle_slider = self._create_slider("Angle Step Max (°)", 0, 180, 45, layout)
        self.vector_magnitude_slider = self._create_slider("Step Magnitude Max", 0, 100, 45, layout)
        return widget

    def _create_ciede_controls(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.delta_e_slider = self._create_slider("ΔE2000 Step Max", 0, 50, 40, layout)
        self.delta_e_var_slider = self._create_slider("ΔE2000 Variance Tolerance", 0, 30, 15, layout)
        return widget

    def _create_slider(self, label_text, min_val, max_val, default, layout):
        label = QLabel(f"{label_text}: {default}")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        slider.valueChanged.connect(lambda val, l=label, t=label_text: l.setText(f"{t}: {val}"))
        layout.addWidget(label)
        layout.addWidget(slider)
        return slider

    def update_extraction_controls(self):
        method = self.extraction_method_selector.currentText()
        self.basic_controls.setVisible(method == "Basic HSV")
        self.vector_controls.setVisible(method == "Vector HSV")
        self.ciede_controls.setVisible(method == "CIEDE2000")

    def extract_color_ramps(self):
        graph = self.graph_viewer.color_graph
        if graph is None:
            return

        method = self.extraction_method_selector.currentText()
        params = self._get_extraction_params(method)
        ramps = self.find_color_ramps(graph, method, params)
        self.display_color_ramps(ramps)

    def _get_extraction_params(self, method):
        if method == "Basic HSV":
            return {
                'max_step': [
                    self.h_slider.value() / 180.0,
                    self.s_slider.value() / 100.0,
                    self.v_slider.value() / 100.0
                ],
                'tolerance': [
                    self.h_tol_slider.value() / 180.0,
                    self.s_tol_slider.value() / 100.0,
                    self.v_tol_slider.value() / 100.0
                ]
            }
        elif method == "Vector HSV":
            return {
                'angle_tolerance_deg': self.vector_angle_slider.value(),
                'max_step_size': self.vector_magnitude_slider.value() / 100.0
            }
        elif method == "CIEDE2000":
            return {
                'max_delta_e': self.delta_e_slider.value(),
                'variance_tolerance': self.delta_e_var_slider.value()
            }
        return {}

    def display_color_ramps(self, ramps):
        # Clear previous ramps
        for i in reversed(range(self.ramps_layout.count())):
            widget = self.ramps_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        for ramp in ramps:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            row_layout.setContentsMargins(10, 0, 0, 0)
            row_layout.setSpacing(0)

            for color in ramp:
                r, g, b, a = color
                swatch = QLabel()
                swatch.setFixedSize(25, 25)
                swatch.setStyleSheet(f"background-color: rgba({r},{g},{b},{a}); border: none;  margin: 0px; padding: 0px;")
                row_layout.addWidget(swatch)

            self.ramps_layout.addWidget(row_widget)

    @staticmethod
    def find_color_ramps(graph, method="Basic HSV", params=None, skip_subsequences=True):
        if params is None:
            params = {}

        ramps = []

        sorted_nodes = sorted(graph.nodes, key=lambda c: color_to_hsv(c)[2])  # Sort by brightness
        n = len(sorted_nodes)

        i = 0
        for start in sorted_nodes:
            print(f"Processing... {i}/{n}")
            i += 1

            stack = [(start, [start])]
            while stack:
                current, path = stack.pop()
                extended = False
                for neighbor in graph.neighbors(current):
                    if neighbor in path:
                        continue
                    new_path = path + [neighbor]
                    if RampExtractionViewer.is_valid_ramp(new_path, method, params):
                        stack.append((neighbor, new_path))
                        extended = True
                if not extended and len(path) >= 3:
                    if skip_subsequences and RampExtractionViewer.is_subsequence_of_any(path, ramps):
                        continue
                    ramps.append(path)

        print(f"Done {n}/{n}")
        return ramps

    @staticmethod
    def is_valid_ramp(path, method, params):
        if method == "Basic HSV":
            return RampExtractionViewer._is_valid_ramp_hsv(path, params)

        elif method == "Vector HSV":
            return RampExtractionViewer._is_valid_ramp_vector_hsv(path, params)

        elif method == "CIEDE2000":
            return RampExtractionViewer.is_valid_ramp_ciede2000(path, params)

        return False

    @staticmethod
    def _is_valid_ramp_hsv(path, params):
        diffs = hsv_diffs(path)

        for i in range(3):  # H, S, V
            comp_diffs = diffs[:, i]
            if not RampExtractionViewer.is_monotonic_direction(comp_diffs):
                return False
            if not RampExtractionViewer.is_within_step_limit(comp_diffs, params.get('max_step', [1, 1, 1])[i]):
                return False
            if not RampExtractionViewer.is_consistent_step_size(comp_diffs, params.get('tolerance', [0.1, 0.1, 0.1])[i]):
                return False

        return True

    @staticmethod
    def _is_valid_ramp_vector_hsv(path, params):
        vectors = hsv_diffs(path)
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

    @staticmethod
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

        if not RampExtractionViewer.is_monotonic_delta_e(delta_e_steps):
            return False

        # Check max ΔE threshold
        if any(de > max_delta_e for de in delta_e_steps):
            return False

        # Check variance in ΔE between steps
        if len(delta_e_steps) > 1:
            diffs = np.abs(np.diff(delta_e_steps))
            if np.any(diffs > variance_tolerance):
                return False

        return True

    @staticmethod
    def is_monotonic_direction(deltas):
        # Ignore near-zero steps to prevent noise triggering false negatives
        non_zero = deltas[np.abs(deltas) > 0.1]
        if len(non_zero) == 0:
            return True  # No real changes, allow flat ramp

        # Check if all are positive or all are negative
        return np.all(non_zero >= 0) or np.all(non_zero <= 0)

    @staticmethod
    def is_monotonic_delta_e(delta_e_steps, tolerance=1):
        diffs = np.diff(delta_e_steps)
        non_zero_diffs = diffs[np.abs(diffs) > tolerance]

        if len(non_zero_diffs) == 0:
            return True  # Flat ΔE changes, accept as monotonic

        return np.all(non_zero_diffs >= 0) or np.all(non_zero_diffs <= 0)

    @staticmethod
    def is_within_step_limit(deltas, max_step):
        return np.all(np.abs(deltas) <= max_step + 1e-5)

    @staticmethod
    def is_consistent_step_size(deltas, tolerance):
        non_zero = deltas[np.abs(deltas) > 1e-5]
        if len(non_zero) < 2:
            return True
        step_diffs = np.diff(non_zero)
        return np.all(np.abs(step_diffs) <= tolerance)

    @staticmethod
    def is_subsequence_of_any(candidate, ramps):
        candidate_length = len(candidate)
        reversed_candidate = list(reversed(candidate))

        for ramp in ramps:
            ramp_length = len(ramp)
            if ramp_length < candidate_length:
                continue
            for i in range(ramp_length - candidate_length + 1):
                if ramp[i:i + candidate_length] == candidate or ramp[i:i + candidate_length] == reversed_candidate:
                    return True
        return False



import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSlider, QPushButton,
    QScrollArea, QSizePolicy, QCheckBox, QGroupBox, QGridLayout, QDialog, QSpacerItem, QFrame, QToolButton, QButtonGroup
)
from PyQt6.QtCore import Qt, QTimer
from colormath.color_conversions import convert_color
from colormath.color_objects import sRGBColor, LabColor
from pyciede2000 import ciede2000
from sklearn.cluster import AgglomerativeClustering

from color_utils import color_to_hsv, hsv_diffs, is_similar_hsv
from palette import ColorRamp, final_palette_manager, ColorPalette, selection_manager
from ui_helpers import VerticalLabel

class RampExtractionViewer(QWidget):
    def __init__(self, graph_viewer, unique_colors, parent=None):
        super().__init__(parent)
        self.graph_viewer = graph_viewer
        self.generated_ramp_widgets = {}
        self.final_ramp_widgets = {}
        self.unique_colors = set(unique_colors)
        self._setup_ui()
        final_palette_manager.register_listener(self.refresh_ramp_views)
        selection_manager.register_listener(self.update_tool_color_display)

    def _setup_ui(self):
        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(10)

        # --- LEFT PANEL: Controls ---
        left_controls_container = QWidget()
        left_layout = QVBoxLayout(left_controls_container)
        left_layout.setSpacing(10)

        # Create method dropdown
        self.extraction_method_selector = QComboBox()
        self.extraction_method_selector.addItems(["Basic HSV", "Vector HSV", "CIEDE2000"])
        self.extraction_method_selector.currentTextChanged.connect(self.update_extraction_controls)

        method_dropdown_row = QWidget()
        method_dropdown_layout = QHBoxLayout(method_dropdown_row)
        method_dropdown_layout.setContentsMargins(0, 0, 0, 0)
        method_dropdown_layout.addWidget(QLabel("Validation Method:"))
        method_dropdown_layout.addWidget(self.extraction_method_selector)

        # Create all controls
        self.basic_controls = self._create_basic_hsv_controls()
        self.vector_controls = self._create_vector_controls()
        self.ciede_controls = self._create_ciede_controls()
        self.max_length_label = QLabel("Max Ramp Length: 20")
        self.max_length_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_length_slider.setRange(3, 20)
        self.max_length_slider.setValue(20)
        self.max_length_slider.valueChanged.connect(
            lambda val: self.max_length_label.setText(f"Max Ramp Length: {val}")
        )
        self.remove_similar_checkbox = QCheckBox("Cluster and Reduce Similar Ramps")
        self.remove_similar_checkbox.setChecked(False)

        self.skip_reverse_checkbox = QCheckBox("Remove Reverses")
        self.skip_subsequences_checkbox = QCheckBox("Remove Subsequences")
        self.skip_permutations_checkbox = QCheckBox("Remove Permutations")
        self.skip_reverse_checkbox.setChecked(True)
        self.skip_subsequences_checkbox.setChecked(True)
        self.skip_permutations_checkbox.setChecked(False)

        # General Controls Column
        general_controls_group = QGroupBox()
        general_layout = QVBoxLayout(general_controls_group)
        general_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        general_layout.addWidget(self.max_length_label)
        general_layout.addWidget(self.max_length_slider)
        general_layout.addWidget(self.remove_similar_checkbox)
        general_layout.addWidget(self.skip_reverse_checkbox)
        general_layout.addWidget(self.skip_subsequences_checkbox)
        general_layout.addWidget(self.skip_permutations_checkbox)

        # Method Controls Column
        method_controls_group = QGroupBox()
        method_controls_layout = QVBoxLayout(method_controls_group)
        method_controls_layout.addWidget(method_dropdown_row)
        method_controls_layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))
        method_controls_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.method_stack = QWidget()
        self.method_stack_layout = QVBoxLayout(self.method_stack)
        self.method_stack_layout.setContentsMargins(0, 0, 0, 0)
        self.method_stack_layout.setSpacing(10)
        self.method_stack_layout.addWidget(self.basic_controls)
        self.method_stack_layout.addWidget(self.vector_controls)
        self.method_stack_layout.addWidget(self.ciede_controls)
        method_controls_layout.addWidget(self.method_stack)

        # Combine both columns side-by-side
        columns_row = QHBoxLayout()
        columns_row.setSpacing(10)
        columns_row.addWidget(general_controls_group, 1)
        columns_row.addWidget(method_controls_group, 1)

        left_layout.addLayout(columns_row)

        # Extract Button below both columns
        self.extract_button = QPushButton("Extract Ramps")
        self.extract_button.clicked.connect(self.extract_color_ramps)
        self.extract_button.setDisabled(True)
        left_layout.addWidget(self.extract_button)

        main_layout.addWidget(left_controls_container, stretch=0)

        # --- CENTER: Candidate Ramps ---
        self.ramp_label = QLabel("Candidate Ramps")
        self.generated_ramps = []
        self.ramps_scroll_area = QScrollArea()
        self.ramps_scroll_area.setWidgetResizable(True)
        self.ramp_container = QWidget()
        self.ramps_layout = QVBoxLayout(self.ramp_container)
        self.ramps_layout.setSpacing(1)
        self.ramps_layout.setContentsMargins(10, 10, 10, 10)
        self.ramps_scroll_area.setWidget(self.ramp_container)

        self.ramp_preview_container = QWidget()
        self.ramp_preview_layout = QVBoxLayout(self.ramp_preview_container)
        self.ramp_preview_layout.setContentsMargins(0, 0, 0, 0)
        self.ramp_preview_layout.addWidget(self.ramp_label)
        self.ramp_preview_layout.addWidget(self.ramps_scroll_area)

        main_layout.addWidget(self.ramp_preview_container, stretch=2)

        # --- RIGHT: Final Ramps + Tools ---
        self.selected_label = QLabel("Selected Ramps")

        self.final_ramps_scroll_area = QScrollArea()
        self.final_ramps_scroll_area.setWidgetResizable(True)
        self.final_ramp_container = QWidget()
        self.final_ramps_layout = QVBoxLayout(self.final_ramp_container)
        self.final_ramps_layout.setSpacing(1)
        self.final_ramps_layout.setContentsMargins(10, 10, 10, 10)
        self.final_ramps_scroll_area.setWidget(self.final_ramp_container)

        # Overlay container
        self.final_ramps_overlay = QWidget()
        self.final_ramps_overlay.setLayout(QVBoxLayout())
        self.final_ramps_overlay.layout().setContentsMargins(0, 0, 0, 0)
        self.final_ramps_overlay.layout().addWidget(self.final_ramps_scroll_area)

        # Final section layout
        self.final_ramp_preview_container = QWidget()
        self.final_ramp_preview_layout = QVBoxLayout(self.final_ramp_preview_container)
        self.final_ramp_preview_layout.setContentsMargins(0, 0, 0, 0)
        self.final_ramp_preview_layout.addWidget(self.selected_label)
        self.final_ramp_preview_layout.addWidget(self.final_ramps_overlay)

        # Floating tool button panel
        self.tool_color_preview = QLabel("No color")
        self.tool_color_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tool_color_preview.setFixedHeight(30)
        self.tool_color_preview.setStyleSheet("""
            border: 1px solid #888;
            background-color: transparent;
            font-size: 10pt;
        """)

        self.tool_button_panel = QFrame(self.final_ramps_overlay)
        self.tool_button_panel.setStyleSheet("""
            QToolButton {
                min-width: 80px;
                min-height: 20px;
                padding: 4px 4px;
                background-color: #eeeeff;
            }
        """)
        self.tool_button_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        tool_layout = QVBoxLayout(self.tool_button_panel)
        tool_layout.setSpacing(10)

        self.add_remove_tool = QToolButton()
        self.add_remove_tool.setText("Add/Remove")
        self.add_remove_tool.setCheckable(True)

        self.split_tool = QToolButton()
        self.split_tool.setText("Split")
        self.split_tool.setCheckable(True)

        self.merge_tool = QToolButton()
        self.merge_tool.setText("Merge")
        self.merge_tool.setCheckable(True)

        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(False)
        self.tool_group.addButton(self.add_remove_tool)
        self.tool_group.addButton(self.split_tool)
        self.tool_group.addButton(self.merge_tool)

        tool_layout.addWidget(self.tool_color_preview)
        tool_layout.addWidget(self.add_remove_tool)
        # tool_layout.addWidget(self.split_tool)
        # tool_layout.addWidget(self.merge_tool)

        self.add_remove_tool.clicked.connect(self._handle_tool_toggle)
        self.split_tool.clicked.connect(self._handle_tool_toggle)
        self.merge_tool.clicked.connect(self._handle_tool_toggle)

        # Unused color palette
        self.unused_label = QLabel("Unused Colors:")
        self.unused_palette = ColorPalette()
        self.unused_palette.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.final_ramp_preview_layout.addWidget(self.unused_label)
        self.final_ramp_preview_layout.addWidget(self.unused_palette)

        main_layout.addWidget(self.final_ramp_preview_container, stretch=2)

        # Initial logic
        self.update_extraction_controls()
        self.refresh_ramp_views()

        # Ensure floating tools appear
        self.tool_button_panel.raise_()
        self.tool_button_panel.show()
        QTimer.singleShot(0, self._move_tool_button_panel)

    def _handle_tool_toggle(self):
        clicked = self.sender()

        # If clicked is already checked, toggle off everything
        if clicked.isChecked():
            # Uncheck all other buttons
            for button in self.tool_group.buttons():
                if button != clicked:
                    button.setChecked(False)
        else:
            # If clicked is being toggled off, nothing else is selected
            for button in self.tool_group.buttons():
                button.setChecked(False)

    def _move_tool_button_panel(self):
        self.tool_button_panel.adjustSize()
        available_width = self.final_ramps_overlay.size().width()
        panel_width = self.tool_button_panel.sizeHint().width()
        x = max(available_width - panel_width - 5, 0)
        self.tool_button_panel.move(x, 5)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.tool_button_panel:
            self._move_tool_button_panel()

    def _create_basic_hsv_controls(self):
        self.h_slider = None
        self.s_slider = None
        self.v_slider = None
        self.h_min_slider = None
        self.s_min_slider = None
        self.v_min_slider = None
        self.h_tol_slider = None
        self.s_tol_slider = None
        self.v_tol_slider = None

        widget = QWidget()
        layout = QGridLayout(widget)
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        layout.setContentsMargins(0, 0, 0, 0)

        factors = [("Hue", 0, 180, "h"), ("Saturation", 0, 100, "s"), ("Value", 0, 100, "v")]

        for row, (factor_name, min_val, max_val, attr_prefix) in enumerate(factors):
            factor_label = VerticalLabel(factor_name)
            factor_label.setAlignment(Qt.AlignmentFlag.AlignTop)
            factor_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
            factor_label.setFixedWidth(15)
            layout.addWidget(factor_label, row, 0)

            group_box = QGroupBox()
            group_layout = QVBoxLayout(group_box)
            group_layout.setSpacing(2)

            self._add_min_max_sliders(
                min_val, max_val, 0, max_val // 2,
                f"{attr_prefix}_min_slider",
                f"{attr_prefix}_slider",
                group_layout
            )

            setattr(self, f"{attr_prefix}_tol_slider", self._create_slider("Step Variance Max", 0, 100, 20, group_layout))
            layout.addWidget(group_box, row, 1)

        self.monotonicity_checkbox = QCheckBox("Monotonous HSV Directions")
        layout.addWidget(self.monotonicity_checkbox, len(factors), 0, 1, 2)

        return widget

    def _add_min_max_sliders(self, min_val, max_val, min_default, max_default, min_attr_name, max_attr_name, parent_layout):
        # Create Labels
        min_label = QLabel(f"Min: {min_default}")
        max_label = QLabel(f"Max: {max_default}")

        # Create Sliders
        min_slider = QSlider(Qt.Orientation.Horizontal)
        min_slider.setRange(min_val, max_val)
        min_slider.setValue(min_default)
        min_slider.setMaximum(max_default)

        max_slider = QSlider(Qt.Orientation.Horizontal)
        max_slider.setRange(min_val, max_val)
        max_slider.setValue(max_default)
        max_slider.setMinimum(min_default)

        # Update Labels Dynamically
        min_slider.valueChanged.connect(lambda val, l=min_label: l.setText(f"Min: {val}"))
        max_slider.valueChanged.connect(lambda val, l=max_label: l.setText(f"Max: {val}"))

        # Enforce min ≤ max constraint
        self.link_min_max_sliders(min_slider, max_slider)

        # Layout for Labels
        label_row = QHBoxLayout()
        label_row.addWidget(min_label)
        label_row.addWidget(max_label)

        # Layout for Sliders
        slider_row = QHBoxLayout()
        slider_row.addWidget(min_slider)
        slider_row.addWidget(max_slider)

        # Add to Parent Layout
        parent_layout.addLayout(label_row)
        parent_layout.addLayout(slider_row)

        # Store sliders as instance attributes
        setattr(self, min_attr_name, min_slider)
        setattr(self, max_attr_name, max_slider)

    @staticmethod
    def link_min_max_sliders(min_slider, max_slider):
        min_slider.valueChanged.connect(lambda val: max_slider.setMinimum(val))
        max_slider.valueChanged.connect(lambda val: min_slider.setMaximum(val))

    def _create_vector_controls(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.vector_angle_slider = self._create_slider("Angle Step Max (°)", 0, 180, 45, layout)
        self.vector_magnitude_slider = self._create_slider("Step Magnitude Max", 0, 100, 45, layout)
        return widget

    def _create_ciede_controls(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.delta_e_slider = self._create_slider("ΔE2000 Step Max", 0, 50, 40, layout)
        self.delta_e_var_slider = self._create_slider("ΔE2000 Variance Tolerance", 0, 30, 15, layout)
        return widget

    @staticmethod
    def _create_slider(label_text, min_val, max_val, default, layout):
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

    def update_extract_button_state(self):
        has_graph = self.graph_viewer.color_graph is not None and len(self.graph_viewer.color_graph.nodes) > 0
        self.extract_button.setEnabled(has_graph)

    def extract_color_ramps(self):
        graph = self.graph_viewer.color_graph
        if graph is None:
            return

        method = self.extraction_method_selector.currentText()
        params = self._get_extraction_params(method)
        remove_similar = self.remove_similar_checkbox.isChecked()

        skip_subsequences = self.skip_subsequences_checkbox.isChecked()
        skip_reverse = self.skip_reverse_checkbox.isChecked()
        skip_permutations = self.skip_permutations_checkbox.isChecked()
        max_ramp_length = self.max_length_slider.value()

        ramps = self.find_color_ramps(
            graph, method, params,
            max_length=max_ramp_length,
            skip_subsequences=skip_subsequences,
            skip_reverse=skip_reverse,
            skip_permutations=skip_permutations
        )

        if len(ramps) > 2 and remove_similar:
            ramps = self.remove_similar_ramps(ramps)

        self.display_color_ramps(ramps)

    def _get_extraction_params(self, method):
        if method == "Basic HSV":
            return {
                'max_step': [
                    self.h_slider.value() / 180.0,
                    self.s_slider.value() / 100.0,
                    self.v_slider.value() / 100.0
                ],
                'min_step': [
                    self.h_min_slider.value() / 180.0,
                    self.s_min_slider.value() / 100.0,
                    self.v_min_slider.value() / 100.0
                ],
                'tolerance': [
                    self.h_tol_slider.value() / 180.0,
                    self.s_tol_slider.value() / 100.0,
                    self.v_tol_slider.value() / 100.0
                ],
                'monotonicity': self.monotonicity_checkbox.isChecked()
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
        self.generated_ramps = ramps
        self.clear_layout(self.ramps_layout)
        self.generated_ramp_widgets.clear()

        for ramp in ramps:
            widget = ColorRamp(ramp, source="generated")
            widget.duplicated = ramp in final_palette_manager.get_ramps()
            widget.update_highlight()
            self.generated_ramp_widgets[tuple(ramp)] = widget
            self.ramps_layout.addWidget(widget)

        self.update_duplicates()
        self.finish_progress()

    def request_ramp_update(self, old_ramp, new_ramp):
        old_key = tuple(old_ramp)
        new_key = tuple(new_ramp)

        # Empty ramp, remove it
        if not new_ramp:
            final_palette_manager.remove_ramp(old_ramp)
            return

        # Duplicate of existing ramp, remove it
        if new_ramp != old_ramp and new_ramp in final_palette_manager.get_ramps():
            final_palette_manager.remove_ramp(old_ramp)
            return

        final_palette_manager.update_ramp(old_ramp, new_ramp)

        # Update the widget reference if needed
        if old_key in self.final_ramp_widgets:
            widget = self.final_ramp_widgets.pop(old_key)
            self.final_ramp_widgets[new_key] = widget
            widget.color_ramp = new_ramp

    def refresh_ramp_views(self):
        current_ramps = final_palette_manager.get_ramps()
        current_keys = [tuple(r) for r in current_ramps]

        # Remove obsolete widgets
        for key in list(self.final_ramp_widgets.keys()):
            if key not in current_keys:
                widget = self.final_ramp_widgets.pop(key)
                self.final_ramps_layout.removeWidget(widget)
                widget.deleteLater()

        # Reorder and insert widgets based on current manager list
        for i, ramp in enumerate(current_ramps):
            key = tuple(ramp)
            if key in self.final_ramp_widgets:
                widget = self.final_ramp_widgets[key]
            else:
                widget = ColorRamp(ramp, source="final", viewer=self)
                self.final_ramp_widgets[key] = widget

            self.final_ramps_layout.insertWidget(i, widget)

        self.update_duplicates()

        used_colors = {c for ramp in current_ramps for c in ramp}
        unused_colors = sorted(self.unique_colors - used_colors, key=lambda c: (c[3], c[0], c[1], c[2]))

        self.unused_label.setText("Unused Colors:" if unused_colors else "Unused Colors: None")
        self.unused_palette.populate(unused_colors, square_size=25)

    def update_duplicates(self):
        generated_keys = set(self.generated_ramp_widgets.keys())
        final_keys = set(self.final_ramp_widgets.keys())

        shared = generated_keys & final_keys

        # Update generated
        for key, widget in self.generated_ramp_widgets.items():
            widget.duplicated = key in shared
            widget.update_highlight()

        # Update final
        for key, widget in self.final_ramp_widgets.items():
            widget.duplicated = key in shared
            widget.update_highlight()

    @staticmethod
    def clear_layout(layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def find_color_ramps(self, graph, method="Basic HSV", params=None, max_length=20,
                         skip_reverse=False, skip_subsequences=True, skip_permutations=True):
        if params is None:
            params = {}

        ramps = []

        sorted_nodes = sorted(graph.nodes, key=lambda c: color_to_hsv(c)[2])  # Sort by brightness
        n = len(sorted_nodes)

        i = 0
        for start in sorted_nodes:
            self.update_progress("Extracting Ramps...", i, n)
            i += 1

            stack = [(start, [start])]
            while stack:
                current, path = stack.pop()

                if len(path) == max_length:
                    extended = False
                else:
                    extended = False
                    for neighbor in graph.neighbors(current):
                        if neighbor in path:
                            continue
                        new_path = path + [neighbor]
                        if len(new_path) > max_length:
                            continue
                        if RampExtractionViewer.is_valid_ramp(new_path, method, params):
                            stack.append((neighbor, new_path))
                            extended = True

                if not extended and len(path) >= 3:
                    if skip_permutations and any(set(path) == set(r) for r in ramps):
                        continue
                    if skip_subsequences and RampExtractionViewer.is_subsequence_of_any(path, ramps):
                        continue
                    if skip_reverse and any(path == list(reversed(r)) for r in ramps):
                        continue
                    ramps.append(path)

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
            abs_diffs = np.abs(comp_diffs)

            # Check max step
            if not np.all(abs_diffs <= params.get('max_step', [1, 1, 1])[i] + 1e-5):
                return False

            # Check min step
            if not np.all(abs_diffs >= params.get('min_step', [0, 0, 0])[i] - 1e-5):
                return False

            # Check step variance
            if not RampExtractionViewer.is_consistent_step_size(
                    comp_diffs, params.get('tolerance', [0.1, 0.1, 0.1])[i]):
                return False

            # Monotonicity Check (Optional)
            if params.get('monotonicity', False):
                if not RampExtractionViewer.is_monotonic_direction(comp_diffs):
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

            if norm_product < 0.001:
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

        # if not RampExtractionViewer.is_monotonic_delta_e(delta_e_steps):
        #     return False

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
        non_zero = deltas[np.abs(deltas) > 0.05]
        if len(non_zero) == 0:
            return True
        return np.all(non_zero >= 0) or np.all(non_zero <= 0)

    @staticmethod
    def is_monotonic_delta_e(delta_e_steps, tolerance=1):
        diffs = np.diff(delta_e_steps)
        non_zero_diffs = diffs[np.abs(diffs) > tolerance]
        if len(non_zero_diffs) == 0:
            return True  # Flat ΔE changes, accept as monotonic
        return np.all(non_zero_diffs >= 0) or np.all(non_zero_diffs <= 0)

    @staticmethod
    def is_consistent_step_size(deltas, tolerance):
        non_zero = deltas[np.abs(deltas) > 0.001]
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

    def remove_similar_ramps(self, ramps, distance_threshold=2):
        if not ramps:
            return ramps

        n = len(ramps)
        total_pairs = (n * (n - 1)) // 2
        pair_count = 0
        distance_matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(i + 1, n):
                pair_count += 1
                self.update_progress("Computing Distances...", pair_count, total_pairs)
                dist = RampExtractionViewer.ramp_edit_distance(
                    ramps[i], ramps[j],
                    swap_cost=0.5,
                    insertion_cost=1.0,
                    permutation_penalty=0.0
                )
                distance_matrix[i, j] = dist
                distance_matrix[j, i] = dist

        self.update_progress("Clustering...", 0, 0)
        clustering = AgglomerativeClustering(
            metric='precomputed',
            linkage='average',
            distance_threshold=distance_threshold,
            n_clusters=None
        )
        clustering.fit(distance_matrix)
        labels = clustering.labels_

        self.show_ramp_clusters(ramps, labels)

        # Select the best ramp from each cluster
        final_ramps = []
        for label in np.unique(labels):
            indices = np.where(labels == label)[0]
            candidate_ramps = [ramps[i] for i in indices]
            best_ramp = RampExtractionViewer.select_best_ramp(candidate_ramps)
            final_ramps.append(best_ramp)

        # Sort final ramps by brightness of the first color (V in HSV)
        final_ramps.sort(key=lambda r: color_to_hsv(r[0])[2])

        return final_ramps

    @staticmethod
    def ramp_edit_distance(r1, r2, similarity_hsv_params=None, swap_cost=0.5, insertion_cost=1.0, substitution_cost=1.0, permutation_penalty=0.0):
        if similarity_hsv_params is None:
            similarity_hsv_params = {'hue_threshold': 15, 'sat_threshold': 0.1, 'val_threshold': 0.1}

        # Quick check: same colors, just reordered
        if set(r1) == set(r2):
            return permutation_penalty

        len_r1, len_r2 = len(r1), len(r2)
        dp = np.zeros((len_r1 + 1, len_r2 + 1))

        for i in range(len_r1 + 1):
            dp[i][0] = i * insertion_cost
        for j in range(len_r2 + 1):
            dp[0][j] = j * insertion_cost

        for i in range(1, len_r1 + 1):
            for j in range(1, len_r2 + 1):
                c1, c2 = r1[i - 1], r2[j - 1]

                if is_similar_hsv(c1, c2, **similarity_hsv_params):
                    subst_cost = 0
                else:
                    subst_cost = substitution_cost

                dp[i][j] = np.min([
                    dp[i - 1][j] + insertion_cost,
                    dp[i][j - 1] + insertion_cost,
                    dp[i - 1][j - 1] + subst_cost
                ])

                # Handle adjacent swaps (Damerau-Levenshtein)
                if i > 1 and j > 1 and r1[i - 1] == r2[j - 2] and r1[i - 2] == r2[j - 1]:
                    dp[i, j] = min(float(dp[i, j]), float(dp[i - 2, j - 2] + swap_cost))

        return dp[len_r1][len_r2]

    @staticmethod
    def select_best_ramp(ramps):
        best_score = -np.inf
        best_ramp = ramps[0]

        ramp_lengths = [len(r) for r in ramps]

        for ramp in ramps:
            (score, _, _, _, _) = RampExtractionViewer.evaluate_ramp_smoothness(ramp, min(ramp_lengths))
            if score > best_score:
                best_score = score
                best_ramp = ramp

        return best_ramp

    @staticmethod
    def evaluate_ramp_smoothness(ramp, min_length_in_cluster=3):
        diffs = hsv_diffs(ramp)
        step_sizes = np.linalg.norm(diffs, axis=1)

        # Variance penalty
        std_devs = np.std(diffs, axis=0)
        variance_penalty = np.mean(std_devs)

        # Monotonicity score
        monotonicity_count = sum(
            RampExtractionViewer.is_monotonic_direction(diffs[:, i]) for i in range(3)
        )
        if monotonicity_count == 3:
            monotonicity_score = 0.1
        elif monotonicity_count == 2:
            monotonicity_score = 0.05
        else:
            monotonicity_score = 0.01

        # Step Size Penalty (penalize extremes)
        preferred_center = 0.15
        preferred_range = 0.15
        penalty = np.mean(((step_sizes - preferred_center) / preferred_range) ** 2) * 0.2

        length_boost = 0.01 * (len(ramp) - min_length_in_cluster)

        final_score = - variance_penalty - penalty + length_boost + monotonicity_score

        return final_score, variance_penalty, penalty, length_boost, monotonicity_score

    def show_ramp_clusters(self, ramps, labels):
        dialog = QDialog(self)
        dialog.setWindowTitle("Ramp Clusters")
        dialog.resize(1200, 600)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        unique_labels = np.unique(labels)

        for cluster_id in unique_labels:
            cluster_label = QLabel(f"Cluster {cluster_id + 1}")
            cluster_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
            layout.addWidget(cluster_label)

            ramp_indices = np.where(labels == cluster_id)[0]
            candidate_ramps = [ramps[i] for i in ramp_indices]
            ramp_lengths = [len(r) for r in candidate_ramps]

            # Compute goodness scores and factors
            results = [self.evaluate_ramp_smoothness(ramp, min(ramp_lengths)) for ramp in candidate_ramps]
            scores = [res[0] for res in results]
            best_index = np.argmax(scores)

            for idx_in_cluster, (ramp, (score, var_penalty, size_penalty, length_boost, mono_score)) in enumerate(
                    zip(candidate_ramps, results)):
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                row_layout.setSpacing(10)

                # Swatches Area (Auto Width, Left-Aligned, No Gaps)
                swatches_widget = QWidget()
                swatches_layout = QHBoxLayout(swatches_widget)
                swatches_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                swatches_layout.setContentsMargins(0, 0, 0, 0)
                swatches_layout.setSpacing(0)

                for color in ramp:
                    r, g, b, a = color
                    swatch = QLabel()
                    swatch.setFixedSize(25, 25)
                    swatch.setStyleSheet(
                        f"background-color: rgba({r},{g},{b},{a}); border: none; margin: 0px; padding: 0px;")
                    swatches_layout.addWidget(swatch)

                row_layout.addWidget(swatches_widget)

                # Selection Label (Fixed Width)
                is_selected = idx_in_cluster == best_index
                selected_label = QLabel("[Selected]" if is_selected else "")
                selected_label.setStyleSheet("""
                    font-weight: bold; 
                    color: green;
                    font-family: monospace;
                """)
                row_layout.addWidget(selected_label)
                row_layout.addStretch()

                # Goodness Factors Label with Colored Factors if Selected
                if is_selected:
                    factor_style = "color: green; font-weight: bold;"
                else:
                    factor_style = ""

                factors_html = (
                    f"<span style='font-family: monospace;'>"
                    f"Good: <span style='{factor_style}'>{score:.3f}</span>, "
                    f"Var: <span style='{factor_style}'>-{var_penalty:.3f}</span>, "
                    f"Siz: <span style='{factor_style}'>-{size_penalty:.3f}</span>, "
                    f"Len: <span style='{factor_style}'>{length_boost:.2f}</span>, "
                    f"Mon: <span style='{factor_style}'>{mono_score:.2f}</span>"
                    f"</span>"
                )

                factors_label = QLabel()
                factors_label.setTextFormat(Qt.TextFormat.RichText)
                factors_label.setText(factors_html)
                factors_label.setFixedWidth(600)
                row_layout.addWidget(factors_label)

                layout.addWidget(row_widget)

        scroll.setWidget(container)

        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.addWidget(scroll)
        dialog.exec()

    def update_progress(self, message, value, maximum):
        parent_window = self.window()
        if hasattr(parent_window, 'progress_overlay'):
            parent_window.progress_overlay.update_progress(message, value, maximum)

    def finish_progress(self):
        parent_window = self.window()
        if hasattr(parent_window, 'progress_overlay'):
            parent_window.progress_overlay.finish()

    def tool_active(self, name):
        return {
            "add_remove": self.add_remove_tool.isChecked(),
            "split": self.split_tool.isChecked(),
            "merge": self.merge_tool.isChecked()
        }.get(name, False)

    def tool_active_any(self):
        return any(btn.isChecked() for btn in self.tool_group.buttons())

    def tool_active_name(self):
        for btn in self.tool_group.buttons():
            if btn.isChecked():
                return btn.text().lower().replace("/", "_")  # e.g., "add_remove"
        return None

    def update_tool_color_display(self, selected_color, hovered_color):
        if selected_color:
            rgba = f"rgba({selected_color[0]},{selected_color[1]},{selected_color[2]},{selected_color[3]})"
            self.tool_color_preview.setText("")
            self.tool_color_preview.setStyleSheet(f"""
                border: 1px solid #888;
                background-color: {rgba};
            """)
        else:
            self.tool_color_preview.setText("No color")
            self.tool_color_preview.setStyleSheet("""
                border: 1px solid #888;
                background-color: transparent;
                font-size: 10pt;
            """)

    def cleanup(self):
        try:
            self.clear_layout(self.ramps_layout)
            self.clear_layout(self.final_ramps_layout)
            self.generated_ramp_widgets.clear()
            self.final_ramp_widgets.clear()
            self.unused_palette.clear()
            final_palette_manager.unregister_listener(self.refresh_ramp_views)
            selection_manager.unregister_listener(self.update_tool_color_display)
        except:
            pass
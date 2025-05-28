import colorsys
import json
import os
from copy import deepcopy

import numpy as np
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QScrollArea, QFileDialog, QMessageBox, QGroupBox, QRadioButton, QComboBox, QCheckBox
)

from colorpicker import ColorPicker
from global_managers import global_selection_manager, global_ramp_manager, global_color_manager
from image_viewer import ImageViewer
from palette import ColorRamp
from ramp_extraction_window import RampWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ramp_window = None
        self._active_ramp_backup = {}
        self._last_selected_id = None

        self.setWindowTitle("Pixel Art Color Processor")
        self.resize(1600, 900)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # === LEFT CONTROL PANEL ===
        self.left_panel = QWidget()
        self.left_panel.setMinimumWidth(300)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(10)

        # Color Picker Container
        self.color_picker_container = QWidget()
        self.color_picker_container.setMinimumHeight(260)
        color_picker_layout = QVBoxLayout(self.color_picker_container)
        color_picker_layout.setContentsMargins(0, 0, 0, 0)
        color_picker_layout.setSpacing(0)

        # Color Picker Widget
        self.color_picker = ColorPicker()
        self.color_picker.colorChanged.connect(self._on_picker_color_changed)
        color_picker_layout.addWidget(self.color_picker)
        self.color_picker.setVisible(False)

        left_layout.addWidget(self.color_picker_container)

        # Mode Selection
        self.mode_group = QGroupBox("Propagation Mode")
        self.mode_group.setStyleSheet("font-weight: bold;")
        mode_layout = QVBoxLayout(self.mode_group)

        self.basic_mode_radio = QRadioButton("Basic")
        self.gradient_mode_radio = QRadioButton("Gradient-Aware")
        self.gradient_mode_radio.setChecked(True)

        mode_layout.addWidget(self.basic_mode_radio)
        mode_layout.addWidget(self.gradient_mode_radio)
        left_layout.addWidget(self.mode_group)
        self.mode_group.hide()

        # Gradient-Aware Options
        self.gradient_options = QWidget()
        gradient_layout = QVBoxLayout(self.gradient_options)
        gradient_layout.setContentsMargins(0, 0, 0, 0)

        self.gradient_style_combo = QComboBox()
        self.gradient_style_combo.addItems(["No Propagation", "Scale & Shift", "Preserve Ratios"])
        self.lock_ends_checkbox = QCheckBox("Lock Ramp Ends")
        self.lock_ends_checkbox.setChecked(False)
        self.lock_ends_checkbox.hide()

        gradient_layout.addWidget(QLabel("Propagation Style:"))
        gradient_layout.addWidget(self.gradient_style_combo)
        gradient_layout.addWidget(self.lock_ends_checkbox)

        # self.gradient_options.setVisible(False)
        color_picker_layout.addWidget(self.gradient_options)
        self.gradient_options.hide()

        # Connect toggles
        self.gradient_mode_radio.toggled.connect(self._on_propagation_mode_changed)

        # Selected Ramps Viewer
        self.ramp_scroll = QScrollArea()
        self.ramp_scroll.setWidgetResizable(True)
        self.ramp_content = QWidget()
        self.ramp_layout = QVBoxLayout(self.ramp_content)
        self.ramp_content.setLayout(self.ramp_layout)
        self.ramp_scroll.setWidget(self.ramp_content)
        left_layout.addWidget(QLabel("Color Ramps"))
        left_layout.addWidget(self.ramp_scroll, stretch=1)

        # Button container
        button_layout = QHBoxLayout()

        # Extract Button
        self.extract_button = QPushButton("Extract")
        self.extract_button.clicked.connect(self.open_ramp_window)
        button_layout.addWidget(self.extract_button)

        # Export Button
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export_color_data)
        self.export_button.setEnabled(False)  # Initially disabled
        button_layout.addWidget(self.export_button)

        # Import Button
        self.import_button = QPushButton("Import")
        self.import_button.clicked.connect(self.import_color_data)
        self.import_button.setEnabled(False)  # Initially disabled
        button_layout.addWidget(self.import_button)

        left_layout.addLayout(button_layout)
        main_layout.addWidget(self.left_panel)

        # === RIGHT: IMAGE VIEWER ===
        self.viewer = ImageViewer(show_color_details=False)
        self.viewer.colorDetails.hide()  # Permanently hide overlay
        main_layout.addWidget(self.viewer, stretch=1)

        self.viewer.load_image(file_path="resources/character/medium-contrast.png")
        self.import_color_data("resources/exports/medium-contrast_ramps.json")

        self.viewer.loadButton.clicked.connect(self.on_new_image_loaded)

        # Listen for color changes
        global_selection_manager.register_listener(self.update_color_details)
        global_ramp_manager.register_listener(self.update_button_states)
        self.update_button_states()

    def _on_propagation_mode_changed(self):
        is_gradient_mode = self.gradient_mode_radio.isChecked()
        self.gradient_options.setVisible(is_gradient_mode)

    def on_new_image_loaded(self):
        global_ramp_manager.clear_ramps()
        self.refresh_ramps()

    def update_button_states(self):
        has_image = self.viewer.original_pixmap is not None
        has_ramps = len(global_ramp_manager.get_ramps()) > 0

        self.extract_button.setEnabled(has_image)
        self.import_button.setEnabled(has_image)
        self.export_button.setEnabled(has_ramps)


    def _on_picker_color_changed(self):
        selected_color_id = global_selection_manager.selected_color_id
        if selected_color_id is None:
            return

        r, g, b = [int(x) for x in self.color_picker.get_rgb()]

        current_color = global_color_manager.color_groups[selected_color_id].current_color
        new_color = (r, g, b, current_color[3])
        if new_color == current_color:
            return

        is_gradient_mode = self.gradient_mode_radio.isChecked()
        preserve_style = self.gradient_style_combo.currentText()
        lock_ends = self.lock_ends_checkbox.isChecked()

        # Save original ramp state if first edit since selection
        if selected_color_id != self._last_selected_id:
            self._active_ramp_backup.clear()
            self._last_selected_id = selected_color_id
            for ramp in global_ramp_manager.get_ramps():
                if selected_color_id in ramp:
                    backup_colors = [(cid, deepcopy(global_color_manager.color_groups[cid].current_color)) for cid in ramp]
                    self._active_ramp_backup[tuple(ramp)] = backup_colors

        # Use backup to compute changes
        for ramp_key, ramp in self._active_ramp_backup.items():
            if selected_color_id not in [cid for cid, _ in ramp]:
                continue

            index = next(i for i, (cid, _) in enumerate(ramp) if cid == selected_color_id)
            original_colors = [color for _, color in self._active_ramp_backup[ramp_key]]

            # Convert to HSV
            hsv_ramp = [colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0) for r, g, b, _ in original_colors]
            h0, s0, v0 = hsv_ramp[index]
            h1, s1, v1 = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

            new_hsv_ramp = []

            if preserve_style == "No Propagation":
                # Just update the selected color without affecting others
                new_hsv_ramp = list(hsv_ramp)
                new_hsv_ramp[index] = (h1, s1, v1)

            elif preserve_style == "Scale & Shift":
                # Extract original S and V curves
                orig_s = np.array([s for _, s, _ in hsv_ramp])
                orig_v = np.array([v for _, _, v in hsv_ramp])
                orig_h = np.array([h for h, _, _ in hsv_ramp])

                # Target new HSV
                h_target, s_target, v_target = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

                # Morph S and V curves
                new_s = self.morph_curve(orig_s, index, s_target, lock_ends)
                new_v = self.morph_curve(orig_v, index, v_target, lock_ends)

                # For hue, wrap delta as circular shift
                delta_h = ((h_target - orig_h[index] + 0.5) % 1.0) - 0.5
                new_h = (orig_h + delta_h) % 1.0
                if lock_ends:
                    new_h[0] = orig_h[0]
                    new_h[-1] = orig_h[-1]

                new_hsv_ramp = [(float(h), float(s), float(v)) for h, s, v in zip(new_h, new_s, new_v)]
                new_hsv_ramp[index] = (h1, s1, v1)

            elif preserve_style == "Preserve Ratios":
                new_hsv_ramp = []
                for j, (h, s, v) in enumerate(hsv_ramp):
                    # Skip if this is the changed color
                    if j == index:
                        new_hsv_ramp.append((h1, s1, v1))
                        continue

                    # Skip if it's a locked end
                    if lock_ends and (j == 0 or j == len(hsv_ramp) - 1):
                        new_hsv_ramp.append((h, s, v))
                        continue

                    # For locked ends, smoothly adjust the ratios based on position
                    if lock_ends:
                        # Who knows
                        pass
                    else:
                        # Original ratio preservation for unlocked ends
                        s_ratio = float(s / s0) if s0 else 1.0
                        v_ratio = float(v / v0) if v0 else 1.0
                        h_diff = float((h - h0 + 0.5) % 1.0 - 0.5)
                        new_h = float((h1 + h_diff) % 1.0)

                    # Apply the ratios
                    new_s = float(max(0, min(1, s1 * s_ratio)))
                    new_v = float(max(0, min(1, v1 * v_ratio)))

                    new_hsv_ramp.append((new_h, new_s, new_v))

            new_rgb_ramp = [tuple(int(x * 255) for x in colorsys.hsv_to_rgb(h, s, v)) + (original_colors[i][3],)
                            for i, (h, s, v) in enumerate(new_hsv_ramp)]

            cid_list = [cid for cid, _ in self._active_ramp_backup[ramp_key]]
            for cid, new_col in zip(cid_list, new_rgb_ramp):
                 global_color_manager.set_color(cid, new_col)
                 self.viewer.replace_color(cid, new_col)

        global_selection_manager.select_color_id(selected_color_id)

    @staticmethod
    def morph_curve(orig_curve, target_index, new_value, lock_ends=False):
        orig = np.array(orig_curve, dtype=float)
        i = target_index

        if lock_ends:
            # Fit scale/shift such that start and end stay fixed
            x1, x2 = orig[i], orig[-1]
            y1, y2 = new_value, orig[-1]

            if i == 0:
                scale = 1.0
                shift = new_value - orig[i]
            elif x2 - x1 == 0:
                scale = 1.0
                shift = y1 - x1
            else:
                scale = (y2 - y1) / (x2 - x1)
                shift = y1 - scale * x1

            new_curve = scale * orig + shift
            new_curve[0] = orig[0]
            new_curve[-1] = orig[-1]

        else:
            orig = np.array(orig_curve, dtype=float)
            if orig[i] == 0:
                return orig

            scale = new_value / orig[i]
            mean_orig = orig.mean()
            shift = mean_orig - (scale * mean_orig)
            new_curve = scale * orig + shift * 1.2

        return np.clip(new_curve, 0, 1)

    def update_color_details(self, selected_color_id, hovered_color_id):
        target_color_id = hovered_color_id or selected_color_id
        if target_color_id is not None:
            # Get the actual color from the color manager using the ID
            actual_color = global_color_manager.color_groups[target_color_id].current_color
            self.color_picker.blockSignals(True)
            self.color_picker.set_rgb((actual_color[0], actual_color[1], actual_color[2]))
            self.color_picker.blockSignals(False)
            self.color_picker.setVisible(True)
            self.gradient_options.setVisible(True)
        else:
            self.color_picker.setVisible(False)
            self.gradient_options.setVisible(False)

    def refresh_ramps(self):
        for i in reversed(range(self.ramp_layout.count())):
            widget = self.ramp_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        for ramp in global_ramp_manager.get_ramps():
            ramp_widget = ColorRamp(ramp, source="final")
            self.ramp_layout.addWidget(ramp_widget)

        self.update_button_states()

    def open_ramp_window(self):
        if not self.viewer.original_pixmap:
            return
        global_selection_manager.clear_selection()
        self.ramp_window = RampWindow(self.viewer.original_pixmap)
        self.ramp_window.ramps_saved.connect(self.refresh_ramps)
        self.ramp_window.show()

    def export_color_data(self):
        if not global_ramp_manager.get_ramps():
            return

        suggested_name = "color_ramps.json"
        if self.viewer.current_image_path:
            suggested_name = os.path.splitext(os.path.basename(self.viewer.current_image_path))[0] + "_ramps.json"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Color Data",
            suggested_name,
            "Color Data Files (*.json)"
        )
        
        if not file_path:
            return
        
        data = {
            'colors': {},
            'ramps': []
        }
        
        # Save color groups, converting numpy.uint8 to int
        for color_id, group in global_color_manager.color_groups.items():
            data['colors'][str(color_id)] = {
                'color': tuple(int(x) for x in group.current_color),
                'positions': list(group.pixel_positions)
            }
        
        # Save ramps, converting any numpy.uint8 to int
        ramps = []
        for ramp in global_ramp_manager.get_ramps():
            ramp_colors = []
            for color in ramp:
                if isinstance(color, (tuple, list)):
                    ramp_colors.append(tuple(int(x) for x in color))
                else:
                    ramp_colors.append(color)
            ramps.append(ramp_colors)
        data['ramps'] = ramps
        
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export color data: {str(e)}")

    def import_color_data(self, file_path=None):
        if not self.viewer.original_pixmap:
            return

        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Load Color Data",
                "",
                "Color Data Files (*.json)"
            )

        if not file_path or not os.path.exists(file_path):
            return

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Verify colors match current image
            current_colors = {
                str(cid): tuple(int(x) for x in group.current_color)
                for cid, group in global_color_manager.color_groups.items()
            }
            imported_colors = {
                cid: tuple(group['color'])
                for cid, group in data['colors'].items()
            }

            if current_colors != imported_colors:
                QMessageBox.critical(
                    self,
                    "Import Error",
                    "The color values in the imported file don't match the current image colors."
                )
                return

            # Import ramps
            ramps = []
            for ramp in data['ramps']:
                ramp_colors = []
                for color in ramp:
                    if isinstance(color, (list, tuple)):
                        ramp_colors.append(tuple(color))
                    else:
                        ramp_colors.append(color)
                ramps.append(ramp_colors)

            global_ramp_manager._ramps = ramps
            global_ramp_manager._notify()

            self.refresh_ramps()
        
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import color data: {str(e)}")
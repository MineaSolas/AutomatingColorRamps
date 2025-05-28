import json
import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QScrollArea, QFileDialog, QMessageBox
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
        self.color_picker_container.setMinimumHeight(240)
        color_picker_layout = QVBoxLayout(self.color_picker_container)
        color_picker_layout.setContentsMargins(0, 0, 0, 0)
        color_picker_layout.setSpacing(0)

        # Color Picker Widget
        self.color_picker = ColorPicker()
        self.color_picker.colorChanged.connect(self._on_picker_color_changed)
        color_picker_layout.addWidget(self.color_picker)
        self.color_picker.setVisible(False)

        left_layout.addWidget(self.color_picker_container)

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

        # Get the new RGB values from the color picker and preserve alpha
        old_color = global_color_manager.color_groups[selected_color_id].current_color
        r, g, b = [int(x) for x in self.color_picker.get_rgb()]
        new_color = (r, g, b, old_color[3])

        if new_color == old_color:
            return

        # Update the color in both the color manager and image
        global_color_manager.set_color(selected_color_id, new_color)
        self.viewer.replace_color(selected_color_id, new_color)

        # Re-select the color to trigger UI updates
        global_selection_manager.select_color_id(selected_color_id)

    def update_color_details(self, selected_color_id, hovered_color_id):
        target_color_id = hovered_color_id or selected_color_id
        if target_color_id is not None:
            # Get the actual color from the color manager using the ID
            actual_color = global_color_manager.color_groups[target_color_id].current_color
            self.color_picker.blockSignals(True)
            self.color_picker.set_rgb((actual_color[0], actual_color[1], actual_color[2]))
            self.color_picker.blockSignals(False)
            self.color_picker.setVisible(True)
        else:
            self.color_picker.setVisible(False)

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

        if file_path is None:
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
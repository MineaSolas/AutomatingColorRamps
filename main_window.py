from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QScrollArea
)

from color_utils import get_text_descriptions
from colorpicker import ColorPicker
from image_viewer import ImageViewer
from palette import ColorRamp, selection_manager, final_palette_manager
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
        self.left_panel.setFixedWidth(320)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(10)

        # Color Picker Widget
        self.color_picker = ColorPicker()
        self.color_picker.colorChanged.connect(self._on_picker_color_changed)
        left_layout.addWidget(self.color_picker)
        self.color_picker.hide()

        # Selected Ramps Viewer
        self.ramp_scroll = QScrollArea()
        self.ramp_scroll.setWidgetResizable(True)
        self.ramp_content = QWidget()
        self.ramp_layout = QVBoxLayout(self.ramp_content)
        self.ramp_content.setLayout(self.ramp_layout)
        self.ramp_scroll.setWidget(self.ramp_content)
        left_layout.addWidget(QLabel("Selected Ramps:"))
        left_layout.addWidget(self.ramp_scroll, stretch=1)

        # Extract Button
        self.extract_button = QPushButton("Extract Color Ramps")
        self.extract_button.clicked.connect(self.open_ramp_window)
        left_layout.addWidget(self.extract_button)

        main_layout.addWidget(self.left_panel)

        # === RIGHT: IMAGE VIEWER ===
        self.viewer = ImageViewer(show_color_details=False)
        self.viewer.colorDetails.hide()  # Permanently hide overlay
        main_layout.addWidget(self.viewer, stretch=1)

        self.viewer.load_image(file_path="resources/character/medium-contrast.png")

        # Listen for color changes
        selection_manager.register_listener(self.update_color_details)

    def _on_picker_color_changed(self):
        old_color = selection_manager.selected_color
        if not old_color:
            return

        r, g, b = self.color_picker.getRGB()
        new_color = (int(r), int(g), int(b), old_color[3])

        if new_color == old_color:
            return

        # Update in image, palette, and ramps
        self.viewer.replace_color(old_color, new_color)
        #final_palette_manager.replace_color(old_color, new_color)
        selection_manager.select_color(new_color)

    def update_color_details(self, selected_color, hovered_color):
        target_color = hovered_color or selected_color
        if target_color:
            color = QColor(*target_color)
            self.color_picker.blockSignals(True)
            self.color_picker.setRGB((color.red(), color.green(), color.blue()))
            self.color_picker.blockSignals(False)
            self.color_picker.show()
        else:
            self.color_picker.hide()

    def refresh_ramps(self):
        for i in reversed(range(self.ramp_layout.count())):
            widget = self.ramp_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        for ramp in final_palette_manager.get_ramps():
            ramp_widget = ColorRamp(ramp, source="final")
            self.ramp_layout.addWidget(ramp_widget)

    def open_ramp_window(self):
        if not self.viewer.original_pixmap:
            return
        self.ramp_window = RampWindow(self.viewer.original_pixmap)
        self.ramp_window.ramps_saved.connect(self.refresh_ramps)
        self.ramp_window.show()


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

        # Color Details Widget
        self.color_details = self._create_color_details_widget()
        left_layout.addWidget(self.color_details)

        # Color Picker Widget
        self.color_picker = ColorPicker()
        self.color_picker.setFixedHeight(240)
        self.color_picker.colorChanged.connect(self._on_picker_color_changed)
        left_layout.addWidget(self.color_picker)

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

    def _create_color_details_widget(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Color Swatch
        self.swatch = QLabel()
        self.swatch.setFixedSize(100, 70)
        self.swatch.setStyleSheet("background-color: #fff; border: 1px solid #000;")
        layout.addWidget(self.swatch)

        # Text Details Stack
        text_layout = QVBoxLayout()
        self.rgb_label = QLabel("RGB:  -")
        self.hex_label = QLabel("HEX:  -")
        self.hsv_label = QLabel("HSV:  -")

        for label in [self.rgb_label, self.hex_label, self.hsv_label]:
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setStyleSheet("font-size: 10pt; border: none;")
            text_layout.addWidget(label)

        layout.addLayout(text_layout)

        return widget

    def _on_picker_color_changed(self):
        r, g, b = self.color_picker.getRGB()
        rgba = (int(r), int(g), int(b), 255)
        selection_manager.select_color(rgba)

    def update_color_details(self, selected_color, hovered_color):
        target_color = hovered_color or selected_color
        if target_color:
            info = get_text_descriptions(target_color)
            self.swatch.setStyleSheet(f"background-color: {info['hex_raw']}; border: 1px solid #000;")
            self.rgb_label.setText(info["rgb"])
            self.hex_label.setText(info["hex"])
            self.hsv_label.setText(info["hsv"])

            color = QColor(*target_color)
            self.color_picker.blockSignals(True)
            self.color_picker.setRGB((color.red(), color.green(), color.blue()))
            self.color_picker.blockSignals(False)
        else:
            self.swatch.setStyleSheet("background-color: #fff; border: 1px solid #000;")
            self.rgb_label.setText("RGB:  -")
            self.hex_label.setText("HEX:  -")
            self.hsv_label.setText("HSV:  -")

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


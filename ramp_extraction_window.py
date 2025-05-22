from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QPushButton, QHBoxLayout, QComboBox, QSlider, QScrollArea
from PyQt6.QtCore import Qt
from graph_viewer import GraphViewer
from image_viewer import ImageViewer
from ramp_extraction_viewer import RampExtractionViewer
from ui_helpers import ProgressOverlay


class RampWindow(QWidget):
    def __init__(self, loaded_pixmap):
        super().__init__()
        self.setWindowTitle("Color Ramp Extraction")
        self.resize(1600, 900)

        layout = QGridLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)

        # Top-Left: Image
        self.mini_viewer = ImageViewer(show_load_button=False, palette_square_size=25)
        self.mini_viewer.load_image(pixmap=loaded_pixmap)
        unique_colors = self.mini_viewer.color_palette.labels.keys()
        layout.addWidget(self.mini_viewer, 0, 0)

        # Top-Right: Graph Extraction
        self.graph_viewer = GraphViewer(
            image_array=self.mini_viewer.get_image_array(),
            unique_colors=unique_colors
        )
        layout.addWidget(self.graph_viewer, 0, 1)

        # Bottom: Ramp Extraction
        self.ramp_extraction_widget = RampExtractionViewer(self.graph_viewer, unique_colors=unique_colors)
        self.graph_viewer.graph_updated.connect(self.ramp_extraction_widget.update_extract_button_state)
        layout.addWidget(self.ramp_extraction_widget, 1, 0, 1, 2)

        # Ensure all grid cells are equal
        layout.setRowStretch(0, 1)
        layout.setRowStretch(1, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

        self.progress_overlay = ProgressOverlay(self)

    def closeEvent(self, event):
        self.mini_viewer.cleanup()
        self.ramp_extraction_widget.cleanup()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.progress_overlay.setGeometry(self.rect())

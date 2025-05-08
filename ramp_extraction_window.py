from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt
from image_viewer import ImageViewerWidget


class RampWindow(QWidget):
    def __init__(self, original_pixmap):
        super().__init__()
        self.setWindowTitle("Color Ramp Extraction")
        self.setMinimumSize(1000, 800)

        layout = QGridLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)

        # Top-Left: Mini viewer
        self.mini_viewer = ImageViewerWidget()
        self.mini_viewer.original_pixmap = original_pixmap
        self.mini_viewer.set_initial_fit_zoom()
        self.mini_viewer.update_image()
        self.mini_viewer.extract_unique_colors()
        layout.addWidget(self.mini_viewer, 0, 0)

        # Top-Right: Placeholder for graph
        self.graph_view = QLabel("Graph View (coming soon)")
        self.graph_view.setStyleSheet("background-color: #eee; border: 1px solid #888;")
        self.graph_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.graph_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.graph_view, 0, 1)

        # Bottom-Left: Placeholder for ramps
        self.ramp_display = QLabel("Ramps View (coming soon)")
        self.ramp_display.setStyleSheet("background-color: #f9f9f9; border: 1px solid #888;")
        self.ramp_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ramp_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.ramp_display, 1, 0)

        # Bottom-Right: Future controls
        self.controls_area = QLabel("Controls / Filters (future)")
        self.controls_area.setStyleSheet("background-color: #ddd; border: 1px solid #888;")
        self.controls_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.controls_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.controls_area, 1, 1)

        # Ensure all grid cells are equal
        layout.setRowStretch(0, 1)
        layout.setRowStretch(1, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

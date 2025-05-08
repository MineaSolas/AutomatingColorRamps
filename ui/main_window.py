from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton
from image_viewer import ImageViewerWidget
from ramp_extraction_window import RampWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pixel Art Color Processor")
        self.resize(1600, 900)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)

        self.viewer = ImageViewerWidget()
        self.layout.addWidget(self.viewer, stretch=1)

        self.extract_button = QPushButton("Extract Color Ramps")
        self.extract_button.clicked.connect(self.open_ramp_window)
        self.layout.addWidget(self.extract_button, stretch=0)

        self.viewer.load_image("resources/tree-sample.png")

    def open_ramp_window(self):
        if not self.viewer.original_pixmap:
            return
        self.ramp_window = RampWindow(self.viewer.original_pixmap)
        self.ramp_window.show()

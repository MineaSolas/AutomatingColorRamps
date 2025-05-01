from PyQt6.QtWidgets import QMainWindow, QFileDialog, QWidget, QGridLayout, QLabel
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt
import numpy as np
from PIL import Image
from ui.main_window import Ui_MainWindow


class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.loadButton.clicked.connect(self.load_image)
        self.ui.zoomSlider.valueChanged.connect(self.update_zoom)

        self.original_pixmap = None
        self.ui.imageLabel.setScaledContents(False)

    def load_image(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open Image",
            "",
            "Images (*.png *.jpg *.bmp)"
        )
        if file_name:
            self.original_pixmap = QPixmap(file_name)
            self.update_zoom()
            self.extract_unique_colors()

    def update_zoom(self):
        if self.original_pixmap:
            zoom = self.ui.zoomSlider.value()
            scaled_pixmap = self.original_pixmap.scaled(
                self.original_pixmap.width() * zoom,
                self.original_pixmap.height() * zoom,
                transformMode=Qt.TransformationMode.FastTransformation
            )
            self.ui.imageLabel.setPixmap(scaled_pixmap)
            self.ui.imageLabel.resize(scaled_pixmap.size())

    def extract_unique_colors(self):
        if not self.original_pixmap:
            return

        qimage = self.original_pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        width = qimage.width()
        height = qimage.height()

        ptr = qimage.bits()
        ptr.setsize(qimage.sizeInBytes())
        arr = np.array(ptr, dtype=np.uint8).reshape((height, width, 4))

        pil_image = Image.fromarray(arr, mode='RGBA')

        pixels = list(pil_image.getdata())
        unique_colors = sorted(set(pixels), key=lambda c: (c[3], c[0], c[1], c[2]))
        unique_colors = [c for c in unique_colors if c[3] > 0]  # Ignore transparent

        self.display_color_palette(unique_colors)

    def display_color_palette(self, colors):
        # Remove existing palette if any
        if hasattr(self, "palette_widget"):
            self.ui.verticalLayout.removeWidget(self.palette_widget)
            self.palette_widget.deleteLater()

        self.palette_widget = QWidget()
        layout = QGridLayout()
        self.palette_widget.setLayout(layout)

        for i, color in enumerate(colors):
            r, g, b, a = color
            label = QLabel()
            label.setFixedSize(20, 20)
            label.setStyleSheet(f"background-color: rgba({r},{g},{b},{a}); border: 1px solid #000;")
            layout.addWidget(label, i // 20, i % 20)

        self.ui.verticalLayout.addWidget(self.palette_widget)



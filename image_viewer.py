import colorsys
from PyQt6.QtWidgets import QMainWindow, QFileDialog, QWidget, QGridLayout, QLabel
from PyQt6.QtGui import QPixmap, QImage, QColor
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

        self.ui.imageLabel.setMouseTracking(True)
        self.ui.imageLabel.mouseMoveEvent = self.image_mouse_move

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
        if hasattr(self, "palette_widget"):
            self.ui.verticalLayout.removeWidget(self.palette_widget)
            self.palette_widget.deleteLater()

        self.palette_widget = QWidget()
        layout = QGridLayout()
        self.palette_widget.setLayout(layout)
        self.palette_labels = {}

        for i, color in enumerate(colors):
            r, g, b, a = color
            label = QLabel()
            label.setFixedSize(20, 20)
            label.setStyleSheet(f"background-color: rgba({r},{g},{b},{a}); border: 1px solid #000;")
            label.setToolTip(f"RGB: ({r}, {g}, {b})\nHEX: #{r:02X}{g:02X}{b:02X}")

            label.enterEvent = lambda event, col=color: self.highlight_color(col)
            label.leaveEvent = lambda event: self.clear_highlight()

            self.palette_labels[color] = label
            layout.addWidget(label, i // 20, i % 20)

        self.ui.verticalLayout.addWidget(self.palette_widget)

    def image_mouse_move(self, event):
        if not self.original_pixmap or not self.ui.imageLabel.pixmap():
            return

        label = self.ui.imageLabel
        pixmap = label.pixmap()
        if not pixmap:
            return

        # Get the size of the QLabel and the pixmap inside it
        label_size = label.size()
        pixmap_size = pixmap.size()

        # Get cursor position relative to QLabel
        pos = event.position().toPoint()

        # Adjust for scaling (centered image)
        offset_x = max((label_size.width() - pixmap_size.width()) // 2, 0)
        offset_y = max((label_size.height() - pixmap_size.height()) // 2, 0)

        x = pos.x() - offset_x
        y = pos.y() - offset_y

        if 0 <= x < pixmap_size.width() and 0 <= y < pixmap_size.height():
            # Map back to original image size
            img_x = int(x * self.original_pixmap.width() / pixmap_size.width())
            img_y = int(y * self.original_pixmap.height() / pixmap_size.height())

            if 0 <= img_x < self.original_pixmap.width() and 0 <= img_y < self.original_pixmap.height():
                image = self.original_pixmap.toImage()
                color = image.pixelColor(img_x, img_y).getRgb()
                self.highlight_color(color)
                return

        self.clear_highlight()

    def highlight_color(self, color):
        r, g, b = [c / 255.0 for c in color[:3]]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)

        if h < 0.125 or h > 0.7:
            highlight_rgb = (0, 255, 255)
        else:
            highlight_rgb = (255, 0, 0)

        highlight_color = QColor(*highlight_rgb)

        # Highlight palette
        target_rgb = tuple(int(c * 255) for c in (r, g, b))
        highlight_css = f"rgb({highlight_color.red()}, {highlight_color.green()}, {highlight_color.blue()})"
        for col, label in self.palette_labels.items():
            if col[:3] == target_rgb:
                label.setStyleSheet(
                    f"background-color: rgba{col}; border: 3px solid {highlight_css};"
                )
            else:
                label.setStyleSheet(
                    f"background-color: rgba{col}; border: 1px solid #000;"
                )

        # Highlight matching pixels with solid highlight color
        image = self.original_pixmap.toImage()
        highlighted = QImage(image)
        for x in range(image.width()):
            for y in range(image.height()):
                pix = image.pixelColor(x, y)
                if (pix.red(), pix.green(), pix.blue()) == target_rgb:
                    highlighted.setPixelColor(x, y, highlight_color)

        # Show
        pixmap = QPixmap.fromImage(highlighted)
        zoom = self.ui.zoomSlider.value()
        scaled_pixmap = pixmap.scaled(
            pixmap.width() * zoom,
            pixmap.height() * zoom,
            transformMode=Qt.TransformationMode.FastTransformation
        )
        self.ui.imageLabel.setPixmap(scaled_pixmap)

    def clear_highlight(self):
        self.update_zoom()  # Resets the image display

        for col, label in self.palette_labels.items():
            label.setStyleSheet(f"background-color: rgba{col}; border: 1px solid #000;")





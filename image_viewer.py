import colorsys
import math

from PyQt6.QtWidgets import QMainWindow, QFileDialog, QWidget, QGridLayout, QLabel, QSizePolicy, QHBoxLayout, \
    QVBoxLayout
from PyQt6.QtGui import QPixmap, QImage, QColor
from PyQt6.QtCore import Qt
import numpy as np
from PIL import Image

from ui.flow_layout import FlowLayout
from ui.main_window import Ui_MainWindow


class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.resize(1200, 800)

        self.ui.loadButton.clicked.connect(self.load_image)
        self.ui.zoomSlider.valueChanged.connect(self.update_zoom)
        self.ui.zoomLabel.setMinimumWidth(50)
        self.ui.zoomLabel.setStyleSheet("padding-bottom: 8px;")

        self.original_pixmap = None
        self.ui.imageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.imageLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.ui.imageLabel.setScaledContents(False)

        self.ui.imageLabel.setMouseTracking(True)
        self.ui.imageLabel.mouseMoveEvent = self.image_mouse_move

        # Create overlay widget on top-left of imageLabel
        self.colorOverlay = QWidget(self.ui.imageLabel)
        self.colorOverlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.colorOverlay.setStyleSheet("background-color: rgba(255, 255, 255, 180); border: 1px solid #999;")
        self.colorOverlay.move(10, 10)
        self.colorOverlay.resize(180, 120)  # increased height to fit all lines

        self.overlayLayout = QVBoxLayout(self.colorOverlay)
        self.overlayLayout.setContentsMargins(5, 5, 5, 5)

        self.colorSwatch = QLabel()
        self.colorSwatch.setFixedHeight(40)
        self.colorSwatch.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.colorSwatch.setStyleSheet("background-color: #ffffff; border: 1px solid #000;")
        self.overlayLayout.addWidget(self.colorSwatch)

        self.colorTextRGB = QLabel("RGB: -")
        self.colorTextHEX = QLabel("HEX: -")
        self.colorTextHSV = QLabel("HSV: -")

        for label in (self.colorTextRGB, self.colorTextHEX, self.colorTextHSV):
            label.setStyleSheet("font-size: 10pt;")
            self.overlayLayout.addWidget(label)

    def load_image(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open Image",
            "",
            "Images (*.png *.jpg *.bmp)"
        )
        if file_name:
            self.original_pixmap = QPixmap(file_name)
            self.set_initial_fit_zoom()
            self.update_zoom()
            self.extract_unique_colors()

    def update_zoom(self):
        zoom = self.get_zoom_factor()
        self.ui.zoomLabel.setText(f"{int(zoom * 100)}%")

        if self.original_pixmap:
            scaled_pixmap = self.original_pixmap.scaled(
                int(self.original_pixmap.width() * zoom),
                int(self.original_pixmap.height() * zoom),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
            self.ui.imageLabel.setPixmap(scaled_pixmap)

    def get_zoom_factor(self):
        return 1.16 ** (self.ui.zoomSlider.value() - 20)

    def set_initial_fit_zoom(self):
        if not self.original_pixmap:
            return

        container_size = self.ui.imageLabel.size()
        image_size = self.original_pixmap.size()

        scale_w = container_size.width() / image_size.width()
        scale_h = container_size.height() / image_size.height()

        zoom = min(scale_w, scale_h)

        # Convert zoom factor to slider value
        slider_value = int(round(math.log(zoom) / math.log(1.16 ) + 20)) - 2

        slider_value = max(self.ui.zoomSlider.minimum(), min(slider_value, self.ui.zoomSlider.maximum()))
        self.ui.zoomSlider.setValue(slider_value)

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
        layout = FlowLayout(spacing=5)
        layout.setContentsMargins(0, 0, 0, 0)
        self.palette_widget.setLayout(layout)
        self.palette_labels = {}

        for i, color in enumerate(colors):
            r, g, b, a = color
            label = QLabel()
            label.setFixedSize(40, 40)
            label.setStyleSheet(f"background-color: rgba({r},{g},{b},{a}); border: 1px solid #000;")

            label.enterEvent = lambda event, col=color: self.highlight_color(col)
            label.leaveEvent = lambda event: self.clear_highlight()

            self.palette_labels[color] = label
            layout.addWidget(label)

        self.ui.verticalLayout.addWidget(self.palette_widget)

    def image_mouse_move(self, event):
        if not self.original_pixmap or not self.ui.imageLabel.pixmap():
            return

        label = self.ui.imageLabel
        pixmap = label.pixmap()
        if not pixmap:
            return

        # Mouse position relative to the QLabel
        mouse_pos = event.position().toPoint()
        label_width = label.width()
        label_height = label.height()

        # Get the scaled pixmap size
        zoom = self.get_zoom_factor()
        pixmap_width = self.original_pixmap.width() * zoom
        pixmap_height = self.original_pixmap.height() * zoom

        # Calculate margins (image may be centered inside QLabel)
        offset_x = (label_width - pixmap_width) // 2
        offset_y = (label_height - pixmap_height) // 2

        # Coordinates inside the image
        x = (mouse_pos.x() - offset_x) // zoom
        y = (mouse_pos.y() - offset_y) // zoom

        # Validate coordinates
        if 0 <= x < self.original_pixmap.width() and 0 <= y < self.original_pixmap.height():
            image = self.original_pixmap.toImage()
            color = image.pixelColor(int(x), int(y)).getRgb()
            self.highlight_color(color)
        else:
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
                    f"background-color: rgba{col}; border: 5px solid {highlight_css};"
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
        zoom = self.get_zoom_factor()
        scaled_pixmap = pixmap.scaled(
            int(pixmap.width() * zoom),
            int(pixmap.height() * zoom),
            transformMode=Qt.TransformationMode.FastTransformation
        )
        self.ui.imageLabel.setPixmap(scaled_pixmap)

        r, g, b = color[:3]
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        h_deg = int(h * 360)
        s_pct = int(s * 100)
        v_pct = int(v * 100)
        hex_str = f"#{r:02X}{g:02X}{b:02X}"

        self.colorSwatch.setStyleSheet(f"background-color: {hex_str}; border: 1px solid #000;")
        self.colorTextRGB.setText(f"RGB: ({r}, {g}, {b})")
        self.colorTextHEX.setText(f"HEX: {hex_str}")
        self.colorTextHSV.setText(f"HSV: ({h_deg}°, {s_pct}%, {v_pct}%)")

    def clear_highlight(self):
        self.update_zoom()  # Resets the image display

        for col, label in self.palette_labels.items():
            label.setStyleSheet(f"background-color: rgba{col}; border: 1px solid #000;")

        self.colorSwatch.setStyleSheet("background-color: #ffffff; border: 1px solid #000;")
        self.colorTextRGB.setText("RGB: -")
        self.colorTextHEX.setText("HEX: -")
        self.colorTextHSV.setText("HSV: -")







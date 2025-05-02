import colorsys
import math

from PyQt6.QtWidgets import QMainWindow, QFileDialog, QLabel, QWidget, QVBoxLayout, QSizePolicy
from PyQt6.QtGui import QPixmap, QImage, QColor
from PyQt6.QtCore import Qt
import numpy as np
from PIL import Image

from clickable_image import ClickableImage
from color_utils import get_highlight_color, get_text_descriptions
from ui.main_window import Ui_MainWindow
from palette import ColorPalette


class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.resize(1200, 800)

        self.original_pixmap = None

        self.selected_color = None
        self.selected_border_color = "red"
        self.hovered_color = None

        self.ui.loadButton.clicked.connect(self.load_image)

        self.ui.zoomSlider.valueChanged.connect(self.update_image)
        self.ui.zoomLabel.setMinimumWidth(50)
        self.ui.zoomLabel.setStyleSheet("padding-bottom: 8px;")

        # Replace default imageLabel
        self.ui.verticalLayout.removeWidget(self.ui.imageLabel)
        self.ui.imageLabel.deleteLater()
        self.ui.imageLabel = ClickableImage(viewer=self)
        self.ui.verticalLayout.insertWidget(1, self.ui.imageLabel)

        # Setup color details overlay widget
        self.colorDetails = QWidget(self.ui.imageLabel)
        self.overlayLayout = QVBoxLayout(self.colorDetails)
        self.colorSwatch = QLabel()
        self.colorTextRGB = QLabel("RGB: -")
        self.colorTextHEX = QLabel("HEX: -")
        self.colorTextHSV = QLabel("HSV: -")
        self.init_color_details_widget()

        self.color_palette = ColorPalette(self)
        self.ui.verticalLayout.addWidget(self.color_palette)

    def init_color_details_widget(self):
        self.colorDetails.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.colorDetails.setStyleSheet("background-color: rgba(255, 255, 255, 180); border: 1px solid #999;")
        self.colorDetails.move(10, 10)
        self.colorDetails.resize(180, 120)

        self.overlayLayout.setContentsMargins(5, 5, 5, 5)

        self.colorSwatch.setFixedHeight(40)
        self.colorSwatch.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.colorSwatch.setStyleSheet("background-color: #ffffff; border: 1px solid #000;")
        self.overlayLayout.addWidget(self.colorSwatch)

        for label in (self.colorTextRGB, self.colorTextHEX, self.colorTextHSV):
            label.setStyleSheet("font-size: 10pt;")
            self.overlayLayout.addWidget(label)

    def load_image(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.bmp)")
        if file_name:
            self.original_pixmap = QPixmap(file_name)
            self.set_initial_fit_zoom()
            self.update_image()
            self.extract_unique_colors()

    def update_image(self):
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
        zoom = min(container_size.width() / image_size.width(), container_size.height() / image_size.height())
        slider_value = int(round(math.log(zoom) / math.log(1.16) + 20)) - 2
        self.ui.zoomSlider.setValue(max(self.ui.zoomSlider.minimum(), min(slider_value, self.ui.zoomSlider.maximum())))

    def extract_unique_colors(self):
        qimage = self.original_pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        ptr = qimage.bits()
        ptr.setsize(qimage.sizeInBytes())
        arr = np.array(ptr, dtype=np.uint8).reshape((qimage.height(), qimage.width(), 4))
        pixels = list(Image.fromarray(arr, mode='RGBA').getdata())
        unique_colors = sorted(set(pixels), key=lambda c: (c[3], c[0], c[1], c[2]))
        self.color_palette.populate([c for c in unique_colors if c[3] > 0])

    def get_image_color_at_pos(self, pos):
        if not self.original_pixmap or not self.ui.imageLabel.pixmap():
            return None
        label = self.ui.imageLabel
        zoom = self.get_zoom_factor()
        offset_x = (label.width() - self.original_pixmap.width() * zoom) // 2
        offset_y = (label.height() - self.original_pixmap.height() * zoom) // 2
        x = (pos.x() - offset_x) // zoom
        y = (pos.y() - offset_y) // zoom
        if 0 <= x < self.original_pixmap.width() and 0 <= y < self.original_pixmap.height():
            return self.original_pixmap.toImage().pixelColor(int(x), int(y)).getRgb()
        return None

    def image_mouse_move(self, event):
        color = self.get_image_color_at_pos(event.position().toPoint())
        self.show_color_info(color, is_hover=True) if color else self.clear_hover()

    def image_mouse_click(self, event):
        color = self.get_image_color_at_pos(event.position().toPoint())
        self.show_color_info(color, is_hover=False) if color else self.clear_selection()

    def show_color_info(self, color, is_hover=False):
        if not color:
            return
        if is_hover:
            self.hovered_color = color
        else:
            self.selected_color = color
            self.selected_border_color = get_highlight_color(color)
            self.hovered_color = None

        active_color = self.hovered_color if is_hover else self.selected_color
        r, g, b = [c / 255.0 for c in active_color[:3]]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        target_rgb = tuple(int(c * 255) for c in (r, g, b))
        highlight_color = QColor(*(0, 255, 255) if h < 0.125 or h > 0.7 else (255, 0, 0))

        self.color_palette.update_borders(self.selected_color, self.hovered_color, self.selected_border_color)

        if is_hover:
            self.update_image_highlight(target_rgb, highlight_color)
        else:
            self.update_image()

        self.update_overlay_text((r * 255, g * 255, b * 255))

    def update_overlay_text(self, color):
        info = get_text_descriptions(color)
        self.colorSwatch.setStyleSheet(f"background-color: {info['hex_raw']}; border: 1px solid #000;")
        self.colorTextRGB.setText(info["rgb"])
        self.colorTextHEX.setText(info["hex"])
        self.colorTextHSV.setText(info["hsv"])

    def update_image_highlight(self, target_rgb, highlight_color):
        image = self.original_pixmap.toImage()
        highlighted = QImage(image)
        for x in range(image.width()):
            for y in range(image.height()):
                pix = image.pixelColor(x, y)
                if (pix.red(), pix.green(), pix.blue()) == target_rgb:
                    highlighted.setPixelColor(x, y, highlight_color)
        zoom = self.get_zoom_factor()
        scaled_pixmap = QPixmap.fromImage(highlighted).scaled(
            int(image.width() * zoom), int(image.height() * zoom),
            transformMode=Qt.TransformationMode.FastTransformation
        )
        self.ui.imageLabel.setPixmap(scaled_pixmap)

    def clear_hover(self):
        self.hovered_color = None
        if self.selected_color:
            self.show_color_info(self.selected_color, is_hover=False)
        else:
            self.update_image()
            self.reset_color_details()

    def clear_selection(self):
        self.selected_color = None
        self.hovered_color = None
        self.update_image()
        self.clear_hover()
        self.reset_color_details()

    def reset_color_details(self):
        self.colorSwatch.setStyleSheet("background-color: #ffffff; border: 1px solid #000;")
        self.colorTextRGB.setText("RGB: -")
        self.colorTextHEX.setText("HEX: -")
        self.colorTextHSV.setText("HSV: -")

        self.color_palette.update_borders(
            self.selected_color,
            self.hovered_color,
            None
        )
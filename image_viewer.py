import colorsys
import math

from PyQt6.QtWidgets import QMainWindow, QFileDialog, QWidget, QLabel, QSizePolicy, QVBoxLayout
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

        self.palette_labels = {}
        self.selected_color = None
        self.hovered_color = None

        # Replace the default imageLabel with a clickable subclass
        self.ui.verticalLayout.removeWidget(self.ui.imageLabel)
        self.ui.imageLabel.deleteLater()

        self.ui.imageLabel = ClickableImageLabel(viewer=self)
        self.ui.verticalLayout.insertWidget(1, self.ui.imageLabel)

        self.ui.loadButton.clicked.connect(self.load_image)
        self.ui.zoomSlider.valueChanged.connect(self.update_zoom)

        self.ui.zoomLabel.setMinimumWidth(50)
        self.ui.zoomLabel.setStyleSheet("padding-bottom: 8px;")

        self.original_pixmap = None

        # Create overlay color widget on top-left of imageLabel
        self.colorOverlay = QWidget(self.ui.imageLabel)
        self.colorOverlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.colorOverlay.setStyleSheet("background-color: rgba(255, 255, 255, 180); border: 1px solid #999;")
        self.colorOverlay.move(10, 10)
        self.colorOverlay.resize(180, 120)

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
            label = ColorLabel(color, self)
            label.setFixedSize(40, 40)
            label.setStyleSheet(f"background-color: rgba({r},{g},{b},{a}); border: 1px solid #000;")

            self.palette_labels[color] = label
            layout.addWidget(label)

        self.ui.verticalLayout.addWidget(self.palette_widget)

    def get_image_color_at_pos(self, pos):
        if not self.original_pixmap or not self.ui.imageLabel.pixmap():
            return None

        label = self.ui.imageLabel
        zoom = self.get_zoom_factor()

        label_width = label.width()
        label_height = label.height()
        pixmap_width = self.original_pixmap.width() * zoom
        pixmap_height = self.original_pixmap.height() * zoom

        offset_x = (label_width - pixmap_width) // 2
        offset_y = (label_height - pixmap_height) // 2

        x = (pos.x() - offset_x) // zoom
        y = (pos.y() - offset_y) // zoom

        if 0 <= x < self.original_pixmap.width() and 0 <= y < self.original_pixmap.height():
            image = self.original_pixmap.toImage()
            return image.pixelColor(int(x), int(y)).getRgb()

        return None

    def image_mouse_move(self, event):
        color = self.get_image_color_at_pos(event.position().toPoint())
        if color:
            self.show_color_info(color, is_hover=True)
        else:
            self.clear_highlight()

    def image_mouse_click(self, event):
        color = self.get_image_color_at_pos(event.position().toPoint())
        if color:
            self.show_color_info(color, is_hover=False)
        else:
            self.clear_selection()

    def show_color_info(self, color, is_hover=False):
        if color is None:
            return

        # Update selection and hover state
        if is_hover:
            self.hovered_color = color
        else:
            self.selected_color = color
            self.selected_border_color = self.get_border_color_from_hue(color)
            self.hovered_color = None

        # Determine color to render (hover takes priority visually)
        active_color = self.hovered_color if is_hover else self.selected_color
        if not active_color:
            return

        # Convert color to HSV for highlight calculations
        r, g, b = [c / 255.0 for c in active_color[:3]]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        target_rgb = tuple(int(c * 255) for c in (r, g, b))

        # Determine highlight color for image
        highlight_rgb = (0, 255, 255) if h < 0.125 or h > 0.7 else (255, 0, 0)
        highlight_color = QColor(*highlight_rgb)

        # Palette highlighting
        for col, label in self.palette_labels.items():
            is_selected = self.selected_color and col[:3] == self.selected_color[:3]
            is_hovered = self.hovered_color and col[:3] == self.hovered_color[:3]

            if is_hovered:
                border_color = self.get_border_color_from_hue(col)
                label.setStyleSheet(f"background-color: rgba{col}; border: 4px solid {border_color};")
            elif is_selected:
                label.setStyleSheet(f"background-color: rgba{col}; border: 6px solid {self.selected_border_color};")
            else:
                label.setStyleSheet(f"background-color: rgba{col}; border: 1px solid #000;")

        # Highlight image pixels (only on hover)
        if is_hover:
            image = self.original_pixmap.toImage()
            highlighted = QImage(image)
            for x in range(image.width()):
                for y in range(image.height()):
                    pix = image.pixelColor(x, y)
                    if (pix.red(), pix.green(), pix.blue()) == target_rgb:
                        highlighted.setPixelColor(x, y, highlight_color)

            pixmap = QPixmap.fromImage(highlighted)
            zoom = self.get_zoom_factor()
            scaled_pixmap = pixmap.scaled(
                int(pixmap.width() * zoom),
                int(pixmap.height() * zoom),
                transformMode=Qt.TransformationMode.FastTransformation
            )
            self.ui.imageLabel.setPixmap(scaled_pixmap)
        else:
            self.update_zoom()

        # Update info overlay
        r_int, g_int, b_int = [int(c * 255) for c in (r, g, b)]
        h_deg = int(h * 360)
        s_pct = int(s * 100)
        v_pct = int(v * 100)
        hex_str = f"#{r_int:02X}{g_int:02X}{b_int:02X}"

        self.colorSwatch.setStyleSheet(f"background-color: {hex_str}; border: 1px solid #000;")
        self.colorTextRGB.setText(f"RGB: ({r_int}, {g_int}, {b_int})")
        self.colorTextHEX.setText(f"HEX: {hex_str}")
        self.colorTextHSV.setText(f"HSV: ({h_deg}°, {s_pct}%, {v_pct}%)")

    @staticmethod
    def get_border_color_from_hue(color):
        r, g, b = [c / 255.0 for c in color[:3]]
        h, _, _ = colorsys.rgb_to_hsv(r, g, b)
        return "cyan" if h < 0.125 or h > 0.7 else "red"

    def clear_highlight(self):
        self.hovered_color = None

        if self.selected_color:
            self.show_color_info(self.selected_color, is_hover=False)
        else:
            self.update_zoom()
            self.colorSwatch.setStyleSheet("background-color: #ffffff; border: 1px solid #000;")
            self.colorTextRGB.setText("RGB: -")
            self.colorTextHEX.setText("HEX: -")
            self.colorTextHSV.setText("HSV: -")

        for col, label in self.palette_labels.items():
            is_selected = self.selected_color and col[:3] == self.selected_color[:3]
            if is_selected:
                label.setStyleSheet(
                    f"background-color: rgba{col}; border: 5px solid {self.selected_border_color};"
                )
            else:
                label.setStyleSheet(f"background-color: rgba{col}; border: 1px solid #000;")

    def clear_selection(self):
        self.selected_color = None
        self.hovered_color = None
        self.update_zoom()
        self.clear_highlight()

        self.colorSwatch.setStyleSheet("background-color: #ffffff; border: 1px solid #000;")
        self.colorTextRGB.setText("RGB: -")
        self.colorTextHEX.setText("HEX: -")
        self.colorTextHSV.setText("HSV: -")


class ColorLabel(QLabel):
    def __init__(self, color, viewer, parent=None):
        super().__init__(parent)
        self.color = color
        self.viewer = viewer

    def mousePressEvent(self, event):
        self.viewer.show_color_info(self.color, is_hover=False)

    def enterEvent(self, event):
        self.viewer.show_color_info(self.color, is_hover=True)

    def leaveEvent(self, event):
        self.viewer.clear_highlight()

class ClickableImageLabel(QLabel):
    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer

        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(1, 1)
        self.setScaledContents(False)
        self.setObjectName("imageLabel")

    def mousePressEvent(self, event):
        self.viewer.image_mouse_click(event)

    def mouseMoveEvent(self, event):
        self.viewer.image_mouse_move(event)









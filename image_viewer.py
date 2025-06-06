from PyQt6 import QtCore
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QSizePolicy, QScrollArea, QFileDialog
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage, QColor
import numpy as np
import math
from PIL import Image

from color_utils import get_text_descriptions
from global_managers import global_selection_manager, global_color_manager
from palette import ColorPalette


class ImageViewer(QWidget):
    def __init__(self, show_load_button=True, palette_square_size=40, show_color_details=True):
        super().__init__()
        self.original_pixmap = None
        self.current_image_path = None
        self.palette_square_size = palette_square_size
        self.show_color_details = show_color_details
        self.show_load_button = show_load_button
        self.image_array = None
        self._setup_ui(show_load_button)
        global_selection_manager.register_listener(self.on_selection_change)

    def _setup_ui(self, show_load_button):
        self.layout = QVBoxLayout(self)

        if show_load_button:
            button_layout = QHBoxLayout()
            self.loadButton = QPushButton("Load Image")
            self.loadButton.clicked.connect(self.load_image)
            button_layout.addWidget(self.loadButton)
        
            self.saveAsButton = QPushButton("Save As")
            self.saveAsButton.clicked.connect(self.save_image_as)
            self.saveAsButton.setEnabled(False)  # Initially disabled
            button_layout.addWidget(self.saveAsButton)
        
            self.layout.addLayout(button_layout)

        self.scrollArea = QScrollArea()
        self.scrollArea.setWidgetResizable(False)
        self.scrollArea.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scrollArea.installEventFilter(self)

        self.imageLabel = QLabel()
        self.imageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.imageLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.imageLabel.setScaledContents(False)
        self.imageLabel.setMouseTracking(True)
        self.imageLabel.mousePressEvent = self.image_mouse_click
        self.imageLabel.mouseMoveEvent = self.image_mouse_move
        self.imageLabel.leaveEvent = self.image_mouse_leave

        self.scrollArea.setWidget(self.imageLabel)
        self.layout.addWidget(self.scrollArea, stretch=1)

        self._setup_zoom_controls()
        self._setup_color_overlay()

        self.color_palette = ColorPalette(self)
        self.layout.addWidget(self.color_palette)

    def _setup_zoom_controls(self):
        hbox = QHBoxLayout()
        self.zoomLabel = QLabel("100%")
        self.zoomSlider = QSlider(Qt.Orientation.Horizontal)
        self.zoomSlider.setRange(1, 40)
        self.zoomSlider.setValue(20)
        self.zoomSlider.valueChanged.connect(self.update_image)
        hbox.addWidget(self.zoomLabel)
        hbox.addWidget(self.zoomSlider)
        self.layout.addLayout(hbox)

    def _setup_color_overlay(self):
        self.colorDetails = QWidget(self.scrollArea)
        self.colorDetails.setMinimumWidth(160)
        self.colorDetails.setStyleSheet("""
            background-color: white;
            border: 2px solid #999;
        """)
        self.colorDetails.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.colorDetails.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)  # Allow interaction

        overlay = QVBoxLayout(self.colorDetails)
        overlay.setContentsMargins(8, 8, 8, 8)
        overlay.setSpacing(6)

        # Color Swatch
        self.colorSwatch = QLabel()
        self.colorSwatch.setFixedHeight(40)
        self.colorSwatch.setStyleSheet("background-color: #ffffff; border: 1px solid #000;")
        overlay.addWidget(self.colorSwatch)

        # Color Value Labels (Selectable Text)
        self.colorTextRGB = QLabel("RGB: -")
        self.colorTextHEX = QLabel("HEX: -")
        self.colorTextHSV = QLabel("HSV: -")

        for label in [self.colorTextRGB, self.colorTextHEX, self.colorTextHSV]:
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setStyleSheet("""
                font-size: 10pt;
                border: none;
            """)
            overlay.addWidget(label)

        # Prevent clicks inside overlay from affecting selection logic
        self.colorDetails.mousePressEvent = lambda event: event.accept()
        self.colorDetails.mouseMoveEvent = lambda event: event.accept()

        self.colorDetails.hide()

    def load_image(self, pixmap = None, file_path=None):
        if pixmap:
            self.original_pixmap = pixmap
        else:
            if not file_path:
                from PyQt6.QtWidgets import QFileDialog
                file_path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.bmp)")
                if not file_path:
                    return
            self.original_pixmap = QPixmap(file_path)

        self.current_image_path = file_path

        if not self.original_pixmap.isNull():
            self.image_array = self.get_image_array()
            global_color_manager.load_image(self.image_array)
            color_groups = global_color_manager.get_color_groups()
            self.color_palette.populate(color_groups, square_size=self.palette_square_size)
            self.set_initial_fit_zoom()
            self.update_image()
            global_selection_manager.clear_selection()
            self.reset_color_details()

            if self.show_load_button:
                self.saveAsButton.setEnabled(True)

    def replace_color(self, color_id, new_color):
        if self.original_pixmap is None or color_id not in global_color_manager.color_groups:
            return

        positions = global_color_manager.color_groups[color_id].pixel_positions

        for x, y in positions:
            self.image_array[y, x] = new_color

        img = QImage(self.image_array.data,
                     self.image_array.shape[1],
                     self.image_array.shape[0],
                     QImage.Format.Format_RGBA8888)
        self.original_pixmap = QPixmap.fromImage(img)
        self.update_image()

    def update_image(self):
        if not self.original_pixmap:
            return
        zoom = self.get_zoom_factor()
        self.zoomLabel.setText(f"{zoom}x")

        scaled_width = int(self.original_pixmap.width() * zoom)
        scaled_height = int(self.original_pixmap.height() * zoom)

        scaled_pixmap = self.original_pixmap.scaled(
            scaled_width,
            scaled_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation
        )

        self.imageLabel.setPixmap(scaled_pixmap)
        self.imageLabel.resize(scaled_width, scaled_height)

    def get_zoom_factor(self):
        base_zoom = 1.16 ** (self.zoomSlider.value() - 20)
        return round(base_zoom, 3)

    def set_initial_fit_zoom(self):
        if not self.original_pixmap:
            return
        container_size = self.scrollArea.size()
        image_size = self.original_pixmap.size()
        zoom = min(container_size.width() / image_size.width(), container_size.height() / image_size.height())
        slider_val = max(1, int(round(math.log(zoom) / math.log(1.16) + 20)) - 2)
        self.zoomSlider.setValue(max(self.zoomSlider.minimum(), min(slider_val, self.zoomSlider.maximum())))

    def get_image_array(self):
        if not self.original_pixmap:
            return None
        qimage = self.original_pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        ptr = qimage.bits()
        ptr.setsize(qimage.sizeInBytes())
        return np.array(ptr, dtype=np.uint8).reshape((qimage.height(), qimage.width(), 4))

    def on_selection_change(self, selected_color_id, hovered_color_id):
        selected_color = None
        if selected_color_id is not None:
            selected_color = global_color_manager.color_groups[selected_color_id].current_color

        hovered_color = None
        if hovered_color_id is not None:
            hovered_color = global_color_manager.color_groups[hovered_color_id].current_color

        if self.show_color_details and (hovered_color or selected_color):
            self.update_overlay_text(hovered_color or selected_color)
            self.colorDetails.show()
        elif not hovered_color:
            self.reset_color_details()

        if hovered_color:
            self.update_image_highlight(hovered_color_id)
        else:
            self.update_image()

    def update_overlay_text(self, color):
        info = get_text_descriptions(color)
        self.colorSwatch.setStyleSheet(f"background-color: {info['hex_raw']}; border: 1px solid #000;")
        self.colorTextRGB.setText(info["rgb"])
        self.colorTextHEX.setText(info["hex"])
        self.colorTextHSV.setText(info["hsv"])

    def reset_color_details(self):
        self.colorSwatch.setStyleSheet("background-color: #fff; border: 1px solid #000;")
        self.colorTextRGB.setText("RGB: -")
        self.colorTextHEX.setText("HEX: -")
        self.colorTextHSV.setText("HSV: -")
        self.colorDetails.hide()

    def update_image_highlight(self, color_id):
        if not self.original_pixmap or color_id is None:
            return

        image = self.original_pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        highlighted = QImage(image)
        highlight_color = QColor(global_selection_manager.highlight_color)

        positions = global_color_manager.color_groups[color_id].pixel_positions

        for x, y in positions:
            highlighted.setPixelColor(x, y, highlight_color)

        zoom = self.get_zoom_factor()
        scaled_pixmap = QPixmap.fromImage(highlighted).scaled(
            int(image.width() * zoom),
            int(image.height() * zoom),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation
        )
        self.imageLabel.setPixmap(scaled_pixmap)

    def image_mouse_move(self, event):
        coord = self.get_pixel_coordinates_at_pos(event.pos())
        if coord:
            x, y = coord
            color_id = global_color_manager.get_color_id_at_position(x, y)
            if color_id >= 0:
                global_selection_manager.hover_color_id(color_id)
                return
        global_selection_manager.clear_hover()

    def image_mouse_click(self, event):
        coord = self.get_pixel_coordinates_at_pos(event.pos())
        if coord:
            x, y = coord
            color_id = global_color_manager.get_color_id_at_position(x, y)
            if color_id >= 0:
                global_selection_manager.select_color_id(color_id)
                return
        global_selection_manager.clear_selection()

    @staticmethod
    def image_mouse_leave(event):
        global_selection_manager.clear_hover()

    def get_pixel_coordinates_at_pos(self, pos):
        if not self.original_pixmap or not self.imageLabel.pixmap():
            return None

        label = self.imageLabel
        zoom = self.get_zoom_factor()
        offset_x = (label.width() - self.original_pixmap.width() * zoom) // 2
        offset_y = (label.height() - self.original_pixmap.height() * zoom) // 2

        x = int((pos.x() - offset_x) / zoom)
        y = int((pos.y() - offset_y) / zoom)

        if 0 <= x < self.original_pixmap.width() and 0 <= y < self.original_pixmap.height():
            return x, y

        return None

    def eventFilter(self, obj, event):
        if obj == self.scrollArea and event.type() == QtCore.QEvent.Type.MouseButtonPress:
            clicked_widget = self.childAt(event.position().toPoint())
            if clicked_widget not in [self.imageLabel, self.colorDetails]:
                global_selection_manager.clear_selection()
        return super().eventFilter(obj, event)

    def cleanup(self):
        try:
            self.color_palette.clear()
            global_selection_manager.unregister_listener(self.on_selection_change)
        except:
            pass

    def save_image_as(self):
        if not self.original_pixmap:
            return
        
        # Generate suggested filename based on the original
        suggested_name = "modified_image.png"
        if self.current_image_path:
            # Get the original filename and directory
            import os
            original_dir = os.path.dirname(self.current_image_path)
            original_name = os.path.basename(self.current_image_path)
            # Insert '_modified' before the extension
            name, ext = os.path.splitext(original_name)
            suggested_name = os.path.join(original_dir, f"{name}_modified{ext}")
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image As",
            suggested_name,
            "Images (*.png *.jpg *.bmp)"
        )
        
        if file_path:
            # Convert the current image array to QImage and save
            img = QImage(self.image_array.data,
                        self.image_array.shape[1],
                        self.image_array.shape[0],
                        QImage.Format.Format_RGBA8888)
            img.save(file_path)
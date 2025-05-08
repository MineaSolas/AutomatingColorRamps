from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

from color_utils import get_highlight_color
from ui.flow_layout import FlowLayout

class ColorLabel(QLabel):
    def __init__(self, color, viewer, size=40, parent=None):
        super().__init__(parent)
        self.color = color
        self.viewer = viewer
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        self.viewer.show_color_info(self.color, is_hover=False)

    def enterEvent(self, event):
        self.viewer.show_color_info(self.color, is_hover=True)

    def leaveEvent(self, event):
        self.viewer.clear_hover()


class ColorPalette(QWidget):
    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.labels = {}
        self.layout = FlowLayout(spacing=5)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

    def populate(self, colors, square_size=40):
        self.clear()
        for color in colors:
            label = ColorLabel(color, self.viewer, size=square_size)
            r, g, b, a = color
            label.setStyleSheet(f"background-color: rgba({r},{g},{b},{a}); border: 1px solid #000;")
            self.labels[color] = label
            self.layout.addWidget(label)

    def clear(self):
        for label in self.labels.values():
            self.layout.removeWidget(label)
            label.deleteLater()
        self.labels.clear()

    def update_borders(self, selected_color, hovered_color, selected_border_color):
        for color, label in self.labels.items():
            is_selected = selected_color and color[:3] == selected_color[:3]
            is_hovered = hovered_color and color[:3] == hovered_color[:3]

            if is_hovered:
                border_color = get_highlight_color(color)
                label.setStyleSheet(f"background-color: rgba{color}; border: 4px solid {border_color};")
            elif is_selected:
                label.setStyleSheet(f"background-color: rgba{color}; border: 6px solid {selected_border_color};")
            else:
                label.setStyleSheet(f"background-color: rgba{color}; border: 1px solid #000;")


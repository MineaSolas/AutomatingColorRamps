from PyQt6.QtWidgets import QLabel, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt

from ui_helpers import FlowLayout
from color_utils import get_highlight_color
from color_selection_manager import ColorSelectionManager

selection_manager = ColorSelectionManager()

class ColorLabel(QLabel):
    def __init__(self, color, size=40, parent=None):
        super().__init__(parent)
        self.color = color
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_border()

        # Listen for selection changes to update border
        selection_manager.register_listener(self.on_selection_change)

    def mousePressEvent(self, event):
        selection_manager.select_color(self.color)

    def enterEvent(self, event):
        selection_manager.hover_color(self.color)

    def leaveEvent(self, event):
        selection_manager.clear_hover()

    def on_selection_change(self, selected_color, hovered_color):
        self.update_border()

    def update_border(self):
        is_selected = selection_manager.selected_color == self.color
        is_hovered = selection_manager.hovered_color == self.color

        if is_hovered:
            self.setStyleSheet(f"background-color: rgba{self.color}; border: 4px solid {selection_manager.highlight_color};")
        elif is_selected:
            selected_border_color = get_highlight_color(self.color)
            self.setStyleSheet(f"background-color: rgba{self.color}; border: 6px solid {selected_border_color};")
        else:
            self.setStyleSheet(f"background-color: rgba{self.color}; border: 1px solid #000;")

    def deleteLater(self):
        selection_manager.unregister_listener(self.on_selection_change)
        super().deleteLater()


class ColorPalette(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = {}
        self.layout = FlowLayout(spacing=5)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

    def populate(self, colors, square_size=40):
        self.clear()
        for color in colors:
            label = ColorLabel(color, size=square_size)
            r, g, b, a = color
            label.setStyleSheet(f"background-color: rgba({r},{g},{b},{a}); border: 1px solid #000;")
            self.labels[color] = label
            self.layout.addWidget(label)

    def clear(self):
        for label in self.labels.values():
            self.layout.removeWidget(label)
            label.deleteLater()
        self.labels.clear()

class ColorRamp(QWidget):
    def __init__(self, color_ramp, swatch_size=25, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        for color in color_ramp:
            r, g, b, a = color
            swatch = QLabel()
            swatch.setFixedSize(swatch_size, swatch_size)
            swatch.setStyleSheet(
                f"background-color: rgba({r},{g},{b},{a});"
                "border: none;"
                "margin: 0px; "
                "padding: 0px;"
            )
            layout.addWidget(swatch)

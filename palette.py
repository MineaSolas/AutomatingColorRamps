from PyQt6.QtGui import QEnterEvent
from PyQt6.QtWidgets import QLabel, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt

from ui_helpers import FlowLayout
from color_utils import get_highlight_color
from color_selection_manager import ColorSelectionManager

selection_manager = ColorSelectionManager()

class ColorLabel(QLabel):
    def __init__(self, color, size=40, show_border=True, parent=None):
        super().__init__(parent)
        self.color = color
        self.show_border = show_border
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
            self.setStyleSheet(f"border: 3px solid {selection_manager.highlight_color};")
        elif is_selected:
            selected_border_color = get_highlight_color(self.color)
            self.setStyleSheet(f"border: 5px solid {selected_border_color};")
        else:
            border_style = "1px solid #000;" if self.show_border else "none;"
            self.setStyleSheet(f"border: {border_style}")
        self.set_background_color()

    def set_background_color(self):
        r, g, b, a = self.color
        self.setStyleSheet(self.styleSheet() + f"; background-color: rgba({r},{g},{b},{a})")

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
        self.setObjectName("ColorRampRow")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.setStyleSheet("""
            border: none;
            background-color: transparent;
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        for color in color_ramp:
            swatch = ColorLabel(color, show_border=False, size=swatch_size)
            layout.addWidget(swatch)

    def enterEvent(self, event: QEnterEvent):
        self.setStyleSheet("""
            border: 3px solid #ffff00;
            background-color: #ffffaa;
        """)

    def leaveEvent(self, event):
        self.setStyleSheet("""
            border: none;
            background-color: transparent;
        """)

    def deleteLater(self):
        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if widget:
                widget.deleteLater()
        super().deleteLater()


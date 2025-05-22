from PyQt6.QtWidgets import QLabel, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt

from ui_helpers import FlowLayout
from color_utils import get_highlight_color
from global_managers import ColorSelectionManager, FinalPaletteManager

selection_manager = ColorSelectionManager()
final_palette_manager = FinalPaletteManager()

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
    def __init__(self, color_ramp, swatch_size=25, source="generated", parent=None):
        super().__init__(parent)
        self.color_ramp = color_ramp
        self.swatch_size = swatch_size
        self.source = source  # "generated" or "final"
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.duplicated = False
        self.hovered = False
        self.init_ui()
        self.setFixedHeight(swatch_size + 16)

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        for color in self.color_ramp:
            label = ColorLabel(color, show_border=False, size=self.swatch_size)
            layout.addWidget(label)
        self.update_highlight()

    def update_highlight(self):
        if self.hovered:
            bg = "#eaf7ff"
            border = "#88ccee"
        elif self.duplicated:
            bg = "#eeeeee"
            border = "#dddddd"
        else:
            bg = "transparent"
            border = "transparent"
        self.setStyleSheet(f"border: 3px solid {border}; background-color: {bg};")

    def enterEvent(self, event):
        self.hovered = True
        self.update_highlight()

    def leaveEvent(self, event):
        self.hovered = False
        self.update_highlight()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.source == "generated":
                final_palette_manager.add_ramp(self.color_ramp)
            elif self.source == "final" and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                final_palette_manager.remove_ramp(self.color_ramp)

    def deleteLater(self):
        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if widget:
                widget.deleteLater()
        super().deleteLater()


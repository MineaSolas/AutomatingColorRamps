from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtWidgets import QLabel, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt, QEvent, QTimer

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
        self.tool_hovered = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_border()

        # Listen for selection changes to update border
        selection_manager.register_listener(self.on_selection_change)

    def mousePressEvent(self, event):
        ramp = self.parent()
        if getattr(ramp, "source", None) == "final" and hasattr(ramp, "viewer") and ramp.viewer and ramp.viewer.tool_active_any():
            event.ignore()
            return
        selection_manager.select_color(self.color)

    def enterEvent(self, event):
        ramp = self.parent()
        if getattr(ramp, "source", None) == "final" and hasattr(ramp, "viewer") and ramp.viewer:
            if ramp.viewer.tool_active("add_remove") or ramp.viewer.tool_active("split"):
                self.tool_hovered = True
        selection_manager.hover_color(self.color)

    def leaveEvent(self, event):
        ramp = self.parent()
        if getattr(ramp, "source", None) == "final" and hasattr(ramp, "viewer") and ramp.viewer:
            if ramp.viewer.tool_active("add_remove") or ramp.viewer.tool_active("split"):
                self.tool_hovered = False
        selection_manager.clear_hover()

    def on_selection_change(self, selected_color, hovered_color):
        self.update_border()

    def update_border(self):
        ramp = self.parent()
        tool_active = getattr(ramp, "source", None) == "final" and hasattr(ramp, "viewer") and ramp.viewer and ramp.viewer.tool_active_any()

        if tool_active:
            tool = ramp.viewer.tool_active_name()
            if self.tool_hovered and tool in ("add_remove", "split"):
                self.setStyleSheet(f"border: 3px solid #ff00ff;")
                self.set_background_color()
            else:
                border_style = "1px solid #000;" if self.show_border else "none;"
                self.setStyleSheet(f"border: {border_style}")
                self.set_background_color()
            return

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
    def __init__(self, color_ramp, swatch_size=25, source="generated", parent=None, viewer=None):
        super().__init__(parent)
        self.color_ramp = color_ramp
        self.swatch_size = swatch_size
        self.source = source  # "generated" or "final"
        self.viewer = viewer
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMouseTracking(True)
        self.duplicated = False
        self.hovered = False
        self.hover_index = None
        self.init_ui()
        self.setFixedHeight(swatch_size + 24)

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        for color in self.color_ramp:
            label = ColorLabel(color, show_border=False, size=self.swatch_size)
            label.setMouseTracking(True)
            label.installEventFilter(self)
            layout.addWidget(label)
        self.update_highlight()

    def eventFilter(self, obj, event):
        if not self.viewer or not self.viewer.tool_active("add_remove"):
            return super().eventFilter(obj, event)

        if event.type() == QEvent.Type.MouseMove:
            local_x = self.mapFromGlobal(event.globalPosition().toPoint()).x()
            self.hover_index = self._compute_insertion_index(local_x)
            self.update()
            return False

        if event.type() == QEvent.Type.Leave:
            self.hover_index = None
            self.update()
            return False

        return super().eventFilter(obj, event)

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
        self.update()

    def leaveEvent(self, event):
        self.hovered = False
        self.hover_index = None
        self.update_highlight()
        self.update()

    def mouseMoveEvent(self, event):
        if self.source != "final":
            return

        if not self.viewer or not self.viewer.tool_active("add_remove"):
            return

        pos_x = event.position().x()
        index = self._compute_insertion_index(pos_x)
        if index != self.hover_index:
            self.hover_index = index
            self.update()

    def _compute_insertion_index(self, x_pos):
        total = self.layout().count()
        swatch_width = self.swatch_size
        margins = self.layout().contentsMargins().left()

        for i in range(total):
            left_edge = margins + i * swatch_width
            right_edge = left_edge + swatch_width
            if x_pos < (left_edge + right_edge) / 2:
                return i
        return total

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.hovered or self.hover_index is None:
            return

        if not self.viewer or not self.viewer.tool_active("add_remove") and not self.viewer.tool_active("split"):
            return

        painter = QPainter(self)
        pen = QPen(Qt.GlobalColor.green)
        pen.setWidth(2)
        painter.setPen(pen)

        x = self.layout().contentsMargins().left() + self.hover_index * self.swatch_size
        painter.drawLine(x, 0, x, self.height())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.source == "generated":
                final_palette_manager.add_ramp(self.color_ramp)

            elif self.source == "final":
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    final_palette_manager.remove_ramp(self.color_ramp)
                elif self.viewer and self.viewer.tool_active("add_remove"):
                    color = selection_manager.selected_color
                    if not color or self.hover_index is None:
                        return
                    new_ramp = (
                            self.color_ramp[:self.hover_index]
                            + [color]
                            + self.color_ramp[self.hover_index:]
                    )
                    self.viewer.request_ramp_update(self.color_ramp, new_ramp)


        elif event.button() == Qt.MouseButton.RightButton:
            if self.source == "final" and self.viewer and self.viewer.tool_active("add_remove"):
                x = event.position().x()
                index = int((x - self.layout().contentsMargins().left()) / self.swatch_size)
                if 0 <= index < len(self.color_ramp):
                    new_ramp = self.color_ramp[:index] + self.color_ramp[index + 1:]
                    self.viewer.request_ramp_update(self.color_ramp, new_ramp)


    def update_self(self, new_ramp):
        old_key = tuple(self.color_ramp)
        new_key = tuple(new_ramp)

        def apply_update():
            final_palette_manager.update_ramp(self.color_ramp, new_ramp)
            if self.viewer:
                self.viewer.final_ramp_widgets.pop(old_key, None)
                self.viewer.final_ramp_widgets[new_key] = self
            self.color_ramp = new_ramp

        QTimer.singleShot(0, apply_update)

    def deleteLater(self):
        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if widget:
                widget.deleteLater()
        super().deleteLater()


from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtWidgets import QLabel, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt, QEvent, QTimer

from hsv_graph import HSVGraphWindow
from ui_helpers import FlowLayout
from color_utils import get_highlight_color
from global_managers import ColorSelectionManager, ColorRampManager, global_selection_manager, global_ramp_manager, \
    ColorGroup, global_color_manager


class ColorLabel(QLabel):
    def __init__(self, color_group: ColorGroup, size=40, show_border=True, parent=None):
        super().__init__(parent)
        self.color_group = color_group
        self.show_border = show_border
        self.tool_hovered = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_default_border()
        self.set_background_color()
        global_selection_manager.register_listener(self.on_selection_changed)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            ramp = self.parent()
            if (getattr(ramp, "source", None) == "final" and hasattr(ramp,"viewer")
                    and ramp.viewer and ramp.viewer.tool_active_any()):
                event.ignore()
                return
            global_selection_manager.select_color_id(self.color_group.color_id)

        elif event.button() == Qt.MouseButton.RightButton:
            event.ignore()

    def enterEvent(self, event):
        ramp = self.parent()
        if getattr(ramp, "source", None) == "final" and hasattr(ramp, "viewer") and ramp.viewer:
            if ramp.viewer.tool_active("add_remove") or ramp.viewer.tool_active("split"):
                self.tool_hovered = True
        global_selection_manager.hover_color_id(self.color_group.color_id)

    def leaveEvent(self, event):
        ramp = self.parent()
        if getattr(ramp, "source", None) == "final" and hasattr(ramp, "viewer") and ramp.viewer:
            if ramp.viewer.tool_active("add_remove") or ramp.viewer.tool_active("split"):
                self.tool_hovered = False
        global_selection_manager.clear_hover()

    def on_selection_changed(self, selected_id, hovered_id):
        ramp = self.parent()
        tool_active = getattr(ramp, "source", None) == "final" and hasattr(ramp, "viewer") and ramp.viewer and ramp.viewer.tool_active_any()

        if tool_active:
            tool = ramp.viewer.tool_active_name()
            if self.tool_hovered and tool in ("add_remove", "split"):
                self.setStyleSheet(f"border: 3px solid #ff00ff;")
                self.set_background_color()
            else:
                self.set_default_border()
                self.set_background_color()
            return

        is_selected = selected_id == self.color_group.color_id
        is_hovered = hovered_id == self.color_group.color_id

        if is_hovered:
            self.setStyleSheet(f"border: 3px solid {global_selection_manager.highlight_color};")
        elif is_selected:
            selected_border_color = get_highlight_color(self.color_group.current_color)
            self.setStyleSheet(f"border: 5px solid {selected_border_color};")
        else:
            self.set_default_border()
        self.set_background_color()

    def set_default_border(self):
        border_style = "1px solid #000;" if self.show_border else "none;"
        self.setStyleSheet(f"border: {border_style}")

    def set_background_color(self):
        r, g, b, a = self.color_group.current_color
        self.setStyleSheet(self.styleSheet() + f"; background-color: rgba({r},{g},{b},{a})")

    def deleteLater(self):
        global_selection_manager.unregister_listener(self.on_selection_changed)
        super().deleteLater()


class ColorPalette(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = {}
        self.layout = FlowLayout(spacing=5)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

    def populate(self, color_groups, square_size=40):
        self.clear()
        sorted_groups = sorted(
            color_groups,
            key=lambda g: (g.current_color[3], g.current_color[0],
                           g.current_color[1], g.current_color[2])
        )

        for group in sorted_groups:
            label = ColorLabel(group, size=square_size)
            self.labels[group.color_id] = label
            self.layout.addWidget(label)

    def clear(self):
        for label in self.labels.values():
            self.layout.removeWidget(label)
            label.deleteLater()
        self.labels.clear()

class ColorRamp(QWidget):
    _hsv_windows = []

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
        color_groups = global_color_manager.get_color_groups()
        for color_id in self.color_ramp:
            group = color_groups[color_id]
            label = ColorLabel(group, show_border=False, size=self.swatch_size)
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

    @staticmethod
    def cleanup_hsv_windows(hsv_window):
        if hsv_window in ColorRamp._hsv_windows:
            ColorRamp._hsv_windows.remove(hsv_window)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            color_groups = global_color_manager.get_color_groups()
            colors = [color_groups[color_id] for color_id in self.color_ramp]

            # Create and show a new HSV graph window
            hsv_window = HSVGraphWindow([c.current_color for c in colors])
            hsv_window.setWindowTitle(f"HSV Progression")

            # When window is closed, remove it from our list
            hsv_window.destroyed.connect(self.cleanup_hsv_windows)

            ColorRamp._hsv_windows.append(hsv_window)
            hsv_window.show()


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
                global_ramp_manager.add_ramp(self.color_ramp)

            elif self.source == "final":
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    global_ramp_manager.remove_ramp(self.color_ramp)
                elif self.viewer and self.viewer.tool_active("add_remove"):
                    selected_id = global_selection_manager.selected_color_id
                    if selected_id is None or self.hover_index is None:
                        return
                    new_ramp = (
                            self.color_ramp[:self.hover_index]
                            + [selected_id]
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
            global_ramp_manager.update_ramp(self.color_ramp, new_ramp)
            if self.viewer:
                self.viewer.final_ramp_widgets.pop(old_key, None)
                self.viewer.final_ramp_widgets[new_key] = self
            self.color_ramp = new_ramp

        QTimer.singleShot(0, apply_update)

    def deleteLater(self):
        for window in ColorRamp._hsv_windows[:]:
            window.close()
            ColorRamp._hsv_windows.remove(window)

        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if widget:
                widget.deleteLater()
        super().deleteLater()


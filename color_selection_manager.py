from color_utils import get_highlight_color

class ColorSelectionManager:
    def __init__(self):
        self.selected_color = None
        self.hovered_color = None
        self.highlight_color = "red"
        self._listeners = []

    def select_color(self, color):
        self.selected_color = color
        self.hovered_color = None
        self.update_highlight_color(color)
        self.notify_listeners()

    def hover_color(self, color):
        self.hovered_color = color
        self.update_highlight_color(color)
        self.notify_listeners()

    def clear_selection(self):
        self.selected_color = None
        self.hovered_color = None
        self.highlight_color = "red"
        self.notify_listeners()

    def clear_hover(self):
        self.hovered_color = None
        if self.selected_color:
            self.update_highlight_color(self.selected_color)
        else:
            self.highlight_color = "red"
        self.notify_listeners()

    def update_highlight_color(self, color):
        if color:
            self.highlight_color = get_highlight_color(color)
        else:
            self.highlight_color = "red"  # Default

    def register_listener(self, callback):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unregister_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def notify_listeners(self):
        for callback in self._listeners:
            callback(self.selected_color, self.hovered_color)

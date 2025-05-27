from dataclasses import dataclass
from typing import List, Set, Tuple, Dict

import color_utils


@dataclass
class ColorGroup:
    color_id: int
    pixel_positions: Set[Tuple[int, int]]
    current_color: Tuple[int, int, int, int]

class ColorManager:
    def __init__(self):
        self.color_groups: Dict[int, ColorGroup] = {}

    def load_image(self, image_array):
        """Initialize color groups from a new image."""
        self.color_groups.clear()
        height, width = image_array.shape[:2]

        color_positions: Dict[Tuple[int, int, int, int], Set[Tuple[int, int]]] = {}

        for y in range(height):
            for x in range(width):
                color = tuple(image_array[y, x])
                if color[3] > 0:  # Only process non-transparent pixels
                    if color not in color_positions:
                        color_positions[color] = set()
                    color_positions[color].add((x, y))

        next_color_id = 0
        for color, positions in color_positions.items():
            color_group = ColorGroup(
                color_id=next_color_id,
                pixel_positions=positions,
                current_color=color
            )
            self.color_groups[next_color_id] = color_group
            next_color_id += 1

    def get_color_groups(self) -> List[ColorGroup]:
        return list(self.color_groups.values())

    def set_color(self, color_id, new_color):
        if color_id in self.color_groups:
            self.color_groups[color_id].current_color = new_color
            return True
        return False

    def get_color_id_at_position(self, x, y):
        for color_id, group in self.color_groups.items():
            if (x, y) in group.pixel_positions:
                return color_id
        return -1

    def get_color_id_by_color(self, color):
        return [
            color_id for color_id, group in self.color_groups.items()
            if group.current_color == color
        ]

    def get_pixel_positions(self, color_ids):
        positions = set()
        for color_id in color_ids:
            if color_id in self.color_groups:
                positions.update(self.color_groups[color_id].pixel_positions)
        return positions


class ColorSelectionManager:
    def __init__(self):
        self.selected_color_id = None
        self.hovered_color_id = None
        self.highlight_color = "red"
        self._listeners = []

    def select_color_id(self, color_id):
        if color_id is not None and color_id in global_color_manager.color_groups:
            self.selected_color_id = color_id
            self.hovered_color_id = None
            self.update_highlight_color(color_id)
            self.notify_listeners()

    def hover_color_id(self, color_id):
        if color_id is not None and color_id in global_color_manager.color_groups:
            self.hovered_color_id = color_id
            self.update_highlight_color(color_id)
            self.notify_listeners()

    def clear_selection(self):
        self.selected_color_id = None
        self.hovered_color_id = None
        self.highlight_color = "red"
        self.notify_listeners()

    def clear_hover(self):
        self.hovered_color_id = None
        if self.selected_color_id is not None and self.selected_color_id in global_color_manager.color_groups:
            self.update_highlight_color(self.selected_color_id)
        self.notify_listeners()

    def update_highlight_color(self, color_id):
        if color_id is not None:
            color = global_color_manager.color_groups[color_id].current_color
            self.highlight_color = color_utils.get_highlight_color(color)
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
            callback(self.selected_color_id, self.hovered_color_id)


class ColorRampManager:
    def __init__(self):
        self._ramps = []
        self._listeners = []

    def add_ramp(self, ramp):
        if ramp not in self._ramps:
            self._ramps.append(ramp)
            self._notify()

    def remove_ramp(self, ramp):
        self._ramps = [r for r in self._ramps if r != ramp]
        self._notify()

    def update_ramp(self, old_ramp, new_ramp):
        for i, r in enumerate(self._ramps):
            if r == old_ramp:
                self._ramps[i] = new_ramp
                self._notify()
                return

    def get_ramps(self):
        return list(self._ramps)

    def register_listener(self, callback):
        self._listeners.append(callback)

    def unregister_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self):
        for cb in self._listeners:
            cb()

global_color_manager = ColorManager()
global_selection_manager = ColorSelectionManager()
global_ramp_manager = ColorRampManager()
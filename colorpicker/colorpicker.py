# ------------------------------------- #
#                                       #
# Modern Color Picker by Tom F.         #
# Edited by GiorgosXou for Qt6 Support. #
#                                       #
# Version 1.3                           #
# made with Qt Creator & PyQt5          #
#                                       #
# ------------------------------------- #

import colorsys

from PyQt6 import QtWidgets
from PyQt6.QtCore import (Qt, pyqtSignal)
from PyQt6.QtWidgets import (QWidget)


from .ui_main import Ui_ColorPicker as Ui_Main


class ColorPicker(QWidget):

    colorChanged = pyqtSignal()

    def __init__(self, *args, **kwargs):

        # Extract Initial Color out of kwargs
        self.color = (0, 0, 0)
        rgb = kwargs.pop("rgb", None)
        hsv = kwargs.pop("hsv", None)
        hex_string = kwargs.pop("hex", None)

        # Store original values for reverting invalid inputs
        self._original_values = {
            'rgb': (0.0, 0.0, 0.0),
            'hsv': (0.0, 0.0, 0.0),
            'hex': '000000'
        }

        super(ColorPicker, self).__init__(*args, **kwargs)

        # Call UI Builder function
        self.width = 180
        self.height = 100
        self.ui = Ui_Main()
        self.ui.setupUi(self)
        self._block_change = False

        # Set up input fields to lose focus on Enter
        for field in [self.ui.red, self.ui.green, self.ui.blue,
                     self.ui.hue, self.ui.saturation, self.ui.value,
                     self.ui.hex]:
            field.returnPressed.connect(field.clearFocus)

        # Enable click outside to lose focus
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)

        # Connect focus out events
        self.ui.red.focusOutEvent = lambda e: self._validate_rgb(e, self.ui.red)
        self.ui.green.focusOutEvent = lambda e: self._validate_rgb(e, self.ui.green)
        self.ui.blue.focusOutEvent = lambda e: self._validate_rgb(e, self.ui.blue)

        self.ui.hue.focusOutEvent = lambda e: self._validate_hsv(e, self.ui.hue, 359)
        self.ui.saturation.focusOutEvent = lambda e: self._validate_hsv(e, self.ui.saturation, 100)
        self.ui.value.focusOutEvent = lambda e: self._validate_hsv(e, self.ui.value, 100)

        self.ui.hex.focusOutEvent = self._validate_hex

        # Remove textEdited connections and use editingFinished instead
        self.ui.red.editingFinished.connect(self._on_rgb_editing_finished)
        self.ui.green.editingFinished.connect(self._on_rgb_editing_finished)
        self.ui.blue.editingFinished.connect(self._on_rgb_editing_finished)

        self.ui.hue.editingFinished.connect(self._on_hsv_editing_finished)
        self.ui.saturation.editingFinished.connect(self._on_hsv_editing_finished)
        self.ui.value.editingFinished.connect(self._on_hsv_editing_finished)

        self.ui.hex.editingFinished.connect(self._on_hex_editing_finished)

        # Connect selector moving functions
        self.ui.hue_slider.mouseMoveEvent = self.move_hue_selector
        self.ui.hue_slider.mousePressEvent = self.move_hue_selector
        self.ui.black_overlay.mouseMoveEvent = self.move_sv_selector
        self.ui.black_overlay.mousePressEvent = self.move_sv_selector

        if rgb:
            self.set_rgb(rgb)
        elif hsv:
            self.set_hsv(hsv)
        elif hex_string:
            self.set_hex(hex_string)
        else:
            self.set_rgb((0, 0, 0))


    ## Main Functions ##
    def get_hsv(self, hrange=100, svrange=100):
        h,s,v = self.color
        return (h*(hrange/100.0), s*(svrange/100.0), v*(svrange/100.0))

    def get_rgb(self, range=255):
        r,g,b = self.i(self.ui.red.text()), self.i(self.ui.green.text()), self.i(self.ui.blue.text())
        return (r*(range/255.0),g*(range/255.0),b*(range/255.0))

    def get_hex(self, ht=False):
        rgb = (self.i(self.ui.red.text()), self.i(self.ui.green.text()), self.i(self.ui.blue.text()))
        if ht: return "#" + self.rgb2hex(rgb)
        else: return self.rgb2hex(rgb)


    ## Update Functions ##
    def _validate_rgb(self, event, widget):
        try:
            value = int(widget.text())
            if 0 <= value <= 255:
                result = True
            else:
                raise ValueError
        except ValueError:
            widget.setText(str(self._original_values['rgb'][['red', 'green', 'blue'].index(widget.objectName())]))
            result = False

        if event:
            return QtWidgets.QLineEdit.focusOutEvent(widget, event)
        return result

    def _validate_hsv(self, event, widget, max_value):
        try:
            value = int(widget.text())
            if 0 <= value <= max_value:
                result = True
            else:
                raise ValueError
        except ValueError:
            widget.setText(str(self._original_values['hsv'][['hue', 'saturation', 'value'].index(widget.objectName())]))
            result = False

        if event:
            return QtWidgets.QLineEdit.focusOutEvent(widget, event)
        return result

    def _validate_hex(self, event):
        hex_value = self.ui.hex.text().strip('#')

        try:
            # Validate hex format
            if not all(c in '0123456789ABCDEFabcdef' for c in hex_value) or len(hex_value) != 6:
                raise ValueError
            result = True
        except ValueError:
            self.ui.hex.setText(self._original_values['hex'])
            result = False

        if event:
            return QtWidgets.QLineEdit.focusOutEvent(self.ui.hex, event)
        return result

    def _on_rgb_editing_finished(self):
        if all(self._validate_rgb(None, w) for w in [self.ui.red, self.ui.green, self.ui.blue]):
            self._original_values['rgb'] = self.get_rgb()
            self.rgb_changed()

    def _on_hsv_editing_finished(self):
        if (self._validate_hsv(None, self.ui.hue, 359) and
            self._validate_hsv(None, self.ui.saturation, 100) and
            self._validate_hsv(None, self.ui.value, 100)):
            h, s, v = int(self.ui.hue.text()), int(self.ui.saturation.text()), int(self.ui.value.text())
            self._original_values['hsv'] = (h, s, v)
            self.hsv_fields_changed()

    def _on_hex_editing_finished(self):
        if self._validate_hex(None):
            self._original_values['hex'] = self.ui.hex.text().strip('#')
            self.hex_changed()

    def hsv_changed(self):
        if self._block_change:
            return

        # Calculate hue from the selector position (0-359)
        selector_height = self.ui.hue_selector.height()
        center_y = self.ui.hue_selector.y() + selector_height / 2
        h = (1 - center_y / float(self.height)) * 359

        s, v = ((self.ui.selector.x() + 6) / (self.width / 100.0),
                (self.height - self.ui.selector.y() - 6) / (self.height / 100.0))
        r, g, b = self.hsv2rgb(h, s, v)
        self.color = (h, s, v)

        # Update original values
        self._original_values['hsv'] = (h, s, v)
        self._original_values['rgb'] = (r, g, b)
        self._original_values['hex'] = self.rgb2hex((r, g, b))

        self._block_change = True
        try:
            self._set_rgb((r, g, b))
            self._set_hex(self.hsv2hex(self.color))
            self.ui.color_vis.setStyleSheet(f"background-color: rgb({r},{g},{b})")
            self.ui.color_view.setStyleSheet(
                f"border-radius: 5px;background-color: qlineargradient(x1:1, x2:0, stop:0 hsl({h},100%,50%), stop:1 #fff);"
            )

            self.colorChanged.emit()
        finally:
              self._block_change = False

        self._block_change = False

    def hsv_fields_changed(self):
        h = int(self.ui.hue.text())
        s = int(self.ui.saturation.text())
        v = int(self.ui.value.text())

        # Store values directly (no conversion needed for h)
        self.color = (h, s, v)

        # Update RGB and HEX
        r, g, b = self.hsv2rgb(h, s, v)
        self._set_rgb((r, g, b))
        self._set_hex(self.rgb2hex((r, g, b)))

        # Update color visualization
        self.ui.color_vis.setStyleSheet(f"background-color: rgb({r},{g},{b})")
        self.ui.color_view.setStyleSheet(
            f"border-radius: 5px;background-color: qlineargradient(x1:1, x2:0, stop:0 hsl({h},100%,50%), stop:1 #fff);")

        # Store original values
        self._original_values['hsv'] = (h, s, v)
        self._original_values['rgb'] = (r, g, b)
        self._original_values['hex'] = self.rgb2hex((r, g, b))

        # Set flag before updating UI
        self._block_change = True

        # Update selector positions
        selector_height = self.ui.hue_selector.height()
        selector_width = self.ui.hue_selector.width()
        slider_width = self.ui.hue_slider.width()
        y = ((359 - h) * self.height / 359.0) - selector_height / 2
        x = (slider_width - selector_width) / 2
        self.ui.hue_selector.move(int(x), int(y))

        self.ui.selector.move(
            int(s * self.width / 100.0 - 6),
            int((self.height - v * self.height / 100.0) - 6)
        )

        self.colorChanged.emit()

        # Reset flag after updating UI
        self._block_change = False

    def rgb_changed(self):
        if self._block_change:
            return

        r, g, b = self.i(self.ui.red.text()), self.i(self.ui.green.text()), self.i(self.ui.blue.text())
        self.color = self.rgb2hsv(r, g, b)

        # Update original values
        self._original_values['rgb'] = (r, g, b)
        self._original_values['hsv'] = self.color
        self._original_values['hex'] = self.rgb2hex((r, g, b))

        self._set_hsv(self.color)
        self._set_hex(self.rgb2hex((r, g, b)))
        self.ui.color_vis.setStyleSheet(f"background-color: rgb({r},{g},{b})")
        self.colorChanged.emit()

    def hex_changed(self):
        if self._block_change:
            return

        hex_value = self.ui.hex.text()
        r, g, b = self.hex2rgb(hex_value)
        self.color = self.hex2hsv(hex_value)

        # Update original values
        self._original_values['hex'] = hex_value.strip('#')
        self._original_values['rgb'] = (r, g, b)
        self._original_values['hsv'] = self.color

        self._set_hsv(self.color)
        self._set_rgb(self.hex2rgb(hex_value))
        self.ui.color_vis.setStyleSheet(f"background-color: rgb({r},{g},{b})")
        self.colorChanged.emit()

    ## internal setting functions ##
    def _set_rgb(self, c):
        r,g,b = c
        self.ui.red.setText(str(self.i(r)))
        self.ui.green.setText(str(self.i(g)))
        self.ui.blue.setText(str(self.i(b)))

    def _set_hsv(self, hsv, update_selectors=True):
        h, s, v = hsv
        self.ui.hue.setText(str(int(h)))
        self.ui.saturation.setText(str(int(s)))
        self.ui.value.setText(str(int(v)))

        # Update the color view gradient
        self.ui.color_view.setStyleSheet(
            f"border-radius: 5px;background-color: qlineargradient(x1:1, x2:0, stop:0 hsl({h},100%,50%), stop:1 #fff);")

        # Only update selectors if the change didn't come from selector movement
        if update_selectors:
            selector_height = self.ui.hue_selector.height()
            selector_width = self.ui.hue_selector.width()
            slider_width = self.ui.hue_slider.width()
            y = ((359 - h) * self.height / 359.0) - selector_height / 2
            x = (slider_width - selector_width) / 2
            self.ui.hue_selector.move(int(x), int(y))

            self.ui.selector.move(
                int(s * self.width / 100.0 - 6),
                int((self.height - v * self.height / 100.0) - 6)
            )

    def _set_hex(self, c):
        self.ui.hex.setText(c.strip('#'))


    ## external setting functions ##
    def set_rgb(self, c):
        self._set_rgb(c)
        self.rgb_changed()

    def set_hsv(self, c, update_selectors=True):
        self._set_hsv(c, update_selectors=update_selectors)
        self.hsv_changed()

    def set_hex(self, c):
        self._set_hex(c)
        self.hex_changed()


    ## Color Utility ##
    def hsv2rgb(self, h_or_color, s = 0, v = 0):
        if type(h_or_color).__name__ == "tuple": h,s,v = h_or_color
        else: h = h_or_color
        h = h / 359.0  # Handle hue wraparound
        s = s / 100.0
        v = v / 100.0
        r,g,b = colorsys.hsv_to_rgb(h, s, v)
        return self.clamp_rgb((r * 255, g * 255, b * 255))

    def rgb2hsv(self, r_or_color, g=0, b=0):
        if type(r_or_color).__name__ == "tuple":
            r, g, b = r_or_color
        else:
            r = r_or_color
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        return (min(359, int(h * 360)), int(s * 100), int(v * 100))

    def hex2rgb(self, hex):
        if len(hex) < 6: hex += "0"*(6-len(hex))
        elif len(hex) > 6: hex = hex[0:6]
        rgb = tuple(int(hex[i:i+2], 16) for i in (0,2,4))
        return rgb

    def rgb2hex(self, r_or_color, g = 0, b = 0):
        if type(r_or_color).__name__ == "tuple": r,g,b = r_or_color
        else: r = r_or_color
        hex = '%02x%02x%02x' % (int(r),int(g),int(b))
        return hex

    def hex2hsv(self, hex):
        return self.rgb2hsv(self.hex2rgb(hex))

    def hsv2hex(self, h_or_color, s = 0, v = 0):
        if type(h_or_color).__name__ == "tuple": h,s,v = h_or_color
        else: h = h_or_color
        return self.rgb2hex(self.hsv2rgb(h,s,v))


    # selector move function
    def move_sv_selector(self, event):
        if event.buttons() != Qt.MouseButton.LeftButton:
            return

        pos = event.pos()
        x = max(0, min(pos.x(), self.width))
        y = max(0, min(pos.y(), self.height))

        self.ui.selector.move(x - 6, y - 6)

        s = (x / float(self.width)) * 100
        v = (1 - y / float(self.height)) * 100
        h = self.color[0]

        self.color = (h, s, v)
        self.set_hsv(self.color, update_selectors=False)

    def move_hue_selector(self, event):
        if event.buttons() != Qt.MouseButton.LeftButton:
            return

        pos = event.pos()
        selector_height = self.ui.hue_selector.height()
        selector_width = self.ui.hue_selector.width()
        slider_width = self.ui.hue_slider.width()
        y = max(-selector_height / 2, min(pos.y() - selector_height / 2, self.height - selector_height / 2))
        x = (slider_width - selector_width) / 2
        self.ui.hue_selector.move(int(x), int(y))

        # Convert from slider position (0-height) to hue (0-359)
        center_y = y + selector_height / 2
        h = (1 - (center_y / self.height)) * 359
        s, v = self.color[1:]

        self.color = (h, s, v)
        self.set_hsv(self.color, update_selectors=False)

    @staticmethod
    def i(text):
        try: return int(text)
        except: return 0

    @staticmethod
    def clamp_rgb(rgb):
        r,g,b = rgb
        if r<0.0001: r=0
        if g<0.0001: g=0
        if b<0.0001: b=0
        if r>255: r=255
        if g>255: g=255
        if b>255: b=255
        return (r,g,b)      

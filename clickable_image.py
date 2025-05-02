from PyQt6.QtWidgets import QLabel, QSizePolicy
from PyQt6.QtCore import Qt


class ClickableImage(QLabel):
    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer

        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(1, 1)
        self.setScaledContents(False)
        self.setObjectName("imageLabel")

    def mousePressEvent(self, event):
        self.viewer.image_mouse_click(event)

    def mouseMoveEvent(self, event):
        self.viewer.image_mouse_move(event)

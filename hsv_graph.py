
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import numpy as np


class HSVGraphWindow(QWidget):
    def __init__(self, colors):
        super().__init__()
        self.setWindowTitle("HSV Progression")
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        # Create matplotlib figure
        fig = Figure(figsize=(8, 6))
        canvas = FigureCanvasQTAgg(fig)
        layout.addWidget(canvas)

        # Create subplots for HSV graphs and color ramp
        gs = fig.add_gridspec(2, 1, height_ratios=[4, 1])
        ax_hsv = fig.add_subplot(gs[0])
        ax_colors = fig.add_subplot(gs[1])

        # Convert colors to HSV and create x-axis points
        hsv_values = np.array([self._rgb_to_hsv(r / 255, g / 255, b / 255)
                               for r, g, b, _ in colors])

        # Calculate x positions to align with color swatch centers
        num_colors = len(colors)
        swatch_width = 1.0 / num_colors
        x = np.array([i * swatch_width + swatch_width / 2 for i in range(num_colors)])

        # Plot HSV lines
        ax_hsv.plot(x, hsv_values[:, 0], label='Hue', color='red', marker='o')
        ax_hsv.plot(x, hsv_values[:, 1], label='Saturation', color='green', marker='o')
        ax_hsv.plot(x, hsv_values[:, 2], label='Value', color='blue', marker='o')

        # Add point annotations
        for i, (h, s, v) in enumerate(hsv_values):
            ax_hsv.annotate(f'H:{int(h * 360)}°\nS:{int(s * 100)}%\nV:{int(v * 100)}%',
                            (x[i], h),
                            textcoords="offset points",
                            xytext=(0, 10),
                            ha='center',
                            bbox=dict(boxstyle='round,pad=0.5',
                                      fc='white',
                                      ec='gray',
                                      alpha=0.8))

        ax_hsv.set_ylim(0, 1)
        ax_hsv.set_xlim(0, 1)
        ax_hsv.legend()
        ax_hsv.grid(True)
        ax_hsv.set_title('HSV Components Progression')

        # Create color ramp visualization
        color_array = np.array([[self._tuple_to_rgb(c) for c in colors]])
        ax_colors.imshow(color_array, extent=[0, 1, 0, 1], aspect='auto')
        ax_colors.set_yticks([])

        # Add x-ticks in the middle of each color swatch
        ax_colors.set_xticks(x)
        ax_colors.set_xticklabels([f'Color {i + 1}' for i in range(len(colors))])

        fig.tight_layout()

    @staticmethod
    def _rgb_to_hsv(r, g, b):
        maxc = max(r, g, b)
        minc = min(r, g, b)
        v = maxc
        if minc == maxc:
            return 0.0, 0.0, v
        s = (maxc - minc) / maxc
        rc = (maxc - r) / (maxc - minc)
        gc = (maxc - g) / (maxc - minc)
        bc = (maxc - b) / (maxc - minc)
        if r == maxc:
            h = bc - gc
        elif g == maxc:
            h = 2.0 + rc - bc
        else:
            h = 4.0 + gc - rc
        h = (h / 6.0) % 1.0
        return h, s, v

    @staticmethod
    def _tuple_to_rgb(color_tuple):
        return [c/255 for c in color_tuple[:3]]
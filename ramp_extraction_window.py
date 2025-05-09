import networkx as nx
from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel, QSizePolicy, QFrame, QVBoxLayout, QPushButton, QHBoxLayout, \
    QComboBox, QSlider
from PyQt6.QtCore import Qt
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from color_utils import extract_adjacent_color_pairs
from image_viewer import ImageViewerWidget


class RampWindow(QWidget):
    def __init__(self, original_pixmap):
        super().__init__()
        self.setWindowTitle("Color Ramp Extraction")
        self.setMinimumSize(1600, 900)

        layout = QGridLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)

        # Top-Left: Mini viewer
        self.mini_viewer = ImageViewerWidget(show_load_button=False, palette_square_size=25)
        self.mini_viewer.setMaximumSize(800, 450)
        self.mini_viewer.original_pixmap = original_pixmap
        self.mini_viewer.extract_unique_colors()
        self.mini_viewer.set_initial_fit_zoom()
        self.mini_viewer.update_image()
        layout.addWidget(self.mini_viewer, 0, 0)

        # Top-Right: Graph container
        self.use_8_neighbors = False
        self.graph_container = QFrame()
        graph_layout = QVBoxLayout()
        self.graph_container.setLayout(graph_layout)
        layout.addWidget(self.graph_container, 0, 1)

        self.graph_canvas = None
        self.graph_canvas_holder = QWidget()
        self.graph_canvas_holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        graph_layout.addWidget(self.graph_canvas_holder, stretch=1)

        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(6)

        # --- Row 1: Slider + Label ---
        row1 = QHBoxLayout()
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setMinimum(1)
        self.threshold_slider.setMaximum(100)
        self.threshold_value_label = QLabel("0.05")
        self.threshold_slider.valueChanged.connect(self.update_threshold_label)
        row1.addWidget(self.threshold_value_label)
        row1.addWidget(self.threshold_slider)
        controls_layout.addLayout(row1)

        # --- Row 2: Method dropdown + Generate button ---
        row2 = QHBoxLayout()
        self.threshold_selector = QComboBox()
        self.threshold_selector.addItems(["Relative to color frequency", "Percentile-based", "Absolute"])
        self.threshold_selector.currentTextChanged.connect(self.update_threshold_controls)
        self.graph_button = QPushButton("Extract Adjacency Graph")
        self.graph_button.clicked.connect(self.generate_graph)
        row2.addWidget(self.threshold_selector)
        row2.addWidget(self.graph_button)
        controls_layout.addLayout(row2)

        # Trigger initial update
        self.update_threshold_controls()
        graph_layout.addLayout(controls_layout)

        # Bottom-Left: Placeholder for ramps
        self.ramp_display = QLabel("Ramps View (coming soon)")
        self.ramp_display.setStyleSheet("background-color: #f9f9f9; border: 1px solid #888;")
        self.ramp_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ramp_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.ramp_display, 1, 0)

        # Bottom-Right: Future controls
        self.controls_area = QLabel("Controls / Filters (future)")
        self.controls_area.setStyleSheet("background-color: #ddd; border: 1px solid #888;")
        self.controls_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.controls_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.controls_area, 1, 1)

        # Ensure all grid cells are equal
        layout.setRowStretch(0, 1)
        layout.setRowStretch(1, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

    def generate_graph(self):
        image_array = self.mini_viewer.get_image_array()
        if image_array is None:
            return

        # Determine method and threshold
        method_name = self.threshold_selector.currentText()
        slider_value = self.threshold_slider.value()

        if method_name == "Percentile-based":
            method = "percentile"
            value = slider_value
        elif method_name == "Relative to color frequency":
            method = "relative"
            value = slider_value / 100.0
        elif method_name == "Absolute":
            method = "absolute"
            value = slider_value
        else:
            return

        # Always remove previous graph canvas first
        if self.graph_canvas:
            self.graph_canvas.setParent(None)
            self.graph_canvas.deleteLater()
            self.graph_canvas = None

        # Restore placeholder if necessary (prevents layout collapse)
        if self.graph_canvas_holder is None:
            self.graph_canvas_holder = QWidget()
            self.graph_canvas_holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.graph_container.layout().insertWidget(0, self.graph_canvas_holder, stretch=1)

        # Extract adjacent color pairs using selected method
        pair_counts = extract_adjacent_color_pairs(
            image_array,
            use_8_neighbors=self.use_8_neighbors,
            threshold_value=value,
            method=method
        )

        # If no pairs, don't build graph — placeholder already shown
        if not pair_counts:
            return

        # Build graph
        graph = nx.Graph()
        for (color1, color2), count in pair_counts.items():
            graph.add_node(color1)
            graph.add_node(color2)
            graph.add_edge(color1, color2)

        # Create matplotlib figure
        fig, ax = plt.subplots(figsize=(6, 6))
        pos = nx.kamada_kawai_layout(graph)

        # Draw nodes
        for node in graph.nodes:
            r, g, b, a = node
            nx.draw_networkx_nodes(
                graph, pos,
                nodelist=[node],
                node_size=500,
                node_color=f"#{r:02X}{g:02X}{b:02X}",
                ax=ax
            )

        # Draw edges
        nx.draw_networkx_edges(
            graph, pos,
            width=1.5,
            alpha=0.6,
            edge_color="gray",
            ax=ax
        )

        ax.set_axis_off()

        # Create new canvas and replace placeholder
        self.graph_canvas = FigureCanvas(fig)
        self.graph_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        if self.graph_canvas_holder:
            self.graph_container.layout().replaceWidget(self.graph_canvas_holder, self.graph_canvas)
            self.graph_canvas_holder.setParent(None)
            self.graph_canvas_holder = None
        else:
            self.graph_container.layout().insertWidget(0, self.graph_canvas, stretch=1)

        plt.close(fig)

    def update_threshold_controls(self):
        method = self.threshold_selector.currentText()
        if method == "Percentile-based":
            self.threshold_slider.setMinimum(1)
            self.threshold_slider.setMaximum(100)
            self.threshold_slider.setSingleStep(1)
            self.threshold_slider.setValue(90)
        elif method == "Relative to color frequency":
            self.threshold_slider.setMinimum(1)
            self.threshold_slider.setMaximum(400)
            self.threshold_slider.setSingleStep(1)
            self.threshold_slider.setValue(40)
        elif method == "Absolute":
            img = self.mini_viewer.get_image_array()
            h, w, _ = img.shape
            max_pairs = (h * w) // 4 or 3
            self.threshold_slider.setMinimum(1)
            self.threshold_slider.setMaximum(max_pairs)
            self.threshold_slider.setSingleStep(1)
            self.threshold_slider.setValue(max_pairs // 20 or 3)
        self.update_threshold_label()

    def update_threshold_label(self):
        method = self.threshold_selector.currentText()
        value = self.threshold_slider.value()
        if method == "Percentile-based":
            self.threshold_value_label.setText(f"Min. percentile:   {value}%  ")
        elif method == "Relative to color frequency":
            self.threshold_value_label.setText(f"Min. relative adjacency strength:   ≥ {value / 400:.3f}  ")
        elif method == "Absolute":
            self.threshold_value_label.setText(f"Min. number of occurrences:   ≥ {value}  ")



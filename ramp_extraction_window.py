import networkx as nx
import numpy as np
from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel, QSizePolicy, QFrame, QVBoxLayout, QPushButton, QHBoxLayout, \
    QComboBox, QSlider, QScrollArea
from PyQt6.QtCore import Qt
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from color_utils import extract_adjacent_color_pairs, color_to_hsv
from image_viewer import ImageViewerWidget
from ramp_analysis import find_color_ramps, find_color_ramps_vector_hsv


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
        self.color_graph = None
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

        # Bottom-Left: Placeholder for palette
        self.ramp_display = QLabel("Palette View (coming soon)")
        self.ramp_display.setStyleSheet("background-color: #f9f9f9; border: 1px solid #888;")
        self.ramp_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ramp_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.ramp_display, 1, 0)

        # Bottom-Right: Two columns: Ramps | Controls
        bottom_right_split = QHBoxLayout()
        layout.addLayout(bottom_right_split, 1, 1)

        # Left: Ramp scroll area
        self.ramp_scroll_area = QScrollArea()
        self.ramp_scroll_area.setWidgetResizable(True)
        self.ramp_container = QWidget()
        self.ramp_layout = QVBoxLayout(self.ramp_container)
        self.ramp_layout.setContentsMargins(0, 0, 0, 0)
        self.ramp_layout.setSpacing(0)
        self.ramp_scroll_area.setWidget(self.ramp_container)
        bottom_right_split.addWidget(self.ramp_scroll_area, 2)

        # Right: Controls
        self.controls_panel = QWidget()
        controls_layout = QVBoxLayout(self.controls_panel)

        self.extraction_method_selector = QComboBox()
        self.extraction_method_selector.addItems(["Basic HSV", "Vector HSV"])
        self.extraction_method_selector.currentTextChanged.connect(self.update_extraction_controls)
        controls_layout.addWidget(QLabel("Extraction Method"))
        controls_layout.addWidget(self.extraction_method_selector)

        # Panels for controls
        self.basic_controls = QWidget()
        basic_layout = QVBoxLayout(self.basic_controls)

        self.h_slider = self.create_labeled_slider("Max Hue Step (˚)", 0, 180, 60, basic_layout)
        self.h_tolerance_slider = self.create_labeled_slider("Hue Step Variance Tolerance (˚)", 0, 100, 30, basic_layout)
        self.s_slider = self.create_labeled_slider("Max Saturation Step", 0, 100, 50, basic_layout)
        self.s_tolerance_slider = self.create_labeled_slider("Saturation Step Variance Tolerance", 0, 100, 20, basic_layout)
        self.v_slider = self.create_labeled_slider("Max Brightness Step", 0, 100, 50, basic_layout)
        self.v_tolerance_slider = self.create_labeled_slider("Brightness Step Variance Tolerance", 0, 100, 20, basic_layout)

        controls_layout.addWidget(self.basic_controls)

        # Vector HSV Controls
        self.vector_controls = QWidget()
        vector_layout = QVBoxLayout(self.vector_controls)

        self.vector_angle_tolerance_slider = self.create_labeled_slider("Angle Tolerance (°)", 0, 180, 15, vector_layout)
        self.vector_step_size_slider = self.create_labeled_slider("Max Step Size", 0, 100, 20, vector_layout)

        self.vector_controls.hide()
        controls_layout.addWidget(self.vector_controls)

        controls_layout.addStretch()
        self.extract_ramps_button = QPushButton("Extract Ramps from Graph")
        self.extract_ramps_button.setEnabled(False)
        self.extract_ramps_button.clicked.connect(self.extract_color_ramps)
        controls_layout.addWidget(self.extract_ramps_button)
        bottom_right_split.addWidget(self.controls_panel, 1)

        # Ensure all grid cells are equal
        layout.setRowStretch(0, 1)
        layout.setRowStretch(1, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

    def create_labeled_slider(self, label_text, min_val, max_val, default, layout):
        label = QLabel(f"{label_text}: {default}")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default)
        slider.valueChanged.connect(lambda val: label.setText(f"{label_text}: {val}"))
        layout.addWidget(label)
        layout.addWidget(slider)
        return slider

    def update_extraction_controls(self):
        method = self.extraction_method_selector.currentText()
        if method == "Basic HSV":
            self.basic_controls.show()
            self.vector_controls.hide()
        elif method == "Vector HSV":
            self.basic_controls.hide()
            self.vector_controls.show()

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
        self.color_graph = None
        self.extract_ramps_button.setEnabled(False)
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

        self.color_graph = graph
        self.extract_ramps_button.setEnabled(True)

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
            self.threshold_slider.setValue(20)
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

    def extract_color_ramps(self):
        if self.color_graph is None:
            return

        method = self.extraction_method_selector.currentText()

        if method == "Basic HSV":
            max_step = [
                self.h_slider.value() / 180.0,
                self.s_slider.value() / 100.0,
                self.v_slider.value() / 100.0,
            ]
            tolerance = [
                self.h_tolerance_slider.value() / 180.0,
                self.s_tolerance_slider.value() / 100.0,
                self.v_tolerance_slider.value() / 100.0,
            ]
            ramps = find_color_ramps(self.color_graph, tolerance, max_step)

        elif method == "Vector HSV":
            angle_tolerance_deg = self.vector_angle_tolerance_slider.value()
            max_step_size = self.vector_step_size_slider.value() / 100.0
            ramps = find_color_ramps_vector_hsv(
                self.color_graph,
                angle_tolerance_deg,
                max_step_size
            )

        else:
            return

        self.display_color_ramps(ramps)

    def display_color_ramps(self, ramps):
        # Clear previous ramp layout
        for i in reversed(range(self.ramp_layout.count())):
            item = self.ramp_layout.itemAt(i)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        for ramp in ramps:
            row_widget = QWidget()
            row_widget.setContentsMargins(0, 0, 0, 0)
            row_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(0)

            for color in ramp:
                r, g, b, a = color
                swatch = QLabel()
                swatch.setFixedSize(25, 25)
                swatch.setStyleSheet(f"""
                    background-color: rgba({r},{g},{b},{a});
                    margin: 0px;
                    padding: 0px;
                    border: none;
                """)
                swatch.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                row_layout.addWidget(swatch)

            self.ramp_layout.addWidget(row_widget)



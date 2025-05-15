import networkx as nx
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QSlider, QPushButton,
    QLabel, QSizePolicy, QCheckBox, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib import pyplot as plt

from color_utils import extract_adjacent_color_pairs, is_similar_hsv, is_similar_ciede2000


class GraphViewer(QWidget):
    def __init__(self, image_array, unique_colors, parent=None):
        super().__init__(parent)
        self.image_array = image_array
        self.unique_colors = list(unique_colors)

        self.color_graph = None
        self.use_8_neighbors = False

        self._cached_adjacency_pairs = None
        self._cached_color_counts = None
        self._cached_similarity_pairs = None

        self._setup_ui()
        self.connect_threshold_updates()
        self.update_ui_visibility()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Graph Type Selection
        graph_type_row = QHBoxLayout()
        graph_type_label = QLabel("Graph Type:")
        graph_type_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self.graph_type_selector = QComboBox()
        self.graph_type_selector.addItems([
            "Spatial Adjacency Graph",
            "Color Similarity Graph",
            "Hybrid Graph (Spatial + Color)"
        ])
        self.graph_type_selector.currentTextChanged.connect(self.update_ui_visibility)
        self.graph_type_selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        graph_type_row.addWidget(graph_type_label)
        graph_type_row.addWidget(self.graph_type_selector)
        layout.addLayout(graph_type_row)

        # Graph Canvas Area
        self.graph_canvas_holder = QWidget()
        self.graph_canvas_holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.graph_canvas_holder)

        # Controls Grid (3 Columns)
        self.controls_grid = QGridLayout()
        self._setup_spatial_controls()
        self._setup_color_controls()
        self._setup_combination_controls()
        layout.addLayout(self.controls_grid)

        # Realtime Graph Update Timer
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.generate_graph)

    def _setup_spatial_controls(self):
        col = 0
        self.spatial_threshold_label = QLabel("Threshold:")
        self.spatial_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.spatial_threshold_slider.setRange(1, 100)
        self.spatial_threshold_slider.setValue(50)

        self.spatial_method_selector = QComboBox()
        self.spatial_method_selector.addItems(["Relative to color frequency", "Percentile-based", "Absolute"])

        self.controls_grid.addWidget(self.spatial_threshold_label, 0, col)
        self.controls_grid.addWidget(self.spatial_threshold_slider, 1, col)
        self.controls_grid.addWidget(self.spatial_method_selector, 2, col)

    def _setup_color_controls(self):
        self.color_threshold_label = QLabel("Threshold:")
        self.color_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.color_threshold_slider.setRange(1, 100)
        self.color_threshold_slider.setValue(30)

        self.color_method_selector = QComboBox()
        self.color_method_selector.addItems(["CIEDE2000", "HSV"])

        # HSV Sliders Container
        self.hsv_sliders_container = QWidget()
        hsv_layout = QVBoxLayout(self.hsv_sliders_container)

        self.hue_slider = self._create_hsv_slider("H-diff:  ≤", 180, 30, hsv_layout, "°")
        self.sat_slider = self._create_hsv_slider("S-diff:  ≤", 100, 30, hsv_layout, "%")
        self.val_slider = self._create_hsv_slider("V-diff:  ≤", 100, 30, hsv_layout, "%")

        self.update_color_controls()

    def _setup_combination_controls(self):
        col = 2
        self.combination_method_selector = QComboBox()
        self.combination_method_selector.addItems(["Union", "Intersection"])

        self.realtime_checkbox = QCheckBox("Auto-Update")
        self.realtime_checkbox.setChecked(False)

        self.generate_button = QPushButton("Generate Graph")
        self.generate_button.clicked.connect(self.generate_graph)

        self.controls_grid.addWidget(self.combination_method_selector, 0, col)
        self.controls_grid.addWidget(self.realtime_checkbox, 1, col)
        self.controls_grid.addWidget(self.generate_button, 2, col)

    def _create_hsv_slider(self, label_text, max_value, default, parent_layout, unit="%"):
        row = QHBoxLayout()
        label = QLabel(f"{label_text} {default}{unit}")
        label.setFixedWidth(90)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, max_value)
        slider.setValue(default)
        slider.valueChanged.connect(lambda val, l=label, t=label_text: l.setText(f"{t} {val}{unit}"))
        slider.valueChanged.connect(self.schedule_graph_update)

        row.addWidget(label)
        row.addWidget(slider)
        parent_layout.addLayout(row)

        return slider

    def update_ui_visibility(self):
        graph_type = self.graph_type_selector.currentText()
        is_hybrid = (graph_type == "Hybrid Graph (Spatial + Color)")

        # Determine which columns to show
        show_spatial = is_hybrid or graph_type == "Spatial Adjacency Graph"
        show_color = is_hybrid or graph_type == "Color Similarity Graph"
        show_combination = is_hybrid

        # Show/Hide spatial controls
        self.spatial_threshold_label.setVisible(show_spatial)
        self.spatial_threshold_slider.setVisible(show_spatial)
        self.spatial_method_selector.setVisible(show_spatial)

        # Show/Hide color controls
        self.color_threshold_label.setVisible(show_color and self.color_method_selector.currentText() != "HSV")
        self.color_threshold_slider.setVisible(show_color and self.color_method_selector.currentText() != "HSV")
        self.color_method_selector.setVisible(show_color)
        self.hsv_sliders_container.setVisible(show_color and self.color_method_selector.currentText() == "HSV")

        # Show/Hide combination controls
        self.combination_method_selector.setVisible(show_combination)

        # Adjust column stretches
        self.controls_grid.setColumnStretch(0, 1 if show_spatial else 0)
        self.controls_grid.setColumnStretch(1, 1 if show_color else 0)
        self.controls_grid.setColumnStretch(2, 1 if show_combination else 0)

        self.update_sliders()

    def update_threshold_labels(self):
        # Spatial Threshold
        spatial_value = self.spatial_threshold_slider.value()
        s_method = self.spatial_method_selector.currentText()
        if s_method == "Percentile-based":
            self.spatial_threshold_label.setText(f"Percentile: {spatial_value}%")
        elif s_method == "Relative to color frequency":
            self.spatial_threshold_label.setText(f"Relative Adjacency: ≥ {spatial_value / 100:.2f}")
        elif s_method == "Absolute":
            self.spatial_threshold_label.setText(f"Occurrences: ≥ {spatial_value}")

        # Color Threshold
        color_value = self.color_threshold_slider.value()
        c_method = self.color_method_selector.currentText()
        if c_method == "CIEDE2000":
            self.color_threshold_label.setText(f"ΔE Similarity: ≤ {color_value}")

    def connect_threshold_updates(self):
        # Spatial Controls
        self.spatial_threshold_slider.valueChanged.connect(self.update_threshold_labels)
        self.spatial_threshold_slider.valueChanged.connect(self.schedule_graph_update)
        self.spatial_method_selector.currentTextChanged.connect(self.update_sliders)
        self.spatial_method_selector.currentTextChanged.connect(self.schedule_graph_update)

        # Color Controls
        self.color_threshold_slider.valueChanged.connect(self.update_threshold_labels)
        self.color_threshold_slider.valueChanged.connect(self.schedule_graph_update)
        self.color_method_selector.currentTextChanged.connect(self.update_color_controls)

        # Combination Controls
        self.combination_method_selector.currentTextChanged.connect(self.update_color_controls)

    def update_sliders(self):
        graph_type = self.graph_type_selector.currentText()

        # Update Spatial Controls
        if graph_type in ["Spatial Adjacency Graph", "Hybrid Graph (Spatial + Color)"]:
            method = self.spatial_method_selector.currentText()
            if method == "Percentile-based":
                self.spatial_threshold_slider.setRange(1, 100)
                self.spatial_threshold_slider.setValue(80)
            elif method == "Relative to color frequency":
                self.spatial_threshold_slider.setRange(1, 200)
                self.spatial_threshold_slider.setValue(50)
            elif method == "Absolute":
                self.calculate_adjacency_pairs()
                max_occurrence = max(self._cached_color_counts.values(), default=1)
                self.spatial_threshold_slider.setRange(1, max_occurrence)
                self.spatial_threshold_slider.setValue(min(20, max_occurrence))

        # Update Color Controls
        if graph_type in ["Color Similarity Graph", "Hybrid Graph (Spatial + Color)"]:
            method = self.color_method_selector.currentText()
            if method == "HSV":
                self.color_threshold_slider.setRange(1, 100)
                self.color_threshold_slider.setValue(30)
            elif method == "CIEDE2000":
                self.color_threshold_slider.setRange(1, 100)
                self.color_threshold_slider.setValue(30)

        self.update_threshold_labels()

    def update_color_controls(self):
        col = 1
        method = self.color_method_selector.currentText()

        self.controls_grid.removeWidget(self.color_threshold_label)
        self.controls_grid.removeWidget(self.color_threshold_slider)
        self.controls_grid.removeWidget(self.hsv_sliders_container)

        self.color_threshold_label.setParent(None)
        self.color_threshold_slider.setParent(None)
        self.hsv_sliders_container.setParent(None)

        if method == "HSV":
            self.controls_grid.addWidget(self.hsv_sliders_container, 0, col, 2, 1)
            self.controls_grid.addWidget(self.color_method_selector, 2, col)
        elif method == "CIEDE2000":
            self.controls_grid.addWidget(self.color_threshold_label, 0, col)
            self.controls_grid.addWidget(self.color_threshold_slider, 1, col)
            self.controls_grid.addWidget(self.color_method_selector, 2, col)

        self.color_threshold_label.setVisible(method != "HSV")
        self.color_threshold_slider.setVisible(method != "HSV")
        self.hsv_sliders_container.setVisible(method == "HSV")

        self.update_sliders()

    def schedule_graph_update(self):
        if self.realtime_checkbox.isChecked():
                self.update_timer.start(100)  # Delay in milliseconds

    def generate_graph(self):
        if self.image_array is None or not self.unique_colors:
            return

        graph_type = self.graph_type_selector.currentText()

        if graph_type == "Spatial Adjacency Graph":
            graph = self.generate_spatial_graph()
        elif graph_type == "Color Similarity Graph":
            graph = self.generate_color_graph()
        elif graph_type == "Hybrid Graph (Spatial + Color)":
            spatial_graph = self.generate_spatial_graph()
            color_graph = self.generate_color_graph()
            graph = self.combine_graphs(spatial_graph, color_graph)
        else:
            raise ValueError(f"Unknown graph type: {graph_type}")

        self.color_graph = graph
        self.display_graph(graph)

    def generate_spatial_graph(self):
        self.calculate_adjacency_pairs()

        method = self.spatial_method_selector.currentText()
        threshold = self.spatial_threshold_slider.value()

        filtered_pairs = self.filter_adjacency_pairs(
            self._cached_adjacency_pairs,
            self._cached_color_counts,
            method,
            threshold
        )

        graph = nx.Graph()
        for (c1, c2), count in filtered_pairs.items():
            graph.add_edge(c1, c2)

        return graph

    def generate_color_graph(self):
        self.calculate_similarity_pairs()

        method = self.color_method_selector.currentText()
        threshold = self.color_threshold_slider.value()

        if method == "HSV":
            hue_thresh = self.hue_slider.value()
            sat_thresh = self.sat_slider.value() / 100.0
            val_thresh = self.val_slider.value() / 100.0
            valid_pairs = [
                (c1, c2) for c1, c2 in self._cached_similarity_pairs
                if is_similar_hsv(c1, c2, hue_thresh, sat_thresh, val_thresh)
            ]
        elif method == "CIEDE2000":
            valid_pairs = [
                (c1, c2) for c1, c2 in self._cached_similarity_pairs
                if is_similar_ciede2000(c1, c2, threshold)
            ]
        else:
            raise ValueError(f"Unknown color similarity method: {method}")

        graph = nx.Graph()
        for c1, c2 in valid_pairs:
            graph.add_edge(c1, c2)

        return graph

    def combine_graphs(self, spatial_graph, color_graph):
        method = self.combination_method_selector.currentText()
        combined_graph = nx.Graph()

        if method == "Union":
            combined_graph.add_edges_from(spatial_graph.edges)
            combined_graph.add_edges_from(color_graph.edges)
        elif method == "Intersection":
            common_edges = set(spatial_graph.edges).intersection(color_graph.edges)
            combined_graph.add_edges_from(common_edges)
        else:
            raise ValueError(f"Unknown combination method: {method}")

        return combined_graph

    def calculate_adjacency_pairs(self):
        if self._cached_adjacency_pairs is None or self._cached_color_counts is None:
            self._cached_adjacency_pairs, self._cached_color_counts = extract_adjacent_color_pairs(
                self.image_array,
                use_8_neighbors=self.use_8_neighbors
            )

    def calculate_similarity_pairs(self):
        if self._cached_similarity_pairs is None:
            pairs = []
            for c1 in self.unique_colors:
                for c2 in self.unique_colors:
                    if c1 != c2:
                        pairs.append((c1, c2))
            self._cached_similarity_pairs = pairs

    @staticmethod
    def filter_adjacency_pairs(pair_counts, color_counts, method, threshold):
        if not pair_counts:
            return {}

        if method == "Absolute":
            return {pair: count for pair, count in pair_counts.items() if count >= threshold}

        elif method == "Relative to color frequency":
            return {
                pair: count for pair, count in pair_counts.items()
                if (count / max(1, color_counts.get(pair[0], 1)) >= threshold / 100.0 or
                    count / max(1, color_counts.get(pair[1], 1)) >= threshold / 100.0)
            }

        elif method == "Percentile-based":
            counts = np.array(list(pair_counts.values()))
            t_val = np.percentile(counts, threshold)
            return {pair: count for pair, count in pair_counts.items() if count >= t_val}

        raise ValueError(f"Unknown spatial filtering method: {method}")

    def display_graph(self, graph):
        fig, ax = plt.subplots(figsize=(6, 6))
        pos = nx.kamada_kawai_layout(graph)
        pos = self.perturb_positions(pos)

        for node in graph.nodes:
            r, g, b, a = node
            nx.draw_networkx_nodes(
                graph, pos,
                nodelist=[node],
                node_size=500,
                node_color=f"#{r:02X}{g:02X}{b:02X}",
                ax=ax
            )

        nx.draw_networkx_edges(graph, pos, width=1.5, alpha=0.6, edge_color="gray", ax=ax)
        ax.set_axis_off()
        plt.close(fig)

        canvas = FigureCanvas(fig)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        holder_layout = self.graph_canvas_holder.layout()
        if not holder_layout:
            holder_layout = QVBoxLayout()
            holder_layout.setContentsMargins(0, 0, 0, 0)
            self.graph_canvas_holder.setLayout(holder_layout)
        else:
            while holder_layout.count():
                item = holder_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)

        holder_layout.addWidget(canvas)

    @staticmethod
    def perturb_positions(pos, epsilon=0.1, precision=4):
        seen = {}
        for node, (x, y) in pos.items():
            key = (round(x, precision), round(y, precision))
            if key in seen:
                # Slightly offset the position to avoid overlap
                pos[node] = (x + epsilon, y + epsilon)
            else:
                seen[key] = node
        return pos
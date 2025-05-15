import networkx as nx
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QSlider, QPushButton,
    QLabel, QSizePolicy, QCheckBox
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

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Graph type selection
        top_row = QHBoxLayout()
        label = QLabel("Color Space Model:")
        label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self.graph_type_selector = QComboBox()
        self.graph_type_selector.addItems(["Spatial Adjacency Graph", "Color Similarity Graph"])
        self.graph_type_selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.graph_type_selector.currentTextChanged.connect(self.update_threshold_controls)
        top_row.addWidget(label)
        top_row.addWidget(self.graph_type_selector)
        layout.addLayout(top_row)

        # Graph canvas area
        self.graph_canvas_holder = QWidget()
        self.graph_canvas_holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.graph_canvas_holder)

        # Threshold slider
        self.general_threshold_container = QWidget()
        threshold_row = QHBoxLayout(self.general_threshold_container)
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(1, 100)
        self.threshold_slider.setValue(20)
        self.threshold_slider.valueChanged.connect(self.update_threshold_label)
        self.threshold_value_label = QLabel("Threshold: 50")
        threshold_row.addWidget(self.threshold_value_label)
        threshold_row.addWidget(self.threshold_slider)
        layout.addWidget(self.general_threshold_container)

        # HSV threshold sliders
        self._setup_hsv_sliders(layout)

        # Threshold method + generate button
        method_row = QHBoxLayout()
        self.threshold_selector = QComboBox()
        self.threshold_selector.addItems(["Relative to color frequency", "Percentile-based", "Absolute"])
        self.threshold_selector.currentTextChanged.connect(self.update_threshold_slider)
        self.threshold_selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.graph_button = QPushButton("Generate Graph")
        self.graph_button.clicked.connect(self.generate_graph)
        self.graph_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.realtime_checkbox = QCheckBox("Auto-update")
        self.realtime_checkbox.setChecked(False)
        method_row.addWidget(self.threshold_selector)
        method_row.addWidget(self.graph_button)
        method_row.addWidget(self.realtime_checkbox)
        layout.addLayout(method_row)

        # Realtime updates when slider values change
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.generate_graph)
        self.threshold_slider.valueChanged.connect(self.schedule_graph_update)
        self.hue_slider.valueChanged.connect(self.schedule_graph_update)
        self.sat_slider.valueChanged.connect(self.schedule_graph_update)
        self.val_slider.valueChanged.connect(self.schedule_graph_update)

        self.update_threshold_controls()

    def schedule_graph_update(self):
        if self.realtime_checkbox.isChecked():
                self.update_timer.start(100)  # Delay in milliseconds

    def _setup_hsv_sliders(self, layout):
        # HSV Per-Aspect Sliders
        self.hsv_sliders_container = QWidget()
        hsv_layout = QVBoxLayout(self.hsv_sliders_container)

        # Hue Slider
        hue_row = QHBoxLayout()
        self.hue_slider = QSlider(Qt.Orientation.Horizontal)
        self.hue_slider.setRange(0, 180)
        self.hue_slider.setValue(30)
        self.hue_label = QLabel("Hue Diff:  ≤ 30°")
        self.hue_label.setFixedWidth(115)
        self.hue_slider.valueChanged.connect(lambda val: self.hue_label.setText(f"Hue Diff:  ≤ {val}°"))
        hue_row.addWidget(self.hue_label)
        hue_row.addWidget(self.hue_slider)
        hsv_layout.addLayout(hue_row)

        # Saturation Slider
        sat_row = QHBoxLayout()
        self.sat_slider = QSlider(Qt.Orientation.Horizontal)
        self.sat_slider.setRange(0, 100)
        self.sat_slider.setValue(30)
        self.sat_label = QLabel("Sat Diff:   ≤ 30%")
        self.sat_label.setFixedWidth(115)
        self.sat_slider.valueChanged.connect(lambda val: self.sat_label.setText(f"Sat Diff:   ≤ {val}%"))
        sat_row.addWidget(self.sat_label)
        sat_row.addWidget(self.sat_slider)
        hsv_layout.addLayout(sat_row)

        # Value Slider
        val_row = QHBoxLayout()
        self.val_slider = QSlider(Qt.Orientation.Horizontal)
        self.val_slider.setRange(0, 100)
        self.val_slider.setValue(30)
        self.val_label = QLabel("Val Diff:   ≤ 30%")
        self.val_label.setFixedWidth(115)
        self.val_slider.valueChanged.connect(lambda val: self.val_label.setText(f"Val Diff:   ≤ {val}%"))
        val_row.addWidget(self.val_label)
        val_row.addWidget(self.val_slider)
        hsv_layout.addLayout(val_row)

        layout.addWidget(self.hsv_sliders_container)
        self.hsv_sliders_container.hide()

    def update_threshold_controls(self):
        graph_type = self.graph_type_selector.currentText()
        self.threshold_selector.clear()
        self.hsv_sliders_container.hide()
        self.general_threshold_container.show()
        if graph_type == "Spatial Adjacency Graph":
            self.threshold_selector.addItems(["Relative to color frequency", "Percentile-based", "Absolute"])
            self.threshold_selector.setCurrentText("Relative to color frequency")
        elif graph_type == "Color Similarity Graph":
            self.threshold_selector.addItems(["HSV", "CIEDE2000"])
            self.threshold_selector.setCurrentText("CIEDE2000")
        else:
            raise ValueError(f"Unknown color space model: {graph_type}")
        self.update_threshold_slider()

    def update_threshold_slider(self):
        graph_type = self.graph_type_selector.currentText()
        method = self.threshold_selector.currentText()
        self.hsv_sliders_container.hide()
        self.general_threshold_container.show()

        if graph_type == "Spatial Adjacency Graph":
            if method == "Percentile-based":
                self.threshold_slider.setRange(1, 100)
                self.threshold_slider.setValue(80)
            elif method == "Relative to color frequency":
                self.threshold_slider.setRange(1, 200)
                self.threshold_slider.setValue(50)
            elif method == "Absolute":
                self.calculate_adjacency_pairs()
                max_occurrence = max(self._cached_color_counts.values(), default=1)
                self.threshold_slider.setRange(1, max_occurrence)
                self.threshold_slider.setValue(min(20, max_occurrence))

        elif graph_type == "Color Similarity Graph":
            if method == "HSV":
                self.hsv_sliders_container.show()
                self.general_threshold_container.hide()
            elif method == "CIEDE2000":
                self.threshold_slider.setRange(1, 100)
                self.threshold_slider.setValue(30)

        else:
            raise ValueError(f"Unknown color space model: {graph_type}")

        self.update_threshold_label()

    def update_threshold_label(self):
        graph_type = self.graph_type_selector.currentText()
        method = self.threshold_selector.currentText()
        value = self.threshold_slider.value()

        if graph_type == "Spatial Adjacency Graph":
            if method == "Percentile-based":
                self.threshold_value_label.setText(f"Percentile: {value}%")
            elif method == "Relative to color frequency":
                self.threshold_value_label.setText(f"Relative Adjacency: ≥ {value / 100:.2f}")
            elif method == "Absolute":
                self.threshold_value_label.setText(f"Occurrences: ≥ {value}")

        elif graph_type == "Color Similarity Graph":
            if method == "CIEDE2000":
                self.threshold_value_label.setText(f"Similarity (ΔE): ≤ {value}")

        else:
            raise ValueError(f"Unknown color space model: {graph_type}")

    def generate_graph(self):
        if self.image_array is None or not self.unique_colors:
            return

        graph_type = self.graph_type_selector.currentText()
        if graph_type == "Spatial Adjacency Graph":
            graph = self.generate_spatial_graph()
        elif graph_type == "Color Similarity Graph":
            graph = self.generate_similarity_graph()
        else:
            raise ValueError(f"Unknown color space model: {graph_type}")

        self.color_graph = graph
        self._display_graph(graph)

    def generate_spatial_graph(self):
        self.calculate_adjacency_pairs()
        method, threshold = self._map_spatial_threshold(
            self.threshold_selector.currentText(),
            self.threshold_slider.value()
        )

        filtered_pairs = self.filter_adjacency_pairs(
            self._cached_adjacency_pairs,
            self._cached_color_counts,
            method,
            threshold
        )

        graph = nx.Graph()
        for (color1, color2), count in filtered_pairs.items():
            graph.add_node(color1)
            graph.add_node(color2)
            graph.add_edge(color1, color2)

        return graph

    @staticmethod
    def filter_adjacency_pairs(pair_counts, color_counts, method, threshold):
        if not pair_counts:
            return {}

        if method == "absolute":
            return {pair: count for pair, count in pair_counts.items() if count >= threshold}

        elif method == "relative":
            return {
                pair: count for pair, count in pair_counts.items()
                if (count / max(1, color_counts.get(pair[0], 1)) >= threshold * 4 or
                    count / max(1, color_counts.get(pair[1], 1)) >= threshold * 4)
            }

        elif method == "percentile":
            counts = np.array(list(pair_counts.values()))
            threshold = np.percentile(counts, threshold)
            return {pair: count for pair, count in pair_counts.items() if count >= threshold}

        else:
            raise ValueError(f"Unknown filtering method: {method}")

    def generate_similarity_graph(self):
        method = self.threshold_selector.currentText()
        self.calculate_similarity_pairs()

        if method == "HSV":
            hue_thresh = self.hue_slider.value()
            sat_thresh = self.sat_slider.value() / 100.0
            val_thresh = self.val_slider.value() / 100.0
            valid_pairs = [
                (c1, c2) for c1, c2 in self._cached_similarity_pairs
                if is_similar_hsv(c1, c2, hue_thresh, sat_thresh, val_thresh)
            ]
        elif method == "CIEDE2000":
            slider_value = self.threshold_slider.value()
            valid_pairs = [
                (c1, c2) for c1, c2 in self._cached_similarity_pairs
                if is_similar_ciede2000(c1, c2, slider_value)
            ]
        else:
            raise ValueError(f"Unknown filtering method: {method}")

        graph = nx.Graph()
        for c1, c2 in valid_pairs:
            graph.add_node(c1)
            graph.add_node(c2)
            graph.add_edge(c1, c2)

        return graph

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
                    if c1 == c2:
                        continue
                    pairs.append((c1, c2))
            self._cached_similarity_pairs = pairs

    @staticmethod
    def _map_spatial_threshold(method_name, slider_value):
        if method_name == "Percentile-based":
            return "percentile", slider_value
        elif method_name == "Relative to color frequency":
            return "relative", slider_value / 100.0
        elif method_name == "Absolute":
            return "absolute", slider_value
        else:
            raise ValueError(f"Unknown filtering method: {method_name}")

    def _display_graph(self, graph):
        fig, ax = plt.subplots(figsize=(6, 6))
        pos = nx.kamada_kawai_layout(graph)

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

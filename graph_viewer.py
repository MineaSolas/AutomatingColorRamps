import networkx as nx
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QSlider, QPushButton,
    QLabel, QSizePolicy, QCheckBox, QGridLayout, QGroupBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib import pyplot as plt

from color_utils import extract_adjacent_color_pairs, is_similar_hsv, is_similar_ciede2000
from global_managers import global_color_manager, global_ramp_manager


class GraphViewer(QWidget):
    def __init__(self, image_array, parent=None):
        super().__init__(parent)
        self.image_array = image_array
        self.color_groups = {
            group.color_id: group
            for group in global_color_manager.get_color_groups()
        }

        self.color_graph = None
        self.use_8_neighbors = False
        self.graph_window = None  # Add this line to store the window reference

        self._cached_adjacency_pairs = None
        self._cached_color_counts = None
        self._cached_similarity_pairs = None
        self.spatial_slider_values = {}
        self.color_slider_values = {}

        self._setup_ui()
        self.connect_updates()
        self.update_ui_visibility()

    graph_updated = pyqtSignal()

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
        self.graph_type_selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        graph_type_row.addWidget(graph_type_label)
        graph_type_row.addWidget(self.graph_type_selector)
        layout.addLayout(graph_type_row)

        # Graph Canvas Area
        self.graph_canvas_holder_box = QGroupBox()
        self.graph_canvas_holder_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        box_layout = QVBoxLayout(self.graph_canvas_holder_box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(0)

        self.graph_canvas_holder = QWidget()
        self.graph_canvas_holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        box_layout.addWidget(self.graph_canvas_holder)
        layout.addWidget(self.graph_canvas_holder_box, stretch=1)

        # Realtime Graph Update Timer
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)

        # Controls Grid (3 Columns)
        self.controls_grid = QGridLayout()
        self._setup_combination_controls()
        self._setup_spatial_controls()
        self._setup_color_controls()
        layout.addLayout(self.controls_grid)

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

        self.realtime_checkbox = QCheckBox("Auto-update")
        self.realtime_checkbox.setChecked(True)

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

    def connect_updates(self):
        self.graph_type_selector.currentTextChanged.connect(self.update_ui_visibility)
        self.graph_type_selector.currentTextChanged.connect(self.schedule_graph_update)
        self.update_timer.timeout.connect(self.generate_graph)

        # Spatial Controls
        self.spatial_threshold_slider.valueChanged.connect(self.update_threshold_labels)
        self.spatial_threshold_slider.valueChanged.connect(self.cache_spatial_slider_value)
        self.spatial_threshold_slider.valueChanged.connect(self.schedule_graph_update)
        self.spatial_method_selector.currentTextChanged.connect(self.update_sliders)
        self.spatial_method_selector.currentTextChanged.connect(self.schedule_graph_update)

        # Color Controls
        self.color_threshold_slider.valueChanged.connect(self.update_threshold_labels)
        self.color_threshold_slider.valueChanged.connect(self.cache_color_slider_value)
        self.color_threshold_slider.valueChanged.connect(self.schedule_graph_update)
        self.color_method_selector.currentTextChanged.connect(self.update_color_controls)
        self.color_method_selector.currentTextChanged.connect(self.schedule_graph_update)

        # Combination Controls
        self.combination_method_selector.currentTextChanged.connect(self.update_color_controls)
        self.combination_method_selector.currentTextChanged.connect(self.schedule_graph_update)

    def update_sliders(self):
        graph_type = self.graph_type_selector.currentText()

        # Spatial Controls
        if graph_type in ["Spatial Adjacency Graph", "Hybrid Graph (Spatial + Color)"]:
            method = self.spatial_method_selector.currentText()
            if method == "Percentile-based":
                max_value = 100
            elif method == "Relative to color frequency":
                max_value = 200
            elif method == "Absolute":
                self.calculate_adjacency_pairs()
                max_value = max(self._cached_color_counts.values(), default=1)
            self.spatial_threshold_slider.setRange(1, max_value)

            # Restore last value or set default
            last_value = self.spatial_slider_values.get(method, 50)
            self.spatial_threshold_slider.setValue(last_value)

        # Color Controls
        if graph_type in ["Color Similarity Graph", "Hybrid Graph (Spatial + Color)"]:
            method = self.color_method_selector.currentText()
            self.color_threshold_slider.setRange(1, 100)

            last_value = self.color_slider_values.get(method, 30)
            self.color_threshold_slider.setValue(last_value)

        self.update_threshold_labels()

    def cache_spatial_slider_value(self, value):
        method = self.spatial_method_selector.currentText()
        self.spatial_slider_values[method] = value

    def cache_color_slider_value(self, value):
        method = self.color_method_selector.currentText()
        self.color_slider_values[method] = value

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
        if self.realtime_checkbox and self.realtime_checkbox.isChecked():
                self.update_timer.start(100)  # Delay in milliseconds

    def generate_graph(self):
        if self.image_array is None:
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
        
        # Count total edges and mark relevant ones
        total_edges = len(graph.edges)
        
        # Add relevance attribute to edges
        ramps = global_ramp_manager.get_ramps()
        if ramps:
            relevant_edges = 0
            for edge in graph.edges:
                # Check if these color IDs are neighbors in any ramp
                is_relevant = False
                for ramp in ramps:
                    # Check if color IDs are adjacent in the ramp
                    for i in range(len(ramp) - 1):
                        if (ramp[i] == edge[0] and ramp[i + 1] == edge[1]) or \
                           (ramp[i] == edge[1] and ramp[i + 1] == edge[0]):
                            is_relevant = True
                            break
                    if is_relevant:
                        break

                # Store the relevance as an edge attribute
                graph.edges[edge]['relevant'] = is_relevant
                if is_relevant:
                    relevant_edges += 1
        
            print(f"Total edges: {total_edges}")
            print(f"Relevant edges: {relevant_edges}")
            print(f"Irrelevant edges: {total_edges - relevant_edges}")
        else:
            # If no ramps, mark all edges as relevant
            for edge in graph.edges:
                graph.edges[edge]['relevant'] = True
            print(f"Total edges: {total_edges}")

        self.display_graph(graph)
        self.graph_updated.emit()

    def generate_spatial_graph(self):
        self.calculate_adjacency_pairs()

        method = self.spatial_method_selector.currentText()
        threshold = self.spatial_threshold_slider.value()

        if method == "Percentile-based":
            print(f"Percentile: {threshold}%")
        elif method == "Relative to color frequency":
            print(f"Relative Adjacency: ≥ {threshold / 100:.2f}")
        elif method == "Absolute":
            print(f"Occurrences: ≥ {threshold}")

        filtered_pairs = self.filter_adjacency_pairs(
            self._cached_adjacency_pairs,
            self._cached_color_counts,
            method,
            threshold
        )

        graph = nx.Graph()
        for (id1, id2), count in filtered_pairs.items():
            graph.add_edge(id1, id2)

        return graph

    def generate_color_graph(self):
        self.calculate_similarity_pairs()

        method = self.color_method_selector.currentText()
        threshold = self.color_threshold_slider.value()

        if method == "HSV":
            hue_thresh = self.hue_slider.value()
            sat_thresh = self.sat_slider.value() / 100.0
            val_thresh = self.val_slider.value() / 100.0
            print(f"Hue diff: ≤ {hue_thresh}°")
            print(f"Sat diff: ≤ {sat_thresh:.2f}")
            print(f"Val diff: ≤ {val_thresh:.2f}")

            valid_pairs = [
                (c1_id, c2_id) for c1_id, c2_id in self._cached_similarity_pairs
                if is_similar_hsv(
                    self.color_groups[c1_id].current_color,
                    self.color_groups[c2_id].current_color,
                    hue_thresh, sat_thresh, val_thresh
                )
            ]
        elif method == "CIEDE2000":
            print(f"ΔE Similarity: ≤ {threshold}")
            valid_pairs = [
                (c1_id, c2_id) for c1_id, c2_id in self._cached_similarity_pairs
                if is_similar_ciede2000(
                    self.color_groups[c1_id].current_color,
                    self.color_groups[c2_id].current_color,
                    threshold
                )
            ]
        else:
            raise ValueError(f"Unknown color similarity method: {method}")

        graph = nx.Graph()
        for c1_id, c2_id in valid_pairs:
            graph.add_edge(c1_id, c2_id)

        return graph

    def combine_graphs(self, spatial_graph, color_graph):
        method = self.combination_method_selector.currentText()
        combined_graph = nx.Graph()

        if method == "Union":
            combined_graph.add_edges_from(spatial_graph.edges)
            combined_graph.add_edges_from(color_graph.edges)
        elif method == "Intersection":
            spatial_edges = {frozenset(edge) for edge in spatial_graph.edges}
            color_edges = {frozenset(edge) for edge in color_graph.edges}
            common_edges = spatial_edges.intersection(color_edges)
            for edge in common_edges:
                combined_graph.add_edge(*tuple(edge))
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
            color_ids = list(self.color_groups.keys())
            self._cached_similarity_pairs = [
                (c1, c2) for i, c1 in enumerate(color_ids)
                for c2 in color_ids[i + 1:]
            ]

    @staticmethod
    def filter_adjacency_pairs(pair_counts, color_counts, method, threshold):
        if not pair_counts:
            return {}

        if method == "Absolute":
            return {pair: count for pair, count in pair_counts.items()
                    if count >= threshold}

        elif method == "Relative to color frequency":
            relative_counts = GraphViewer.calculate_relative_adjacency(pair_counts, color_counts)
            return {
                pair: count for pair, count in pair_counts.items()
                if relative_counts[pair] >= threshold / 100.0
            }

        elif method == "Percentile-based":
            relative_counts = GraphViewer.calculate_relative_adjacency(pair_counts, color_counts)
            t_val = np.percentile(list(relative_counts.values()), threshold)
            return {pair: count for pair, count in pair_counts.items()
                    if relative_counts[pair] >= t_val}


        raise ValueError(f"Unknown spatial filtering method: {method}")

    @staticmethod
    def calculate_relative_adjacency(pair_counts, color_counts):
        adjacency = {
            pair: max(
                count / max(1, color_counts[pair[0]]),
                count / max(1, color_counts[pair[1]])
            )
            for pair, count in pair_counts.items()
        }
        ## print("Adjacency values:", adjacency)
        return adjacency

    def display_graph(self, graph):
        fig, ax = plt.subplots(figsize=(6, 6))
        pos = nx.kamada_kawai_layout(graph)
        pos = self.perturb_positions(pos)

        # Create a node colors list from color groups
        node_colors = []
        for node in graph.nodes:
            color = global_color_manager.color_groups[node].current_color
            r, g, b, a = color
            node_colors.append(f"#{r:02X}{g:02X}{b:02X}")

        # Draw all nodes at once with their respective colors
        nx.draw_networkx_nodes(
            graph, pos,
            node_size=500,
            node_color=node_colors,
            ax=ax
        )

        # Separate relevant and irrelevant edges
        relevant_edges = [(u, v) for (u, v) in graph.edges if graph.edges[(u, v)]['relevant']]
        irrelevant_edges = [(u, v) for (u, v) in graph.edges if not graph.edges[(u, v)]['relevant']]

        # Draw relevant edges in green
        if relevant_edges:
            nx.draw_networkx_edges(
                graph, pos,
                edgelist=relevant_edges,
                edge_color='green',
                width=1.5,
                alpha=0.6,
                ax=ax
            )

        # Draw irrelevant edges in red
        if irrelevant_edges:
            nx.draw_networkx_edges(
                graph, pos,
                edgelist=irrelevant_edges,
                edge_color='red',
                width=1.5,
                alpha=0.6,
                ax=ax
            )

        ax.set_axis_off()
        plt.close(fig)

        canvas = FigureCanvas(fig)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        # Add double-click event handler
        canvas.mouseDoubleClickEvent = lambda event: self.open_graph_in_new_window()

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

    def open_graph_in_new_window(self):
        if not self.color_graph:
            return

        # Create a new window and store the reference
        self.graph_window = QWidget()
        self.graph_window.setWindowTitle("Graph Visualization")
        self.graph_window.resize(800, 800)
        layout = QVBoxLayout(self.graph_window)

        # Create a larger figure for the new window
        fig, ax = plt.subplots(figsize=(12, 12))
        pos = nx.spring_layout(self.color_graph, k=0.5)
        pos = self.perturb_positions(pos)

        # Create node colors list
        node_colors = []
        for node in self.color_graph.nodes:
            color = global_color_manager.color_groups[node].current_color
            r, g, b, a = color
            node_colors.append(f"#{r:02X}{g:02X}{b:02X}")

        # Draw nodes
        nx.draw_networkx_nodes(
            self.color_graph, pos,
            node_size=1000,  # Larger nodes for better visibility
            node_color=node_colors,
            ax=ax
        )

        # Separate relevant and irrelevant edges
        relevant_edges = [(u, v) for (u, v) in self.color_graph.edges 
                     if self.color_graph.edges[(u, v)]['relevant']]
        irrelevant_edges = [(u, v) for (u, v) in self.color_graph.edges 
                       if not self.color_graph.edges[(u, v)]['relevant']]

        # Draw relevant edges in green
        if relevant_edges:
            nx.draw_networkx_edges(
                self.color_graph, pos,
                edgelist=relevant_edges,
                edge_color='green',
                width=2.0,
                alpha=0.6,
                ax=ax
            )

        # Draw irrelevant edges in red
        if irrelevant_edges:
            nx.draw_networkx_edges(
                self.color_graph, pos,
                edgelist=irrelevant_edges,
                edge_color='red',
                width=2.0,
                alpha=0.6,
                ax=ax
            )

        ax.set_axis_off()
        plt.close(fig)

        # Create and add canvas to the window
        canvas = FigureCanvas(fig)
        layout.addWidget(canvas)

        # Show the window
        self.graph_window.show()
        
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
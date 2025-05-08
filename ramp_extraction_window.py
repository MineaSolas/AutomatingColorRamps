import networkx as nx
from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel, QSizePolicy, QFrame, QVBoxLayout, QPushButton
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

        # Top-Right: Graph view
        self.graph_container = QFrame()
        self.graph_container.setLayout(QVBoxLayout())
        layout.addWidget(self.graph_container, 0, 1)

        self.graph_button = QPushButton("Extract Adjacency Graph")
        self.graph_button.clicked.connect(self.generate_graph)
        self.graph_container.layout().addWidget(self.graph_button)

        self.graph_canvas = None  # placeholder for matplotlib canvas

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

        pair_counts = extract_adjacent_color_pairs(image_array)

        if not pair_counts:
            return

        # Build graph
        graph = nx.Graph()
        for (color1, color2), count in pair_counts.items():
            graph.add_node(color1)
            graph.add_node(color2)
            graph.add_edge(color1, color2, weight=count)

        # Remove old canvas if present
        if self.graph_canvas:
            self.graph_container.layout().removeWidget(self.graph_canvas)
            self.graph_canvas.setParent(None)
            self.graph_canvas = None

        # Create a matplotlib figure
        fig, ax = plt.subplots(figsize=(6, 6))
        pos = nx.spring_layout(graph, seed=42)

        for node in graph.nodes:
            r, g, b, a = node
            nx.draw_networkx_nodes(graph, pos,
                                   nodelist=[node],
                                   node_size=200,
                                   node_color=f"#{r:02X}{g:02X}{b:02X}",
                                   ax=ax)

        nx.draw_networkx_edges(graph, pos, ax=ax, alpha=0.5)
        ax.set_axis_off()

        self.graph_canvas = FigureCanvas(fig)
        self.graph_container.layout().addWidget(self.graph_canvas)


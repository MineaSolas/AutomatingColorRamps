from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QPushButton, QHBoxLayout, QComboBox, QSlider, QScrollArea
from PyQt6.QtCore import Qt
from graph_viewer import GraphViewer
from image_viewer import ImageViewer
from ramp_analysis import find_color_ramps


class RampWindow(QWidget):
    def __init__(self, loaded_pixmap):
        super().__init__()
        self.setWindowTitle("Color Ramp Extraction")
        self.resize(1600, 900)

        layout = QGridLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)

        # Top-Left: Image viewer
        self.mini_viewer = ImageViewer(show_load_button=False, palette_square_size=25)
        self.mini_viewer.load_image(pixmap=loaded_pixmap)
        layout.addWidget(self.mini_viewer, 0, 0)

        # Top-Right: Graph Viewer
        self.graph_viewer = GraphViewer(
            image_array=self.mini_viewer.get_image_array(),
            unique_colors=self.mini_viewer.color_palette.labels.keys()
        )
        layout.addWidget(self.graph_viewer, 0, 1)

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
        self.ramp_layout.setContentsMargins(20, 0, 0, 0)
        self.ramp_layout.setSpacing(0)
        self.ramp_scroll_area.setWidget(self.ramp_container)
        bottom_right_split.addWidget(self.ramp_scroll_area, 2)

        # Right: Controls
        self.controls_panel = QWidget()
        controls_layout = QVBoxLayout(self.controls_panel)

        self.extraction_method_selector = QComboBox()
        self.extraction_method_selector.addItems(["Basic HSV", "Vector HSV", "CIEDE2000"])
        self.extraction_method_selector.currentTextChanged.connect(self.update_extraction_controls)
        controls_layout.addWidget(QLabel("Ramp Extraction Method"))
        controls_layout.addWidget(self.extraction_method_selector)

        # Panels for controls
        self.basic_controls = QWidget()
        basic_layout = QVBoxLayout(self.basic_controls)

        self.h_slider = self.create_labeled_slider("Hue Step Max (˚)", 0, 180, 60, basic_layout)
        self.h_tolerance_slider = self.create_labeled_slider("Hue Step Variance Max (˚)", 0, 100, 30, basic_layout)
        self.s_slider = self.create_labeled_slider("Saturation Step Max", 0, 100, 50, basic_layout)
        self.s_tolerance_slider = self.create_labeled_slider("Saturation Step Variance Max", 0, 100, 20, basic_layout)
        self.v_slider = self.create_labeled_slider("Brightness Step Max", 0, 100, 50, basic_layout)
        self.v_tolerance_slider = self.create_labeled_slider("Brightness Step Variance Max", 0, 100, 20, basic_layout)

        controls_layout.addWidget(self.basic_controls)

        # Vector HSV Controls
        self.vector_controls = QWidget()
        vector_layout = QVBoxLayout(self.vector_controls)

        self.vector_angle_tolerance_slider = self.create_labeled_slider("Angle Step Max (°)", 0, 180, 45, vector_layout)
        self.vector_step_size_slider = self.create_labeled_slider("Step Magnitude Max", 0, 100, 45, vector_layout)

        self.vector_controls.hide()
        controls_layout.addWidget(self.vector_controls)

        # CIEDE2000 Controls
        self.ciede_controls = QWidget()
        ciede_layout = QVBoxLayout(self.ciede_controls)

        self.ciede_max_delta_e_slider = self.create_labeled_slider("ΔE2000 Step Max", 0, 50, 40, ciede_layout)
        self.ciede_variance_tolerance_slider = self.create_labeled_slider("ΔE2000 Variance Tolerance", 0, 30, 15, ciede_layout)

        self.ciede_controls.hide()
        controls_layout.addWidget(self.ciede_controls)

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

    @staticmethod
    def create_labeled_slider(label_text, min_val, max_val, default, layout):
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
        self.basic_controls.setVisible(method == "Basic HSV")
        self.vector_controls.setVisible(method == "Vector HSV")
        self.ciede_controls.setVisible(method == "CIEDE2000")

    def extract_color_ramps(self):
        if self.graph_viewer.color_graph is None:
            return

        method = self.extraction_method_selector.currentText()

        if method == "Basic HSV":
            params = {
                'max_step': [
                    self.h_slider.value() / 180.0,
                    self.s_slider.value() / 100.0,
                    self.v_slider.value() / 100.0,
                ],
                'tolerance': [
                    self.h_tolerance_slider.value() / 180.0,
                    self.s_tolerance_slider.value() / 100.0,
                    self.v_tolerance_slider.value() / 100.0,
                ]
            }

        elif method == "Vector HSV":
            params = {
                'angle_tolerance_deg': self.vector_angle_tolerance_slider.value(),
                'max_step_size': self.vector_step_size_slider.value() / 100.0
            }

        elif method == "CIEDE2000":
            params = {
                'max_delta_e': self.ciede_max_delta_e_slider.value(),
                'variance_tolerance': self.ciede_variance_tolerance_slider.value()
            }

        else:
            return

        ramps = find_color_ramps(self.graph_viewer.color_graph, method, params)
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



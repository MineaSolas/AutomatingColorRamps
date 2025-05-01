import sys
from PyQt6.QtWidgets import QApplication
from image_viewer import ImageViewer

def main():
    app = QApplication(sys.argv)
    window = ImageViewer()
    window.setWindowTitle("Pixel Art Color Processor")
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

import sys
import traceback

from PyQt6.QtWidgets import QApplication
from main_window import MainWindow

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    print("Unhandled exception:", exc_value)
    traceback.print_exception(exc_type, exc_value, exc_traceback)

sys.excepthook = handle_exception

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

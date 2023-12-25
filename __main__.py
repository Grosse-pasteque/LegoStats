import sys
from PyQt5.QtWidgets import QApplication
from window import Window

def main():
    app = QApplication(sys.argv)
    ui = Window()
    ui.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

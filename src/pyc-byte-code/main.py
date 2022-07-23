from user_interface import UserInterface
from sys import argv, exit
from PyQt5.QtWidgets import QApplication

if __name__ == '__main__':
    app = QApplication(argv)
    main = UserInterface()
    exit(app.exec_())

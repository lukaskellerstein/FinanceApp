import logging
import logging.config
import sys
import os

from PyQt6.QtWidgets import QApplication

from finance_app.ui.windows.main.main_window import MainWindow

# Change to the finance_app directory so relative UI paths work
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# set logging from config file
logging.config.fileConfig("../logging.conf")

# create logger
log = logging.getLogger("CellarLogger")


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setStartDragDistance(1)  # pixels
        app.setStartDragTime(1)  # ms

        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        log.fatal(e)
    except:
        log.fatal("Something else went wrong")

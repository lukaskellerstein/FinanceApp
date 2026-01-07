import logging
import logging.config
import signal
import sys
import os

from PyQt6.QtCore import QTimer
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

        # Allow Ctrl+C to properly terminate the application
        signal.signal(signal.SIGINT, lambda *args: app.quit())
        # Timer lets Python process signals while Qt event loop runs
        timer = QTimer()
        timer.timeout.connect(lambda: None)
        timer.start(100)

        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        log.fatal(e)
    except:
        log.fatal("Something else went wrong")

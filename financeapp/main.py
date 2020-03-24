import asyncio

import gbulb
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


from ui.pages.overview.main import OverviewPage
from ui.pages.account.main import AccountPage
from ui.pages.portfolio.main import PortfolioPage


gbulb.install(gtk=True)
# loop = gbulb.get_event_loop()
loop = asyncio.get_event_loop()


class MyWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        Gtk.ApplicationWindow.__init__(self, application=app)

        self.builder = Gtk.Builder()
        self.builder.add_from_file("main.glade")

        # set tabs
        main_tabs = self.builder.get_object("MainTabs")

        self.overview_tab = OverviewPage()
        main_tabs.append_page(self.overview_tab.template, Gtk.Label("Overview"))

        self.account_tab = AccountPage()
        main_tabs.append_page(self.account_tab.template, Gtk.Label("Account"))

        self.portfolio_tab = PortfolioPage()
        main_tabs.append_page(self.portfolio_tab.template, Gtk.Label("Portfolio"))

        # render window
        window = self.builder.get_object("MainWindow")
        window.connect("delete-event", self.onDestroy)
        window.show_all()

    def onDestroy(self, *args):
        print("onDestroy")
        loop.stop()
        loop.close()
        Gtk.main_quit()


class MyApplication(Gtk.Application):
    def __init__(self):
        Gtk.Application.__init__(self)

    def do_activate(self):
        self.main_window = MyWindow(self)
        print("Running Loop")
        loop.run_forever()


# ------------------------------------------------------
# RUN
# ------------------------------------------------------
# loop.run_forever(application=MyApplication)

try:
    app = MyApplication()
    app.run()
except KeyboardInterrupt:
    pass
finally:
    print("Closing Loop")
    loop.close()

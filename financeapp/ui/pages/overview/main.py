import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ui.core.pages.base_page import BasePage
from ui.pages.overview.stocks.main import StocksPage
from ui.pages.overview.futures.main import FuturesPage
from ui.pages.overview.fixed_income.main import FixedIncomePage
from ui.pages.overview.interest_rate.main import InterestRatePage


class OverviewPage(BasePage):
    def __init__(self):
        BasePage.__init__(self, "ui/pages/overview/main.glade", "OverviewBox")

        # set tabs
        main_tabs = self.builder.get_object("MainTabs")

        self.interest_rate_tab = InterestRatePage()
        main_tabs.append_page(
            self.interest_rate_tab.template, Gtk.Label("Interest Rate")
        )

        self.fixed_income_tab = FixedIncomePage()
        main_tabs.append_page(self.fixed_income_tab.template, Gtk.Label("Fixed Income"))

        self.stocks_tab = StocksPage()
        main_tabs.append_page(self.stocks_tab.template, Gtk.Label("Stocks"))

        self.futures_tab = FuturesPage()
        main_tabs.append_page(self.futures_tab.template, Gtk.Label("Futures"))

        self.template.show_all()

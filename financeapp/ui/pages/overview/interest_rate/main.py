from ui.core.pages.base_page import BasePage


class InterestRatePage(BasePage):
    def __init__(self):
        BasePage.__init__(
            self, "ui/pages/overview/interest_rate/main.glade", "InterestRateMainWindow"
        )

        self.template.show_all()

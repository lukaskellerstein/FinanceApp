from ui.core.pages.base_page import BasePage


class FixedIncomePage(BasePage):
    def __init__(self):
        BasePage.__init__(
            self, "ui/pages/overview/fixed_income/main.glade", "FixedIncomeMainWindow"
        )

        self.template.show_all()

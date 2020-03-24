from ui.core.pages.base_page import BasePage


class PortfolioPage(BasePage):
    def __init__(self):
        BasePage.__init__(self, "ui/pages/portfolio/main.glade", "PortfolioWindow")

        self.template.show_all()

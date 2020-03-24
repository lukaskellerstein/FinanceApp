from ui.core.pages.base_page import BasePage


class AccountPage(BasePage):
    def __init__(self):
        BasePage.__init__(self, "ui/pages/account/main.glade", "AccountWindow")

        self.template.show_all()

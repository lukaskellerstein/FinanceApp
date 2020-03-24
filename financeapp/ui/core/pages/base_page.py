import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class BasePage:
    def __init__(self, template, window):
        self.builder = Gtk.Builder()
        self.builder.add_from_file(template)
        self.template = self.builder.get_object(window)
        # unregister from glade gtk parent object/window/box ... etc.
        parent = self.template.get_parent()
        parent.remove(self.template)

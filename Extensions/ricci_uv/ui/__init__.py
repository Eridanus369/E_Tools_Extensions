from . import header_panel
from . import pie_menu


def register():
    header_panel.register()
    pie_menu.register()


def unregister():
    pie_menu.unregister()
    header_panel.unregister()
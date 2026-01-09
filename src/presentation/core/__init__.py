"""
MVVM (Model-View-ViewModel) base classes for the presentation layer.

Contains:
- BaseViewModel: Base class with observable properties and commands
- BaseView: Base class with automatic .ui/.qss loading
- BaseWindow: Base class for windows
- Command: Wrapper for bindable commands
"""

from src.presentation.core.base_view_model import BaseViewModel, ObservableProperty
from src.presentation.core.base_view import BaseView
from src.presentation.core.base_window import BaseWindow
from src.presentation.core.command import Command, AsyncCommand

__all__ = [
    "BaseViewModel",
    "ObservableProperty",
    "BaseView",
    "BaseWindow",
    "Command",
    "AsyncCommand",
]

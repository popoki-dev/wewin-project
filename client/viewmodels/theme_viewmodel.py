from __future__ import annotations

from PySide6.QtCore import Property, QObject, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication, QPalette

from client.app.storage import Storage

MODES = ("system", "light", "dark")


class ThemeViewModel(QObject):
    """Light/dark/system preference. The palette itself lives in themes/Theme.qml."""

    modeChanged = Signal()
    darkChanged = Signal()

    def __init__(self, storage: Storage, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._storage = storage
        mode = storage.value("ui/theme", "system")
        self._mode = mode if mode in MODES else "system"
        self._dark = self._resolve()
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._update)

    @staticmethod
    def _system_is_dark() -> bool:
        scheme = QGuiApplication.styleHints().colorScheme()
        if scheme != Qt.ColorScheme.Unknown:
            return scheme == Qt.ColorScheme.Dark
        # Some Linux desktops do not report a scheme; infer it from the palette.
        return QGuiApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128

    def _resolve(self) -> bool:
        return self._system_is_dark() if self._mode == "system" else self._mode == "dark"

    def _update(self) -> None:
        dark = self._resolve()
        if dark != self._dark:
            self._dark = dark
            self.darkChanged.emit()

    def _get_mode(self) -> str:
        return self._mode

    def _set_mode(self, value: str) -> None:
        if value not in MODES or value == self._mode:
            return
        self._mode = value
        self._storage.set_value("ui/theme", value)
        self.modeChanged.emit()
        self._update()

    mode = Property(str, _get_mode, _set_mode, notify=modeChanged)

    @Property(bool, notify=darkChanged)
    def dark(self) -> bool:
        return self._dark

    @Slot()
    def cycle(self) -> None:
        self._set_mode(MODES[(MODES.index(self._mode) + 1) % len(MODES)])

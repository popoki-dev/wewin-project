"""Creates the application objects, exposes view models to QML and loads the UI."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonInstance

from client import __version__
from client.api.auth_api import AuthApi
from client.api.client import ApiClient
from client.api.members_api import MembersApi
from client.api.projects_api import ProjectsApi
from client.app.storage import Storage
from client.viewmodels.auth_viewmodel import AuthViewModel
from client.viewmodels.members_viewmodel import MembersViewModel
from client.viewmodels.projects_viewmodel import ProjectsViewModel
from client.viewmodels.theme_viewmodel import ThemeViewModel

QML_DIR = Path(__file__).resolve().parent.parent / "frontend" / "qml"


class Application:
    """Owns every long-lived object so none is garbage-collected while QML uses it."""

    def __init__(self, argv: list[str]) -> None:
        # The Basic style is fully customisable, which the WeWin theme relies on.
        os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
        QCoreApplication.setOrganizationName("WeWin")
        QCoreApplication.setApplicationName("WeWin")
        QCoreApplication.setApplicationVersion(__version__)

        self.qt_app = QGuiApplication(argv)
        self.qt_app.setWindowIcon(QIcon(str(QML_DIR / "assets" / "logo.svg")))

        self.storage = Storage()
        self.api_client = ApiClient()
        self.theme = ThemeViewModel(self.storage)
        self.auth = AuthViewModel(self.storage, AuthApi(self.api_client))
        self.members = MembersViewModel(self.auth, MembersApi(self.api_client))
        self.projects = ProjectsViewModel(self.auth, ProjectsApi(self.api_client))

        qmlRegisterSingletonInstance(ThemeViewModel, "WeWin.ViewModels", 1, 0, "ThemeViewModel", self.theme)
        qmlRegisterSingletonInstance(AuthViewModel, "WeWin.ViewModels", 1, 0, "AuthViewModel", self.auth)
        qmlRegisterSingletonInstance(MembersViewModel, "WeWin.ViewModels", 1, 0, "MembersViewModel", self.members)
        qmlRegisterSingletonInstance(ProjectsViewModel, "WeWin.ViewModels", 1, 0, "ProjectsViewModel", self.projects)

        self.engine = QQmlApplicationEngine()
        self.engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))

    def exec(self) -> int:
        if not self.engine.rootObjects():
            return 1
        self.auth.restoreSession()
        return self.qt_app.exec()


def run() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return Application(sys.argv).exec()

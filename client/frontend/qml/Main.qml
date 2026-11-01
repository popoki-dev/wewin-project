import QtQuick
import QtQuick.Controls
import WeWin.ViewModels
import "themes"
import "pages"

ApplicationWindow {
    id: window

    width: 1120
    height: 720
    minimumWidth: 420
    minimumHeight: 560
    visible: true
    title: AuthViewModel.loggedIn ? qsTr("WeWin — %1").arg(AuthViewModel.userName) : qsTr("WeWin — Sign in")
    color: Theme.background

    font.family: Theme.fontFamily
    palette.window: Theme.background
    palette.windowText: Theme.text
    palette.base: Theme.inputBackground
    palette.text: Theme.text
    palette.button: Theme.surface
    palette.buttonText: Theme.text
    palette.highlight: Theme.accent
    palette.highlightedText: Theme.accentText
    palette.toolTipBase: Theme.surfaceAlt
    palette.toolTipText: Theme.text

    Loader {
        id: pageLoader
        anchors.fill: parent
        // An initial password locks the app until it is changed.
        sourceComponent: !AuthViewModel.loggedIn ? loginComponent
                       : AuthViewModel.mustChangePassword ? changePasswordComponent
                       : dashboardComponent

        onLoaded: fade.restart()
        NumberAnimation { id: fade; target: pageLoader.item; property: "opacity"; from: 0; to: 1; duration: 220 }
    }

    Component { id: loginComponent; LoginPage {} }
    Component { id: changePasswordComponent; ChangePasswordPage {} }
    Component { id: dashboardComponent; DashboardPage {} }
}

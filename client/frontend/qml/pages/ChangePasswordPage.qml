import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"
import "../components"
import "../layouts"

// Shown after signing in with an initial password. Nothing else is reachable
// until the password is changed (the server enforces this too).
AuthLayout {
    id: page

    Component.onCompleted: form.forceFocus()

    ColumnLayout {
        spacing: 6
        Label {
            text: qsTr("Set your password")
            color: Theme.text
            font.pixelSize: 28
            font.weight: Font.Bold
        }
        Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: qsTr("You signed in with an initial password. Choose your own password to continue.")
            color: Theme.textMuted
            font.pixelSize: 14
        }
    }

    ChangePasswordForm {
        id: form
        Layout.fillWidth: true
        Layout.topMargin: 8
        submitText: qsTr("Set password and continue")
    }

    LinkButton {
        Layout.alignment: Qt.AlignHCenter
        text: qsTr("Sign out")
        onClicked: AuthViewModel.logout()
    }
}

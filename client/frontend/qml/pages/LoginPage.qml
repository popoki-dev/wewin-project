import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"
import "../components"
import "../layouts"

AuthLayout {
    id: page

    function submit() {
        AuthViewModel.login(serverField.text, emailField.text, passwordField.text, rememberBox.checked)
    }

    Component.onCompleted: {
        if (serverField.text.length > 0)
            AuthViewModel.checkServer(serverField.text)
        if (serverField.text.length === 0) serverField.forceFocus()
        else if (emailField.text.length === 0) emailField.forceFocus()
        else passwordField.forceFocus()
    }

    Connections {
        target: AuthViewModel
        function onSessionChanged() { if (AuthViewModel.loggedIn) passwordField.text = "" }
    }

    ColumnLayout {
        spacing: 6
        Label {
            text: qsTr("Welcome back")
            color: Theme.text
            font.pixelSize: 28
            font.weight: Font.Bold
        }
        Label {
            text: qsTr("Sign in to your WeWin workspace.")
            color: Theme.textMuted
            font.pixelSize: 14
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        Layout.topMargin: 8
        spacing: 6

        AppTextField {
            id: serverField
            Layout.fillWidth: true
            label: qsTr("Server address")
            iconName: "server"
            placeholderText: "wewin.example.com"
            text: AuthViewModel.savedServerUrl
            invalid: AuthViewModel.serverInsecure
            field.inputMethodHints: Qt.ImhUrlCharactersOnly | Qt.ImhNoAutoUppercase
            field.onEditingFinished: AuthViewModel.checkServer(text)
            field.onTextEdited: serverCheckDelay.restart()
            onAccepted: emailField.forceFocus()

            trailing: [
                Rectangle {
                    id: statusDot
                    width: 8; height: 8; radius: 4
                    anchors.verticalCenter: parent.verticalCenter
                    visible: AuthViewModel.serverStatus !== "unknown"
                    color: AuthViewModel.serverStatus === "online" ? Theme.success
                         : AuthViewModel.serverStatus === "offline" ? Theme.danger : Theme.warning
                    SequentialAnimation on opacity {
                        running: AuthViewModel.serverStatus === "checking"
                        loops: Animation.Infinite
                        onRunningChanged: if (!running) statusDot.opacity = 1
                        NumberAnimation { to: 0.3; duration: 450 }
                        NumberAnimation { to: 1; duration: 450 }
                    }
                    HoverHandler { id: dotHover }
                    ToolTip.visible: dotHover.hovered
                    ToolTip.text: AuthViewModel.serverStatus === "online" ? qsTr("Server reachable")
                                : AuthViewModel.serverStatus === "offline" ? qsTr("Server unreachable")
                                : qsTr("Checking server…")
                }
            ]

            Timer {
                id: serverCheckDelay
                interval: 700
                onTriggered: AuthViewModel.checkServer(serverField.text)
            }
        }

        RowLayout {
            visible: AuthViewModel.serverInsecure
            Layout.fillWidth: true
            spacing: 6
            Icon { name: "alert"; color: Theme.danger; width: 14; height: 14 }
            Label {
                Layout.fillWidth: true
                text: qsTr("This connection is not encrypted. Use https:// for remote servers.")
                color: Theme.danger
                font.pixelSize: 12
                wrapMode: Text.Wrap
            }
        }
    }

    AppTextField {
        id: emailField
        Layout.fillWidth: true
        label: qsTr("Email")
        iconName: "mail"
        placeholderText: "you@company.com"
        text: AuthViewModel.savedEmail
        field.inputMethodHints: Qt.ImhEmailCharactersOnly | Qt.ImhNoAutoUppercase
        onAccepted: passwordField.forceFocus()
    }

    AppTextField {
        id: passwordField
        Layout.fillWidth: true
        label: qsTr("Password")
        iconName: "lock"
        password: true
        placeholderText: qsTr("Enter your password")
        onAccepted: page.submit()
    }

    RowLayout {
        Layout.fillWidth: true
        AppCheckBox {
            id: rememberBox
            text: qsTr("Remember me")
            checked: AuthViewModel.savedRememberMe
        }
        Item { Layout.fillWidth: true }
        LinkButton {
            text: qsTr("Forgot password?")
            onClicked: forgotDialog.openFor(serverField.text, emailField.text)
        }
    }

    Banner {
        Layout.fillWidth: true
        kind: "error"
        text: AuthViewModel.errorMessage
    }

    AppButton {
        Layout.fillWidth: true
        Layout.topMargin: 4
        text: AuthViewModel.busy ? qsTr("Signing in…") : qsTr("Sign in")
        busy: AuthViewModel.busy
        enabled: !AuthViewModel.busy
        onClicked: page.submit()
    }

    Label {
        Layout.fillWidth: true
        Layout.topMargin: 6
        horizontalAlignment: Text.AlignHCenter
        text: qsTr("Need an account? Ask your organization's owner or admin to invite you.")
        color: Theme.textFaint
        font.pixelSize: 12
        wrapMode: Text.Wrap
    }

    ForgotPasswordDialog {
        id: forgotDialog
        onPasswordReset: function(email) {
            emailField.text = email
            passwordField.text = ""
            passwordField.forceFocus()
        }
    }
}

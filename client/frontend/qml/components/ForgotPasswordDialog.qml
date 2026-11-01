import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"

// Three steps: request a code -> enter code + new password -> done.
Popup {
    id: dialog
    objectName: "forgotPasswordDialog"

    property string server
    property int step: 0
    property string infoMessage

    signal passwordReset(string email)

    function openFor(serverText, emailText) {
        server = serverText
        resetEmail.text = emailText
        codeField.text = ""
        newPassword.text = ""
        confirmPassword.text = ""
        infoMessage = ""
        step = 0
        AuthViewModel.clearResetState()
        open()
    }

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(440, (parent ? parent.width : 440) - 32)
    modal: true
    focus: true
    padding: 28
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    onOpened: resetEmail.forceFocus()

    Overlay.modal: Rectangle {
        color: Qt.rgba(0, 0, 0, Theme.dark ? 0.6 : 0.35)
        Behavior on opacity { NumberAnimation { duration: 150 } }
    }

    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 160 }
            NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: 160; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition { NumberAnimation { property: "opacity"; to: 0; duration: 120 } }

    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.surface
        border.width: 1
        border.color: Theme.border
    }

    Connections {
        target: AuthViewModel
        function onResetCodeSent(message) {
            dialog.infoMessage = message
            if (dialog.step === 0) {
                dialog.step = 1
                codeField.forceFocus()
            }
        }
        function onPasswordResetDone(message) {
            dialog.infoMessage = message
            dialog.step = 2
        }
    }

    contentItem: ColumnLayout {
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Rectangle {
                width: 40; height: 40; radius: 12
                color: dialog.step === 2 ? Theme.successSoft : Theme.accentSoft
                Icon {
                    anchors.centerIn: parent
                    width: 20; height: 20
                    name: dialog.step === 2 ? "check" : "key"
                    color: dialog.step === 2 ? Theme.success : Theme.accent
                }
            }
            ColumnLayout {
                spacing: 2
                Layout.fillWidth: true
                Label {
                    text: dialog.step === 2 ? qsTr("Password updated") : qsTr("Reset your password")
                    color: Theme.text
                    font.pixelSize: 18
                    font.weight: Font.Bold
                }
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    color: Theme.textMuted
                    font.pixelSize: 13
                    text: dialog.step === 0 ? qsTr("We'll email you a 6-digit code.")
                        : dialog.step === 1 ? qsTr("Enter the code sent to %1.").arg(resetEmail.text.trim())
                        : qsTr("You can now sign in with your new password.")
                }
            }
            ToolButton {
                id: closeButton
                Layout.alignment: Qt.AlignTop
                width: 32; height: 32
                hoverEnabled: true
                onClicked: dialog.close()
                Accessible.name: qsTr("Close")
                background: Rectangle { radius: Theme.radiusSmall; color: closeButton.hovered ? Theme.surfaceHover : "transparent" }
                contentItem: Item { Icon { anchors.centerIn: parent; name: "close"; color: Theme.textMuted } }
            }
        }

        StackLayout {
            id: steps
            Layout.fillWidth: true
            // Size to the visible step, not the tallest one.
            Layout.preferredHeight: steps.children[steps.currentIndex] ? steps.children[steps.currentIndex].implicitHeight : 0
            currentIndex: dialog.step

            // Step 0: request a code
            ColumnLayout {
                spacing: 16
                AppTextField {
                    id: resetEmail
                    Layout.fillWidth: true
                    label: qsTr("Email")
                    iconName: "mail"
                    placeholderText: "you@company.com"
                    onAccepted: AuthViewModel.requestResetCode(dialog.server, text)
                }
                Label {
                    Layout.fillWidth: true
                    text: qsTr("Server: %1").arg(dialog.server || qsTr("not set"))
                    color: Theme.textFaint
                    font.pixelSize: 12
                    elide: Text.ElideMiddle
                }
            }

            // Step 1: code + new password
            ColumnLayout {
                spacing: 16
                AppTextField {
                    id: codeField
                    Layout.fillWidth: true
                    label: qsTr("Verification code")
                    placeholderText: "123456"
                    field.maximumLength: 6
                    field.validator: RegularExpressionValidator { regularExpression: /\d{0,6}/ }
                    field.inputMethodHints: Qt.ImhDigitsOnly
                    field.font.letterSpacing: 4
                    onAccepted: newPassword.forceFocus()
                    labelAccessory: [
                        LinkButton {
                            text: qsTr("Resend code")
                            font.pixelSize: 12
                            enabled: !AuthViewModel.resetBusy
                            onClicked: AuthViewModel.requestResetCode(dialog.server, resetEmail.text)
                        }
                    ]
                }
                AppTextField {
                    id: newPassword
                    Layout.fillWidth: true
                    label: qsTr("New password")
                    iconName: "lock"
                    password: true
                    placeholderText: qsTr("At least 8 characters")
                    onAccepted: confirmPassword.forceFocus()
                }
                AppTextField {
                    id: confirmPassword
                    Layout.fillWidth: true
                    label: qsTr("Confirm new password")
                    iconName: "lock"
                    password: true
                    invalid: text.length > 0 && text !== newPassword.text
                    onAccepted: submitButton.clicked()
                }
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    color: Theme.textFaint
                    font.pixelSize: 12
                    text: qsTr("Use 8+ characters with at least three of: lowercase, uppercase, numbers, symbols.")
                }
            }

            // Step 2: done
            Item { implicitHeight: 4 }
        }

        Banner {
            Layout.fillWidth: true
            kind: "error"
            text: AuthViewModel.resetError
        }
        Banner {
            Layout.fillWidth: true
            kind: "success"
            text: dialog.step === 1 && !AuthViewModel.resetError ? dialog.infoMessage : ""
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            AppButton {
                visible: dialog.step === 1
                variant: "secondary"
                text: qsTr("Back")
                iconName: "back"
                implicitWidth: 100
                onClicked: { AuthViewModel.clearResetState(); dialog.step = 0 }
            }
            AppButton {
                id: submitButton
                Layout.fillWidth: true
                busy: AuthViewModel.resetBusy
                enabled: !AuthViewModel.resetBusy
                text: dialog.step === 0 ? qsTr("Send reset code")
                    : dialog.step === 1 ? qsTr("Reset password")
                    : qsTr("Back to sign in")
                onClicked: {
                    if (dialog.step === 0) {
                        AuthViewModel.requestResetCode(dialog.server, resetEmail.text)
                    } else if (dialog.step === 1) {
                        AuthViewModel.resetPassword(dialog.server, resetEmail.text, codeField.text,
                                           newPassword.text, confirmPassword.text)
                    } else {
                        dialog.passwordReset(resetEmail.text.trim())
                        dialog.close()
                    }
                }
            }
        }
    }
}

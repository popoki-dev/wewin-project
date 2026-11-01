import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"

// Current + new + confirm password, wired to AuthViewModel.changePassword.
ColumnLayout {
    id: root

    property string submitText: qsTr("Change password")

    function reset() {
        currentField.text = ""
        newField.text = ""
        confirmField.text = ""
        AuthViewModel.clearError()
    }
    function forceFocus() { currentField.forceFocus() }
    function submit() { AuthViewModel.changePassword(currentField.text, newField.text, confirmField.text) }

    spacing: 16

    AppTextField {
        id: currentField
        Layout.fillWidth: true
        label: qsTr("Current password")
        iconName: "lock"
        password: true
        invalid: AuthViewModel.errorFields.indexOf("current") >= 0
        field.onTextEdited: AuthViewModel.fieldEdited("current")
        onAccepted: newField.forceFocus()
    }
    AppTextField {
        id: newField
        Layout.fillWidth: true
        label: qsTr("New password")
        iconName: "key"
        password: true
        placeholderText: qsTr("At least 8 characters")
        invalid: AuthViewModel.errorFields.indexOf("newPassword") >= 0
        field.onTextEdited: AuthViewModel.fieldEdited("newPassword")
        onAccepted: confirmField.forceFocus()
    }
    AppTextField {
        id: confirmField
        Layout.fillWidth: true
        label: qsTr("Confirm new password")
        iconName: "key"
        password: true
        invalid: (text.length > 0 && text !== newField.text) || AuthViewModel.errorFields.indexOf("confirm") >= 0
        field.onTextEdited: AuthViewModel.fieldEdited("confirm")
        onAccepted: root.submit()
    }
    Label {
        Layout.fillWidth: true
        wrapMode: Text.Wrap
        color: Theme.textFaint
        font.pixelSize: 12
        text: qsTr("Use 8+ characters with at least three of: lowercase, uppercase, numbers, symbols.")
    }

    Banner {
        Layout.fillWidth: true
        kind: "error"
        text: AuthViewModel.errorMessage
    }

    AppButton {
        Layout.fillWidth: true
        text: AuthViewModel.busy ? qsTr("Saving…") : root.submitText
        busy: AuthViewModel.busy
        enabled: !AuthViewModel.busy
        onClicked: root.submit()
    }
}

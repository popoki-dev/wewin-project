import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"

// Edit a member's details, or delete the account. What is offered follows the
// current user's permissions; the server enforces the same rules.
AppDialog {
    id: dialog

    property var member: ({})
    property bool confirmingDelete: false
    readonly property bool isSelf: member.email === AuthViewModel.userEmail
    readonly property bool isOwnerAccount: member.role === "owner"

    function openFor(m) {
        member = m
        confirmingDelete = false
        nameField.text = m.full_name || ""
        emailField.text = m.email
        activeBox.checked = m.is_active
        passwordField.text = ""
        teamBox.model = MembersViewModel.teams.map(t => ({ value: t.id, text: t.name }))
        teamBox.selectValue(m.team_id)
        MembersViewModel.clearMessages()
        open()
    }

    title: confirmingDelete ? qsTr("Delete %1?").arg(member.full_name || member.email || "")
                            : qsTr("Edit %1").arg(member.full_name || member.email || "")
    subtitle: confirmingDelete
              ? qsTr("The account, its device registration and its sessions are removed for good. The audit log keeps a record.")
              : isSelf ? qsTr("Changing your email signs you out; sign in again with the new address.")
                       : qsTr("Changing the email, setting a new password or disabling the account signs them out.")
    iconName: confirmingDelete ? "alert" : "users"

    onOpened: nameField.forceFocus()

    Connections {
        target: MembersViewModel
        function onMemberSaved() { if (dialog.opened) dialog.close() }
        function onMemberDeleted() { if (dialog.opened) dialog.close() }
    }

    // ------------------------------------------------------------------ edit
    ColumnLayout {
        visible: !dialog.confirmingDelete
        Layout.fillWidth: true
        spacing: 16

        AppTextField {
            id: nameField
            Layout.fillWidth: true
            label: qsTr("Full name")
            iconName: "users"
            field.maximumLength: 200
            onAccepted: emailField.forceFocus()
        }
        AppTextField {
            id: emailField
            Layout.fillWidth: true
            label: qsTr("Email")
            iconName: "mail"
            invalid: MembersViewModel.errorFields.indexOf("email") >= 0
            field.onTextEdited: MembersViewModel.fieldEdited("email")
        }
        AppComboBox {
            id: teamBox
            // Only the Owner moves people between teams; the Owner has no team.
            visible: AuthViewModel.isOwner && !dialog.isOwnerAccount
            Layout.fillWidth: true
            label: qsTr("Team")
            invalid: MembersViewModel.errorFields.indexOf("team") >= 0
        }
        AppTextField {
            id: passwordField
            visible: !dialog.isSelf
            Layout.fillWidth: true
            label: qsTr("New initial password (optional)")
            iconName: "lock"
            password: true
            placeholderText: qsTr("Leave empty to keep the current password")
            invalid: MembersViewModel.errorFields.indexOf("password") >= 0
            field.onTextEdited: MembersViewModel.fieldEdited("password")
        }
        AppCheckBox {
            id: activeBox
            visible: !dialog.isSelf
            text: qsTr("Account active (can sign in)")
        }

        Banner { Layout.fillWidth: true; kind: "error"; text: dialog.opened ? MembersViewModel.errorMessage : "" }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            AppButton {
                visible: MembersViewModel.canDeleteMember(dialog.member) && !dialog.isSelf
                variant: "secondary"
                text: qsTr("Delete…")
                implicitWidth: 110
                onClicked: { MembersViewModel.clearMessages(); dialog.confirmingDelete = true }
            }
            AppButton {
                Layout.fillWidth: true
                text: qsTr("Save changes")
                busy: MembersViewModel.busy
                enabled: !MembersViewModel.busy
                onClicked: MembersViewModel.saveMember(
                    dialog.member, nameField.text, emailField.text,
                    teamBox.visible && teamBox.currentValue !== undefined ? teamBox.currentValue : 0,
                    dialog.isSelf ? true : activeBox.checked, passwordField.text)
            }
        }
    }

    // --------------------------------------------------------- confirm delete
    ColumnLayout {
        visible: dialog.confirmingDelete
        Layout.fillWidth: true
        spacing: 16

        Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            color: Theme.text
            font.pixelSize: 13
            text: qsTr("To keep the account but stop sign-ins, cancel and untick “Account active” instead.")
        }
        Banner { Layout.fillWidth: true; kind: "error"; text: dialog.opened ? MembersViewModel.errorMessage : "" }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            AppButton {
                variant: "secondary"
                text: qsTr("Cancel")
                Layout.fillWidth: true
                onClicked: dialog.confirmingDelete = false
            }
            Button {
                id: deleteButton
                Layout.fillWidth: true
                implicitHeight: Theme.controlHeight
                enabled: !MembersViewModel.busy
                hoverEnabled: true
                text: qsTr("Delete account")
                font.pixelSize: 14
                font.weight: Font.DemiBold
                onClicked: MembersViewModel.deleteMember(dialog.member)
                background: Rectangle {
                    radius: Theme.radius
                    color: deleteButton.hovered ? Qt.darker(Theme.danger, 1.1) : Theme.danger
                    opacity: deleteButton.enabled ? 1 : 0.55
                }
                contentItem: Label {
                    text: deleteButton.text
                    font: deleteButton.font
                    color: "#ffffff"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }
}

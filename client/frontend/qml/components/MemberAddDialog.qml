import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"

// Add a member: email, name, team, base role (Owner only), initial password and
// optional role bundles. Closes once the member is added; the page shows the notice.
AppDialog {
    id: dialog

    // Role bundles to give the new member.
    property var bundles: []

    function openNew() {
        emailField.text = ""
        nameField.text = ""
        passwordField.text = ""
        bundles = []
        roleBox.currentIndex = 0
        teamBox.model = MembersViewModel.teams.map(t => ({ value: t.id, text: t.name }))
        // A Team Leader can only add to their own team; with one team, there is nothing to pick.
        teamBox.selectValue(!AuthViewModel.isOwner ? AuthViewModel.userTeamId
                            : MembersViewModel.teams.length === 1 ? MembersViewModel.teams[0].id : -1)
        MembersViewModel.clearMessages()
        open()
    }
    function toggleBundle(id, on) {
        const next = bundles.filter(v => v !== id)
        if (on) next.push(id)
        bundles = next
    }
    function submit() {
        MembersViewModel.addMember(
            emailField.text, nameField.text,
            teamBox.currentValue !== undefined ? teamBox.currentValue : 0,
            AuthViewModel.isOwner ? roleBox.currentValue : "member",
            passwordField.text, bundles)
    }

    title: qsTr("Add member")
    subtitle: AuthViewModel.isOwner ? qsTr("They sign in with the initial password and must change it.")
                                    : qsTr("Members you add join your team and must change the initial password.")
    iconName: "plus"

    onOpened: emailField.forceFocus()
    // Don't leave a form error behind on the page when the dialog is dismissed.
    onClosed: if (MembersViewModel.errorMessage) MembersViewModel.clearMessages()

    Connections {
        target: MembersViewModel
        function onMemberAdded() { if (dialog.opened) dialog.close() }
    }

    Label {
        visible: AuthViewModel.isOwner && MembersViewModel.teams.length === 0
        Layout.fillWidth: true
        wrapMode: Text.Wrap
        text: qsTr("There are no teams yet. Create one on the Teams tab first.")
        color: Theme.warning
        font.pixelSize: 13
    }

    AppTextField {
        id: emailField
        Layout.fillWidth: true
        label: qsTr("Email")
        iconName: "mail"
        placeholderText: "name@company.com"
        invalid: MembersViewModel.errorFields.indexOf("email") >= 0
        field.onTextEdited: MembersViewModel.fieldEdited("email")
        onAccepted: nameField.forceFocus()
    }
    AppTextField {
        id: nameField
        Layout.fillWidth: true
        label: qsTr("Full name (optional)")
        iconName: "users"
        field.maximumLength: 200
        onAccepted: passwordField.forceFocus()
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: 12
        AppComboBox {
            id: teamBox
            Layout.fillWidth: true
            label: qsTr("Team")
            box.enabled: AuthViewModel.isOwner
            invalid: MembersViewModel.errorFields.indexOf("team") >= 0
            onActivated: MembersViewModel.fieldEdited("team")
        }
        AppComboBox {
            id: roleBox
            visible: AuthViewModel.isOwner
            Layout.preferredWidth: 170
            label: qsTr("Role")
            model: [{ value: "member", text: qsTr("Member") },
                    { value: "team_leader", text: qsTr("Team Leader") }]
            currentIndex: 0
        }
    }
    AppTextField {
        id: passwordField
        Layout.fillWidth: true
        label: qsTr("Initial password")
        iconName: "lock"
        password: true
        placeholderText: qsTr("At least 8 characters")
        invalid: MembersViewModel.errorFields.indexOf("password") >= 0
        field.onTextEdited: MembersViewModel.fieldEdited("password")
        onAccepted: dialog.submit()
    }
    ColumnLayout {
        visible: MembersViewModel.assignableBundleIds.length > 0
        Layout.fillWidth: true
        spacing: 6
        Label { text: qsTr("Role bundles (optional)"); color: Theme.text; font.pixelSize: 13; font.weight: Font.Medium }
        Flow {
            Layout.fillWidth: true
            spacing: 6
            Repeater {
                model: MembersViewModel.bundles.filter(b => MembersViewModel.assignableBundleIds.indexOf(b.id) >= 0)
                delegate: ToggleChip {
                    required property var modelData
                    text: modelData.name
                    checked: dialog.bundles.indexOf(modelData.id) >= 0
                    onToggled: dialog.toggleBundle(modelData.id, checked)
                    ToolTip.visible: hovered && modelData.description.length > 0
                    ToolTip.delay: 400
                    ToolTip.text: modelData.description
                }
            }
        }
    }

    Banner { Layout.fillWidth: true; kind: "error"; text: dialog.opened ? MembersViewModel.errorMessage : "" }

    AppButton {
        Layout.fillWidth: true
        iconName: "plus"
        text: qsTr("Add member")
        busy: MembersViewModel.busy
        enabled: !MembersViewModel.busy
        onClicked: dialog.submit()
    }
}

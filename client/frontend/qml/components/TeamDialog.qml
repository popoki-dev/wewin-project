import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"

// Create a team, or rename one (openFor). Closes once the server accepts the name.
AppDialog {
    id: dialog

    property var team: null

    function openNew() {
        team = null
        nameField.text = ""
        MembersViewModel.clearMessages()
        open()
    }
    function openFor(t) {
        team = t
        nameField.text = t.name
        MembersViewModel.clearMessages()
        open()
    }
    function submit() {
        if (team) MembersViewModel.renameTeam(team.id, nameField.text)
        else MembersViewModel.createTeam(nameField.text)
    }

    title: team ? qsTr("Rename team") : qsTr("New team")
    subtitle: team ? qsTr("Members keep their team; only the name changes.")
                   : qsTr("Members are added to a team on the Members page.")
    iconName: "grid"

    onOpened: nameField.forceFocus()
    onClosed: if (MembersViewModel.errorMessage) MembersViewModel.clearMessages()

    Connections {
        target: MembersViewModel
        function onTeamCreated() { if (dialog.opened) dialog.close() }
        function onTeamRenamed() { if (dialog.opened) dialog.close() }
    }

    AppTextField {
        id: nameField
        Layout.fillWidth: true
        label: qsTr("Team name")
        iconName: "grid"
        placeholderText: qsTr("e.g. Sales")
        field.maximumLength: 100
        invalid: MembersViewModel.errorFields.indexOf("teamName") >= 0
        field.onTextEdited: MembersViewModel.fieldEdited("teamName")
        onAccepted: dialog.submit()
    }

    Banner { Layout.fillWidth: true; kind: "error"; text: dialog.opened ? MembersViewModel.errorMessage : "" }

    AppButton {
        Layout.fillWidth: true
        iconName: dialog.team ? "" : "plus"
        text: dialog.team ? qsTr("Rename") : qsTr("Create team")
        busy: MembersViewModel.busy
        enabled: !MembersViewModel.busy
        onClicked: dialog.submit()
    }
}

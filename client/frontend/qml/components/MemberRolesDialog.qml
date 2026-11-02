import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"

// Assign a member's role bundles (the base role is set in the Edit dialog). Bundles the current
// user may not hand out (they lack some of its permissions) are shown but locked.
AppDialog {
    id: dialog

    property var member: ({})
    property var selected: []

    function openFor(m) {
        member = m
        selected = m.role_bundles.map(b => b.id)
        MembersViewModel.clearMessages()
        open()
    }
    function toggle(id, on) {
        const next = selected.filter(v => v !== id)
        if (on) next.push(id)
        selected = next
    }

    title: qsTr("Roles for %1").arg(member.full_name || member.email || "")
    subtitle: qsTr("Permissions from role bundles add to the base role and apply immediately.")
    iconName: "users"

    Connections {
        target: MembersViewModel
        function onMemberRolesSaved() { if (dialog.opened) dialog.close() }
    }

    Label {
        text: qsTr("Role bundles")
        color: Theme.text
        font.pixelSize: 13
        font.weight: Font.Medium
    }
    Label {
        visible: MembersViewModel.bundles.length === 0
        Layout.fillWidth: true
        wrapMode: Text.Wrap
        text: AuthViewModel.isOwner ? qsTr("No role bundles yet. Create them on the Roles page.")
                                    : qsTr("The Owner has not created any role bundles yet.")
        color: Theme.textFaint
        font.pixelSize: 12
    }

    Repeater {
        model: MembersViewModel.bundles
        delegate: RowLayout {
            id: bundleRow
            required property var modelData
            readonly property bool assignable: MembersViewModel.assignableBundleIds.indexOf(modelData.id) >= 0
            Layout.fillWidth: true
            spacing: 10

            AppCheckBox {
                readonly property bool on: dialog.selected.indexOf(bundleRow.modelData.id) >= 0
                checked: on
                enabled: bundleRow.assignable
                onToggled: {
                    dialog.toggle(bundleRow.modelData.id, checked)
                    checked = Qt.binding(() => on)
                }
                Accessible.name: bundleRow.modelData.name
            }
            ColumnLayout {
                spacing: 0
                Layout.fillWidth: true
                Label {
                    text: bundleRow.modelData.name
                    color: bundleRow.assignable ? Theme.text : Theme.textMuted
                    font.pixelSize: 13
                    font.weight: Font.Medium
                }
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    color: Theme.textFaint
                    font.pixelSize: 12
                    text: bundleRow.assignable
                          ? (bundleRow.modelData.description
                             || (bundleRow.modelData.permissions.length === 1 ? qsTr("1 permission")
                                 : qsTr("%1 permissions").arg(bundleRow.modelData.permissions.length)))
                          : qsTr("Includes permissions you don't have, so you can't change it.")
                }
            }
        }
    }

    Banner {
        Layout.fillWidth: true
        kind: "error"
        text: MembersViewModel.errorMessage
    }

    AppButton {
        Layout.fillWidth: true
        text: qsTr("Save roles")
        busy: MembersViewModel.busy
        enabled: !MembersViewModel.busy
        // The base role (Member / Team Leader) is set in the Edit dialog.
        onClicked: MembersViewModel.saveMemberRoles(dialog.member.id, "", dialog.selected)
    }
}

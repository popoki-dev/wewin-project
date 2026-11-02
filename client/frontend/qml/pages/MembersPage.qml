import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"
import "../components"

// Owner: every team and member. Everyone else: their own team, with whatever their
// permissions (base role plus role bundles) allow. The server enforces the same rules.
Item {
    id: page

    readonly property bool owner: AuthViewModel.isOwner
    readonly property bool wide: width >= 960
    readonly property bool canAdd: AuthViewModel.permissions.indexOf("members.add") >= 0
    // Dialogs show their own errors; the page banner would only repeat them behind the overlay.
    readonly property bool dialogOpen: addDialog.opened || editDialog.opened || rolesDialog.opened

    function roleLabel(role) {
        return role === "owner" ? qsTr("Owner") : role === "team_leader" ? qsTr("Team Leader") : qsTr("Member")
    }
    function statusLabel(m) {
        if (!m.is_active) return qsTr("Disabled")
        if (m.must_change_password) return m.device_registered ? qsTr("Must change password") : qsTr("Not signed in yet")
        return m.device_registered ? qsTr("Device registered") : qsTr("No device registered")
    }

    Component.onCompleted: MembersViewModel.refresh()

    Connections {
        target: MembersViewModel
    }

    MemberAddDialog { id: addDialog; objectName: "memberAddDialog" }
    MemberRolesDialog { id: rolesDialog; objectName: "memberRolesDialog" }
    MemberEditDialog { id: editDialog; objectName: "memberEditDialog" }

    ScrollView {
        id: scroller
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true

        ColumnLayout {
            width: scroller.availableWidth
            spacing: 20

            Item { Layout.preferredHeight: 20 }

            // ------------------------------------------------------- header
            RowLayout {
                Layout.leftMargin: 40
                Layout.rightMargin: 40
                Layout.fillWidth: true
                spacing: 12
                ColumnLayout {
                    spacing: 4
                    Layout.fillWidth: true
                    Label { text: qsTr("Members"); color: Theme.text; font.pixelSize: 28; font.weight: Font.Bold; Layout.fillWidth: true }
                    Label {
                        text: page.owner ? qsTr("Everyone in your organization.") : AuthViewModel.scopeTeamIds.length > 1 ? qsTr("Members of the teams you lead.") : qsTr("Members of your team.")
                        color: Theme.textMuted
                        font.pixelSize: 14
                    }
                }
                AppButton {
                    variant: "secondary"
                    iconName: "refresh"
                    text: qsTr("Refresh")
                    busy: MembersViewModel.busy
                    enabled: !MembersViewModel.busy
                    onClicked: { MembersViewModel.clearMessages(); MembersViewModel.refresh() }
                }
            }

            Banner {
                Layout.leftMargin: 40
                Layout.rightMargin: 40
                Layout.fillWidth: true
                kind: "error"
                text: page.dialogOpen ? "" : MembersViewModel.errorMessage
            }
            Banner {
                Layout.leftMargin: 40
                Layout.rightMargin: 40
                Layout.fillWidth: true
                kind: "success"
                text: MembersViewModel.errorMessage ? "" : MembersViewModel.notice
            }

            // ------------------------------------------------------ members list
            Card {
                Layout.leftMargin: 40
                Layout.rightMargin: 40
                Layout.fillWidth: true
                title: qsTr("People")
                subtitle: MembersViewModel.members.length === 1 ? qsTr("1 account") : qsTr("%1 accounts").arg(MembersViewModel.members.length)
                actions: [
                    AppButton {
                        visible: page.canAdd
                        iconName: "plus"
                        text: qsTr("Add member")
                        implicitHeight: 38
                        enabled: !MembersViewModel.busy
                        onClicked: addDialog.openNew()
                    }
                ]

                Repeater {
                    model: MembersViewModel.members
                    delegate: ColumnLayout {
                        id: row
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        spacing: 10

                        Rectangle { visible: row.index > 0; Layout.fillWidth: true; height: 1; color: Theme.border }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            Rectangle {
                                width: 34; height: 34; radius: 17
                                color: Theme.accentSoft
                                Label {
                                    anchors.centerIn: parent
                                    text: (row.modelData.full_name || row.modelData.email).charAt(0).toUpperCase()
                                    color: Theme.accent
                                    font.weight: Font.Bold
                                }
                            }
                            ColumnLayout {
                                spacing: 0
                                Layout.fillWidth: true
                                Label {
                                    text: row.modelData.full_name || row.modelData.email
                                    color: Theme.text; font.pixelSize: 14; font.weight: Font.DemiBold
                                    elide: Text.ElideRight; Layout.fillWidth: true
                                }
                                Label {
                                    text: row.modelData.full_name ? row.modelData.email : ""
                                    visible: text.length > 0
                                    color: Theme.textMuted; font.pixelSize: 12
                                    elide: Text.ElideRight; Layout.fillWidth: true
                                }
                                Label {
                                    visible: row.modelData.role_bundles.length > 0
                                    text: qsTr("+ %1").arg(row.modelData.role_bundles.map(b => b.name).join(", "))
                                    color: Theme.accent; font.pixelSize: 12
                                    elide: Text.ElideRight; Layout.fillWidth: true
                                }
                            }
                            // Team, plus a Team Leader's quick moves in and out of their team.
                            ColumnLayout {
                                visible: page.wide
                                Layout.preferredWidth: 140
                                Layout.maximumWidth: 140
                                spacing: 0
                                Label {
                                    readonly property var led: row.modelData.led_teams || []
                                    Layout.fillWidth: true
                                    text: led.length > 0 ? qsTr("Leads %1").arg(led.map(t => t.name).join(", "))
                                        : row.modelData.team_name || (row.modelData.role === "owner" ? "—" : qsTr("No team"))
                                    color: row.modelData.team_name || led.length > 0 ? Theme.textMuted : Theme.textFaint
                                    font.pixelSize: 13; elide: Text.ElideRight
                                    ToolTip.visible: leadHover.hovered && led.length > 1
                                    ToolTip.text: text
                                    HoverHandler { id: leadHover }
                                }
                                LinkButton {
                                    id: bringIn
                                    visible: MembersViewModel.canBringIntoTeam(row.modelData)
                                    text: MembersViewModel.scopeTeams.length > 1 ? qsTr("Add to a team ▾") : qsTr("Add to my team")
                                    font.pixelSize: 12
                                    enabled: !MembersViewModel.busy
                                    onClicked: {
                                        const scope = MembersViewModel.scopeTeams
                                        if (scope.length === 1) MembersViewModel.setMemberTeam(row.modelData, scope[0].id)
                                        else teamMenu.popup(bringIn, 0, bringIn.height)
                                    }
                                    Menu {
                                        id: teamMenu
                                        Instantiator {
                                            model: MembersViewModel.scopeTeams
                                            delegate: MenuItem {
                                                required property var modelData
                                                text: modelData.name
                                                onTriggered: MembersViewModel.setMemberTeam(row.modelData, modelData.id)
                                            }
                                            onObjectAdded: (index, object) => teamMenu.insertItem(index, object)
                                            onObjectRemoved: (index, object) => teamMenu.removeItem(object)
                                        }
                                    }
                                }
                                LinkButton {
                                    visible: MembersViewModel.canTakeOutOfTeam(row.modelData)
                                    text: qsTr("Remove from team")
                                    font.pixelSize: 12
                                    enabled: !MembersViewModel.busy
                                    onClicked: MembersViewModel.setMemberTeam(row.modelData, 0)
                                }
                            }
                            Item {
                                // Fixed-width column, so the team column lines up across rows.
                                Layout.preferredWidth: 110
                                implicitHeight: 24
                                Rectangle {
                                    width: roleText.implicitWidth + 16
                                    height: 24
                                    radius: 12
                                    color: row.modelData.role === "member" ? Theme.surfaceAlt : Theme.accentSoft
                                    Label {
                                        id: roleText
                                        anchors.centerIn: parent
                                        text: page.roleLabel(row.modelData.role)
                                        color: row.modelData.role === "member" ? Theme.textMuted : Theme.accent
                                        font.pixelSize: 12; font.weight: Font.Medium
                                    }
                                }
                            }
                            Label {
                                Layout.preferredWidth: 160
                                horizontalAlignment: Text.AlignRight
                                text: page.statusLabel(row.modelData)
                                color: row.modelData.must_change_password ? Theme.warning : Theme.textFaint
                                font.pixelSize: 12
                                elide: Text.ElideRight
                            }
                            AppButton {
                                variant: "ghost"
                                implicitWidth: 64
                                implicitHeight: 34
                                font.pixelSize: 12
                                text: qsTr("Edit")
                                visible: MembersViewModel.canEditMember(row.modelData)
                                enabled: !MembersViewModel.busy
                                onClicked: editDialog.openFor(row.modelData)
                            }
                            Item { visible: !MembersViewModel.canEditMember(row.modelData); implicitWidth: 64 }
                            AppButton {
                                variant: "ghost"
                                implicitWidth: 70
                                implicitHeight: 34
                                font.pixelSize: 12
                                text: qsTr("Roles")
                                visible: MembersViewModel.canEditRoles(row.modelData)
                                enabled: !MembersViewModel.busy
                                onClicked: rolesDialog.openFor(row.modelData)
                            }
                            Item { visible: !MembersViewModel.canEditRoles(row.modelData); implicitWidth: 70 }
                            AppButton {
                                variant: "ghost"
                                implicitWidth: 120
                                implicitHeight: 34
                                font.pixelSize: 12
                                text: qsTr("Reset device")
                                visible: MembersViewModel.canResetDevice(row.modelData)
                                enabled: !MembersViewModel.busy
                                ToolTip.visible: hovered
                                ToolTip.delay: 400
                                ToolTip.text: qsTr("Sign this person out and let their next sign-in register a new PC.")
                                onClicked: MembersViewModel.resetDevice(row.modelData.id)
                            }
                            Item { visible: !MembersViewModel.canResetDevice(row.modelData); implicitWidth: 120 }
                        }
                    }
                }
            }

            Item { Layout.preferredHeight: 20 }
        }
    }
}

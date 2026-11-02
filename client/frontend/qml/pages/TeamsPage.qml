import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"
import "../components"

// The Owner (and holders of teams.*) see every team; anyone else sees their own team.
Item {
    id: page

    readonly property bool canCreateTeams: AuthViewModel.permissions.indexOf("teams.create") >= 0
    readonly property bool canRenameTeams: AuthViewModel.permissions.indexOf("teams.rename") >= 0
    readonly property bool orgWide: AuthViewModel.isOwner || canCreateTeams || canRenameTeams

    function membersText(n) { return n === 1 ? qsTr("1 member") : qsTr("%1 members").arg(n) }
    // Leaders who lead only this team, so deleting it makes them Members.
    function soleLeadersOf(teamId) {
        return MembersViewModel.members
            .filter(m => (m.led_teams || []).length === 1 && m.led_teams[0].id === teamId)
            .map(m => m.full_name || m.email)
    }

    TeamDialog { id: teamDialog; objectName: "teamDialog" }
    TeamMembersDialog { id: manageDialog; objectName: "teamMembersDialog" }

    // Owner only. The team's members are kept, with no team; its Team Leaders become members.
    AppDialog {
        id: deleteDialog
        objectName: "teamDeleteDialog"
        property var team: ({})
        readonly property var leaders: team.id ? page.soleLeadersOf(team.id) : []
        function openFor(t) {
            team = t
            MembersViewModel.clearMessages()
            open()
        }
        title: qsTr("Delete “%1”?").arg(team.name || "")
        subtitle: qsTr("The team is removed for good. Its members keep their accounts.")
        iconName: "alert"
        onClosed: if (MembersViewModel.errorMessage) MembersViewModel.clearMessages()

        Connections {
            target: MembersViewModel
            function onTeamDeleted() { if (deleteDialog.opened) deleteDialog.close() }
        }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            color: Theme.text
            font.pixelSize: 13
            text: deleteDialog.team.member_count > 0
                  ? qsTr("%1 will have no team until you assign a new one with Edit on the Members page.")
                        .arg(page.membersText(deleteDialog.team.member_count))
                  : qsTr("The team has no members.")
        }
        Label {
            visible: deleteDialog.leaders.length > 0
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            color: Theme.warning
            font.pixelSize: 13
            text: qsTr("%1 leads no other team, so will become a regular member and lose Team Leader permissions.")
                  .arg(deleteDialog.leaders.join(", "))
        }
        Banner { Layout.fillWidth: true; kind: "error"; text: deleteDialog.opened ? MembersViewModel.errorMessage : "" }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            AppButton {
                variant: "secondary"
                text: qsTr("Cancel")
                Layout.fillWidth: true
                onClicked: deleteDialog.close()
            }
            Button {
                id: confirmDelete
                Layout.fillWidth: true
                implicitHeight: Theme.controlHeight
                enabled: !MembersViewModel.busy
                hoverEnabled: true
                text: qsTr("Delete team")
                font.pixelSize: 14
                font.weight: Font.DemiBold
                onClicked: MembersViewModel.deleteTeam(deleteDialog.team)
                background: Rectangle {
                    radius: Theme.radius
                    color: confirmDelete.hovered ? Qt.darker(Theme.danger, 1.1) : Theme.danger
                    opacity: confirmDelete.enabled ? 1 : 0.55
                }
                contentItem: Label {
                    text: confirmDelete.text
                    font: confirmDelete.font
                    color: "#ffffff"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }

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
                    Label { text: qsTr("Teams"); color: Theme.text; font.pixelSize: 28; font.weight: Font.Bold; Layout.fillWidth: true }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: page.orgWide ? qsTr("Every team in your organization. Each member belongs to one team.")
                                           : AuthViewModel.userRole === "team_leader" ? qsTr("The teams you lead.")
                                           : qsTr("The team you belong to.")
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
                AppButton {
                    visible: page.canCreateTeams
                    iconName: "plus"
                    text: qsTr("New team")
                    enabled: !MembersViewModel.busy
                    onClicked: teamDialog.openNew()
                }
            }

            Banner {
                Layout.leftMargin: 40
                Layout.rightMargin: 40
                Layout.fillWidth: true
                kind: "error"
                text: teamDialog.opened || deleteDialog.opened || manageDialog.opened ? "" : MembersViewModel.errorMessage
            }
            Banner {
                Layout.leftMargin: 40
                Layout.rightMargin: 40
                Layout.fillWidth: true
                kind: "success"
                text: MembersViewModel.errorMessage ? "" : MembersViewModel.notice
            }

            Card {
                Layout.leftMargin: 40
                Layout.rightMargin: 40
                Layout.fillWidth: true
                title: page.orgWide ? qsTr("All teams") : MembersViewModel.teams.length > 1 ? qsTr("Your teams") : qsTr("Your team")
                subtitle: MembersViewModel.teams.length === 1 ? qsTr("1 team") : qsTr("%1 teams").arg(MembersViewModel.teams.length)

                Label {
                    visible: MembersViewModel.teams.length === 0
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: page.canCreateTeams ? qsTr("No teams yet. Create one with New team, then add members to it.")
                                              : qsTr("You are not assigned to a team.")
                    color: Theme.textFaint
                    font.pixelSize: 13
                }

                Repeater {
                    model: MembersViewModel.teams
                    delegate: ColumnLayout {
                        id: row
                        required property var modelData
                        required property int index
                        readonly property var leaders: (modelData.leaders || []).map(p => p.name)
                        Layout.fillWidth: true
                        spacing: 10

                        Rectangle { visible: row.index > 0; Layout.fillWidth: true; height: 1; color: Theme.border }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12
                            Rectangle {
                                width: 34; height: 34; radius: 10
                                color: Theme.accentSoft
                                Icon { anchors.centerIn: parent; name: "grid"; width: 16; height: 16; color: Theme.accent }
                            }
                            ColumnLayout {
                                spacing: 0
                                Layout.fillWidth: true
                                Label {
                                    text: row.modelData.name
                                    color: Theme.text; font.pixelSize: 14; font.weight: Font.DemiBold
                                    elide: Text.ElideRight; Layout.fillWidth: true
                                }
                                Label {
                                    visible: row.leaders.length > 0
                                    text: qsTr("Led by %1").arg(row.leaders.join(", "))
                                    color: Theme.textMuted; font.pixelSize: 12
                                    elide: Text.ElideRight; Layout.fillWidth: true
                                }
                            }
                            Label {
                                text: page.membersText(row.modelData.member_count)
                                color: Theme.textMuted
                                font.pixelSize: 12
                            }
                            AppButton {
                                visible: AuthViewModel.isOwner
                                variant: "secondary"
                                text: qsTr("Manage")
                                implicitWidth: 86
                                implicitHeight: 32
                                font.pixelSize: 12
                                enabled: !MembersViewModel.busy
                                onClicked: manageDialog.openFor(row.modelData)
                            }
                            AppButton {
                                visible: page.canRenameTeams
                                variant: "ghost"
                                text: qsTr("Rename")
                                implicitWidth: 80
                                implicitHeight: 32
                                font.pixelSize: 12
                                enabled: !MembersViewModel.busy
                                onClicked: teamDialog.openFor(row.modelData)
                            }
                            AppButton {
                                visible: AuthViewModel.isOwner
                                variant: "ghost"
                                text: qsTr("Delete")
                                implicitWidth: 80
                                implicitHeight: 32
                                font.pixelSize: 12
                                enabled: !MembersViewModel.busy
                                onClicked: deleteDialog.openFor(row.modelData)
                            }
                        }
                    }
                }
            }

            Item { Layout.preferredHeight: 20 }
        }
    }
}

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
    // Team Leaders of a team, from the member list (empty when the user cannot list members).
    function leadersOf(teamId) {
        return MembersViewModel.members
            .filter(m => m.team_id === teamId && m.role === "team_leader")
            .map(m => m.full_name || m.email)
    }

    TeamDialog { id: teamDialog; objectName: "teamDialog" }

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
                text: teamDialog.opened ? "" : MembersViewModel.errorMessage
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
                title: page.orgWide ? qsTr("All teams") : qsTr("Your team")
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
                        readonly property var leaders: page.leadersOf(modelData.id)
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
                                visible: page.canRenameTeams
                                variant: "ghost"
                                text: qsTr("Rename")
                                implicitWidth: 80
                                implicitHeight: 32
                                font.pixelSize: 12
                                enabled: !MembersViewModel.busy
                                onClicked: teamDialog.openFor(row.modelData)
                            }
                        }
                    }
                }
            }

            Item { Layout.preferredHeight: 20 }
        }
    }
}

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"
import "../layouts"

AppShell {
    id: shell
    objectName: "appShell"

    onCurrentPageChanged: if (currentPage === "members" || currentPage === "roles") MembersViewModel.refresh()

    StackLayout {
        anchors.fill: parent
        currentIndex: shell.currentPage === "members" ? 1 : shell.currentPage === "roles" ? 2 : 0

        // Overview: placeholder until the Projects and Revenue modules land.
        Item {
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 40
                spacing: 8

                Label {
                    text: qsTr("Welcome, %1").arg(AuthViewModel.userName)
                    color: Theme.text
                    font.pixelSize: 28
                    font.weight: Font.Bold
                }
                Label {
                    readonly property string role: AuthViewModel.userRole === "team_leader" ? qsTr("Team Leader")
                                                 : AuthViewModel.userRole === "owner" ? qsTr("Owner") : qsTr("Member")
                    text: qsTr("Signed in as %1 · %2").arg(role).arg(AuthViewModel.serverUrl)
                    color: Theme.textMuted
                    font.pixelSize: 14
                }
                Rectangle {
                    Layout.topMargin: 24
                    Layout.fillWidth: true
                    Layout.preferredHeight: 160
                    radius: Theme.radiusLarge
                    color: Theme.surface
                    border.width: 1
                    border.color: Theme.border
                    Label {
                        anchors.centerIn: parent
                        width: parent.width - 48
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: AuthViewModel.canManageMembers
                              ? qsTr("Manage your people under Members. Projects and Revenue are coming next.")
                              : qsTr("Projects and Revenue modules will appear here.")
                        color: Theme.textMuted
                    }
                }
                Item { Layout.fillHeight: true }
            }
        }

        MembersPage {}
        RolesPage {}
    }
}

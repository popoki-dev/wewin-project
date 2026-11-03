import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"
import "../components"

// Signed-in frame: navigation sidebar with the user card, and a content area.
Rectangle {
    id: root

    default property alias content: contentArea.data
    property string currentPage: "home"

    color: Theme.background

    ChangePasswordDialog { id: changePasswordDialog }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: 240
            color: Theme.surface

            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.border }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 4

                Logo { Layout.margins: 6; Layout.bottomMargin: 18 }

                Repeater {
                    model: [
                        { page: "home",     icon: "home",   text: qsTr("Overview"), ready: true },
                        { page: "members",  icon: "users",  text: qsTr("Members"),  ready: AuthViewModel.canManageMembers },
                        { page: "teams",    icon: "grid",   text: qsTr("Teams"),    ready: AuthViewModel.canViewTeams },
                        { page: "roles",    icon: "key",    text: qsTr("Roles"),    ready: AuthViewModel.isOwner },
                        { page: "projects", icon: "folder", text: qsTr("Projects"), ready: AuthViewModel.permissions.indexOf("projects.view") >= 0 },
                        { page: "revenue",  icon: "chart",  text: qsTr("Revenue"),  ready: false }
                    ]
                    delegate: ItemDelegate {
                        id: navItem
                        required property var modelData
                        readonly property bool current: root.currentPage === modelData.page
                        // Members needs members.view; Teams, members.view or teams.*; Roles is the Owner's.
                        visible: modelData.page === "members" ? AuthViewModel.canManageMembers
                               : modelData.page === "teams" ? AuthViewModel.canViewTeams
                               : modelData.page === "roles" ? AuthViewModel.isOwner : true
                        Layout.fillWidth: true
                        implicitHeight: 40
                        enabled: modelData.ready
                        hoverEnabled: true
                        onClicked: root.currentPage = modelData.page
                        background: Rectangle {
                            radius: Theme.radiusSmall
                            color: navItem.current ? Theme.accentSoft : navItem.hovered ? Theme.surfaceHover : "transparent"
                        }
                        contentItem: RowLayout {
                            spacing: 10
                            Icon {
                                name: navItem.modelData.icon
                                color: navItem.current ? Theme.accent : navItem.enabled ? Theme.textMuted : Theme.textFaint
                            }
                            Label {
                                text: navItem.modelData.text
                                color: navItem.current ? Theme.accent : navItem.enabled ? Theme.text : Theme.textMuted
                                font.pixelSize: 14
                                font.weight: navItem.current ? Font.DemiBold : Font.Normal
                                Layout.fillWidth: true
                            }
                            Label { visible: !navItem.enabled; text: qsTr("Soon"); color: Theme.textFaint; font.pixelSize: 11 }
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                ThemeSwitcher { Layout.alignment: Qt.AlignHCenter; Layout.bottomMargin: 8 }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: userRow.implicitHeight + 20
                    radius: Theme.radius
                    color: Theme.surfaceAlt

                    RowLayout {
                        id: userRow
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 10

                        Rectangle {
                            width: 34; height: 34; radius: 17
                            color: Theme.accentSoft
                            Label {
                                anchors.centerIn: parent
                                text: AuthViewModel.userName.charAt(0).toUpperCase()
                                color: Theme.accent
                                font.weight: Font.Bold
                            }
                        }
                        ColumnLayout {
                            spacing: 0
                            Layout.fillWidth: true
                            Label { text: AuthViewModel.userName; color: Theme.text; font.pixelSize: 13; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
                            Label { text: AuthViewModel.userEmail; color: Theme.textMuted; font.pixelSize: 11; elide: Text.ElideRight; Layout.fillWidth: true }
                        }
                        ToolButton {
                            id: passwordButton
                            width: 32; height: 32
                            hoverEnabled: true
                            onClicked: changePasswordDialog.openDialog()
                            Accessible.name: qsTr("Change password")
                            ToolTip.visible: hovered
                            ToolTip.text: qsTr("Change password")
                            background: Rectangle { radius: Theme.radiusSmall; color: passwordButton.hovered ? Theme.surfaceHover : "transparent" }
                            contentItem: Item { Icon { anchors.centerIn: parent; name: "key"; color: passwordButton.hovered ? Theme.accent : Theme.textMuted } }
                        }
                        ToolButton {
                            id: logoutButton
                            width: 32; height: 32
                            hoverEnabled: true
                            onClicked: AuthViewModel.logout()
                            Accessible.name: qsTr("Sign out")
                            ToolTip.visible: hovered
                            ToolTip.text: qsTr("Sign out")
                            background: Rectangle { radius: Theme.radiusSmall; color: logoutButton.hovered ? Theme.surfaceHover : "transparent" }
                            contentItem: Item { Icon { anchors.centerIn: parent; name: "logout"; color: logoutButton.hovered ? Theme.danger : Theme.textMuted } }
                        }
                    }
                }
            }
        }

        Item {
            id: contentArea
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}

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

    color: Theme.background

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
                        { icon: "users",  text: qsTr("Members") },
                        { icon: "folder", text: qsTr("Projects") },
                        { icon: "chart",  text: qsTr("Revenue") }
                    ]
                    delegate: ItemDelegate {
                        id: navItem
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: 40
                        enabled: false
                        background: Rectangle { radius: Theme.radiusSmall; color: "transparent" }
                        contentItem: RowLayout {
                            spacing: 10
                            Icon { name: navItem.modelData.icon; color: Theme.textFaint }
                            Label { text: navItem.modelData.text; color: Theme.textMuted; font.pixelSize: 14; Layout.fillWidth: true }
                            Label { text: qsTr("Soon"); color: Theme.textFaint; font.pixelSize: 11 }
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

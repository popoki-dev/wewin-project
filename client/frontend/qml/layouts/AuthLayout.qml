import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../themes"
import "../components"

// Split screen for signed-out pages: brand panel on the left (wide windows only),
// theme switcher and a centred content column on the right.
Item {
    id: root

    default property alias content: column.data
    readonly property bool wide: width >= 880

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ---------------------------------------------------------- brand panel
        Rectangle {
            visible: root.wide
            Layout.fillHeight: true
            Layout.preferredWidth: Math.round(root.width * 0.44)
            gradient: Gradient {
                orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: Theme.brandStart }
                GradientStop { position: 1.0; color: Theme.brandEnd }
            }

            // Soft decorative shapes
            Rectangle {
                width: parent.width * 0.9; height: width; radius: width / 2
                x: -width * 0.35; y: parent.height - height * 0.55
                color: Qt.rgba(1, 1, 1, 0.06)
            }
            Rectangle {
                width: parent.width * 0.55; height: width; radius: width / 2
                x: parent.width - width * 0.6; y: -height * 0.3
                color: Qt.rgba(1, 1, 1, 0.07)
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 48
                spacing: 0

                Logo { light: true }

                Item { Layout.fillHeight: true }

                Label {
                    text: qsTr("Run your organization\nwith clarity.")
                    color: "white"
                    font.pixelSize: 34
                    font.weight: Font.Bold
                    lineHeight: 1.15
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                }
                Label {
                    text: qsTr("Members, projects and revenue — together in one workspace.")
                    color: Qt.rgba(1, 1, 1, 0.78)
                    font.pixelSize: 15
                    Layout.topMargin: 14
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                }

                ColumnLayout {
                    Layout.topMargin: 36
                    spacing: 14
                    Repeater {
                        model: [
                            { icon: "users",  text: qsTr("Manage members and roles") },
                            { icon: "folder", text: qsTr("Track every project") },
                            { icon: "chart",  text: qsTr("See revenue at a glance") }
                        ]
                        delegate: RowLayout {
                            required property var modelData
                            spacing: 12
                            Rectangle {
                                width: 34; height: 34; radius: 10
                                color: Qt.rgba(1, 1, 1, 0.14)
                                Icon { anchors.centerIn: parent; name: modelData.icon; color: "white" }
                            }
                            Label { text: modelData.text; color: "white"; font.pixelSize: 14 }
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                Label {
                    text: qsTr("© %1 WeWin").arg(new Date().getFullYear())
                    color: Qt.rgba(1, 1, 1, 0.6)
                    font.pixelSize: 12
                }
            }
        }

        // ---------------------------------------------------------- content side
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.background
            Behavior on color { ColorAnimation { duration: Theme.animationMs } }

            ThemeSwitcher {
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.margins: 20
                z: 1
            }

            Flickable {
                anchors.fill: parent
                contentHeight: Math.max(height, column.implicitHeight + 96)
                boundsBehavior: Flickable.StopAtBounds
                clip: true
                ScrollBar.vertical: ScrollBar {}

                ColumnLayout {
                    id: column
                    width: Math.min(400, parent.width - 48)
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: Math.max(64, (parent.height - implicitHeight) / 2)
                    spacing: 18

                    Logo { visible: !root.wide; Layout.bottomMargin: 8 }
                }
            }
        }
    }
}

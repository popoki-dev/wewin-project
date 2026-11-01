import QtQuick
import QtQuick.Controls
import "../themes"

Row {
    id: root

    // Use white text when placed on the brand gradient.
    property bool light: false

    spacing: 10

    Rectangle {
        width: 36; height: 36; radius: 10
        anchors.verticalCenter: parent.verticalCenter
        color: root.light ? Qt.rgba(1, 1, 1, 0.16) : "transparent"
        border.width: root.light ? 1 : 0
        border.color: Qt.rgba(1, 1, 1, 0.3)

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            visible: !root.light
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Theme.brandStart }
                GradientStop { position: 1; color: Theme.brandEnd }
            }
        }

        Label {
            anchors.centerIn: parent
            text: "W"
            color: "white"
            font.pixelSize: 19
            font.weight: Font.Black
        }
    }

    Label {
        anchors.verticalCenter: parent.verticalCenter
        text: "WeWin"
        color: root.light ? "white" : Theme.text
        font.pixelSize: 21
        font.weight: Font.Bold
        font.letterSpacing: -0.3
    }
}

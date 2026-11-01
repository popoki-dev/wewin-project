import QtQuick
import QtQuick.Controls
import "../themes"

CheckBox {
    id: root

    hoverEnabled: true
    padding: 0
    spacing: 8
    font.pixelSize: 13

    indicator: Rectangle {
        implicitWidth: 18
        implicitHeight: 18
        x: root.leftPadding
        y: (root.height - height) / 2
        radius: 5
        color: root.checked ? Theme.accent : Theme.inputBackground
        border.width: root.checked ? 0 : 1
        border.color: root.hovered ? Theme.borderStrong : Theme.border
        Behavior on color { ColorAnimation { duration: Theme.animationMs } }

        Icon {
            anchors.centerIn: parent
            width: 14; height: 14
            name: "tick"
            color: Theme.accentText
            strokeWidth: 2.6
            visible: root.checked
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: -3
            radius: 8
            color: "transparent"
            border.width: 3
            border.color: Theme.focusRing
            visible: root.visualFocus
        }
    }

    contentItem: Label {
        text: root.text
        font: root.font
        color: Theme.textMuted
        leftPadding: root.indicator.width + root.spacing
        verticalAlignment: Text.AlignVCenter
    }
}

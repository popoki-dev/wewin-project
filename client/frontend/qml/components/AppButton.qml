import QtQuick
import QtQuick.Controls
import "../themes"

Button {
    id: root

    // "primary" | "secondary" | "ghost"
    property string variant: "primary"
    property bool busy: false
    property string iconName

    readonly property bool primary: variant === "primary"

    implicitHeight: Theme.controlHeight
    implicitWidth: Math.max(120, contentItem.implicitWidth + 32)
    hoverEnabled: true
    font.pixelSize: 14
    font.weight: Font.DemiBold
    Accessible.name: text

    background: Rectangle {
        radius: Theme.radius
        color: root.primary
               ? (root.down ? Qt.darker(Theme.accentHover, 1.08) : root.hovered ? Theme.accentHover : Theme.accent)
               : root.variant === "secondary"
                 ? (root.hovered ? Theme.surfaceHover : Theme.surface)
                 : (root.hovered ? Theme.surfaceHover : "transparent")
        border.width: root.variant === "secondary" ? 1 : 0
        border.color: Theme.border
        opacity: root.enabled || root.busy ? 1 : 0.55
        Behavior on color { ColorAnimation { duration: Theme.animationMs } }

        Rectangle {
            anchors.fill: parent
            anchors.margins: -3
            radius: parent.radius + 3
            color: "transparent"
            border.width: 3
            border.color: Theme.focusRing
            visible: root.visualFocus
        }
    }

    contentItem: Item {
        implicitWidth: row.implicitWidth
        implicitHeight: row.implicitHeight

        Row {
            id: row
            anchors.centerIn: parent
            spacing: 8

            Spinner {
                visible: root.busy
                anchors.verticalCenter: parent.verticalCenter
                color: root.primary ? Theme.accentText : Theme.accent
            }
            Icon {
                visible: !root.busy && root.iconName.length > 0
                name: root.iconName
                anchors.verticalCenter: parent.verticalCenter
                color: label.color
            }
            Label {
                id: label
                text: root.text
                font: root.font
                color: root.primary ? Theme.accentText : Theme.text
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }
}

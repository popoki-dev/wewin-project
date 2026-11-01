import QtQuick
import QtQuick.Controls
import "../themes"

// Small rounded on/off pill, e.g. for picking role bundles.
AbstractButton {
    id: root

    checkable: true
    hoverEnabled: true
    implicitHeight: 30
    implicitWidth: row.implicitWidth + 24
    font.pixelSize: 12
    Accessible.role: Accessible.CheckBox
    Accessible.name: text

    background: Rectangle {
        radius: height / 2
        color: root.checked ? Theme.accentSoft : root.hovered && root.enabled ? Theme.surfaceHover : Theme.surface
        border.width: 1
        border.color: root.checked ? Theme.accent : Theme.border
        opacity: root.enabled ? 1 : 0.5
    }

    contentItem: Item {
        Row {
            id: row
            anchors.centerIn: parent
            spacing: 6
            Icon {
                visible: root.checked
                width: 14; height: 14
                name: "tick"
                strokeWidth: 2.4
                color: Theme.accent
                anchors.verticalCenter: parent.verticalCenter
            }
            Label {
                text: root.text
                font: root.font
                color: root.checked ? Theme.accent : Theme.textMuted
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    HoverHandler { cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
}

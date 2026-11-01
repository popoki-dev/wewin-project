import QtQuick
import QtQuick.Controls
import "../themes"

AbstractButton {
    id: root

    hoverEnabled: true
    padding: 2
    font.pixelSize: 13
    font.weight: Font.Medium
    Accessible.role: Accessible.Link
    Accessible.name: text

    contentItem: Label {
        text: root.text
        font.pixelSize: root.font.pixelSize
        font.weight: root.font.weight
        font.underline: root.hovered || root.visualFocus
        color: root.hovered ? Theme.accentHover : Theme.accent
    }

    HoverHandler { cursorShape: Qt.PointingHandCursor }
}

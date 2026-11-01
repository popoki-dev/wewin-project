import QtQuick
import QtQuick.Controls
import WeWin.ViewModels
import "../themes"

// Segmented System / Light / Dark control.
Rectangle {
    id: root

    implicitWidth: row.implicitWidth + 8
    implicitHeight: 36
    radius: Theme.radius
    color: Theme.surfaceAlt
    border.width: 1
    border.color: Theme.border

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 2

        Repeater {
            model: [
                { mode: "system", icon: "monitor", label: qsTr("Follow system theme") },
                { mode: "light",  icon: "sun",     label: qsTr("Light theme") },
                { mode: "dark",   icon: "moon",    label: qsTr("Dark theme") }
            ]

            delegate: AbstractButton {
                id: segment
                required property var modelData
                readonly property bool selected: ThemeViewModel.mode === modelData.mode

                width: 36; height: 28
                hoverEnabled: true
                checkable: false
                onClicked: ThemeViewModel.mode = modelData.mode
                Accessible.name: modelData.label
                Accessible.checkable: true
                Accessible.checked: selected
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: modelData.label

                background: Rectangle {
                    radius: Theme.radiusSmall
                    color: segment.selected ? Theme.surface : segment.hovered ? Theme.surfaceHover : "transparent"
                    border.width: segment.selected ? 1 : 0
                    border.color: Theme.border
                    Behavior on color { ColorAnimation { duration: Theme.animationMs } }
                }
                contentItem: Item {
                    Icon {
                        anchors.centerIn: parent
                        width: 16; height: 16
                        name: segment.modelData.icon
                        color: segment.selected ? Theme.accent : Theme.textMuted
                    }
                }
            }
        }
    }
}

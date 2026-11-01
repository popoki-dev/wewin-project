import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../themes"

// Modal card with an icon, title, subtitle and close button; children go below the header.
Popup {
    id: dialog

    property string title
    property string subtitle
    property string iconName: "key"
    default property alias content: body.data

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(480, (parent ? parent.width : 480) - 32)
    height: Math.min(implicitHeight, (parent ? parent.height : 720) - 32)
    modal: true
    focus: true
    padding: 28
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, Theme.dark ? 0.6 : 0.35) }

    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 160 }
            NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: 160; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition { NumberAnimation { property: "opacity"; to: 0; duration: 120 } }

    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.surface
        border.width: 1
        border.color: Theme.border
    }

    contentItem: ColumnLayout {
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Rectangle {
                width: 40; height: 40; radius: 12
                color: Theme.accentSoft
                Icon { anchors.centerIn: parent; width: 20; height: 20; name: dialog.iconName; color: Theme.accent }
            }
            ColumnLayout {
                spacing: 2
                Layout.fillWidth: true
                Label { text: dialog.title; color: Theme.text; font.pixelSize: 18; font.weight: Font.Bold; Layout.fillWidth: true; elide: Text.ElideRight }
                Label {
                    visible: dialog.subtitle.length > 0
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    color: Theme.textMuted
                    font.pixelSize: 13
                    text: dialog.subtitle
                }
            }
            ToolButton {
                id: closeButton
                Layout.alignment: Qt.AlignTop
                width: 32; height: 32
                hoverEnabled: true
                onClicked: dialog.close()
                Accessible.name: qsTr("Close")
                background: Rectangle { radius: Theme.radiusSmall; color: closeButton.hovered ? Theme.surfaceHover : "transparent" }
                contentItem: Item { Icon { anchors.centerIn: parent; name: "close"; color: Theme.textMuted } }
            }
        }

        ScrollView {
            id: scroller
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: body.implicitHeight
            contentWidth: availableWidth
            clip: true

            ColumnLayout {
                id: body
                width: scroller.availableWidth
                spacing: 16
            }
        }
    }
}

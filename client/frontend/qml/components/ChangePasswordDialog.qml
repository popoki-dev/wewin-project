import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"

// Voluntary password change from the signed-in shell.
Popup {
    id: dialog

    function openDialog() {
        form.reset()
        open()
    }

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(420, (parent ? parent.width : 420) - 32)
    modal: true
    focus: true
    padding: 28
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    onOpened: form.forceFocus()
    onClosed: AuthViewModel.clearError()

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

    Connections {
        target: AuthViewModel
        function onPasswordChanged() { if (dialog.opened) dialog.close() }
    }

    contentItem: ColumnLayout {
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Rectangle {
                width: 40; height: 40; radius: 12
                color: Theme.accentSoft
                Icon { anchors.centerIn: parent; width: 20; height: 20; name: "key"; color: Theme.accent }
            }
            ColumnLayout {
                spacing: 2
                Layout.fillWidth: true
                Label { text: qsTr("Change password"); color: Theme.text; font.pixelSize: 18; font.weight: Font.Bold }
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    color: Theme.textMuted
                    font.pixelSize: 13
                    text: qsTr("Other computers and sessions will be signed out.")
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

        ChangePasswordForm { id: form; Layout.fillWidth: true }
    }
}

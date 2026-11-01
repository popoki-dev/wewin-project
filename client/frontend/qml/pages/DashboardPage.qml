import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"
import "../layouts"

// Placeholder until the Members, Projects and Revenue modules land.
AppShell {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 40
        spacing: 8

        Label {
            text: qsTr("Welcome, %1").arg(AuthViewModel.userName)
            color: Theme.text
            font.pixelSize: 28
            font.weight: Font.Bold
        }
        Label {
            text: qsTr("Signed in as %1 · %2").arg(AuthViewModel.userRole).arg(AuthViewModel.serverUrl)
            color: Theme.textMuted
            font.pixelSize: 14
        }
        Rectangle {
            Layout.topMargin: 24
            Layout.fillWidth: true
            Layout.preferredHeight: 160
            radius: Theme.radiusLarge
            color: Theme.surface
            border.width: 1
            border.color: Theme.border
            Label {
                anchors.centerIn: parent
                width: parent.width - 48
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                text: qsTr("Members, Projects and Revenue modules will appear here.")
                color: Theme.textMuted
            }
        }
        Item { Layout.fillHeight: true }
    }
}

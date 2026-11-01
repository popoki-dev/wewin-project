import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../themes"

// A titled surface with optional header actions; children stack vertically below the title.
Rectangle {
    id: card

    property string title
    property string subtitle
    property alias actions: actionsRow.data
    default property alias content: body.data

    implicitHeight: body.implicitHeight + 48
    radius: Theme.radiusLarge
    color: Theme.surface
    border.width: 1
    border.color: Theme.border

    ColumnLayout {
        id: body
        anchors.fill: parent
        anchors.margins: 24
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            ColumnLayout {
                spacing: 2
                Layout.fillWidth: true
                Label { text: card.title; color: Theme.text; font.pixelSize: 16; font.weight: Font.Bold; Layout.fillWidth: true }
                Label {
                    visible: card.subtitle.length > 0
                    Layout.fillWidth: true
                    text: card.subtitle
                    wrapMode: Text.Wrap
                    color: Theme.textMuted
                    font.pixelSize: 12
                }
            }
            Row { id: actionsRow; spacing: 8; Layout.alignment: Qt.AlignVCenter }
        }
    }
}

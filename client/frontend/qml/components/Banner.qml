import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../themes"

// Inline status message ("error" or "success").
Rectangle {
    id: root

    property string text
    property string kind: "error"

    readonly property color tone: kind === "error" ? Theme.danger : Theme.success

    visible: text.length > 0
    implicitHeight: row.implicitHeight + 20
    radius: Theme.radius
    color: kind === "error" ? Theme.dangerSoft : Theme.successSoft
    border.width: 1
    border.color: Qt.rgba(tone.r, tone.g, tone.b, 0.35)
    Accessible.role: Accessible.AlertMessage
    Accessible.name: text

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.margins: 10
        anchors.leftMargin: 12
        spacing: 10

        Icon {
            name: root.kind === "error" ? "alert" : "check"
            color: root.tone
            Layout.alignment: Qt.AlignTop
        }
        Label {
            text: root.text
            color: root.tone
            wrapMode: Text.Wrap
            font.pixelSize: 13
            Layout.fillWidth: true
        }
    }
}

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../themes"

// A small read-only table with a header and an Edit (or View) action per row; rows are
// edited elsewhere. Clicking a row opens it too.
Rectangle {
    id: table

    // [{title, width?, fill?, right?, strong?}]: a column has a fixed `width` or fills the rest.
    property var columns: []
    // One array of cell texts per row, in column order.
    property var rows: []
    // Per row, the column indexes shown in the danger colour (e.g. a negative balance).
    property var dangerCells: []
    property bool editable: true
    property string removeLabel: qsTr("Remove")

    signal openRow(int index)
    signal removeRow(int index)

    implicitHeight: content.implicitHeight + 2
    radius: Theme.radius
    color: Theme.surface
    border.width: 1
    border.color: Theme.border
    clip: true

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: 1
        spacing: 0

        // Header.
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 34
            color: Theme.surfaceAlt
            radius: Theme.radius
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: parent.radius; color: parent.color }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 8
                spacing: 10
                Repeater {
                    model: table.columns
                    delegate: Label {
                        required property var modelData
                        Layout.fillWidth: !!modelData.fill
                        Layout.preferredWidth: modelData.fill ? 60 : modelData.width
                        Layout.maximumWidth: modelData.fill ? Number.POSITIVE_INFINITY : modelData.width
                        horizontalAlignment: modelData.right ? Text.AlignRight : Text.AlignLeft
                        text: modelData.title
                        color: Theme.textMuted
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                }
                Item { Layout.preferredWidth: actions.implicitWidth; implicitHeight: 1 }
            }
        }

        Repeater {
            model: table.rows
            delegate: Rectangle {
                id: rowItem
                required property var modelData
                required property int index
                Layout.fillWidth: true
                implicitHeight: 40
                color: hover.hovered ? Theme.surfaceHover : "transparent"
                Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Theme.border }

                HoverHandler { id: hover }
                TapHandler { onTapped: table.openRow(rowItem.index) }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 8
                    spacing: 10
                    Repeater {
                        model: table.columns
                        delegate: Label {
                            required property var modelData
                            required property int index
                            readonly property bool danger: (table.dangerCells[rowItem.index] || []).indexOf(index) >= 0
                            Layout.fillWidth: !!modelData.fill
                            Layout.preferredWidth: modelData.fill ? 60 : modelData.width
                            Layout.maximumWidth: modelData.fill ? Number.POSITIVE_INFINITY : modelData.width
                            horizontalAlignment: modelData.right ? Text.AlignRight : Text.AlignLeft
                            text: rowItem.modelData[index] === undefined ? "" : rowItem.modelData[index]
                            color: danger ? Theme.danger : Theme.text
                            font.pixelSize: 12
                            font.weight: modelData.strong ? Font.DemiBold : Font.Normal
                            elide: Text.ElideRight
                        }
                    }
                    RowLayout {
                        spacing: 2
                        LinkButton {
                            text: table.editable ? qsTr("Edit") : qsTr("View")
                            font.pixelSize: 12
                            onClicked: table.openRow(rowItem.index)
                        }
                        ToolButton {
                            id: removeButton
                            visible: table.editable
                            implicitWidth: 28
                            implicitHeight: 28
                            hoverEnabled: true
                            Accessible.name: table.removeLabel
                            ToolTip.visible: hovered
                            ToolTip.text: table.removeLabel
                            onClicked: table.removeRow(rowItem.index)
                            background: Rectangle { radius: Theme.radiusSmall; color: removeButton.hovered ? Theme.surface : "transparent" }
                            contentItem: Item { Icon { anchors.centerIn: parent; name: "close"; color: removeButton.hovered ? Theme.danger : Theme.textMuted } }
                        }
                    }
                }
            }
        }
    }

    // Measures the action column so the header lines up with the rows.
    RowLayout {
        id: actions
        visible: false
        spacing: 2
        LinkButton { text: table.editable ? qsTr("Edit") : qsTr("View"); font.pixelSize: 12 }
        Item { visible: table.editable; implicitWidth: 28; implicitHeight: 28 }
    }
}

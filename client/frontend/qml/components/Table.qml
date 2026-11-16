import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../themes"

// A small read-only table with a header and an Edit (or View) action per row; rows are
// edited elsewhere. Clicking a row opens it too. Optionally shows each row's review state
// with a Review / Undo action.
Rectangle {
    id: table

    // [{title, width?, fill?, right?, strong?}]: a column has a fixed `width` or fills the rest.
    property var columns: []
    // One array of cell texts per row, in column order.
    property var rows: []
    // Per row, the column indexes shown in the danger colour (e.g. a negative balance).
    property var dangerCells: []
    property bool editable: true
    // Per row, whether it may be changed (defaults to `editable`); locked rows offer View only.
    property var rowEditable: []
    property string removeLabel: qsTr("Remove")
    // Review column: per row {text, tone} (see ReviewChip), and per row the review action
    // offered: "review", "unreview" or "" (none). Hidden while `reviewStatus` is empty.
    property var reviewStatus: []
    property var reviewActions: []
    property string reviewHint: ""      // shown instead of the actions, e.g. "save first"
    readonly property bool showReview: reviewStatus.length > 0
    readonly property int actionsWidth: 72 + (showReview ? 54 : 0)

    signal openRow(int index)
    signal removeRow(int index)
    signal reviewRow(int index, string action)

    function rowMayEdit(i) {
        return table.editable && (table.rowEditable.length <= i || table.rowEditable[i] !== false)
    }

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
                    delegate: HeaderLabel {
                        required property var modelData
                        Layout.fillWidth: !!modelData.fill
                        Layout.preferredWidth: modelData.fill ? 60 : modelData.width
                        Layout.maximumWidth: modelData.fill ? Number.POSITIVE_INFINITY : modelData.width
                        horizontalAlignment: modelData.right ? Text.AlignRight : Text.AlignLeft
                        text: modelData.title
                    }
                }
                HeaderLabel {
                    visible: table.showReview
                    Layout.preferredWidth: 78
                    Layout.maximumWidth: 78
                    text: qsTr("Review")
                }
                Item { Layout.preferredWidth: table.actionsWidth; implicitHeight: 1 }
            }
        }

        Repeater {
            model: table.rows
            delegate: Rectangle {
                id: rowItem
                required property var modelData
                required property int index
                readonly property bool mayEdit: table.rowMayEdit(index)
                readonly property string reviewAction: table.reviewActions[index] || ""
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
                    Item {
                        visible: table.showReview
                        Layout.preferredWidth: 78
                        Layout.maximumWidth: 78
                        implicitHeight: 22
                        ReviewChip {
                            anchors.verticalCenter: parent.verticalCenter
                            readonly property var status: table.reviewStatus[rowItem.index] || ({})
                            text: status.text || ""
                            tone: status.tone || "pending"
                        }
                    }
                    RowLayout {
                        Layout.preferredWidth: table.actionsWidth
                        Layout.maximumWidth: table.actionsWidth
                        spacing: 6
                        Item { Layout.fillWidth: true }
                        LinkButton {
                            visible: table.showReview && rowItem.reviewAction !== "" && table.reviewHint === ""
                            text: rowItem.reviewAction === "review" ? qsTr("Review") : qsTr("Undo")
                            font.pixelSize: 12
                            onClicked: table.reviewRow(rowItem.index, rowItem.reviewAction)
                        }
                        LinkButton {
                            text: rowItem.mayEdit ? qsTr("Edit") : qsTr("View")
                            font.pixelSize: 12
                            onClicked: table.openRow(rowItem.index)
                        }
                        ToolButton {
                            id: removeButton
                            // Kept in the layout (invisible) on locked rows so the columns line up.
                            opacity: rowItem.mayEdit ? 1 : 0
                            enabled: rowItem.mayEdit
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

    component HeaderLabel: Label {
        color: Theme.textMuted
        font.pixelSize: 11
        font.weight: Font.DemiBold
        elide: Text.ElideRight
    }
}

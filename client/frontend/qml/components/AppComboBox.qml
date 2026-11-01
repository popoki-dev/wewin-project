import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../themes"

// Labelled drop-down styled like AppTextField. `model` is a list of {value, text}.
ColumnLayout {
    id: root

    property string label
    property alias model: box.model
    property alias currentIndex: box.currentIndex
    property alias box: box
    property bool invalid: false
    readonly property var currentValue: box.currentIndex >= 0 && box.model && box.model.length > box.currentIndex
                                        ? box.model[box.currentIndex].value : undefined

    signal activated()

    spacing: 6

    function selectValue(value) {
        for (let i = 0; i < (box.model ? box.model.length : 0); i++) {
            if (box.model[i].value === value) { box.currentIndex = i; return }
        }
        box.currentIndex = -1
    }

    Label {
        visible: root.label.length > 0
        text: root.label
        color: Theme.text
        font.pixelSize: 13
        font.weight: Font.Medium
    }

    ComboBox {
        id: box
        Layout.fillWidth: true
        implicitHeight: Theme.controlHeight
        textRole: "text"
        hoverEnabled: true
        font.pixelSize: 14
        onActivated: root.activated()

        contentItem: Label {
            leftPadding: 14
            rightPadding: 36
            verticalAlignment: Text.AlignVCenter
            text: box.currentIndex >= 0 ? box.displayText : qsTr("Select…")
            color: box.currentIndex >= 0 ? Theme.text : Theme.textFaint
            font: box.font
            elide: Text.ElideRight
        }

        indicator: Icon {
            x: box.width - width - 12
            y: (box.height - height) / 2
            name: "chevron"
            color: Theme.textFaint
        }

        background: Rectangle {
            radius: Theme.radius
            color: Theme.inputBackground
            border.width: 1
            border.color: root.invalid ? Theme.danger
                        : box.activeFocus ? Theme.accent
                        : box.hovered ? Theme.borderStrong : Theme.border
        }

        delegate: ItemDelegate {
            id: option
            required property var modelData
            required property int index
            width: ListView.view ? ListView.view.width : box.width
            highlighted: box.highlightedIndex === index
            contentItem: Label { text: option.modelData.text; color: Theme.text; font.pixelSize: 14; elide: Text.ElideRight }
            background: Rectangle {
                radius: Theme.radiusSmall
                color: option.highlighted ? Theme.surfaceHover : "transparent"
            }
        }

        popup: Popup {
            y: box.height + 4
            width: box.width
            padding: 4
            implicitHeight: Math.min(contentItem.implicitHeight + 8, 260)
            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight
                model: box.popup.visible ? box.delegateModel : null
                currentIndex: box.highlightedIndex
            }
            background: Rectangle {
                radius: Theme.radius
                color: Theme.surface
                border.width: 1
                border.color: Theme.border
            }
        }
    }
}

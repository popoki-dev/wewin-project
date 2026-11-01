import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../themes"

// Labelled text input with a leading icon, optional password reveal toggle
// and an optional trailing status item.
ColumnLayout {
    id: root

    property alias text: field.text
    property alias placeholderText: field.placeholderText
    property alias field: field
    property string label
    property string iconName
    property bool password: false
    property bool invalid: false
    property alias trailing: trailingSlot.data
    property alias labelAccessory: labelAccessorySlot.data

    signal accepted()

    spacing: 6

    function forceFocus() { field.forceActiveFocus() }

    RowLayout {
        Layout.fillWidth: true
        visible: root.label.length > 0
        Label {
            text: root.label
            color: Theme.text
            font.pixelSize: 13
            font.weight: Font.Medium
            Layout.fillWidth: true
        }
        Row { id: labelAccessorySlot }
    }

    TextField {
        id: field

        property bool revealed: false

        Layout.fillWidth: true
        implicitHeight: Theme.controlHeight
        leftPadding: root.iconName ? 40 : 14
        rightPadding: (root.password ? 40 : 14) + trailingSlot.width
        color: Theme.text
        placeholderTextColor: Theme.textFaint
        selectionColor: Theme.accent
        selectedTextColor: Theme.accentText
        font.pixelSize: 14
        echoMode: root.password && !revealed ? TextInput.Password : TextInput.Normal
        selectByMouse: true
        onAccepted: root.accepted()

        background: Rectangle {
            radius: Theme.radius
            color: Theme.inputBackground
            border.width: 1
            border.color: root.invalid ? Theme.danger
                        : field.activeFocus ? Theme.accent
                        : field.hovered ? Theme.borderStrong : Theme.border
            Behavior on border.color { ColorAnimation { duration: Theme.animationMs } }

            // Focus ring
            Rectangle {
                anchors.fill: parent
                anchors.margins: -3
                radius: parent.radius + 3
                color: "transparent"
                border.width: 3
                border.color: root.invalid ? Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.22) : Theme.focusRing
                opacity: field.activeFocus ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Theme.animationMs } }
            }
        }

        Icon {
            visible: root.iconName.length > 0
            name: root.iconName
            color: field.activeFocus ? Theme.accent : Theme.textFaint
            anchors.left: parent.left
            anchors.leftMargin: 13
            anchors.verticalCenter: parent.verticalCenter
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: root.password ? 6 : 12
            anchors.verticalCenter: parent.verticalCenter
            spacing: 4

            Row {
                id: trailingSlot
                anchors.verticalCenter: parent.verticalCenter
            }

            ToolButton {
                id: revealButton
                visible: root.password
                width: 32; height: 32
                focusPolicy: Qt.NoFocus
                hoverEnabled: true
                onClicked: field.revealed = !field.revealed
                ToolTip.visible: hovered
                ToolTip.delay: 500
                ToolTip.text: field.revealed ? qsTr("Hide password") : qsTr("Show password")
                Accessible.name: ToolTip.text
                background: Rectangle {
                    radius: Theme.radiusSmall
                    color: revealButton.hovered ? Theme.surfaceHover : "transparent"
                }
                contentItem: Item {
                    Icon {
                        anchors.centerIn: parent
                        name: field.revealed ? "eyeOff" : "eye"
                        color: revealButton.hovered ? Theme.text : Theme.textFaint
                    }
                }
            }
        }
    }
}

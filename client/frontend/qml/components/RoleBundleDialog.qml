import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"

// Create or edit a role bundle: a name, a description and a set of permissions.
AppDialog {
    id: dialog

    property int bundleId: 0
    property var selected: []

    function openNew() {
        bundleId = 0
        nameField.text = ""
        descriptionField.text = ""
        selected = []
        MembersViewModel.clearMessages()
        open()
    }
    function openFor(bundle) {
        bundleId = bundle.id
        nameField.text = bundle.name
        descriptionField.text = bundle.description
        selected = bundle.permissions.slice()
        MembersViewModel.clearMessages()
        open()
    }
    function toggle(value, on) {
        const next = selected.filter(v => v !== value)
        if (on) next.push(value)
        selected = next
        MembersViewModel.fieldEdited("bundlePermissions")
    }
    function save() {
        if (bundleId > 0)
            MembersViewModel.updateBundle(bundleId, nameField.text, descriptionField.text, selected)
        else
            MembersViewModel.createBundle(nameField.text, descriptionField.text, selected)
    }

    title: bundleId > 0 ? qsTr("Edit role bundle") : qsTr("New role bundle")
    subtitle: qsTr("Members holding this bundle get these permissions on top of their base role.")
    iconName: "key"
    width: Math.min(560, (parent ? parent.width : 560) - 32)

    onOpened: nameField.forceFocus()

    Connections {
        target: MembersViewModel
        function onBundleSaved() { if (dialog.opened) dialog.close() }
    }

    AppTextField {
        id: nameField
        Layout.fillWidth: true
        label: qsTr("Name")
        placeholderText: qsTr("e.g. Onboarding")
        field.maximumLength: 60
        invalid: MembersViewModel.errorFields.indexOf("bundleName") >= 0
        field.onTextEdited: MembersViewModel.fieldEdited("bundleName")
        onAccepted: descriptionField.forceFocus()
    }
    AppTextField {
        id: descriptionField
        Layout.fillWidth: true
        label: qsTr("Description (optional)")
        placeholderText: qsTr("What this bundle is for")
        field.maximumLength: 300
        onAccepted: dialog.save()
    }

    Label {
        text: qsTr("Permissions")
        color: MembersViewModel.errorFields.indexOf("bundlePermissions") >= 0 ? Theme.danger : Theme.text
        font.pixelSize: 13
        font.weight: Font.Medium
    }

    Repeater {
        model: MembersViewModel.permissionCatalog
        delegate: ColumnLayout {
            id: group
            required property var modelData
            Layout.fillWidth: true
            spacing: 8

            Label {
                text: group.modelData.group
                color: Theme.textMuted
                font.pixelSize: 12
                font.weight: Font.DemiBold
                font.capitalization: Font.AllUppercase
            }
            Repeater {
                model: group.modelData.permissions
                delegate: RowLayout {
                    id: permRow
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 10
                    AppCheckBox {
                        readonly property bool on: dialog.selected.indexOf(permRow.modelData.value) >= 0
                        checked: on
                        onToggled: {
                            dialog.toggle(permRow.modelData.value, checked)
                            checked = Qt.binding(() => on)  // `selected` stays the single source of truth
                        }
                        Accessible.name: permRow.modelData.label
                    }
                    ColumnLayout {
                        spacing: 0
                        Layout.fillWidth: true
                        Label {
                            text: permRow.modelData.label
                            color: Theme.text
                            font.pixelSize: 13
                            TapHandler {
                                onTapped: dialog.toggle(permRow.modelData.value,
                                                        dialog.selected.indexOf(permRow.modelData.value) < 0)
                            }
                        }
                        Label {
                            Layout.fillWidth: true
                            text: permRow.modelData.description
                            color: Theme.textFaint
                            font.pixelSize: 12
                            wrapMode: Text.Wrap
                        }
                    }
                }
            }
        }
    }

    Banner {
        Layout.fillWidth: true
        kind: "error"
        text: MembersViewModel.errorMessage
    }

    AppButton {
        Layout.fillWidth: true
        text: dialog.bundleId > 0 ? qsTr("Save bundle") : qsTr("Create bundle")
        busy: MembersViewModel.busy
        enabled: !MembersViewModel.busy
        onClicked: dialog.save()
    }
}

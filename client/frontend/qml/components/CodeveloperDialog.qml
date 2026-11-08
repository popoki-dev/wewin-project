import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"

// Add, edit or view one co-developer of the project being edited. Nothing is saved here:
// `accepted` hands the entry back to the project dialog, which saves it with the project.
AppDialog {
    id: dialog

    property int index: -1              // -1: a new co-developer
    property bool readOnly: false
    property int rowId: 0
    property string problem: ""

    signal accepted(int index, var row)

    function openNew() {
        fill(-1, { id: 0, nationality: "", name: "", external_id: "", contact: "" }, false)
    }
    function openFor(index, row, readOnly) {
        fill(index, row, readOnly)
    }
    function fill(index, row, readOnly) {
        dialog.index = index
        dialog.readOnly = readOnly
        rowId = row.id || 0
        nationalityField.text = row.nationality
        nameField.text = row.name
        idField.text = row.external_id
        contactField.text = row.contact || ""
        problem = ""
        open()
    }
    function entry() {
        return { id: rowId, nationality: nationalityField.text, name: nameField.text,
                 external_id: idField.text, contact: contactField.text }
    }
    function accept() {
        const row = entry()
        problem = ProjectsViewModel.codeveloperProblem(row)
        if (problem) return
        accepted(index, row)
        close()
    }

    title: readOnly ? qsTr("Co-developer") : index < 0 ? qsTr("Add co-developer") : qsTr("Edit co-developer")
    subtitle: readOnly ? "" : qsTr("Enter a nationality, a name or an ID (at least one). Contact details are optional.")
    iconName: "users"
    z: 10  // above the project dialog
    onOpened: if (!readOnly) nameField.forceFocus()

    AppTextField {
        id: nameField
        Layout.fillWidth: true
        label: qsTr("Name")
        placeholderText: qsTr("e.g. Aiko Tanaka")
        field.readOnly: dialog.readOnly
        field.maximumLength: 200
        field.onTextEdited: dialog.problem = ""
        field.onAccepted: dialog.accept()
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: 12
        AppTextField {
            id: idField
            Layout.fillWidth: true
            label: qsTr("ID")
            placeholderText: qsTr("e.g. a platform username")
            field.readOnly: dialog.readOnly
            field.maximumLength: 100
            field.onTextEdited: dialog.problem = ""
            field.onAccepted: dialog.accept()
        }
        AppTextField {
            id: nationalityField
            Layout.fillWidth: true
            label: qsTr("Nationality")
            placeholderText: qsTr("e.g. Japan")
            field.readOnly: dialog.readOnly
            field.maximumLength: 100
            field.onTextEdited: dialog.problem = ""
            field.onAccepted: dialog.accept()
        }
    }
    AppTextField {
        id: contactField
        Layout.fillWidth: true
        label: qsTr("Contact (optional)")
        placeholderText: qsTr("Email, phone, messenger…")
        field.readOnly: dialog.readOnly
        field.maximumLength: 300
        field.onAccepted: dialog.accept()
    }

    Banner { Layout.fillWidth: true; kind: "error"; text: dialog.problem }

    RowLayout {
        Layout.fillWidth: true
        spacing: 10
        AppButton {
            variant: "secondary"
            text: dialog.readOnly ? qsTr("Close") : qsTr("Cancel")
            Layout.fillWidth: true
            onClicked: dialog.close()
        }
        AppButton {
            visible: !dialog.readOnly
            Layout.fillWidth: true
            text: dialog.index < 0 ? qsTr("Add") : qsTr("Done")
            onClicked: dialog.accept()
        }
    }
}

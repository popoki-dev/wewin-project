import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"

// Add, edit or view one payment of the project being edited: what was received, your
// portion, what each co-developer was paid and where the money is kept. Nothing is saved
// here: `accepted` hands the entry back to the project dialog, which saves it with the project.
AppDialog {
    id: dialog

    property int index: -1              // -1: a new payment
    property bool readOnly: false
    // The project's co-developers as [{value: position, text}], for the payouts.
    property var codevOptions: []
    // The entry being edited: {id, paid_on, description, amount, my_share, fund_location,
    // payouts: [{codeveloper_index, amount}]}, amounts as typed.
    property var row: ({})
    property int tick: 0
    property string problem: ""
    readonly property var summary: (tick, ProjectsViewModel.paymentRemaining(row))

    signal accepted(int index, var row)

    function openNew() {
        fill(-1, { id: 0, paid_on: ProjectsViewModel.today(), description: "", amount: "", my_share: "",
                   fund_location: "", payouts: [] }, false)
    }
    function openFor(index, entry, readOnly) {
        fill(index, entry, readOnly)
    }
    function fill(index, entry, readOnly) {
        dialog.index = index
        dialog.readOnly = readOnly
        // A copy, so Cancel leaves the project's entry untouched.
        row = Object.assign({}, entry, { payouts: entry.payouts.map(o => Object.assign({}, o)) })
        dateField.text = row.paid_on
        descriptionField.text = row.description
        amountField.text = row.amount
        shareField.text = row.my_share
        locationField.text = row.fund_location
        problem = ""
        tick++
        open()
    }
    // Payout rows get a copy of their item from the Repeater, so edits are written back
    // into `row` itself (without replacing it, which would rebuild the rows mid-typing).
    function set(key, value) {
        row[key] = value
        edited()
    }
    function setPayout(i, key, value) {
        row.payouts[i][key] = value
        edited()
    }
    function addPayout() {
        // Suggest the first co-developer not yet paid in this payment.
        const used = row.payouts.map(o => o.codeveloper_index)
        const next = codevOptions.findIndex((_, i) => used.indexOf(i) < 0)
        row = Object.assign({}, row, { payouts: row.payouts.concat([{ codeveloper_index: next, amount: "" }]) })
        edited()
    }
    function removePayout(i) {
        row = Object.assign({}, row, { payouts: row.payouts.filter((_, n) => n !== i) })
        edited()
    }
    function edited() {
        tick++
        problem = ""
    }
    function accept() {
        problem = ProjectsViewModel.paymentProblem(row, codevOptions.length)
        if (problem) return
        accepted(index, row)
        close()
    }

    title: readOnly ? qsTr("Payment") : index < 0 ? qsTr("Add payment") : qsTr("Edit payment")
    subtitle: readOnly ? "" : qsTr("Your portion and the payouts may not add up to more than the total received.")
    iconName: "chart"
    width: Math.min(560, (parent ? parent.width : 560) - 32)
    z: 10  // above the project dialog
    onOpened: if (!readOnly) descriptionField.forceFocus()

    RowLayout {
        Layout.fillWidth: true
        spacing: 12
        AppTextField {
            id: dateField
            Layout.preferredWidth: 150
            Layout.maximumWidth: 150
            label: qsTr("Date")
            placeholderText: "YYYY-MM-DD"
            field.readOnly: dialog.readOnly
            field.maximumLength: 10
            field.validator: RegularExpressionValidator { regularExpression: /[0-9-]{0,10}/ }
            field.onTextEdited: dialog.set("paid_on", text)
        }
        AppTextField {
            id: descriptionField
            Layout.fillWidth: true
            label: qsTr("Description")
            placeholderText: qsTr("e.g. Milestone 1")
            field.readOnly: dialog.readOnly
            field.maximumLength: 300
            field.onTextEdited: dialog.set("description", text)
        }
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: 12
        AppTextField {
            id: amountField
            Layout.fillWidth: true
            label: qsTr("Total received (USD)")
            placeholderText: "0.00"
            field.readOnly: dialog.readOnly
            field.inputMethodHints: Qt.ImhFormattedNumbersOnly
            field.horizontalAlignment: TextInput.AlignRight
            field.onTextEdited: dialog.set("amount", text)
        }
        AppTextField {
            id: shareField
            Layout.fillWidth: true
            label: qsTr("Your portion (USD)")
            placeholderText: "0.00"
            field.readOnly: dialog.readOnly
            field.inputMethodHints: Qt.ImhFormattedNumbersOnly
            field.horizontalAlignment: TextInput.AlignRight
            field.onTextEdited: dialog.set("my_share", text)
        }
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 4
        AppTextField {
            id: locationField
            Layout.fillWidth: true
            label: qsTr("Funds kept at")
            placeholderText: qsTr("e.g. Wise USD account")
            field.readOnly: dialog.readOnly
            field.maximumLength: 200
            field.onTextEdited: dialog.set("fund_location", text)
        }
        // Places used before, matching what is typed.
        Flow {
            readonly property string typed: (dialog.tick, dialog.row.fund_location || "")
            readonly property var matches: ProjectsViewModel.fundLocations
                .filter(l => l !== typed && l.toLowerCase().indexOf(typed.toLowerCase()) >= 0).slice(0, 4)
            visible: !dialog.readOnly && locationField.field.activeFocus && matches.length > 0
            Layout.fillWidth: true
            spacing: 10
            Repeater {
                model: parent.matches
                delegate: LinkButton {
                    required property string modelData
                    text: modelData
                    font.pixelSize: 12
                    onClicked: {
                        locationField.text = modelData
                        dialog.set("fund_location", modelData)
                    }
                }
            }
        }
    }

    // Payouts to co-developers.
    RowLayout {
        Layout.fillWidth: true
        Label {
            Layout.fillWidth: true
            text: qsTr("Paid to co-developers")
            color: Theme.text
            font.pixelSize: 13
            font.weight: Font.Medium
        }
        LinkButton {
            visible: !dialog.readOnly && dialog.codevOptions.length > (dialog.row.payouts || []).length
            text: qsTr("+ Pay a co-developer")
            font.pixelSize: 12
            onClicked: dialog.addPayout()
        }
    }
    Label {
        visible: (dialog.row.payouts || []).length === 0
        Layout.fillWidth: true
        wrapMode: Text.Wrap
        text: dialog.codevOptions.length === 0
              ? qsTr("The project has no co-developers. Add them in the project to record payouts to them.")
              : qsTr("No payouts in this payment.")
        color: Theme.textFaint
        font.pixelSize: 12
    }
    Repeater {
        model: dialog.row.payouts || []
        delegate: RowLayout {
            id: payoutRow
            required property var modelData
            required property int index
            Layout.fillWidth: true
            spacing: 8
            AppComboBox {
                id: payoutWho
                Layout.fillWidth: true
                model: dialog.codevOptions
                box.enabled: !dialog.readOnly
                Component.onCompleted: selectValue(payoutRow.modelData.codeveloper_index)
                onActivated: dialog.setPayout(payoutRow.index, "codeveloper_index", payoutWho.currentValue)
            }
            AppTextField {
                Layout.preferredWidth: 150
                Layout.maximumWidth: 150
                placeholderText: "0.00"
                text: payoutRow.modelData.amount
                field.readOnly: dialog.readOnly
                field.inputMethodHints: Qt.ImhFormattedNumbersOnly
                field.horizontalAlignment: TextInput.AlignRight
                field.onTextEdited: dialog.setPayout(payoutRow.index, "amount", text)
            }
            ToolButton {
                id: removePayoutButton
                visible: !dialog.readOnly
                implicitWidth: 32
                implicitHeight: 32
                hoverEnabled: true
                Accessible.name: qsTr("Remove payout")
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Remove payout")
                onClicked: dialog.removePayout(payoutRow.index)
                background: Rectangle { radius: Theme.radiusSmall; color: removePayoutButton.hovered ? Theme.surfaceHover : "transparent" }
                contentItem: Item { Icon { anchors.centerIn: parent; name: "close"; color: removePayoutButton.hovered ? Theme.danger : Theme.textMuted } }
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Item { Layout.fillWidth: true }
        Label {
            text: dialog.summary.text ? qsTr("Remaining %1").arg(dialog.summary.text) : ""
            color: dialog.summary.over ? Theme.danger : Theme.text
            font.pixelSize: 14
            font.weight: Font.DemiBold
        }
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

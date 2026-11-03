import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"

// Create, edit or view a project with its payment history. A project the user may not
// change (locked by a check, or out of their reach) opens read-only, with the reason shown.
AppDialog {
    id: dialog

    property var project: null          // null: a new project
    property bool confirmingDelete: false
    // Payment rows being edited: [{id, paid_on, description, amount}] (amount in dollars, as typed).
    property var payments: []
    property string paidText: ""
    readonly property bool editable: project === null || project.access.edit
    readonly property bool isNew: project === null

    function openNew() {
        project = null
        fill({ title: "", start_date: ProjectsViewModel.today(), end_date: null, category: "fixed",
               total_budget_cents: null, monthly_budget_cents: null, details: "", team_id: null, payments: [] })
        open()
    }
    function openFor(p) {
        project = p
        fill(p)
        open()
    }
    function fill(p) {
        confirmingDelete = false
        titleField.text = p.title
        startField.text = p.start_date
        endField.text = p.end_date || ""
        categoryBox.selectValue(p.category)
        totalField.text = ProjectsViewModel.moneyInput(p.total_budget_cents)
        monthlyField.text = ProjectsViewModel.moneyInput(p.monthly_budget_cents)
        detailsArea.text = p.details
        const teams = AuthViewModel.isOwner ? MembersViewModel.teams : MembersViewModel.scopeTeams
        teamBox.model = (AuthViewModel.isOwner ? [{ value: 0, text: qsTr("No team") }] : [])
            .concat(teams.map(t => ({ value: t.id, text: t.name })))
        teamBox.selectValue(p.team_id || (AuthViewModel.isOwner ? 0 : teams.length === 1 ? teams[0].id : -1))
        payments = p.payments.map(x => ({ id: x.id, paid_on: x.paid_on, description: x.description,
                                          amount: ProjectsViewModel.moneyInput(x.amount_cents) }))
        recalc()
        ProjectsViewModel.clearMessages()
    }
    function addPayment() {
        payments = payments.concat([{ id: 0, paid_on: ProjectsViewModel.today(), description: "", amount: "" }])
        recalc()
        ProjectsViewModel.fieldEdited("payments")
    }
    function removePayment(index) {
        payments = payments.filter((_, i) => i !== index)
        recalc()
        ProjectsViewModel.fieldEdited("payments")
    }
    // Rows get a copy of their payment from the Repeater, so edits are written back into
    // `payments` itself (without replacing the array, which would rebuild the rows mid-typing).
    function setPayment(index, key, value) {
        payments[index][key] = value
        if (key === "amount") recalc()
        ProjectsViewModel.fieldEdited("payments")
    }
    function recalc() {
        let cents = 0
        for (const row of payments) {
            const n = Number(String(row.amount).replace(/[$,\s]/g, ""))
            if (isFinite(n) && n > 0) cents += Math.round(n * 100)
        }
        paidText = ProjectsViewModel.money(cents)
    }
    function save() {
        ProjectsViewModel.saveProject(
            isNew ? 0 : project.id, titleField.text, startField.text, endField.text,
            categoryBox.currentValue !== undefined ? categoryBox.currentValue : "",
            totalField.text, monthlyField.text, detailsArea.text,
            teamBox.visible && teamBox.currentValue !== undefined ? teamBox.currentValue : 0,
            payments)
    }
    function lockReason() {
        if (isNew || project.access.edit) return ""
        if (project.owner_check) return qsTr("Checked by the Owner (%1) — it can no longer be changed.").arg(project.owner_check.by || "")
        if (project.leader_check) return qsTr("Checked by a Team Leader (%1) — it can no longer be changed.").arg(project.leader_check.by || "")
        return qsTr("You can view this project but not change it.")
    }

    title: confirmingDelete ? qsTr("Delete “%1”?").arg(project ? project.title : "")
         : isNew ? qsTr("New project") : editable ? qsTr("Edit project") : qsTr("Project")
    subtitle: confirmingDelete ? qsTr("The project and its payment history are removed for good. The audit log keeps a record.")
            : isNew ? qsTr("The start date is today unless you change it; the completion date may stay blank.")
            : project.team_name ? qsTr("%1 · created by %2").arg(project.team_name).arg(project.created_by_name || qsTr("a deleted account"))
            : qsTr("No team · created by %1").arg(project.created_by_name || qsTr("a deleted account"))
    iconName: confirmingDelete ? "alert" : "folder"
    width: Math.min(720, (parent ? parent.width : 720) - 32)

    onOpened: if (editable) titleField.forceFocus()
    onClosed: if (ProjectsViewModel.errorMessage) ProjectsViewModel.clearMessages()

    Connections {
        target: ProjectsViewModel
        function onProjectSaved() { if (dialog.opened) dialog.close() }
        function onProjectDeleted() { if (dialog.opened) dialog.close() }
    }

    // ---------------------------------------------------------------- form
    ColumnLayout {
        visible: !dialog.confirmingDelete
        Layout.fillWidth: true
        spacing: 14

        Banner { Layout.fillWidth: true; kind: "error"; text: dialog.opened ? dialog.lockReason() : "" }

        AppTextField {
            id: titleField
            Layout.fillWidth: true
            label: qsTr("Title")
            iconName: "folder"
            placeholderText: qsTr("e.g. Website redesign")
            field.readOnly: !dialog.editable
            field.maximumLength: ProjectsViewModel.titleMaxLength
            invalid: ProjectsViewModel.errorFields.indexOf("title") >= 0
            field.onTextEdited: ProjectsViewModel.fieldEdited("title")
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            AppTextField {
                id: startField
                Layout.fillWidth: true
                label: qsTr("Start date")
                placeholderText: "YYYY-MM-DD"
                field.readOnly: !dialog.editable
                field.maximumLength: 10
                field.validator: RegularExpressionValidator { regularExpression: /[0-9-]{0,10}/ }
                invalid: ProjectsViewModel.errorFields.indexOf("startDate") >= 0
                field.onTextEdited: ProjectsViewModel.fieldEdited("startDate")
            }
            AppTextField {
                id: endField
                Layout.fillWidth: true
                label: qsTr("Completion date (optional)")
                placeholderText: "YYYY-MM-DD"
                field.readOnly: !dialog.editable
                field.maximumLength: 10
                field.validator: RegularExpressionValidator { regularExpression: /[0-9-]{0,10}/ }
                invalid: ProjectsViewModel.errorFields.indexOf("endDate") >= 0
                field.onTextEdited: ProjectsViewModel.fieldEdited("endDate")
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            AppComboBox {
                id: categoryBox
                Layout.fillWidth: true
                label: qsTr("Category")
                model: ProjectsViewModel.categories
                box.enabled: dialog.editable
                invalid: ProjectsViewModel.errorFields.indexOf("category") >= 0
                onActivated: ProjectsViewModel.fieldEdited("totalBudget")  // the total may now be optional
            }
            AppComboBox {
                id: teamBox
                // Members' projects always belong to their own team.
                visible: AuthViewModel.isOwner || AuthViewModel.userRole === "team_leader"
                Layout.fillWidth: true
                label: qsTr("Team")
                box.enabled: dialog.editable
                invalid: ProjectsViewModel.errorFields.indexOf("team") >= 0
                onActivated: ProjectsViewModel.fieldEdited("team")
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            AppTextField {
                id: totalField
                Layout.fillWidth: true
                // Hourly projects may have no overall budget.
                label: categoryBox.currentValue === "hourly" ? qsTr("Total budget (USD, optional)") : qsTr("Total budget (USD)")
                placeholderText: categoryBox.currentValue === "hourly" ? qsTr("No limit") : qsTr("e.g. 12,000.00")
                field.readOnly: !dialog.editable
                field.inputMethodHints: Qt.ImhFormattedNumbersOnly
                invalid: ProjectsViewModel.errorFields.indexOf("totalBudget") >= 0
                field.onTextEdited: ProjectsViewModel.fieldEdited("totalBudget")
            }
            AppTextField {
                id: monthlyField
                Layout.fillWidth: true
                label: qsTr("Monthly budget (USD, optional)")
                placeholderText: qsTr("e.g. 1,000.00")
                field.readOnly: !dialog.editable
                field.inputMethodHints: Qt.ImhFormattedNumbersOnly
                invalid: ProjectsViewModel.errorFields.indexOf("monthlyBudget") >= 0
                field.onTextEdited: ProjectsViewModel.fieldEdited("monthlyBudget")
            }
        }

        // ---------------------------------------------------------- payments
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 4
            Label {
                text: qsTr("Payment history")
                color: ProjectsViewModel.errorFields.indexOf("payments") >= 0 ? Theme.danger : Theme.text
                font.pixelSize: 13
                font.weight: Font.Medium
            }
            Label {
                Layout.fillWidth: true
                text: dialog.payments.length > 0 ? qsTr("Paid %1").arg(dialog.paidText) : ""
                color: Theme.textMuted
                font.pixelSize: 12
            }
            AppButton {
                visible: dialog.editable
                variant: "secondary"
                iconName: "plus"
                text: qsTr("Add payment")
                implicitHeight: 32
                font.pixelSize: 12
                onClicked: dialog.addPayment()
            }
        }
        Label {
            visible: dialog.payments.length === 0
            text: qsTr("No payments yet.")
            color: Theme.textFaint
            font.pixelSize: 12
        }
        Repeater {
            model: dialog.payments
            delegate: RowLayout {
                id: paymentRow
                required property var modelData
                required property int index
                Layout.fillWidth: true
                spacing: 8
                // Edits go into dialog.payments (see setPayment); the rows are only rebuilt on add/remove.
                AppTextField {
                    Layout.preferredWidth: 130
                    Layout.maximumWidth: 130
                    placeholderText: "YYYY-MM-DD"
                    text: paymentRow.modelData.paid_on
                    field.readOnly: !dialog.editable
                    field.maximumLength: 10
                    field.validator: RegularExpressionValidator { regularExpression: /[0-9-]{0,10}/ }
                    field.onTextEdited: dialog.setPayment(paymentRow.index, "paid_on", text)
                }
                AppTextField {
                    Layout.fillWidth: true
                    placeholderText: qsTr("Description")
                    text: paymentRow.modelData.description
                    field.readOnly: !dialog.editable
                    field.maximumLength: 300
                    field.onTextEdited: dialog.setPayment(paymentRow.index, "description", text)
                }
                AppTextField {
                    Layout.preferredWidth: 140
                    Layout.maximumWidth: 140
                    placeholderText: qsTr("Amount")
                    text: paymentRow.modelData.amount
                    field.readOnly: !dialog.editable
                    field.inputMethodHints: Qt.ImhFormattedNumbersOnly
                    field.horizontalAlignment: TextInput.AlignRight
                    field.onTextEdited: dialog.setPayment(paymentRow.index, "amount", text)
                }
                ToolButton {
                    id: removeButton
                    visible: dialog.editable
                    width: 32; height: 32
                    hoverEnabled: true
                    onClicked: dialog.removePayment(paymentRow.index)
                    Accessible.name: qsTr("Remove payment")
                    ToolTip.visible: hovered
                    ToolTip.text: qsTr("Remove payment")
                    background: Rectangle { radius: Theme.radiusSmall; color: removeButton.hovered ? Theme.surfaceHover : "transparent" }
                    contentItem: Item { Icon { anchors.centerIn: parent; name: "close"; color: removeButton.hovered ? Theme.danger : Theme.textMuted } }
                }
            }
        }

        // ----------------------------------------------------------- details
        Label { text: qsTr("Details"); color: Theme.text; font.pixelSize: 13; font.weight: Font.Medium; Layout.topMargin: 4 }
        ScrollView {
            id: detailsScroll
            Layout.fillWidth: true
            Layout.preferredHeight: 180
            clip: true
            background: Rectangle {
                radius: Theme.radius
                color: Theme.inputBackground
                border.width: 1
                border.color: detailsArea.activeFocus ? Theme.accent : Theme.border
            }
            TextArea {
                id: detailsArea
                // Plain text, shown and saved exactly as typed: line breaks, tabs and spaces included.
                textFormat: TextEdit.PlainText
                wrapMode: TextEdit.Wrap
                readOnly: !dialog.editable
                selectByMouse: true
                placeholderText: dialog.editable ? qsTr("Scope, contacts, notes… Line breaks are kept.") : ""
                color: Theme.text
                placeholderTextColor: Theme.textFaint
                selectionColor: Theme.accent
                selectedTextColor: Theme.accentText
                font.pixelSize: 13
                padding: 12
                background: null
                onTextChanged: if (length > ProjectsViewModel.detailsMaxLength) remove(ProjectsViewModel.detailsMaxLength, length)
            }
        }

        Banner { Layout.fillWidth: true; kind: "error"; text: dialog.opened ? ProjectsViewModel.errorMessage : "" }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            AppButton {
                visible: !dialog.isNew && dialog.project.access.delete
                variant: "secondary"
                text: qsTr("Delete…")
                implicitWidth: 110
                onClicked: { ProjectsViewModel.clearMessages(); dialog.confirmingDelete = true }
            }
            Item { Layout.fillWidth: true; visible: !dialog.editable }
            AppButton {
                visible: dialog.editable
                Layout.fillWidth: true
                text: dialog.isNew ? qsTr("Create project") : qsTr("Save changes")
                busy: ProjectsViewModel.busy
                enabled: !ProjectsViewModel.busy
                onClicked: dialog.save()
            }
            AppButton {
                visible: !dialog.editable
                variant: "secondary"
                text: qsTr("Close")
                implicitWidth: 110
                onClicked: dialog.close()
            }
        }
    }

    // ------------------------------------------------------ confirm delete
    ColumnLayout {
        visible: dialog.confirmingDelete
        Layout.fillWidth: true
        spacing: 16
        Banner { Layout.fillWidth: true; kind: "error"; text: dialog.opened ? ProjectsViewModel.errorMessage : "" }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            AppButton {
                variant: "secondary"
                text: qsTr("Cancel")
                Layout.fillWidth: true
                onClicked: dialog.confirmingDelete = false
            }
            Button {
                id: deleteButton
                Layout.fillWidth: true
                implicitHeight: Theme.controlHeight
                enabled: !ProjectsViewModel.busy
                hoverEnabled: true
                text: qsTr("Delete project")
                font.pixelSize: 14
                font.weight: Font.DemiBold
                onClicked: ProjectsViewModel.deleteProject(dialog.project)
                background: Rectangle {
                    radius: Theme.radius
                    color: deleteButton.hovered ? Qt.darker(Theme.danger, 1.1) : Theme.danger
                    opacity: deleteButton.enabled ? 1 : 0.55
                }
                contentItem: Label {
                    text: deleteButton.text
                    font: deleteButton.font
                    color: "#ffffff"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }
}

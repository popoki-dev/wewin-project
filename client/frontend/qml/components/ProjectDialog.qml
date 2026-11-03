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
    // Co-developer rows being edited: [{id, nationality, name, external_id}].
    property var codevs: []
    // Payment rows being edited: [{id, paid_on, description, amount, my_share, fund_location,
    // payouts: [{codeveloper_index, amount}]}], amounts in dollars as typed. A payout names its
    // co-developer by position in `codevs`.
    property var payments: []
    property string paidText: ""
    // Bumped on every edit, so bindings that read the (unnotified) rows re-evaluate.
    property int tick: 0
    readonly property var codevOptions: (tick, codevs.map((c, i) => ({ value: i, text: codevLabel(c, i) })))
    readonly property bool editable: project === null || project.access.edit
    readonly property bool isNew: project === null

    function openNew() {
        project = null
        fill({ title: "", start_date: ProjectsViewModel.today(), end_date: null, category: "fixed",
               total_budget_cents: null, monthly_budget_cents: null, details: "", team_id: null,
               codevelopers: [], payments: [] })
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
        codevs = p.codevelopers.map(c => ({ id: c.id, nationality: c.nationality, name: c.name,
                                            external_id: c.external_id }))
        const position = {}
        p.codevelopers.forEach((c, i) => position[c.id] = i)
        payments = p.payments.map(x => ({
            id: x.id, paid_on: x.paid_on, description: x.description,
            amount: ProjectsViewModel.moneyInput(x.amount_cents),
            my_share: x.my_share_cents ? ProjectsViewModel.moneyInput(x.my_share_cents) : "",
            fund_location: x.fund_location,
            payouts: x.payouts.map(o => ({ codeveloper_index: position[o.codeveloper_id],
                                           amount: ProjectsViewModel.moneyInput(o.amount_cents) }))
        }))
        changed()
        ProjectsViewModel.clearMessages()
    }
    function codevLabel(c, i) {
        const parts = [c.name, c.external_id, c.nationality].filter(x => x && x.trim().length > 0)
        return parts.length ? parts.join(" · ") : qsTr("Co-developer %1").arg(i + 1)
    }
    function changed() {
        tick++
        let cents = 0
        for (const row of payments) {
            const n = Number(String(row.amount).replace(/[$,\s]/g, ""))
            if (isFinite(n) && n > 0) cents += Math.round(n * 100)
        }
        paidText = ProjectsViewModel.money(cents)
    }

    // Rows get a copy of their item from the Repeater, so edits are written back into
    // `codevs` / `payments` themselves (without replacing the arrays, which would rebuild
    // the rows mid-typing). Adding and removing rows does replace them.
    function setCodev(index, key, value) {
        codevs[index][key] = value
        changed()
        ProjectsViewModel.fieldEdited("codevelopers")
    }
    function addCodev() {
        codevs = codevs.concat([{ id: 0, nationality: "", name: "", external_id: "" }])
        changed()
    }
    function removeCodev(index) {
        codevs = codevs.filter((_, i) => i !== index)
        // Their payouts go too; later co-developers move up one place.
        payments = payments.map(pay => Object.assign({}, pay, {
            payouts: pay.payouts.filter(o => o.codeveloper_index !== index)
                .map(o => ({ codeveloper_index: o.codeveloper_index > index ? o.codeveloper_index - 1 : o.codeveloper_index,
                             amount: o.amount }))
        }))
        changed()
        ProjectsViewModel.fieldEdited("codevelopers")
        ProjectsViewModel.fieldEdited("payments")
    }
    function setPayment(index, key, value) {
        payments[index][key] = value
        changed()
        ProjectsViewModel.fieldEdited("payments")
    }
    function addPayment() {
        payments = payments.concat([{ id: 0, paid_on: ProjectsViewModel.today(), description: "", amount: "",
                                      my_share: "", fund_location: "", payouts: [] }])
        changed()
        ProjectsViewModel.fieldEdited("payments")
    }
    function removePayment(index) {
        payments = payments.filter((_, i) => i !== index)
        changed()
        ProjectsViewModel.fieldEdited("payments")
    }
    function setPayout(paymentIndex, payoutIndex, key, value) {
        payments[paymentIndex].payouts[payoutIndex][key] = value
        changed()
        ProjectsViewModel.fieldEdited("payments")
    }
    function addPayout(paymentIndex) {
        // Suggest the first co-developer not yet paid in this payment.
        const used = payments[paymentIndex].payouts.map(o => o.codeveloper_index)
        const next = codevs.findIndex((_, i) => used.indexOf(i) < 0)
        const copy = payments.slice()
        copy[paymentIndex] = Object.assign({}, copy[paymentIndex], {
            payouts: copy[paymentIndex].payouts.concat([{ codeveloper_index: next, amount: "" }])
        })
        payments = copy
        changed()
    }
    function removePayout(paymentIndex, payoutIndex) {
        const copy = payments.slice()
        copy[paymentIndex] = Object.assign({}, copy[paymentIndex], {
            payouts: copy[paymentIndex].payouts.filter((_, i) => i !== payoutIndex)
        })
        payments = copy
        changed()
        ProjectsViewModel.fieldEdited("payments")
    }
    function save() {
        ProjectsViewModel.saveProject(
            isNew ? 0 : project.id, titleField.text, startField.text, endField.text,
            categoryBox.currentValue !== undefined ? categoryBox.currentValue : "",
            totalField.text, monthlyField.text, detailsArea.text,
            teamBox.visible && teamBox.currentValue !== undefined ? teamBox.currentValue : 0,
            codevs, payments)
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

        // ----------------------------------------------------- co-developers
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 4
            Label {
                Layout.fillWidth: true
                text: qsTr("Co-developers")
                color: ProjectsViewModel.errorFields.indexOf("codevelopers") >= 0 ? Theme.danger : Theme.text
                font.pixelSize: 13
                font.weight: Font.Medium
            }
            AppButton {
                visible: dialog.editable
                variant: "secondary"
                iconName: "plus"
                text: qsTr("Add co-developer")
                implicitHeight: 32
                font.pixelSize: 12
                onClicked: dialog.addCodev()
            }
        }
        Label {
            visible: dialog.codevs.length === 0
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: qsTr("No co-developers. Add the people this project's income is shared with (nationality, name or ID).")
            color: Theme.textFaint
            font.pixelSize: 12
        }
        Repeater {
            model: dialog.codevs
            delegate: RowLayout {
                id: codevRow
                required property var modelData
                required property int index
                Layout.fillWidth: true
                spacing: 8
                AppTextField {
                    Layout.preferredWidth: 150
                    Layout.maximumWidth: 150
                    placeholderText: qsTr("Nationality")
                    text: codevRow.modelData.nationality
                    field.readOnly: !dialog.editable
                    field.maximumLength: 100
                    field.onTextEdited: dialog.setCodev(codevRow.index, "nationality", text)
                }
                AppTextField {
                    Layout.fillWidth: true
                    placeholderText: qsTr("Name")
                    text: codevRow.modelData.name
                    field.readOnly: !dialog.editable
                    field.maximumLength: 200
                    field.onTextEdited: dialog.setCodev(codevRow.index, "name", text)
                }
                AppTextField {
                    Layout.preferredWidth: 160
                    Layout.maximumWidth: 160
                    placeholderText: qsTr("ID")
                    text: codevRow.modelData.external_id
                    field.readOnly: !dialog.editable
                    field.maximumLength: 100
                    field.onTextEdited: dialog.setCodev(codevRow.index, "external_id", text)
                }
                RemoveButton {
                    visible: dialog.editable
                    label: qsTr("Remove co-developer (and their payouts)")
                    onClicked: dialog.removeCodev(codevRow.index)
                }
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
                text: dialog.payments.length > 0 ? qsTr("Received %1").arg(dialog.paidText) : ""
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
            delegate: Rectangle {
                id: paymentCard
                required property var modelData
                required property int index
                readonly property var summary: (dialog.tick, ProjectsViewModel.paymentRemaining(dialog.payments[index] || {}))
                Layout.fillWidth: true
                implicitHeight: paymentBody.implicitHeight + 24
                radius: Theme.radius
                color: Theme.surfaceAlt
                border.width: 1
                border.color: Theme.border

                ColumnLayout {
                    id: paymentBody
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    // Date, description, total received.
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        AppTextField {
                            Layout.preferredWidth: 130
                            Layout.maximumWidth: 130
                            label: qsTr("Date")
                            placeholderText: "YYYY-MM-DD"
                            text: paymentCard.modelData.paid_on
                            field.readOnly: !dialog.editable
                            field.maximumLength: 10
                            field.validator: RegularExpressionValidator { regularExpression: /[0-9-]{0,10}/ }
                            field.onTextEdited: dialog.setPayment(paymentCard.index, "paid_on", text)
                        }
                        AppTextField {
                            Layout.fillWidth: true
                            label: qsTr("Description")
                            placeholderText: qsTr("e.g. Milestone 1")
                            text: paymentCard.modelData.description
                            field.readOnly: !dialog.editable
                            field.maximumLength: 300
                            field.onTextEdited: dialog.setPayment(paymentCard.index, "description", text)
                        }
                        AppTextField {
                            Layout.preferredWidth: 150
                            Layout.maximumWidth: 150
                            label: qsTr("Total received")
                            placeholderText: "0.00"
                            text: paymentCard.modelData.amount
                            field.readOnly: !dialog.editable
                            field.inputMethodHints: Qt.ImhFormattedNumbersOnly
                            field.horizontalAlignment: TextInput.AlignRight
                            field.onTextEdited: dialog.setPayment(paymentCard.index, "amount", text)
                        }
                        RemoveButton {
                            visible: dialog.editable
                            Layout.alignment: Qt.AlignBottom
                            label: qsTr("Remove payment")
                            onClicked: dialog.removePayment(paymentCard.index)
                        }
                    }

                    // Your portion and where the money is kept.
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        AppTextField {
                            Layout.preferredWidth: 150
                            Layout.maximumWidth: 150
                            label: qsTr("Your portion")
                            placeholderText: "0.00"
                            text: paymentCard.modelData.my_share
                            field.readOnly: !dialog.editable
                            field.inputMethodHints: Qt.ImhFormattedNumbersOnly
                            field.horizontalAlignment: TextInput.AlignRight
                            field.onTextEdited: dialog.setPayment(paymentCard.index, "my_share", text)
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            AppTextField {
                                id: locationField
                                Layout.fillWidth: true
                                label: qsTr("Funds kept at")
                                placeholderText: qsTr("e.g. Wise USD account")
                                text: paymentCard.modelData.fund_location
                                field.readOnly: !dialog.editable
                                field.maximumLength: 200
                                field.onTextEdited: dialog.setPayment(paymentCard.index, "fund_location", text)
                            }
                            // Places used before, matching what is typed.
                            Flow {
                                readonly property string typed: (dialog.tick, (dialog.payments[paymentCard.index] || {}).fund_location || "")
                                readonly property var matches: ProjectsViewModel.fundLocations
                                    .filter(l => l !== typed && l.toLowerCase().indexOf(typed.toLowerCase()) >= 0).slice(0, 4)
                                visible: dialog.editable && locationField.field.activeFocus && matches.length > 0
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
                                            dialog.setPayment(paymentCard.index, "fund_location", modelData)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // Payouts to co-developers.
                    Repeater {
                        model: paymentCard.modelData.payouts
                        delegate: RowLayout {
                            id: payoutRow
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true
                            spacing: 8
                            Label { text: qsTr("Paid to"); color: Theme.textMuted; font.pixelSize: 12 }
                            AppComboBox {
                                id: payoutWho
                                Layout.fillWidth: true
                                model: dialog.codevOptions
                                box.enabled: dialog.editable
                                Component.onCompleted: selectValue(payoutRow.modelData.codeveloper_index)
                                onModelChanged: selectValue((dialog.payments[paymentCard.index].payouts[payoutRow.index] || {}).codeveloper_index)
                                onActivated: dialog.setPayout(paymentCard.index, payoutRow.index, "codeveloper_index", currentValue)
                            }
                            AppTextField {
                                Layout.preferredWidth: 150
                                Layout.maximumWidth: 150
                                placeholderText: "0.00"
                                text: payoutRow.modelData.amount
                                field.readOnly: !dialog.editable
                                field.inputMethodHints: Qt.ImhFormattedNumbersOnly
                                field.horizontalAlignment: TextInput.AlignRight
                                field.onTextEdited: dialog.setPayout(paymentCard.index, payoutRow.index, "amount", text)
                            }
                            RemoveButton {
                                visible: dialog.editable
                                label: qsTr("Remove payout")
                                onClicked: dialog.removePayout(paymentCard.index, payoutRow.index)
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        LinkButton {
                            visible: dialog.editable && dialog.codevs.length > paymentCard.modelData.payouts.length
                            text: qsTr("+ Pay a co-developer")
                            font.pixelSize: 12
                            onClicked: dialog.addPayout(paymentCard.index)
                        }
                        Label {
                            visible: dialog.editable && dialog.codevs.length === 0
                            text: qsTr("Add co-developers above to record payouts to them.")
                            color: Theme.textFaint
                            font.pixelSize: 12
                        }
                        Item { Layout.fillWidth: true }
                        Label {
                            text: paymentCard.summary.text ? qsTr("Remaining %1").arg(paymentCard.summary.text) : ""
                            color: paymentCard.summary.over ? Theme.danger : Theme.text
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }
                    }
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

    component RemoveButton: ToolButton {
        id: removeButton
        property string label
        implicitWidth: 32
        implicitHeight: 32
        hoverEnabled: true
        Accessible.name: label
        ToolTip.visible: hovered
        ToolTip.text: label
        background: Rectangle { radius: Theme.radiusSmall; color: removeButton.hovered ? Theme.surfaceHover : "transparent" }
        contentItem: Item { Icon { anchors.centerIn: parent; name: "close"; color: removeButton.hovered ? Theme.danger : Theme.textMuted } }
    }
}

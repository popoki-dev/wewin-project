import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"

// Create, edit or view a project with its payment history. Co-developers and payments are
// listed in tables and added or edited in their own windows (CodeveloperDialog, PaymentDialog). A project the user may not
// change (locked by a check, or out of their reach) opens read-only, with the reason shown.
AppDialog {
    id: dialog

    property var project: null          // null: a new project
    property bool confirmingDelete: false
    // Co-developer rows being edited: [{id, nationality, name, external_id, contact}].
    property var codevs: []
    // Payment rows being edited: [{id, paid_on, description, amount, my_share, fund_location,
    // payouts: [{codeveloper_index, amount}]}], amounts in dollars as typed. A payout names its
    // co-developer by position in `codevs`.
    property var payments: []
    // Expected revenue rows being edited: [{year, month, amount}], year and amount as typed.
    property var forecasts: []
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
               project_owner_id: null, project_owner_name: null, codevelopers: [], payments: [],
               revenue_forecasts: [] })
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
        fillProjectOwners(p)
        codevs = p.codevelopers.map(c => ({ id: c.id, nationality: c.nationality, name: c.name,
                                            external_id: c.external_id, contact: c.contact }))
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
        forecasts = p.revenue_forecasts.map(f => ({ year: String(f.year), month: f.month,
                                                    amount: ProjectsViewModel.moneyInput(f.amount_cents) }))
        changed()
        ProjectsViewModel.clearMessages()
    }
    // The people the user may make project owner, plus the current owner if they are not
    // among them (kept on save). New projects start with the user themselves.
    function fillProjectOwners(p) {
        const teamNames = {}
        MembersViewModel.teams.forEach(t => teamNames[t.id] = t.name)
        const options = ProjectsViewModel.projectOwnerOptions.map(o => ({
            value: o.id, team_id: o.team_id,
            text: o.email === AuthViewModel.userEmail ? qsTr("%1 (you)").arg(o.name)
                  : o.team_id && teamNames[o.team_id] ? qsTr("%1 · %2").arg(o.name).arg(teamNames[o.team_id]) : o.name
        }))
        if (p.project_owner_id && !options.some(o => o.value === p.project_owner_id))
            options.push({ value: p.project_owner_id, team_id: null, text: p.project_owner_name || "" })
        if (!isNew && !p.project_owner_id)
            options.unshift({ value: 0, team_id: null, text: qsTr("None (account deleted)") })
        projectOwnerBox.model = options
        if (isNew) {
            const me = ProjectsViewModel.projectOwnerOptions.find(o => o.email === AuthViewModel.userEmail)
            projectOwnerBox.selectValue(me ? me.id : -1)
        } else {
            projectOwnerBox.selectValue(p.project_owner_id || 0)
        }
    }
    // Picking someone on a team the project may be filed under files it there too.
    function projectOwnerPicked() {
        const option = projectOwnerBox.model[projectOwnerBox.currentIndex]
        if (option && option.team_id && teamBox.visible && teamBox.model.some(t => t.value === option.team_id))
            teamBox.selectValue(option.team_id)
        ProjectsViewModel.fieldEdited("projectOwner")
        ProjectsViewModel.fieldEdited("team")
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

    // Co-developers and payments are added and edited in their own windows; the tables
    // here show them. Each change replaces the array, so the tables rebuild.
    function codevAccepted(index, row) {
        codevs = index < 0 ? codevs.concat([row]) : codevs.map((c, i) => i === index ? row : c)
        changed()
        ProjectsViewModel.fieldEdited("codevelopers")
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
    function paymentAccepted(index, row) {
        payments = index < 0 ? payments.concat([row]) : payments.map((x, i) => i === index ? row : x)
        changed()
        ProjectsViewModel.fieldEdited("payments")
    }
    function removePayment(index) {
        payments = payments.filter((_, i) => i !== index)
        changed()
        ProjectsViewModel.fieldEdited("payments")
    }
    function openPayment(index) {
        paymentDialog.codevOptions = codevOptions
        if (index < 0) paymentDialog.openNew()
        else paymentDialog.openFor(index, payments[index], !editable)
    }
    function setForecast(index, key, value) {
        forecasts[index][key] = value
        changed()
        ProjectsViewModel.fieldEdited("forecasts")
    }
    // A new row is for the month after the last one (this month when there is none).
    function addForecast() {
        let year, month
        const last = forecasts.length ? forecasts[forecasts.length - 1] : null
        if (last && Number(last.year) > 0 && last.month >= 1) {
            year = Number(last.year) + (last.month === 12 ? 1 : 0)
            month = last.month === 12 ? 1 : last.month + 1
        } else {
            const today = new Date()
            year = today.getFullYear()
            month = today.getMonth() + 1
        }
        forecasts = forecasts.concat([{ year: String(year), month: month, amount: "" }])
        changed()
        ProjectsViewModel.fieldEdited("forecasts")
    }
    function removeForecast(index) {
        forecasts = forecasts.filter((_, i) => i !== index)
        changed()
        ProjectsViewModel.fieldEdited("forecasts")
    }
    function save() {
        ProjectsViewModel.saveProject(
            isNew ? 0 : project.id, titleField.text, startField.text, endField.text,
            categoryBox.currentValue !== undefined ? categoryBox.currentValue : "",
            totalField.text, monthlyField.text, detailsArea.text,
            teamBox.visible && teamBox.currentValue !== undefined ? teamBox.currentValue : 0,
            ProjectsViewModel.canChooseProjectOwner && projectOwnerBox.currentValue !== undefined
                ? projectOwnerBox.currentValue : 0,
            codevs, payments, forecasts)
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
    width: Math.min(880, (parent ? parent.width : 880) - 32)

    onOpened: if (editable) titleField.forceFocus()
    onClosed: if (ProjectsViewModel.errorMessage) ProjectsViewModel.clearMessages()

    CodeveloperDialog {
        id: codevDialog
        onAccepted: (index, row) => dialog.codevAccepted(index, row)
    }
    PaymentDialog {
        id: paymentDialog
        onAccepted: (index, row) => dialog.paymentAccepted(index, row)
    }

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

        AppComboBox {
            id: projectOwnerBox
            Layout.fillWidth: true
            label: qsTr("Project owner")
            // Members' projects are always their own, so they only see who it is.
            box.enabled: dialog.editable && ProjectsViewModel.canChooseProjectOwner
            invalid: ProjectsViewModel.errorFields.indexOf("projectOwner") >= 0
            onActivated: dialog.projectOwnerPicked()
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

        // -------------------------------------------------- expected revenue
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 4
            Label {
                text: qsTr("Expected monthly revenue")
                color: ProjectsViewModel.errorFields.indexOf("forecasts") >= 0 ? Theme.danger : Theme.text
                font.pixelSize: 13
                font.weight: Font.Medium
            }
            Label {
                Layout.fillWidth: true
                text: (dialog.tick, dialog.forecasts.length > 0
                       ? qsTr("Expected %1").arg(ProjectsViewModel.expectedTotal(dialog.forecasts)) : "")
                color: Theme.textMuted
                font.pixelSize: 12
            }
            AppButton {
                visible: dialog.editable
                variant: "secondary"
                iconName: "plus"
                text: qsTr("Add month")
                implicitHeight: 32
                font.pixelSize: 12
                onClicked: dialog.addForecast()
            }
        }
        Label {
            visible: dialog.forecasts.length === 0
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: qsTr("No expected revenue yet. Add the revenue you expect for each month.")
            color: Theme.textFaint
            font.pixelSize: 12
        }
        Repeater {
            model: dialog.forecasts
            delegate: RowLayout {
                id: forecastRow
                required property var modelData
                required property int index
                Layout.fillWidth: true
                spacing: 8
                AppTextField {
                    Layout.preferredWidth: 100
                    Layout.maximumWidth: 100
                    placeholderText: qsTr("Year")
                    text: forecastRow.modelData.year
                    field.readOnly: !dialog.editable
                    field.maximumLength: 4
                    field.inputMethodHints: Qt.ImhDigitsOnly
                    field.validator: RegularExpressionValidator { regularExpression: /[0-9]{0,4}/ }
                    field.onTextEdited: dialog.setForecast(forecastRow.index, "year", text)
                }
                AppComboBox {
                    id: monthBox
                    Layout.fillWidth: true
                    model: ProjectsViewModel.months
                    box.enabled: dialog.editable
                    Component.onCompleted: selectValue(forecastRow.modelData.month)
                    onActivated: dialog.setForecast(forecastRow.index, "month", monthBox.currentValue)
                }
                AppTextField {
                    Layout.preferredWidth: 170
                    Layout.maximumWidth: 170
                    placeholderText: qsTr("Expected (USD)")
                    text: forecastRow.modelData.amount
                    field.readOnly: !dialog.editable
                    field.inputMethodHints: Qt.ImhFormattedNumbersOnly
                    field.horizontalAlignment: TextInput.AlignRight
                    field.onTextEdited: dialog.setForecast(forecastRow.index, "amount", text)
                }
                RemoveButton {
                    visible: dialog.editable
                    label: qsTr("Remove month")
                    onClicked: dialog.removeForecast(forecastRow.index)
                }
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
                onClicked: codevDialog.openNew()
            }
        }
        Label {
            visible: dialog.codevs.length === 0
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: qsTr("No co-developers. Add the people this project's income is shared with (nationality, name or ID, plus optional contact details).")
            color: Theme.textFaint
            font.pixelSize: 12
        }
        Table {
            visible: dialog.codevs.length > 0
            Layout.fillWidth: true
            columns: [
                { title: qsTr("Name"), fill: true },
                { title: qsTr("ID"), width: 120 },
                { title: qsTr("Nationality"), width: 110 },
                { title: qsTr("Contact"), fill: true },
            ]
            rows: dialog.codevs.map(c => [c.name || "—", c.external_id || "—", c.nationality || "—", c.contact || "—"])
            editable: dialog.editable
            removeLabel: qsTr("Remove co-developer (and their payouts)")
            onOpenRow: i => codevDialog.openFor(i, dialog.codevs[i], !dialog.editable)
            onRemoveRow: i => dialog.removeCodev(i)
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
                onClicked: dialog.openPayment(-1)
            }
        }
        Label {
            visible: dialog.payments.length === 0
            text: qsTr("No payments yet.")
            color: Theme.textFaint
            font.pixelSize: 12
        }
        Table {
            visible: dialog.payments.length > 0
            Layout.fillWidth: true
            columns: [
                { title: qsTr("Date"), width: 86 },
                { title: qsTr("Description"), fill: true },
                { title: qsTr("Received"), width: 96, right: true },
                { title: qsTr("Your portion"), width: 96, right: true },
                { title: qsTr("Paid out"), width: 90, right: true },
                { title: qsTr("Remaining"), width: 96, right: true, strong: true },
                { title: qsTr("Kept at"), width: 100 },
            ]
            rows: (dialog.tick, dialog.payments.map(x => {
                const sum = ProjectsViewModel.paymentSummary(x)
                return [x.paid_on, x.description || "—", sum.total, sum.mine, sum.paid_out,
                        sum.remaining, x.fund_location || "—"]
            }))
            dangerCells: (dialog.tick, dialog.payments.map(x => ProjectsViewModel.paymentSummary(x).over ? [5] : []))
            editable: dialog.editable
            removeLabel: qsTr("Remove payment")
            onOpenRow: i => dialog.openPayment(i)
            onRemoveRow: i => dialog.removePayment(i)
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

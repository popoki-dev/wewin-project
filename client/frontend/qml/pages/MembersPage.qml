import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"
import "../components"

// Owner: every team and member. Everyone else: their own team, with whatever their
// permissions (base role plus role bundles) allow. The server enforces the same rules.
Item {
    id: page

    readonly property bool owner: AuthViewModel.isOwner
    readonly property bool wide: width >= 960
    readonly property bool canAdd: AuthViewModel.permissions.indexOf("members.add") >= 0
    // Reserve an action column only when some row on this page uses it, so the name and
    // team get the room otherwise.
    readonly property bool anyEdit: MembersViewModel.pagedMembers.some(m => MembersViewModel.canEditMember(m))
    readonly property bool anyRoles: MembersViewModel.pagedMembers.some(m => MembersViewModel.canEditRoles(m))
    readonly property bool anyReset: MembersViewModel.pagedMembers.some(m => MembersViewModel.canResetDevice(m))
    // Dialogs show their own errors; the page banner would only repeat them behind the overlay.
    readonly property bool dialogOpen: addDialog.opened || editDialog.opened || rolesDialog.opened

    function roleLabel(role) {
        return role === "owner" ? qsTr("Owner") : role === "team_leader" ? qsTr("Team Leader") : qsTr("Member")
    }
    function statusLabel(m) {
        if (!m.is_active) return qsTr("Disabled")
        if (m.must_change_password) return m.device_registered ? qsTr("Must change password") : qsTr("Not signed in yet")
        return m.device_registered ? qsTr("Device registered") : qsTr("No device registered")
    }

    Component.onCompleted: MembersViewModel.refresh()

    Connections {
        target: MembersViewModel
    }

    MemberAddDialog { id: addDialog; objectName: "memberAddDialog" }
    MemberRolesDialog { id: rolesDialog; objectName: "memberRolesDialog" }
    MemberEditDialog { id: editDialog; objectName: "memberEditDialog" }

    // Title, messages and the People card's header, filters and pagination stay put;
    // only the member rows scroll (see listScroller).
    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 40
        anchors.bottomMargin: 24
        spacing: 20

        // ------------------------------------------------------- header
        RowLayout {
            Layout.leftMargin: 40
            Layout.rightMargin: 40
            Layout.fillWidth: true
            spacing: 12
            ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                Label { text: qsTr("Members"); color: Theme.text; font.pixelSize: 28; font.weight: Font.Bold; Layout.fillWidth: true }
                Label {
                    text: page.owner ? qsTr("Everyone in your organization.") : AuthViewModel.scopeTeamIds.length > 1 ? qsTr("Members of the teams you lead.") : qsTr("Members of your team.")
                    color: Theme.textMuted
                    font.pixelSize: 14
                }
            }
            AppButton {
                variant: "secondary"
                iconName: "refresh"
                text: qsTr("Refresh")
                busy: MembersViewModel.busy
                enabled: !MembersViewModel.busy
                onClicked: { MembersViewModel.clearMessages(); MembersViewModel.refresh() }
            }
        }

        Banner {
            Layout.leftMargin: 40
            Layout.rightMargin: 40
            Layout.fillWidth: true
            kind: "error"
            text: page.dialogOpen ? "" : MembersViewModel.errorMessage
        }
        Banner {
            Layout.leftMargin: 40
            Layout.rightMargin: 40
            Layout.fillWidth: true
            kind: "success"
            text: MembersViewModel.errorMessage ? "" : MembersViewModel.notice
        }

        // ------------------------------------------------------ members list
        Card {
            Layout.leftMargin: 40
            Layout.rightMargin: 40
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: qsTr("People")
            subtitle: MembersViewModel.filterActive
                      ? qsTr("Showing %1 of %2").arg(MembersViewModel.filteredMembers.length).arg(MembersViewModel.members.length)
                      : MembersViewModel.members.length === 1 ? qsTr("1 account")
                      : qsTr("%1 accounts").arg(MembersViewModel.members.length)
            actions: [
                AppButton {
                    visible: page.canAdd
                    iconName: "plus"
                    text: qsTr("Add member")
                    implicitHeight: 38
                    enabled: !MembersViewModel.busy
                    onClicked: addDialog.openNew()
                }
            ]

            // ------------------------------------------------- filters
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    AppTextField {
                        id: searchField
                        Layout.fillWidth: true
                        iconName: "search"
                        placeholderText: qsTr("Search name or email")
                        text: MembersViewModel.filterText
                        field.onTextEdited: MembersViewModel.setFilterText(text)
                    }
                    AppComboBox {
                        id: roleFilter
                        Layout.preferredWidth: 160
                        model: [{ value: "", text: qsTr("All roles") },
                                { value: "owner", text: qsTr("Owner") },
                                { value: "team_leader", text: qsTr("Team Leader") },
                                { value: "member", text: qsTr("Member") }]
                        Component.onCompleted: selectValue(MembersViewModel.filterRole)
                        onActivated: MembersViewModel.setFilterRole(currentValue)
                        // Follow the filter however it changes (e.g. Clear filters).
                        Connections {
                            target: MembersViewModel
                            function onFilterChanged() { roleFilter.selectValue(MembersViewModel.filterRole) }
                        }
                    }
                    AppComboBox {
                        id: teamFilter
                        Layout.preferredWidth: 180
                        model: [{ value: -1, text: qsTr("All teams") }, { value: 0, text: qsTr("No team") }]
                               .concat(MembersViewModel.teams.map(t => ({ value: t.id, text: t.name })))
                        Component.onCompleted: selectValue(MembersViewModel.filterTeamId)
                        onModelChanged: selectValue(MembersViewModel.filterTeamId)
                        onActivated: MembersViewModel.setFilterTeam(currentValue)
                        Connections {
                            target: MembersViewModel
                            function onFilterChanged() { teamFilter.selectValue(MembersViewModel.filterTeamId) }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Label { text: qsTr("Registered"); color: Theme.textMuted; font.pixelSize: 13 }
                    AppTextField {
                        id: fromField
                        Layout.preferredWidth: 170
                        Layout.maximumWidth: 170
                        placeholderText: qsTr("From YYYY-MM-DD")
                        text: MembersViewModel.filterFrom
                        field.maximumLength: 10
                        field.inputMethodHints: Qt.ImhDate
                        field.validator: RegularExpressionValidator { regularExpression: /[0-9-]{0,10}/ }
                        invalid: MembersViewModel.filterErrorFields.indexOf("dateFrom") >= 0
                        field.onTextEdited: MembersViewModel.setFilterDates(text, toField.text)
                    }
                    Label { text: "–"; color: Theme.textMuted }
                    AppTextField {
                        id: toField
                        Layout.preferredWidth: 170
                        Layout.maximumWidth: 170
                        placeholderText: qsTr("To YYYY-MM-DD")
                        text: MembersViewModel.filterTo
                        field.maximumLength: 10
                        field.inputMethodHints: Qt.ImhDate
                        field.validator: RegularExpressionValidator { regularExpression: /[0-9-]{0,10}/ }
                        invalid: MembersViewModel.filterErrorFields.indexOf("dateTo") >= 0
                        field.onTextEdited: MembersViewModel.setFilterDates(fromField.text, text)
                    }
                    Label {
                        Layout.fillWidth: true
                        text: MembersViewModel.filterError
                        color: Theme.danger
                        font.pixelSize: 12
                        elide: Text.ElideRight
                    }
                    AppButton {
                        visible: MembersViewModel.filterActive
                        variant: "ghost"
                        iconName: "close"
                        text: qsTr("Clear filters")
                        implicitHeight: 36
                        font.pixelSize: 12
                        onClicked: MembersViewModel.clearFilters()
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

            ScrollView {
                id: listScroller
                objectName: "memberListScroller"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 120
                contentWidth: availableWidth
                clip: true
                // Show the scrollbar whenever the rows overflow, beside (not over) the row buttons.
                readonly property bool overflowing: contentHeight > height
                rightPadding: overflowing ? 16 : 0
                ScrollBar.vertical.policy: overflowing ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded

                // A new page or filter starts at the top of the list.
                Connections {
                    target: MembersViewModel
                    function onFilterChanged() { listScroller.contentItem.contentY = 0 }
                }

                ColumnLayout {
                    width: listScroller.availableWidth
                    spacing: 10

                Label {
                    visible: MembersViewModel.members.length > 0 && MembersViewModel.filteredMembers.length === 0
                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    horizontalAlignment: Text.AlignHCenter
                    text: qsTr("No one matches these filters.")
                    color: Theme.textFaint
                    font.pixelSize: 13
                }

                Repeater {
                    model: MembersViewModel.pagedMembers
                    delegate: ColumnLayout {
                        id: row
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        spacing: 10

                        Rectangle { visible: row.index > 0; Layout.fillWidth: true; height: 1; color: Theme.border }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            Rectangle {
                                width: 34; height: 34; radius: 17
                                color: Theme.accentSoft
                                Label {
                                    anchors.centerIn: parent
                                    text: (row.modelData.full_name || row.modelData.email).charAt(0).toUpperCase()
                                    color: Theme.accent
                                    font.weight: Font.Bold
                                }
                            }
                            ColumnLayout {
                                spacing: 0
                                Layout.fillWidth: true
                                Label {
                                    text: row.modelData.full_name || row.modelData.email
                                    color: Theme.text; font.pixelSize: 14; font.weight: Font.DemiBold
                                    elide: Text.ElideRight; Layout.fillWidth: true
                                }
                                Label {
                                    text: row.modelData.full_name ? row.modelData.email : ""
                                    visible: text.length > 0
                                    color: Theme.textMuted; font.pixelSize: 12
                                    elide: Text.ElideRight; Layout.fillWidth: true
                                }
                                Label {
                                    visible: row.modelData.role_bundles.length > 0
                                    text: qsTr("+ %1").arg(row.modelData.role_bundles.map(b => b.name).join(", "))
                                    color: Theme.accent; font.pixelSize: 12
                                    elide: Text.ElideRight; Layout.fillWidth: true
                                }
                                TeamCell {
                                    visible: !page.wide && row.modelData.role !== "owner"  // the Owner has no team
                                    Layout.fillWidth: true
                                    member: row.modelData
                                }
                            }
                            // Team column (wide windows); narrow windows show it under the email.
                            TeamCell {
                                visible: page.wide
                                Layout.preferredWidth: 110
                                Layout.maximumWidth: 110
                                member: row.modelData
                            }
                            Item {
                                // Fixed-width column, so the team column lines up across rows.
                                Layout.preferredWidth: 110
                                implicitHeight: 24
                                Rectangle {
                                    width: roleText.implicitWidth + 16
                                    height: 24
                                    radius: 12
                                    color: row.modelData.role === "member" ? Theme.surfaceAlt : Theme.accentSoft
                                    Label {
                                        id: roleText
                                        anchors.centerIn: parent
                                        text: page.roleLabel(row.modelData.role)
                                        color: row.modelData.role === "member" ? Theme.textMuted : Theme.accent
                                        font.pixelSize: 12; font.weight: Font.Medium
                                    }
                                }
                            }
                            Label {
                                Layout.preferredWidth: 130
                                horizontalAlignment: Text.AlignRight
                                text: page.statusLabel(row.modelData)
                                color: row.modelData.must_change_password ? Theme.warning : Theme.textFaint
                                font.pixelSize: 12
                                elide: Text.ElideRight
                            }
                            AppButton {
                                variant: "ghost"
                                implicitWidth: 64
                                implicitHeight: 34
                                font.pixelSize: 12
                                text: qsTr("Edit")
                                visible: MembersViewModel.canEditMember(row.modelData)
                                enabled: !MembersViewModel.busy
                                onClicked: editDialog.openFor(row.modelData)
                            }
                            Item { visible: page.anyEdit && !MembersViewModel.canEditMember(row.modelData); implicitWidth: 64 }
                            AppButton {
                                variant: "ghost"
                                implicitWidth: 70
                                implicitHeight: 34
                                font.pixelSize: 12
                                text: qsTr("Roles")
                                visible: MembersViewModel.canEditRoles(row.modelData)
                                enabled: !MembersViewModel.busy
                                onClicked: rolesDialog.openFor(row.modelData)
                            }
                            Item { visible: page.anyRoles && !MembersViewModel.canEditRoles(row.modelData); implicitWidth: 70 }
                            AppButton {
                                variant: "ghost"
                                implicitWidth: 120
                                implicitHeight: 34
                                font.pixelSize: 12
                                text: qsTr("Reset device")
                                visible: MembersViewModel.canResetDevice(row.modelData)
                                enabled: !MembersViewModel.busy
                                ToolTip.visible: hovered
                                ToolTip.delay: 400
                                ToolTip.text: qsTr("Sign this person out and let their next sign-in register a new PC.")
                                onClicked: MembersViewModel.resetDevice(row.modelData.id)
                            }
                            Item { visible: page.anyReset && !MembersViewModel.canResetDevice(row.modelData); implicitWidth: 120 }
                        }
                    }
                }
                }
            }

            // ---------------------------------------------- pagination
            Rectangle {
                visible: MembersViewModel.filteredMembers.length > 0
                Layout.fillWidth: true
                height: 1
                color: Theme.border
            }
            RowLayout {
                visible: MembersViewModel.filteredMembers.length > 0
                Layout.fillWidth: true
                spacing: 10

                Label { text: qsTr("Rows per page"); color: Theme.textMuted; font.pixelSize: 12 }
                AppComboBox {
                    id: pageSizeBox
                    Layout.preferredWidth: 90
                    Layout.maximumWidth: 90
                    model: MembersViewModel.pageSizes.map(n => ({ value: n, text: String(n) }))
                    Component.onCompleted: selectValue(MembersViewModel.pageSize)
                    onActivated: MembersViewModel.setPageSize(currentValue)
                    Connections {
                        target: MembersViewModel
                        function onFilterChanged() { pageSizeBox.selectValue(MembersViewModel.pageSize) }
                    }
                }
                Label {
                    Layout.fillWidth: true
                    text: MembersViewModel.pageRange
                    color: Theme.textMuted
                    font.pixelSize: 12
                }

                AppButton {
                    variant: "ghost"
                    iconName: "back"
                    text: qsTr("Previous")
                    implicitWidth: 104
                    implicitHeight: 34
                    font.pixelSize: 12
                    enabled: MembersViewModel.pageIndex > 0
                    opacity: enabled ? 1 : 0.4
                    onClicked: MembersViewModel.previousPage()
                }
                Repeater {
                    model: MembersViewModel.pageNumbers
                    delegate: Item {
                        id: pageCell
                        required property int modelData
                        readonly property bool current: modelData === MembersViewModel.pageIndex + 1
                        implicitWidth: Math.max(34, numberLabel.implicitWidth + 16)
                        implicitHeight: 34
                        Rectangle {
                            anchors.fill: parent
                            visible: pageCell.modelData > 0
                            radius: Theme.radiusSmall
                            color: pageCell.current ? Theme.accent : pageHover.hovered ? Theme.surfaceHover : "transparent"
                        }
                        Label {
                            id: numberLabel
                            anchors.centerIn: parent
                            text: pageCell.modelData > 0 ? String(pageCell.modelData) : "…"
                            color: pageCell.current ? Theme.accentText : Theme.textMuted
                            font.pixelSize: 13
                            font.weight: pageCell.current ? Font.DemiBold : Font.Normal
                        }
                        HoverHandler {
                            id: pageHover
                            enabled: pageCell.modelData > 0
                            cursorShape: Qt.PointingHandCursor
                        }
                        TapHandler {
                            enabled: pageCell.modelData > 0 && !pageCell.current
                            onTapped: MembersViewModel.setPage(pageCell.modelData - 1)
                        }
                        Accessible.role: Accessible.Button
                        Accessible.name: pageCell.modelData > 0 ? qsTr("Page %1").arg(pageCell.modelData) : ""
                    }
                }
                AppButton {
                    variant: "ghost"
                    text: qsTr("Next")
                    implicitWidth: 80
                    implicitHeight: 34
                    font.pixelSize: 12
                    enabled: MembersViewModel.pageIndex < MembersViewModel.pageCount - 1
                    opacity: enabled ? 1 : 0.4
                    onClicked: MembersViewModel.nextPage()
                }
            }
        }
    }

    // A member's team ("Leads …" for Team Leaders, "No team"), plus a Team Leader's
    // quick moves in and out of their teams. Used in the Team column and, in narrow
    // windows, under the member's email.
    component TeamCell: ColumnLayout {
        id: cell
        property var member: ({})
        spacing: 0
        Label {
            readonly property var led: cell.member.led_teams || []
            Layout.fillWidth: true
            text: led.length > 0 ? qsTr("Leads %1").arg(led.map(t => t.name).join(", "))
                : cell.member.team_name || (cell.member.role === "owner" ? "—" : qsTr("No team"))
            color: cell.member.team_name || led.length > 0 ? Theme.textMuted : Theme.textFaint
            font.pixelSize: 13; elide: Text.ElideRight
            // Long names are cut short to keep the column narrow; hovering shows them in full.
            ToolTip.visible: leadHover.hovered && (truncated || led.length > 1)
            ToolTip.text: text
            HoverHandler { id: leadHover }
        }
        LinkButton {
            id: bringIn
            visible: MembersViewModel.canBringIntoTeam(cell.member)
            text: MembersViewModel.scopeTeams.length > 1 ? qsTr("Add to a team ▾") : qsTr("Add to my team")
            font.pixelSize: 12
            enabled: !MembersViewModel.busy
            onClicked: {
                const scope = MembersViewModel.scopeTeams
                if (scope.length === 1) MembersViewModel.setMemberTeam(cell.member, scope[0].id)
                else teamMenu.popup(bringIn, 0, bringIn.height)
            }
            Menu {
                id: teamMenu
                Instantiator {
                    model: MembersViewModel.scopeTeams
                    delegate: MenuItem {
                        required property var modelData
                        text: modelData.name
                        onTriggered: MembersViewModel.setMemberTeam(cell.member, modelData.id)
                    }
                    onObjectAdded: (index, object) => teamMenu.insertItem(index, object)
                    onObjectRemoved: (index, object) => teamMenu.removeItem(object)
                }
            }
        }
        LinkButton {
            visible: MembersViewModel.canTakeOutOfTeam(cell.member)
            text: qsTr("Remove from team")
            font.pixelSize: 12
            enabled: !MembersViewModel.busy
            onClicked: MembersViewModel.setMemberTeam(cell.member, 0)
        }
    }
}

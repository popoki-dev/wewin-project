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
    readonly property bool canCreateTeams: AuthViewModel.permissions.indexOf("teams.create") >= 0
    readonly property bool canRenameTeams: AuthViewModel.permissions.indexOf("teams.rename") >= 0
    // Role bundles to give the member being added.
    property var addBundles: []

    function toggleAddBundle(id, on) {
        const next = addBundles.filter(v => v !== id)
        if (on) next.push(id)
        addBundles = next
    }

    function roleLabel(role) {
        return role === "owner" ? qsTr("Owner") : role === "team_leader" ? qsTr("Team Leader") : qsTr("Member")
    }
    function statusLabel(m) {
        if (!m.is_active) return qsTr("Disabled")
        if (m.must_change_password) return m.device_registered ? qsTr("Must change password") : qsTr("Not signed in yet")
        return m.device_registered ? qsTr("Device registered") : qsTr("No device registered")
    }
    function teamOptions() {
        return MembersViewModel.teams.map(t => ({ value: t.id, text: t.name }))
    }

    Component.onCompleted: MembersViewModel.refresh()

    Connections {
        target: MembersViewModel
        function onMemberAdded() {
            emailField.text = ""
            nameField.text = ""
            passwordField.text = ""
            page.addBundles = []
        }
        function onTeamCreated() { teamNameField.text = "" }
        function onChanged() {
            // Keep the chosen team; default to the only one a Team Leader can pick.
            const keep = teamBox.currentValue
            teamBox.model = page.teamOptions()
            teamBox.selectValue(keep !== undefined ? keep : (page.owner ? -1 : AuthViewModel.userTeamId))
        }
    }

    MemberRolesDialog { id: rolesDialog; objectName: "memberRolesDialog" }

    AppDialog {
        id: renameDialog
        property var team: ({})
        function openFor(t) {
            team = t
            renameField.text = t.name
            MembersViewModel.clearMessages()
            open()
        }
        title: qsTr("Rename team")
        iconName: "folder"
        onOpened: renameField.forceFocus()

        Connections {
            target: MembersViewModel
            function onTeamRenamed() { if (renameDialog.opened) renameDialog.close() }
        }

        AppTextField {
            id: renameField
            Layout.fillWidth: true
            label: qsTr("Team name")
            field.maximumLength: 100
            invalid: MembersViewModel.errorFields.indexOf("teamName") >= 0
            field.onTextEdited: MembersViewModel.fieldEdited("teamName")
            onAccepted: MembersViewModel.renameTeam(renameDialog.team.id, text)
        }
        Banner { Layout.fillWidth: true; kind: "error"; text: renameDialog.opened ? MembersViewModel.errorMessage : "" }
        AppButton {
            Layout.fillWidth: true
            text: qsTr("Rename")
            busy: MembersViewModel.busy
            enabled: !MembersViewModel.busy
            onClicked: MembersViewModel.renameTeam(renameDialog.team.id, renameField.text)
        }
    }

    ScrollView {
        id: scroller
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true

        ColumnLayout {
            width: scroller.availableWidth
            spacing: 20

            Item { Layout.preferredHeight: 20 }

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
                        text: page.owner ? qsTr("Everyone in your organization.") : qsTr("Members of your team.")
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
                text: MembersViewModel.errorMessage
            }
            Banner {
                Layout.leftMargin: 40
                Layout.rightMargin: 40
                Layout.fillWidth: true
                kind: "success"
                text: MembersViewModel.errorMessage ? "" : MembersViewModel.notice
            }

            GridLayout {
                Layout.leftMargin: 40
                Layout.rightMargin: 40
                Layout.fillWidth: true
                columns: page.wide ? 2 : 1
                columnSpacing: 20
                rowSpacing: 20

                // ------------------------------------------------ add member
                Card {
                    visible: page.canAdd
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    title: qsTr("Add member")
                    subtitle: page.owner ? qsTr("They sign in with the initial password and must change it.")
                                         : qsTr("Members you add join your team.")

                    AppTextField {
                        id: emailField
                        Layout.fillWidth: true
                        label: qsTr("Email")
                        iconName: "mail"
                        placeholderText: "name@company.com"
                        invalid: MembersViewModel.errorFields.indexOf("email") >= 0
                        field.onTextEdited: MembersViewModel.fieldEdited("email")
                        onAccepted: nameField.forceFocus()
                    }
                    AppTextField {
                        id: nameField
                        Layout.fillWidth: true
                        label: qsTr("Full name (optional)")
                        iconName: "users"
                        onAccepted: passwordField.forceFocus()
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        AppComboBox {
                            id: teamBox
                            Layout.fillWidth: true
                            label: qsTr("Team")
                            model: page.teamOptions()
                            box.enabled: page.owner
                            invalid: MembersViewModel.errorFields.indexOf("team") >= 0
                            onActivated: MembersViewModel.fieldEdited("team")
                        }
                        AppComboBox {
                            id: roleBox
                            visible: page.owner
                            Layout.preferredWidth: 170
                            label: qsTr("Role")
                            model: [{ value: "member", text: qsTr("Member") },
                                    { value: "team_leader", text: qsTr("Team Leader") }]
                            currentIndex: 0
                        }
                    }
                    AppTextField {
                        id: passwordField
                        Layout.fillWidth: true
                        label: qsTr("Initial password")
                        iconName: "lock"
                        password: true
                        placeholderText: qsTr("At least 8 characters")
                        invalid: MembersViewModel.errorFields.indexOf("password") >= 0
                        field.onTextEdited: MembersViewModel.fieldEdited("password")
                        onAccepted: addButton.clicked()
                    }
                    ColumnLayout {
                        visible: MembersViewModel.assignableBundleIds.length > 0
                        Layout.fillWidth: true
                        spacing: 6
                        Label { text: qsTr("Role bundles (optional)"); color: Theme.text; font.pixelSize: 13; font.weight: Font.Medium }
                        Flow {
                            Layout.fillWidth: true
                            spacing: 6
                            Repeater {
                                model: MembersViewModel.bundles.filter(b => MembersViewModel.assignableBundleIds.indexOf(b.id) >= 0)
                                delegate: ToggleChip {
                                    required property var modelData
                                    text: modelData.name
                                    checked: page.addBundles.indexOf(modelData.id) >= 0
                                    onToggled: page.toggleAddBundle(modelData.id, checked)
                                    ToolTip.visible: hovered && modelData.description.length > 0
                                    ToolTip.delay: 400
                                    ToolTip.text: modelData.description
                                }
                            }
                        }
                    }
                    AppButton {
                        id: addButton
                        Layout.fillWidth: true
                        iconName: "plus"
                        text: qsTr("Add member")
                        enabled: !MembersViewModel.busy
                        onClicked: MembersViewModel.addMember(
                            emailField.text, nameField.text,
                            teamBox.currentValue !== undefined ? teamBox.currentValue : 0,
                            page.owner ? roleBox.currentValue : "member",
                            passwordField.text, page.addBundles)
                    }
                }

                // ----------------------------------------------------- teams
                Card {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    title: qsTr("Teams")
                    subtitle: page.owner ? qsTr("Every member belongs to one team.") : qsTr("The team you lead.")

                    RowLayout {
                        visible: page.canCreateTeams
                        Layout.fillWidth: true
                        spacing: 10
                        AppTextField {
                            id: teamNameField
                            Layout.fillWidth: true
                            placeholderText: qsTr("New team name")
                            iconName: "folder"
                            invalid: MembersViewModel.errorFields.indexOf("teamName") >= 0
                            field.onTextEdited: MembersViewModel.fieldEdited("teamName")
                            onAccepted: MembersViewModel.createTeam(text)
                        }
                        AppButton {
                            variant: "secondary"
                            iconName: "plus"
                            text: qsTr("Create")
                            implicitWidth: 110
                            enabled: !MembersViewModel.busy
                            onClicked: MembersViewModel.createTeam(teamNameField.text)
                        }
                    }

                    Label {
                        visible: MembersViewModel.teams.length === 0
                        text: page.canCreateTeams ? qsTr("No teams yet. Create one to start adding members.") : qsTr("No team assigned.")
                        color: Theme.textFaint
                        font.pixelSize: 13
                    }

                    Repeater {
                        model: MembersViewModel.teams
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 10
                            Rectangle {
                                width: 30; height: 30; radius: 8
                                color: Theme.accentSoft
                                Icon { anchors.centerIn: parent; name: "users"; width: 16; height: 16; color: Theme.accent }
                            }
                            Label { text: modelData.name; color: Theme.text; font.pixelSize: 14; Layout.fillWidth: true; elide: Text.ElideRight }
                            Label {
                                text: modelData.member_count === 1 ? qsTr("1 member") : qsTr("%1 members").arg(modelData.member_count)
                                color: Theme.textMuted
                                font.pixelSize: 12
                            }
                            AppButton {
                                visible: page.canRenameTeams
                                variant: "ghost"
                                text: qsTr("Rename")
                                implicitWidth: 80
                                implicitHeight: 30
                                font.pixelSize: 12
                                onClicked: renameDialog.openFor(modelData)
                            }
                        }
                    }
                }
            }

            // ------------------------------------------------------ members list
            Card {
                Layout.leftMargin: 40
                Layout.rightMargin: 40
                Layout.fillWidth: true
                title: qsTr("People")
                subtitle: MembersViewModel.members.length === 1 ? qsTr("1 account") : qsTr("%1 accounts").arg(MembersViewModel.members.length)

                Repeater {
                    model: MembersViewModel.members
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
                            }
                            Label {
                                visible: page.wide
                                Layout.preferredWidth: 140
                                text: row.modelData.team_name || "—"
                                color: Theme.textMuted; font.pixelSize: 13; elide: Text.ElideRight
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
                                Layout.preferredWidth: 160
                                horizontalAlignment: Text.AlignRight
                                text: page.statusLabel(row.modelData)
                                color: row.modelData.must_change_password ? Theme.warning : Theme.textFaint
                                font.pixelSize: 12
                                elide: Text.ElideRight
                            }
                            AppButton {
                                variant: "ghost"
                                implicitWidth: 100
                                implicitHeight: 34
                                font.pixelSize: 12
                                text: qsTr("Edit roles")
                                visible: MembersViewModel.canEditRoles(row.modelData)
                                enabled: !MembersViewModel.busy
                                onClicked: rolesDialog.openFor(row.modelData)
                            }
                            Item { visible: !MembersViewModel.canEditRoles(row.modelData); implicitWidth: 100 }
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
                            Item { visible: !MembersViewModel.canResetDevice(row.modelData); implicitWidth: 120 }
                        }
                    }
                }
            }

            Item { Layout.preferredHeight: 20 }
        }
    }

    // A titled surface; children stack vertically below the title.
    component Card: Rectangle {
        id: card
        property string title
        property string subtitle
        default property alias content: body.data

        implicitHeight: body.implicitHeight + 48
        radius: Theme.radiusLarge
        color: Theme.surface
        border.width: 1
        border.color: Theme.border

        ColumnLayout {
            id: body
            anchors.fill: parent
            anchors.margins: 24
            spacing: 14

            ColumnLayout {
                spacing: 2
                Layout.fillWidth: true
                Label { text: card.title; color: Theme.text; font.pixelSize: 16; font.weight: Font.Bold }
                Label {
                    visible: card.subtitle.length > 0
                    Layout.fillWidth: true
                    text: card.subtitle
                    wrapMode: Text.Wrap
                    color: Theme.textMuted
                    font.pixelSize: 12
                }
            }
        }
    }
}

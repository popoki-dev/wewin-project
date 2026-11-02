import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"

// Owner: a team's leaders and members, with Remove on each and an Add picker.
// Lists are read live from MembersViewModel, so they update after every change.
AppDialog {
    id: dialog

    property int teamId: 0
    readonly property var team: MembersViewModel.teams.find(t => t.id === teamId) || ({ name: "", leaders: [] })
    readonly property var leaders: MembersViewModel.members
        .filter(m => (m.led_teams || []).some(t => t.id === teamId))
    readonly property var members: MembersViewModel.members
        .filter(m => m.role === "member" && m.team_id === teamId)
    // Who can be added in the chosen capacity: as member, any plain member not already in
    // this team (they move here); as leader, anyone but the Owner not already leading it.
    readonly property var candidates: MembersViewModel.members.filter(m => asBox.currentValue === "leader"
        ? m.role !== "owner" && !(m.led_teams || []).some(t => t.id === teamId)
        : m.role === "member" && m.team_id !== teamId)

    function openFor(t) {
        teamId = t.id
        asBox.currentIndex = 0
        refreshPeople()
        MembersViewModel.clearMessages()
        open()
    }
    function refreshPeople() {
        personBox.model = candidates.map(m => ({
            value: m.id,
            text: (m.full_name || m.email) + (m.team_name ? " — " + m.team_name
                  : m.role === "team_leader" ? qsTr(" — Team Leader") : qsTr(" — no team"))
        }))
        personBox.currentIndex = -1
    }
    function personById(id) { return MembersViewModel.members.find(m => m.id === id) }
    function displayName(m) { return m.full_name || m.email }

    title: qsTr("Manage “%1”").arg(team.name)
    subtitle: qsTr("Leaders lead this team (and may lead others). Members belong to this team only.")
    iconName: "grid"
    width: Math.min(560, (parent ? parent.width : 560) - 32)

    onClosed: if (MembersViewModel.errorMessage) MembersViewModel.clearMessages()

    Connections {
        target: MembersViewModel
        function onChanged() { if (dialog.opened) dialog.refreshPeople() }
    }

    // ----------------------------------------------------------- leaders
    Label { text: qsTr("Leaders"); color: Theme.text; font.pixelSize: 13; font.weight: Font.DemiBold }
    Label {
        visible: dialog.leaders.length === 0
        text: qsTr("No leader yet.")
        color: Theme.textFaint
        font.pixelSize: 12
    }
    Repeater {
        model: dialog.leaders
        delegate: PersonRow {
            required property var modelData
            person: modelData
            detail: modelData.led_teams.length > 1
                    ? qsTr("Also leads %1").arg(modelData.led_teams.filter(t => t.id !== dialog.teamId).map(t => t.name).join(", "))
                    : qsTr("Leads only this team; removing makes them a Member")
            onRemove: MembersViewModel.removeTeamLeader(dialog.teamId, modelData)
        }
    }

    // ----------------------------------------------------------- members
    Label { text: qsTr("Members"); color: Theme.text; font.pixelSize: 13; font.weight: Font.DemiBold; Layout.topMargin: 6 }
    Label {
        visible: dialog.members.length === 0
        text: qsTr("No members yet.")
        color: Theme.textFaint
        font.pixelSize: 12
    }
    Repeater {
        model: dialog.members
        delegate: PersonRow {
            required property var modelData
            person: modelData
            detail: modelData.email
            onRemove: MembersViewModel.setMemberTeam(modelData, 0)
        }
    }

    // --------------------------------------------------------------- add
    Rectangle { Layout.fillWidth: true; Layout.topMargin: 6; height: 1; color: Theme.border }
    RowLayout {
        Layout.fillWidth: true
        spacing: 10
        AppComboBox {
            id: personBox
            Layout.fillWidth: true
            label: qsTr("Add a person")
        }
        AppComboBox {
            id: asBox
            Layout.preferredWidth: 140
            label: qsTr("As")
            model: [{ value: "member", text: qsTr("Member") }, { value: "leader", text: qsTr("Leader") }]
            currentIndex: 0
            onActivated: dialog.refreshPeople()
        }
    }
    Label {
        visible: personBox.currentValue !== undefined
        Layout.fillWidth: true
        wrapMode: Text.Wrap
        color: Theme.textMuted
        font.pixelSize: 12
        text: {
            const p = dialog.personById(personBox.currentValue)
            if (!p) return ""
            if (asBox.currentValue === "leader")
                return p.role === "member" ? qsTr("%1 becomes a Team Leader and leaves their current team.").arg(dialog.displayName(p))
                                           : qsTr("%1 will lead this team as well.").arg(dialog.displayName(p))
            return p.team_name ? qsTr("%1 moves here from %2.").arg(dialog.displayName(p)).arg(p.team_name) : ""
        }
    }

    Banner { Layout.fillWidth: true; kind: "error"; text: dialog.opened ? MembersViewModel.errorMessage : "" }
    Banner { Layout.fillWidth: true; kind: "success"; text: dialog.opened && !MembersViewModel.errorMessage ? MembersViewModel.notice : "" }

    AppButton {
        Layout.fillWidth: true
        iconName: "plus"
        text: asBox.currentValue === "leader" ? qsTr("Add as leader") : qsTr("Add as member")
        enabled: !MembersViewModel.busy && personBox.currentValue !== undefined
        onClicked: {
            const p = dialog.personById(personBox.currentValue)
            if (!p) return
            if (asBox.currentValue === "leader") MembersViewModel.addTeamLeader(dialog.teamId, p)
            else MembersViewModel.setMemberTeam(p, dialog.teamId)
        }
    }

    component PersonRow: RowLayout {
        id: personRow
        property var person
        property string detail
        signal remove()
        Layout.fillWidth: true
        spacing: 10
        Rectangle {
            width: 30; height: 30; radius: 15
            color: Theme.accentSoft
            Label {
                anchors.centerIn: parent
                text: (personRow.person.full_name || personRow.person.email).charAt(0).toUpperCase()
                color: Theme.accent
                font.weight: Font.Bold
                font.pixelSize: 12
            }
        }
        ColumnLayout {
            spacing: 0
            Layout.fillWidth: true
            Label {
                Layout.fillWidth: true
                text: personRow.person.full_name || personRow.person.email
                color: Theme.text; font.pixelSize: 13; elide: Text.ElideRight
            }
            Label {
                Layout.fillWidth: true
                text: personRow.detail
                color: Theme.textFaint; font.pixelSize: 11; elide: Text.ElideRight
            }
        }
        AppButton {
            variant: "ghost"
            text: qsTr("Remove")
            implicitWidth: 80
            implicitHeight: 30
            font.pixelSize: 12
            enabled: !MembersViewModel.busy
            onClicked: personRow.remove()
        }
    }
}

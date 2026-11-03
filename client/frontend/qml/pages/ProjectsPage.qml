import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"
import "../components"

// Projects the user may see: all (Owner), their teams' (Team Leaders) or their own (members).
// What each user may do with a project comes from the server (project.access).
Item {
    id: page

    readonly property bool wide: width >= 960

    function datesText(p) {
        return p.end_date ? qsTr("%1 → %2").arg(p.start_date).arg(p.end_date) : qsTr("%1 → ongoing").arg(p.start_date)
    }

    ProjectDialog { id: projectDialog; objectName: "projectDialog" }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 40
        anchors.bottomMargin: 24
        spacing: 20

        // --------------------------------------------------------- header
        RowLayout {
            Layout.leftMargin: 40
            Layout.rightMargin: 40
            Layout.fillWidth: true
            spacing: 12
            ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                Label { text: qsTr("Projects"); color: Theme.text; font.pixelSize: 28; font.weight: Font.Bold; Layout.fillWidth: true }
                Label {
                    Layout.fillWidth: true
                    text: AuthViewModel.isOwner ? qsTr("Every project in your organization.")
                        : AuthViewModel.userRole === "team_leader" ? qsTr("Projects of the teams you lead, and your own.")
                        : qsTr("Your projects.")
                    color: Theme.textMuted
                    font.pixelSize: 14
                }
            }
            AppButton {
                variant: "secondary"
                iconName: "refresh"
                text: qsTr("Refresh")
                busy: ProjectsViewModel.busy
                enabled: !ProjectsViewModel.busy
                onClicked: { ProjectsViewModel.clearMessages(); ProjectsViewModel.refresh() }
            }
            AppButton {
                visible: ProjectsViewModel.canCreate
                iconName: "plus"
                text: qsTr("New project")
                enabled: !ProjectsViewModel.busy
                onClicked: projectDialog.openNew()
            }
        }

        Banner {
            Layout.leftMargin: 40
            Layout.rightMargin: 40
            Layout.fillWidth: true
            kind: "error"
            text: projectDialog.opened ? "" : ProjectsViewModel.errorMessage
        }
        Banner {
            Layout.leftMargin: 40
            Layout.rightMargin: 40
            Layout.fillWidth: true
            kind: "success"
            text: ProjectsViewModel.errorMessage ? "" : ProjectsViewModel.notice
        }

        // ----------------------------------------------------------- list
        Card {
            Layout.leftMargin: 40
            Layout.rightMargin: 40
            Layout.fillWidth: true
            Layout.fillHeight: true
            title: qsTr("All projects")
            subtitle: ProjectsViewModel.projects.length === 1 ? qsTr("1 project")
                    : qsTr("%1 projects").arg(ProjectsViewModel.projects.length)

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

            Label {
                visible: ProjectsViewModel.projects.length === 0 && !ProjectsViewModel.busy
                Layout.fillWidth: true
                Layout.topMargin: 6
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                text: ProjectsViewModel.canCreate ? qsTr("No projects yet. Register one with New project.") : qsTr("No projects yet.")
                color: Theme.textFaint
                font.pixelSize: 13
            }

            ScrollView {
                id: listScroller
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 120
                contentWidth: availableWidth
                clip: true
                readonly property bool overflowing: contentHeight > height
                rightPadding: overflowing ? 16 : 0
                ScrollBar.vertical.policy: overflowing ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded

                ColumnLayout {
                    width: listScroller.availableWidth
                    spacing: 10

                    Repeater {
                        model: ProjectsViewModel.projects
                        delegate: ColumnLayout {
                            id: row
                            required property var modelData
                            required property int index
                            // Hourly projects may have no total budget: then there is nothing to measure against.
                            readonly property bool hasTotal: modelData.total_budget_cents !== null
                                                             && modelData.total_budget_cents !== undefined
                            readonly property real usage: hasTotal && modelData.total_budget_cents > 0
                                ? Math.min(1, modelData.paid_cents / modelData.total_budget_cents) : 0
                            Layout.fillWidth: true
                            spacing: 10

                            Rectangle { visible: row.index > 0; Layout.fillWidth: true; height: 1; color: Theme.border }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                Rectangle {
                                    width: 34; height: 34; radius: 10
                                    color: Theme.accentSoft
                                    Icon { anchors.centerIn: parent; name: "folder"; width: 16; height: 16; color: Theme.accent }
                                }
                                ColumnLayout {
                                    spacing: 1
                                    Layout.fillWidth: true
                                    Label {
                                        text: row.modelData.title
                                        color: Theme.text; font.pixelSize: 14; font.weight: Font.DemiBold
                                        elide: Text.ElideRight; Layout.fillWidth: true
                                    }
                                    Label {
                                        text: (row.modelData.team_name || qsTr("No team")) + " · " + page.datesText(row.modelData)
                                        color: Theme.textMuted; font.pixelSize: 12
                                        elide: Text.ElideRight; Layout.fillWidth: true
                                    }
                                }
                                Item {
                                    Layout.preferredWidth: 90
                                    implicitHeight: 24
                                    Rectangle {
                                        width: categoryText.implicitWidth + 16
                                        height: 24
                                        radius: 12
                                        color: Theme.surfaceAlt
                                        Label {
                                            id: categoryText
                                            anchors.centerIn: parent
                                            text: ProjectsViewModel.categoryLabel(row.modelData.category)
                                            color: Theme.textMuted
                                            font.pixelSize: 12
                                        }
                                    }
                                }
                                // Paid against the total budget.
                                ColumnLayout {
                                    visible: page.wide
                                    Layout.preferredWidth: 170
                                    Layout.maximumWidth: 170
                                    spacing: 4
                                    Label {
                                        Layout.fillWidth: true
                                        text: row.hasTotal
                                              ? qsTr("%1 of %2").arg(ProjectsViewModel.money(row.modelData.paid_cents))
                                                                .arg(ProjectsViewModel.money(row.modelData.total_budget_cents))
                                              : qsTr("%1 received").arg(ProjectsViewModel.money(row.modelData.paid_cents))
                                        color: Theme.textMuted; font.pixelSize: 12; elide: Text.ElideRight
                                    }
                                    Rectangle {
                                        visible: row.hasTotal
                                        Layout.fillWidth: true
                                        height: 4
                                        radius: 2
                                        color: Theme.surfaceAlt
                                        Rectangle {
                                            width: parent.width * row.usage
                                            height: parent.height
                                            radius: 2
                                            color: row.modelData.paid_cents > row.modelData.total_budget_cents ? Theme.danger : Theme.accent
                                        }
                                    }
                                    Label {
                                        visible: row.modelData.payments.length > 0
                                        Layout.fillWidth: true
                                        text: qsTr("Remaining %1").arg(ProjectsViewModel.money(row.modelData.remaining_cents))
                                        color: Theme.textFaint; font.pixelSize: 11; elide: Text.ElideRight
                                    }
                                }
                                // Checks.
                                ColumnLayout {
                                    Layout.preferredWidth: 120
                                    Layout.maximumWidth: 120
                                    spacing: 2
                                    Label {
                                        text: row.modelData.owner_check ? qsTr("✓ Owner checked") : ""
                                        visible: text.length > 0
                                        color: Theme.success; font.pixelSize: 12
                                    }
                                    Label {
                                        text: row.modelData.leader_check ? qsTr("✓ Leader checked") : ""
                                        visible: text.length > 0
                                        color: Theme.success; font.pixelSize: 12
                                    }
                                    Label {
                                        visible: !row.modelData.owner_check && !row.modelData.leader_check
                                        text: qsTr("Not checked")
                                        color: Theme.textFaint; font.pixelSize: 12
                                    }
                                }
                                AppButton {
                                    variant: "ghost"
                                    implicitWidth: 74
                                    implicitHeight: 34
                                    font.pixelSize: 12
                                    text: row.modelData.access.edit ? qsTr("Edit") : qsTr("View")
                                    enabled: !ProjectsViewModel.busy
                                    onClicked: projectDialog.openFor(row.modelData)
                                }
                                AppButton {
                                    variant: "ghost"
                                    implicitWidth: 84
                                    implicitHeight: 34
                                    font.pixelSize: 12
                                    visible: row.modelData.access.check || row.modelData.access.uncheck
                                    text: row.modelData.access.check ? qsTr("Check") : qsTr("Uncheck")
                                    enabled: !ProjectsViewModel.busy
                                    onClicked: row.modelData.access.check ? ProjectsViewModel.checkProject(row.modelData)
                                                                          : ProjectsViewModel.uncheckProject(row.modelData)
                                }
                                Item {
                                    visible: !(row.modelData.access.check || row.modelData.access.uncheck)
                                    implicitWidth: 84
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

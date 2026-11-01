import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeWin.ViewModels
import "../themes"
import "../components"

// Owner only: define role bundles (named permission sets) that can be assigned to members.
Item {
    id: page

    function membersText(n) { return n === 1 ? qsTr("1 member") : qsTr("%1 members").arg(n) }

    function labelFor(value) {
        for (const group of MembersViewModel.permissionCatalog)
            for (const p of group.permissions)
                if (p.value === value) return p.label
        return value
    }

    RoleBundleDialog { id: bundleDialog; objectName: "roleBundleDialog" }

    Popup {
        id: confirmDelete
        property var bundle: ({})
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(400, (parent ? parent.width : 400) - 32)
        modal: true
        padding: 24
        Overlay.modal: Rectangle { color: Qt.rgba(0, 0, 0, Theme.dark ? 0.6 : 0.35) }
        background: Rectangle { radius: Theme.radiusLarge; color: Theme.surface; border.width: 1; border.color: Theme.border }
        contentItem: ColumnLayout {
            spacing: 16
            Label { text: qsTr("Delete “%1”?").arg(confirmDelete.bundle.name || ""); color: Theme.text; font.pixelSize: 17; font.weight: Font.Bold }
            Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                color: Theme.textMuted
                font.pixelSize: 13
                text: confirmDelete.bundle.member_count > 0
                      ? qsTr("%1 will lose its permissions immediately.").arg(page.membersText(confirmDelete.bundle.member_count))
                      : qsTr("No one holds this bundle.")
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                AppButton { variant: "secondary"; text: qsTr("Cancel"); Layout.fillWidth: true; onClicked: confirmDelete.close() }
                AppButton {
                    text: qsTr("Delete")
                    Layout.fillWidth: true
                    onClicked: { MembersViewModel.deleteBundle(confirmDelete.bundle.id); confirmDelete.close() }
                }
            }
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

            RowLayout {
                Layout.leftMargin: 40
                Layout.rightMargin: 40
                Layout.fillWidth: true
                spacing: 12
                ColumnLayout {
                    spacing: 4
                    Layout.fillWidth: true
                    Label { text: qsTr("Roles"); color: Theme.text; font.pixelSize: 28; font.weight: Font.Bold; Layout.fillWidth: true }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        text: qsTr("Role bundles add permissions on top of a member's base role. Assign them on the Members page.")
                        color: Theme.textMuted
                        font.pixelSize: 14
                    }
                }
                AppButton {
                    iconName: "plus"
                    text: qsTr("New bundle")
                    onClicked: bundleDialog.openNew()
                }
            }

            Banner {
                Layout.leftMargin: 40
                Layout.rightMargin: 40
                Layout.fillWidth: true
                kind: "error"
                text: bundleDialog.opened ? "" : MembersViewModel.errorMessage
            }
            Banner {
                Layout.leftMargin: 40
                Layout.rightMargin: 40
                Layout.fillWidth: true
                kind: "success"
                text: MembersViewModel.errorMessage ? "" : MembersViewModel.notice
            }

            Label {
                visible: MembersViewModel.bundles.length === 0
                Layout.leftMargin: 40
                text: qsTr("No role bundles yet.")
                color: Theme.textFaint
            }

            Repeater {
                model: MembersViewModel.bundles
                delegate: Rectangle {
                    id: card
                    required property var modelData
                    Layout.leftMargin: 40
                    Layout.rightMargin: 40
                    Layout.fillWidth: true
                    implicitHeight: cardBody.implicitHeight + 40
                    radius: Theme.radiusLarge
                    color: Theme.surface
                    border.width: 1
                    border.color: Theme.border

                    ColumnLayout {
                        id: cardBody
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 12

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            ColumnLayout {
                                spacing: 2
                                Layout.fillWidth: true
                                Label { text: card.modelData.name; color: Theme.text; font.pixelSize: 16; font.weight: Font.Bold; Layout.fillWidth: true }
                                Label {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    text: (card.modelData.description ? card.modelData.description + " · " : "")
                                          + page.membersText(card.modelData.member_count)
                                    color: Theme.textMuted
                                    font.pixelSize: 12
                                }
                            }
                            AppButton {
                                variant: "secondary"
                                text: qsTr("Edit")
                                implicitWidth: 90
                                implicitHeight: 36
                                onClicked: bundleDialog.openFor(card.modelData)
                            }
                            AppButton {
                                variant: "ghost"
                                text: qsTr("Delete")
                                implicitWidth: 90
                                implicitHeight: 36
                                onClicked: { confirmDelete.bundle = card.modelData; confirmDelete.open() }
                            }
                        }

                        Flow {
                            Layout.fillWidth: true
                            spacing: 6
                            Repeater {
                                model: card.modelData.permissions
                                delegate: Rectangle {
                                    required property string modelData
                                    implicitWidth: permText.implicitWidth + 16
                                    implicitHeight: 24
                                    radius: 12
                                    color: Theme.surfaceAlt
                                    Label {
                                        id: permText
                                        anchors.centerIn: parent
                                        text: page.labelFor(parent.modelData)
                                        color: Theme.textMuted
                                        font.pixelSize: 12
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Item { Layout.preferredHeight: 20 }
        }
    }
}

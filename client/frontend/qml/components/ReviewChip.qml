import QtQuick
import QtQuick.Controls
import "../themes"

// An item's review state: "To review", "Leader ✓" or "Owner ✓" (see ProjectsViewModel.reviewStatus).
Rectangle {
    id: chip

    property string text
    property string tone: "pending"     // pending | leader | owner
    readonly property color ink: tone === "owner" ? Theme.success : tone === "leader" ? Theme.accent : Theme.warning

    implicitWidth: label.implicitWidth + 16
    implicitHeight: 22
    radius: 11
    color: tone === "owner" ? Theme.successSoft : tone === "leader" ? Theme.accentSoft
                                                                     : Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.14)

    Label {
        id: label
        anchors.centerIn: parent
        text: chip.text
        color: chip.ink
        font.pixelSize: 11
        font.weight: Font.DemiBold
    }
}

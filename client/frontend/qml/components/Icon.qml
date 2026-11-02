import QtQuick
import QtQuick.Shapes
import "../themes"

// Line icon drawn from 24x24 SVG path data, so it can take any theme colour.
Item {
    id: root

    property string name
    property color color: Theme.textMuted
    property real strokeWidth: 1.8

    implicitWidth: 18
    implicitHeight: 18

    readonly property var paths: ({
        "server":  "M4 4h16v6H4z M4 14h16v6H4z M8 7h.01 M8 17h.01",
        "mail":    "M3 6h18v12H3z M3 7l9 6.5L21 7",
        "lock":    "M6 11h12v9H6z M8.5 11V8a3.5 3.5 0 0 1 7 0v3",
        "eye":     "M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z M12 9a3 3 0 1 0 0.001 0z",
        "eyeOff":  "M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z M12 9a3 3 0 1 0 0.001 0z M4 4l16 16",
        "sun":     "M12 8a4 4 0 1 0 0.001 0z M12 2v2 M12 20v2 M4.9 4.9l1.4 1.4 M17.7 17.7l1.4 1.4 M2 12h2 M20 12h2 M4.9 19.1l1.4-1.4 M17.7 6.3l1.4-1.4",
        "moon":    "M20.5 14.5A8.5 8.5 0 1 1 9.5 3.5a7 7 0 0 0 11 11z",
        "monitor": "M3 4h18v12H3z M8 20h8 M12 16v4",
        "alert":   "M12 3a9 9 0 1 0 0.001 0z M12 7.5v5.5 M12 16.5h.01",
        "tick":    "M5 12.5l4.5 4.5L19 7.5",
        "check":"M12 3a9 9 0 1 0 0.001 0z M8 12.5l2.8 2.8L16.5 9.5",
        "key":     "M8 10a5 5 0 1 0 0.001 0z M11.5 11.5L21 2 M17 6l3 3 M15 8l2 2",
        "back":    "M19 12H5 M11 6l-6 6 6 6",
        "logout":  "M9 21H5V3h4 M16 17l5-5-5-5 M21 12H9",
        "users":   "M9 4a4 4 0 1 0 0.001 0z M2 21v-1a6 6 0 0 1 12 0v1 M16 4.5a3.5 3.5 0 0 1 0 7 M18 14.5a5 5 0 0 1 4 5v1.5",
        "folder":  "M3 6a1 1 0 0 1 1-1h5l2 2.5h9a1 1 0 0 1 1 1V19a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z",
        "chart":   "M3 20h18 M6 16v-5 M11 16V6 M16 16v-8 M20.5 16v-3",
        "close":   "M6 6l12 12 M18 6L6 18",
        "chevron": "M6 9l6 6 6-6",
        "plus":    "M12 5v14 M5 12h14",
        "refresh": "M20 12a8 8 0 1 1-2.3-5.7 M20 4v4h-4",
        "home":    "M3 11l9-7 9 7 M5 10v10h14V10",
        "grid":    "M4 4h7v7H4z M13 4h7v7h-7z M4 13h7v7H4z M13 13h7v7h-7z",
        "search":  "M11 4a7 7 0 1 0 0.001 0z M20 20l-4-4"
    })

    Shape {
        width: 24
        height: 24
        anchors.centerIn: parent
        scale: Math.min(root.width, root.height) / 24
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: root.color
            strokeWidth: root.strokeWidth
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: root.paths[root.name] || "" }
        }
    }
}

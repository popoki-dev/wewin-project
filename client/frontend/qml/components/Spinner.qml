import QtQuick
import QtQuick.Shapes
import "../themes"

Item {
    id: root

    property color color: Theme.accentText
    property bool running: visible

    implicitWidth: 18
    implicitHeight: 18

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        RotationAnimator on rotation {
            from: 0; to: 360; duration: 800
            loops: Animation.Infinite
            running: root.running
        }

        ShapePath {
            strokeColor: root.color
            strokeWidth: 2.2
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: root.width / 2; centerY: root.height / 2
                radiusX: root.width / 2 - 1.5; radiusY: root.height / 2 - 1.5
                startAngle: 0; sweepAngle: 270
            }
        }
    }
}

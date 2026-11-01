pragma Singleton
import QtQuick
import WeWin.ViewModels

// Design tokens for both colour schemes. Components bind to these, so a
// switch in ThemeViewModel restyles the whole UI.
QtObject {
    readonly property bool dark: ThemeViewModel.dark

    // Surfaces
    readonly property color background:   dark ? "#0b0f19" : "#f4f5fa"
    readonly property color surface:      dark ? "#121826" : "#ffffff"
    readonly property color surfaceAlt:   dark ? "#1a2233" : "#f1f3f8"
    readonly property color surfaceHover: dark ? "#222b3f" : "#e9ecf4"
    readonly property color border:       dark ? "#283248" : "#e1e5ee"
    readonly property color borderStrong: dark ? "#3a4560" : "#c9cfdc"

    // Text
    readonly property color text:      dark ? "#e7e9f0" : "#0f172a"
    readonly property color textMuted: dark ? "#98a2b8" : "#5b6478"
    readonly property color textFaint: dark ? "#6b7590" : "#8b93a7"

    // Brand / states
    readonly property color accent:      dark ? "#6366f1" : "#4f46e5"
    readonly property color accentHover: dark ? "#7577f5" : "#4338ca"
    readonly property color accentSoft:  dark ? "#24254a" : "#eceafd"
    readonly property color accentText:    "#ffffff"
    readonly property color danger:      dark ? "#f87171" : "#dc2626"
    readonly property color dangerSoft:  dark ? "#2c1418" : "#fdeeee"
    readonly property color success:     dark ? "#4ade80" : "#16a34a"
    readonly property color successSoft: dark ? "#10261a" : "#e9f8ef"
    readonly property color warning:     dark ? "#fbbf24" : "#d97706"

    readonly property color inputBackground: dark ? "#0f1422" : "#ffffff"
    readonly property color focusRing: Qt.rgba(accent.r, accent.g, accent.b, 0.28)

    // Brand panel gradient
    readonly property color brandStart: dark ? "#312e81" : "#4f46e5"
    readonly property color brandEnd:   dark ? "#0e7490" : "#06b6d4"

    // Metrics
    readonly property int radiusSmall: 8
    readonly property int radius: 10
    readonly property int radiusLarge: 16
    readonly property int controlHeight: 44
    readonly property int animationMs: 160

    readonly property string fontFamily: "Inter, Segoe UI, SF Pro Text, Roboto, Noto Sans, Helvetica, Arial"
}

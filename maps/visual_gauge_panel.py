"""The panel for the gauge specimen, as a registered overlay kind (see
visual_square_panel.py for why a specimen needs one).

The subject is the engine's own status-panel look - label, value, and a bar colored
green / yellow / red by how full it is - drawn three ways: as markdown lines in a
gui_text_area, as a header-less grid of gauge cells in a text-area table, and as
`gui_gauge` layout widgets that the specimen drives live. A test can assert the bar's
rect; only an eye can say the bar sits under its label, the colors read, and the grid
lines up with the engine's own ENGN/WEAP/SHLD/SENS block.
"""
from sbs_utils.procedural.gui import (gui_row, gui_text, gui_text_area, gui_gauge,
                                      overlay_register)

LBL = "font:gui-3;color:#8cf;justify:left;"

# The live widgets, so the specimen's loop can move them. One panel at a time.
_live = {}


def _gauge_panel(client_id, content):
    gui_row("row-height: content;")
    gui_text(f"$text:`Gauges in a text area (static)`;{LBL}")
    gui_row("row-height: 30em;")
    gui_text_area(
        "## Artemis\n"
        "[Energy](gauge://946?max=1000)\n"
        "[FRNT SHLD](gauge://45?max=120)\n"
        "[REAR SHLD](gauge://12?max=120)\n"
        "[Homing](gauge://-45?max=8&show=frac)\n"
        "[Cargo](gauge://7?max=20&show=pct)\n"
        "[Heat](gauge://90?max=100&color=#e80)\n"
        "<hr>\n"
        "| | |\n"
        "|:--:|:--:|\n"
        "| [ENGN](gauge://1?max=1&show=none) | [WEAP](gauge://0.4?max=1&show=none) |\n"
        "| [SHLD](gauge://0.2?max=1&show=none) | [SENS](gauge://1?max=1&show=none) |\n"
        "\n"
        "| System | Level |\n"
        "|:--|:--|\n"
        "| Impulse | [](gauge://80?max=100) |\n"
        "| Warp | [](gauge://30?max=100&show=pct) |",
        style="col-width: 22em;")

    gui_row("row-height: content;")
    gui_text(f"$text:`gui_gauge widgets (live - they should sweep)`;{LBL}")
    for name in ("Energy", "FRNT SHLD", "REAR SHLD"):
        gui_row("row-height: content;")
        _live[name] = gui_gauge(100, 100, name, style="col-width: 22em;")


def visual_gauge_set(name, value):
    """Move one live gauge. Returns False when the panel is not up."""
    g = _live.get(name)
    if g is None:
        return False
    g.value = value
    return True


def visual_gauge_count():
    return len(_live)


overlay_register("visual_gauge", _gauge_panel)

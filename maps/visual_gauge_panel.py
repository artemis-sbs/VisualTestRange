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
                                      overlay_register, overlay_slot_define)

LBL = "font:gui-3;color:#8cf;justify:left;"

# Build counter for the live slot, so the specimen can assert patches landed.
_built = {}


# Two slots, because an overlay builder fills ONE layout (a gui_section inside it is
# never presented). The document sits above the harness card (1,52..46,99); the live
# gauges go to the right.
overlay_slot_define("visual_gauge_doc", (1.0, 2.0, 30.0, 44.0), draw_layer=30000)
overlay_slot_define("visual_gauge_live", (50.0, 2.0, 80.0, 30.0), draw_layer=30000)


def _gauge_doc(client_id, content):
    gui_row("row-height: content;")
    gui_text(f"$text:`text area (static)`;{LBL}")
    gui_row("")
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
        "| Warp | [](gauge://30?max=100&show=pct) |")


def _gauge_live(client_id, content):
    # Values come from the overlay's CONTENT, and the loop changes them with
    # overlay_patch - a gauge inside a slot cannot repaint itself (the engine
    # overdraws re-sent text), so the slot is re-filled instead.
    gui_row("row-height: content;")
    gui_text(f"$text:`gui_gauge (live, sweeping)`;{LBL}")
    for name, key in (("Energy", "energy"), ("FRNT SHLD", "front"), ("REAR SHLD", "rear")):
        gui_row("row-height: content;")
        gui_gauge(content.get(key, 100), 100, name, show="frac")
    _built["live"] = _built.get("live", 0) + 1


def visual_gauge_builds():
    """How many times the live slot has been filled (1 + one per patch)."""
    return _built.get("live", 0)


overlay_register("visual_gauge_doc", _gauge_doc)
overlay_register("visual_gauge_live", _gauge_live)

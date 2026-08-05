"""The panel for the `layer:` style specimen (GUI_LAYER_CLIP_PLAN.md Phase B).

Its companion `visual_draw_layer` asked the ENGINE a question and got a yes: an opaque
fill at a higher draw_layer hides text that overflowed into it. But it asked by emitting
raw send_gui_* at hand-written rects, deliberately bypassing our layout -- so it says
nothing about whether OUR plumbing delivers that to the engine.

This one asks exactly that, through the normal `gui_*` path, because missions load the
PACKAGED sbslib and the whole Phase B change (the `layer:` key, the section->row->column
cascade, the unpinned backgrounds, ImageAtlas no longer dropping draw_layer) has only
ever run headless.

TWO THINGS THIS FILE LEARNED THE HARD WAY, in the engine, first attempt:

  * The spill has to REACH the band. A paragraph across the full panel width wrapped to
    two lines, which fit the row it was given, so nothing overflowed onto the band below
    and the feature and the control produced an identical picture -- inconclusive, and
    it looked like a pass. The text now sits in a NARROW column so it wraps deep enough
    to land well inside the band.
  * The section has to FIT. Four bands of title + spill + band + caption oversubscribed
    the panel; every row was scaled down and the content-sized title rows collapsed
    toward zero, so the titles were drawn over the paragraphs. Two bands per screen, and
    the captions carry what the titles used to.

Both are the same lesson the whole plan is about: this engine does not clip.
"""
from sbs_utils.procedural.gui import (
    gui_row, gui_text, gui_blank, overlay_register)


# Long, and rendered in a ~25%-wide column, so it wraps to something like seven lines
# and overflows a 2em row by several times its own height. The spill IS the specimen --
# if it is marginal, the specimen answers nothing (see the module docstring).
SPILL = ("This paragraph is far too long for the two-em row it was given, and it sits "
         "in a narrow column so that it wraps to many lines. The engine does not clip, "
         "so every line past the first is drawn below the row, straight over the band "
         "underneath it.")

LBL = "font:gui-1;color:#b9c4d0;"

# Raised above the 1001 that text defaults to. Below the overlay band (20000+) that this
# panel is itself riding in -- the kind of collision the layer map exists to prevent.
OVER = 1500

_LAST_BUILD = {"rows": 0}


def rows_built():
    """Rows the last completed build emitted. 0 means the builder never ran."""
    return _LAST_BUILD["rows"]


def _spill_row():
    """The overflow: a long paragraph in a narrow column, in a row far too short."""
    gui_row("row-height: 2em;")
    gui_text(f"$text:`{SPILL}`;font:gui-2;", "col-width: 25;")
    gui_blank()


def _layer_style_panel(client_id, content):
    n = 0

    gui_row("row-height: 1.6em;")
    gui_text("$text:`layer: - the SAME overflow twice, with the key and without`;font:gui-3;color:#8cf;")
    n += 1

    # 1. The feature. A row background raised over the previous row's content. Before
    #    Phase B this was impossible: backgrounds were pinned to a hardcoded
    #    draw_layer:1000 -- UNDER content -- so a backdrop could never cover a
    #    neighbour's spill no matter what the author wrote.
    _spill_row()
    gui_row(f"row-height: 9em; background: #2a4a6a; layer: {OVER};")
    gui_blank()
    gui_row("row-height: 2.2em;")
    gui_text(f"$text:`1. layer: {OVER} on the row -- the blue band should be SOLID, spill hidden`;{LBL}")
    n += 4

    # 2. The control. Identical, minus the layer. The background stays at 1000 and the
    #    spill is drawn over it, exactly as it always was. This one failing is worse
    #    than the feature failing: it would mean every existing background moved.
    _spill_row()
    gui_row("row-height: 9em; background: #6a2a2a;")
    gui_blank()
    gui_row("row-height: 2.2em;")
    gui_text(f"$text:`2. CONTROL, no layer: -- the red band MUST show the spill over it`;{LBL}")
    n += 4

    _LAST_BUILD["rows"] = n


overlay_register("visual_layer_style", _layer_style_panel)

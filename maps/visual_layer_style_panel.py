"""The panel for the `layer:` style specimen (GUI_LAYER_CLIP_PLAN.md Phase B).

Its companion `visual_draw_layer` asked the ENGINE a question and got a yes: an opaque
fill at a higher draw_layer hides text that overflowed into it. But it asked by emitting
raw send_gui_* at hand-written rects, deliberately bypassing our layout -- so it says
nothing about whether OUR plumbing delivers that to the engine.

This one asks exactly that, through the normal `gui_*` path, because missions load the
PACKAGED sbslib and the whole Phase B change (the `layer:` key, the section->row->column
cascade, the unpinned backgrounds, ImageAtlas no longer dropping draw_layer) has only
ever run headless.

Every pair below is the same overflow twice: once with `layer:` and once without. The
one WITHOUT is the control, and it must still look exactly like it always did -- the
back-compat half of the claim is as important as the feature half.
"""
from sbs_utils.procedural.gui import (
    gui_row, gui_text, gui_blank, gui_image_stretch, overlay_register)


# Long enough to overrun a 2em row several times over at any plausible window size.
SPILL = ("This paragraph is far too long for the two-em row it was given. The engine "
         "does not clip, so every line past the first is drawn below the row, over "
         "whatever the layout put there.")

LBL = "font:gui-1;color:#b9c4d0;"
TITLE = "font:gui-3;color:#8cf;"

# Raised above the 1001 the text defaults to. Below the overlay band (20000+) that this
# very panel is riding in, which is the kind of collision the layer map exists to avoid.
OVER = 1500

_LAST_BUILD = {"rows": 0}


def rows_built():
    """Rows the last completed build emitted. 0 means the builder never ran."""
    return _LAST_BUILD["rows"]


def _label(text):
    gui_row("row-height: 2.4em;")
    gui_text(f"$text:`{text}`;{LBL}")


def _layer_style_panel(client_id, content):
    n = 0

    gui_row("row-height: content;")
    gui_text(f"$text:`layer: - does our plumbing reach the engine?`;font:gui-4;color:#8cf;")
    n += 1

    # 1. The feature. A row background raised over the previous row's content. Before
    #    Phase B this was impossible: backgrounds were pinned to a hardcoded
    #    draw_layer:1000, i.e. UNDER content, so a backdrop could never cover a
    #    neighbour's spill no matter what the author wrote.
    gui_row("row-height: content;")
    gui_text(f"$text:`1. row background at layer {OVER} - should HIDE the spill`;{TITLE}")
    gui_row("row-height: 2em;")
    gui_text(f"$text:`{SPILL}`;")
    gui_row(f"row-height: 6em; background: #2a4a6a; layer: {OVER};")
    gui_blank()
    _label("   the blue band above should be SOLID - no text showing through it")
    n += 5

    # 2. The control. Identical, minus the layer. The background stays at 1000 and the
    #    spill is drawn over it, exactly as it always was.
    gui_row("row-height: content;")
    gui_text(f"$text:`2. CONTROL - same rows, no layer:`;{TITLE}")
    gui_row("row-height: 2em;")
    gui_text(f"$text:`{SPILL}`;")
    gui_row("row-height: 6em; background: #6a2a2a;")
    gui_blank()
    _label("   the red band MUST show the spill over it - that is the unchanged default")
    n += 5

    # 3. The cascade. `layer:` on the ROW, not on the widget. Proves the
    #    section->row->column resolution in Layout.calc reaches a plain gui_text.
    gui_row("row-height: content;")
    gui_text(f"$text:`3. cascade - layer: on the ROW, text inherits it`;{TITLE}")
    gui_row("row-height: 2em;")
    gui_text(f"$text:`{SPILL}`;")
    gui_row(f"row-height: 6em; layer: {OVER}; background: #2a6a4a;")
    gui_text(f"$text:`INHERITED - this text rides the row's layer`;font:gui-2;color:#fff;")
    _label("   green band solid, and its own text still readable on top of it")
    n += 5

    # 4. The image path. ImageAtlas used to DROP draw_layer outright - get_props rebuilt
    #    the string from file/color/sub_rect - so the one widget that can paint an opaque
    #    rectangle was the one that could not be raised.
    gui_row("row-height: content;")
    gui_text(f"$text:`4. gui_image at layer {OVER} - ImageAtlas used to drop it`;{TITLE}")
    gui_row("row-height: 2em;")
    gui_text(f"$text:`{SPILL}`;")
    gui_row("row-height: 6em;")
    gui_image_stretch("image:smallWhite;color:#6a5a2a;", f"layer: {OVER};")
    _label("   the olive band should be SOLID - if the spill shows, the atlas still drops it")
    n += 5

    _LAST_BUILD["rows"] = n


overlay_register("visual_layer_style", _layer_style_panel)

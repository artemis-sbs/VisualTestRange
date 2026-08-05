"""The panel for the `draw_layer` occlusion specimen (GUI_LAYER_CLIP_PLAN.md Phase 0).

The question: the ENGINE does not clip, so text that overruns its rect is drawn over
whatever is beside or below it. Can `draw_layer` plus an opaque fill hide that spill --
i.e. can we build clipping out of paint order? Everything in GUI_LAYER_CLIP_PLAN.md
hangs off the answer, and only an eye in a real Cosmos session can give it.

RAW EMISSION ON PURPOSE. This panel calls `sbs.send_gui_text` / `sbs.send_gui_image`
directly at explicit percent rects instead of using `gui_*`. Two reasons:

  1. It cannot be built out of `gui_*` calls. The two library gaps this plan is about
     are exactly in the way: row/column/section backgrounds are pinned to
     `draw_layer:1000` (a hardcoded literal), and `gui_image` DROPS `draw_layer`
     entirely -- `ImageAtlas.get_props` rebuilds the props string from file/color/
     sub_rect. So the one widget that can paint an opaque rectangle is the one that
     cannot be raised.
  2. The question is about ENGINE paint semantics. Routing it through our layout would
     only add variables to an answer that has to be unambiguous.

Rects are percent-local to the overlay's own sub-region, which is the full screen.
"""
from sbs_utils.helpers import FrameContext
from sbs_utils.procedural.gui import overlay_register


# The fill every occluder uses. SIX-digit hex on purpose: an occluder that is not
# opaque answers a different question than the one being asked.
BLUE = "#2a4a6a"
RED = "#a33a3a"

# Long enough to overrun a 3%-tall box several times over at any plausible window
# size -- the spill IS the specimen, so it must not be marginal.
SPILL = ("This paragraph is far too long for the box it was given, which is only three "
         "percent of the screen tall. The engine does not clip, so every line past the "
         "first is drawn BELOW the box, on top of whatever the layout put there.")

# What each cell asks the engine, recorded so the headless half can assert the panel
# actually built what it claims.
#   (title, occluder draw_layer or None for "send no draw_layer", is there an occluder)
# Cell 1 and cell 3 both carry layer None and mean different things -- one sends no
# fill at all, the other sends a fill with no layer on it -- so the flag is separate.
CELLS = [
    ("1. CONTROL - no occluder", None, False),
    ("2. OCCLUDER draw_layer 2000", 2000, True),
    ("3. OCCLUDER no draw_layer", None, True),
    ("4. OCCLUDER draw_layer 500", 500, True),
    ("5. BUTTON under draw_layer 5000", 5000, True),
    ("6. BUTTON under draw_layer 500", 500, True),
]


# Widgets emitted by the LAST completed build. The overlay swallows builder exceptions
# (it prints and returns), so "the run was green" is not evidence the panel drew
# anything - this is what the headless half asserts against.
_LAST_BUILD = {"n": 0}


def cell_specs():
    """The cells this panel declares -- the headless half checks against this."""
    return list(CELLS)


def emitted_count():
    """How many widgets the last completed build emitted. 0 means it never ran."""
    return _LAST_BUILD["n"]


def _cell_origin(i):
    """Top-left of cell `i` in a 3-wide, 2-tall grid, in screen percent."""
    col = i % 3
    row = i // 3
    return 3.0 + col * 32.0, 14.0 + row * 38.0


class _Emit:
    """The three raw senders, with the region and client already bound."""

    def __init__(self, client_id, region_tag):
        self.sbs = FrameContext.context.sbs
        self.cid = client_id
        self.region = region_tag
        self.n = 0

    def _tag(self, name):
        self.n += 1
        return f"dl_{name}_{self.n}"

    def text(self, body, left, top, right, bottom, font="gui-2", color="#e8eef5"):
        self.sbs.send_gui_text(
            self.cid, self.region, self._tag("t"),
            f"$text:`{body}`;font:{font};color:{color};",
            left, top, right, bottom)

    def fill(self, color, layer, left, top, right, bottom):
        props = f"image:smallwhite;color:{color};"
        if layer is not None:
            props += f"draw_layer:{layer};"
        self.sbs.send_gui_image(
            self.cid, self.region, self._tag("i"), props,
            left, top, right, bottom)

    def button(self, body, left, top, right, bottom):
        # No handler: cells 5 and 6 are judged by LOOKING (is it covered?) and by
        # HOVERING (does it still highlight, i.e. did the occluder steal input?).
        self.sbs.send_gui_button(
            self.cid, self.region, self._tag("b"),
            f"$text:`{body}`;font:gui-2;",
            left, top, right, bottom)


def _spill_cell(e, i, title, layer, occluder, caption):
    """A box too small for its text, with an optional opaque fill over the spill zone."""
    x, y = _cell_origin(i)
    r = x + 30.0
    e.text(title, x, y, r, y + 3.5, font="gui-3", color="#8cf")
    # The box. Three percent tall: one line fits, the rest lands below it.
    e.text(SPILL, x, y + 4.0, r, y + 7.0)
    if occluder:
        # The spill zone, filled. Emitted AFTER the text, so if draw_layer is ignored
        # and emission order rules, this covers the spill no matter what number it
        # carries -- which is precisely what cell 4 is there to detect.
        e.fill(BLUE, layer, x, y + 7.0, r, y + 17.0)
    e.text(caption, x, y + 18.0, r, y + 34.0, font="gui-1", color="#b9c4d0")


def _button_cell(e, i, title, layer, caption):
    """A button with an opaque fill directly over it, to bracket the button's layer."""
    x, y = _cell_origin(i)
    r = x + 30.0
    e.text(title, x, y, r, y + 3.5, font="gui-3", color="#8cf")
    e.button("CAN YOU SEE ME", x, y + 4.5, r, y + 10.0)
    e.fill(RED, layer, x, y + 4.5, r, y + 10.0)
    e.text(caption, x, y + 11.0, r, y + 34.0, font="gui-1", color="#b9c4d0")


def _draw_layer_panel(client_id, content):
    page = FrameContext.page
    if page is None:
        return
    e = _Emit(client_id, page.region_tag)

    e.text("draw_layer occlusion - can paint order stand in for clipping?",
           3.0, 4.0, 97.0, 8.0, font="gui-4", color="#8cf")
    e.text("Cell 1 is the baseline: that is what an overflow looks like. Compare every "
           "other cell against it.",
           3.0, 8.5, 97.0, 12.5, font="gui-1", color="#b9c4d0")

    _spill_cell(e, 0, *CELLS[0],
                caption="Nothing over the spill. The text runs on past the box and down "
                        "into this caption. THIS IS THE FAILURE the plan wants to hide.")
    _spill_cell(e, 1, *CELLS[1],
                caption="A blue fill over the spill zone at draw_layer 2000. If the "
                        "spill is GONE behind solid blue, occlusion works and the whole "
                        "plan is live.")
    _spill_cell(e, 2, *CELLS[2],
                caption="Same fill, no draw_layer at all. Tells us how much of cell 2 "
                        "came from the layer and how much from simply being emitted "
                        "later.")
    _spill_cell(e, 3, *CELLS[3],
                caption="Same fill at draw_layer 500 - BELOW the text's default 1001. "
                        "The spill should still be readable over the blue. If it is "
                        "hidden here too, draw_layer is ignored and emission order rules.")
    _button_cell(e, 4, CELLS[4][0], CELLS[4][1],
                 "A red fill at draw_layer 5000 over a button. Covered means the button "
                 "sits below 5000. Now HOVER where the button is: if it still "
                 "highlights, an occluder does not steal input.")
    _button_cell(e, 5, CELLS[5][0], CELLS[5][1],
                 "Same button, fill at draw_layer 500. The button should win. Together "
                 "with cell 5 this brackets the real button layer and settles whether "
                 "it is 1001 or 10000 - the two are documented differently.")

    # Only reached if every send above returned: the build completed.
    _LAST_BUILD["n"] = e.n


overlay_register("visual_draw_layer", _draw_layer_panel)

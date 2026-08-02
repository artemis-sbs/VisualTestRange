"""The panel for the `col-width: square` specimen, as a registered overlay kind.

A specimen cannot build GUI itself - only a console can - and the range's declarative
`visual_widgets()` hook only knows how to draw buttons. An overlay KIND is the way
through: it is a builder run at present time inside its own sub-region, so a specimen
can put arbitrary layout on screen by showing it, without the console needing to know
what the layout is.

The subject is a claim no unit test can settle. A test can assert the builder asked for
`col-width: square`; only an eye can answer whether what comes out is SQUARE - the width
is derived from the row height through the aspect ratio, so a bug there shows up as
subtly-oblong boxes that still pass every structural assertion, and shows up worse the
further the screen is from 16:9.
"""
from sbs_utils.procedural.gui import (
    gui_row, gui_text, gui_face, gui_ship, gui_icon, gui_blank,
    gui_image_keep_aspect_ratio_center, overlay_register)


# Every box gets a background, because the subject IS the box: an unfilled square is
# invisible and the specimen would be asking about something nobody can see.
BOX = "background:#2a4a6aee;"
LBL = "font:gui-1;color:#cfd8e3;justify:left;"


def _label(text):
    gui_text(f"$text:`{text}`;{LBL}")


def _square_panel(client_id, content):
    face = content.get("face", "")
    ship = content.get("ship", "")
    icon = content.get("icon", "")
    image = content.get("image", "")

    gui_row("row-height: content;")
    gui_text("$text:`col-width: square - as wide as it is tall`;font:gui-3;color:#8cf;justify:left")

    # 1. The rule itself, at three heights. The square must track the ROW, so these
    #    should step up in size together - a square that ignores its row is the
    #    failure this row is looking for.
    for em in (2, 4, 7):
        gui_row(f"row-height: {em}em;")
        gui_text(f"$text:` `;{BOX}", "col-width: square;")
        _label(f"  square in a {em}em row - the box should be {em}em WIDE too")

    # 2. The four visuals at ONE height. This is the interchangeability claim the
    #    lower third rests on: swap any for any and nothing moves.
    gui_row("row-height: 5em;")
    if face:
        gui_face(face, style="col-width: square;")
    gui_blank(style="col-width: 0.4em;")
    if ship:
        gui_ship(ship, style="col-width: square;")
    gui_blank(style="col-width: 0.4em;")
    if icon:
        gui_icon(icon, style="col-width: square;")
    gui_blank(style="col-width: 0.4em;")
    if image:
        gui_image_keep_aspect_ratio_center(image, style="col-width: square;")
    _label("  face | ship | icon | image - four sources, ONE footprint")

    # 3. The behavior change, broken and fixed side by side. A face is square from
    #    birth; giving it a width now UN-squares it (they are mutually exclusive)
    #    instead of double-counting it and drawing outside the row.
    gui_row("row-height: 5em;")
    if face:
        gui_face(face, style="col-width: 12;")
    _label("  col-width: 12 on a face -> the width WINS, it is no longer square")
    gui_row("row-height: 5em;")
    if face:
        gui_face(face, style="col-width: square;")
    _label("  col-width: square on the same face -> square again")

    # 4. A square between two flex columns: it holds its shape and the neighbours
    #    split what is left. This is the lower third's own shape, generalized.
    gui_row("row-height: 4em;")
    gui_text(f"$text:`flex left`;{LBL}{BOX}")
    gui_text(f"$text:` `;{BOX}", "col-width: square;")
    gui_text(f"$text:`flex right`;{LBL}{BOX}")


overlay_register("visual_square", _square_panel)

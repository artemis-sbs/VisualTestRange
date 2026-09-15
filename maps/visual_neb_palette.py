"""Support for the nebula palette specimens: the predefined colors, as data.

Everything here is built in PYTHON rather than in the .mast on purpose. A derived icon
is a hex string, and a MAST assignment re-runs a string through f-string formatting
while `#` starts a MAST comment - so a label like `red  #cc3d14` assembled in MAST is
two separate traps. Assembled here it is just a string the specimen hands to a widget.

`_neb_colors` is private library surface and is reached into deliberately: the question
these specimens exist to answer is whether the TABLE's entries match their own key
names, so the table itself is the subject. There is no public accessor for it today -
which is arguably the real gap, since a mission cannot enumerate the palette either.
"""


def visual_neb_palette():
    """[(name, (er, eg, eb), icon_hex)] for every predefined nebula color.

    The icon is asked for exactly the way the library asks for it (no seed), so this is
    the canonical, un-jittered color of each entry - the one the table itself stores.
    """
    from sbs_utils.procedural.terrain import _neb_colors, terrain_nebula_icon_color
    out = []
    for name, entry in _neb_colors.items():
        emis = (float(entry.get("emission_red", 0.0) or 0.0),
                float(entry.get("emission_green", 0.0) or 0.0),
                float(entry.get("emission_blue", 0.0) or 0.0))
        out.append((name, emis, terrain_nebula_icon_color(entry)))
    return out


def visual_neb_names():
    return [p[0] for p in visual_neb_palette()]


def visual_neb_count():
    return len(visual_neb_palette())


def visual_neb_layout(gap=5200.0, row_gap=7000.0, per_row=4):
    """[(name, x, y, z, seed, icon_hex)] - where each preset's cloud goes.

    Two rows rather than one: seven clouds in a line span 31000 units, and a lens far
    enough back to hold that makes every cloud a smudge. Framing is sized to the thing
    being judged, which here is the COLOR of each cloud, so they have to be big enough
    to have a color.

    The seed is fixed per position, so two runs of this specimen are comparable - the
    per-object icon jitter is seeded from it.

    `icon_hex` is the preset's canonical derived icon, carried here so the .mast never has
    to handle a hex string itself - it goes straight from this tuple into a blob write.
    """
    icons = {n: h for n, _e, h in visual_neb_palette()}
    names = visual_neb_names()
    rows = [names[i:i + per_row] for i in range(0, len(names), per_row)]
    out = []
    n = 0
    for ri, row in enumerate(rows):
        x0 = -(len(row) - 1) * gap / 2.0
        for ci, name in enumerate(row):
            out.append((name, x0 + ci * gap, 0.0, ri * row_gap, 4100 + n * 37,
                        icons.get(name, NEB_ICON_FALLBACK)))
            n += 1
    return out


# What a preset with no derivable icon falls back to, mirroring the library's own choice.
NEB_ICON_FALLBACK = "gold"


def visual_neb_order_text():
    """Which dot is which, stated by POSITION - the identification that needs no label.

    The engine draws no name for a nebula, and whether a marker beside one gets labelled is
    the engine's business too. The layout is deterministic and the two rows have different
    counts, so "the row of four" and "the row of three" name every dot unambiguously on any
    renderer, with no orientation claim (which way is "back" on a radar is a guess) and no
    label at all.
    """
    rows = {}
    for name, _x, _y, z, _seed, _icon in visual_neb_layout():
        rows.setdefault(z, []).append(name)
    parts = []
    for z in sorted(rows):
        names = rows[z]
        parts.append("the row of %d is %s" % (len(names), ", ".join(names)))
    return "; ".join(parts) + ", left to right"


def visual_neb_swatches():
    """[label, background] rows for visual_widgets - each preset's ICON, drawn big.

    A radar dot is six pixels and sits under whatever else is on the map; the question
    "is the red one red" should not depend on finding it. The same hex, as a filled
    button, is the icon color with nothing in the way - and it renders identically in
    the engine and the mock, which a radar does not.
    """
    rows = []
    for name, emis, hexcol in visual_neb_palette():
        label = "%-7s %4.2f/%4.2f/%4.2f  %s" % (name, emis[0], emis[1], emis[2], hexcol)
        rows.append([label, hexcol])
    return rows


# ---------------------------------------------------------------------------
# Is a preset the color it is NAMED? - the same question, asked of the numbers.
# ---------------------------------------------------------------------------

# Where each color name sits on the hue wheel. Rough by nature (nobody owns the exact
# degree "orange" starts at), so it is only ever used for a DISTANCE, never a verdict.
# White has no hue at all and is excluded rather than given a fake one.
_NAME_HUE = {
    "red": 0.0, "orange": 30.0, "yellow": 60.0, "green": 120.0,
    "blue": 225.0, "purple": 285.0, "white": None,
}


def visual_neb_hue(hexcol):
    """Hue in degrees of a `#rrggbb` string; None for a neutral (grey/white)."""
    import colorsys
    h = hexcol.lstrip("#")
    if len(h) < 6:
        return None
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    hue, sat, _v = colorsys.rgb_to_hsv(r, g, b)
    if sat < 0.08:
        return None
    return hue * 360.0


def _hue_gap(a, b):
    if a is None or b is None:
        return None
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def visual_neb_name_drift():
    """[(name, derived_hue, hue_the_name_implies, degrees_apart)], worst first.

    Neutrals are skipped. A large gap does NOT mean the icon is wrong - the icon is
    derived from the cloud and matches it. It means the ENTRY does not render as the
    color its key calls it, in the 3D view as much as on the radar.
    """
    out = []
    for name, _emis, hexcol in visual_neb_palette():
        want = _NAME_HUE.get(name)
        got = visual_neb_hue(hexcol)
        if want is None or got is None:
            continue
        out.append((name, got, want, _hue_gap(got, want)))
    out.sort(key=lambda r: -r[3])
    return out


def visual_neb_worst_drift():
    d = visual_neb_name_drift()
    return d[0] if d else None


def visual_neb_closest_pair():
    """(name_a, name_b, degrees) - the two icons hardest to tell apart on a radar.

    Two presets whose icons are a few degrees apart are the same dot to anyone looking
    at the map, however different their clouds are up close.
    """
    pal = [(n, visual_neb_hue(h)) for n, _e, h in visual_neb_palette()]
    pal = [(n, h) for n, h in pal if h is not None]
    best = None
    for i in range(len(pal)):
        for j in range(i + 1, len(pal)):
            d = _hue_gap(pal[i][1], pal[j][1])
            if best is None or d < best[2]:
                best = (pal[i][0], pal[j][0], d)
    return best


def visual_neb_report():
    """Print the palette as a table, so a headless run records the numbers too."""
    print("VISUAL NEBULA PALETTE  name     emission R/G/B      icon     hue   name-hue  drift")
    drift = {d[0]: d for d in visual_neb_name_drift()}
    for name, emis, hexcol in visual_neb_palette():
        hue = visual_neb_hue(hexcol)
        d = drift.get(name)
        print("VISUAL NEBULA  %-7s  %4.2f %4.2f %4.2f   %s  %s  %s  %s" % (
            name, emis[0], emis[1], emis[2], hexcol,
            "   -" if hue is None else "%4.0f" % hue,
            "    -" if d is None else "%5.0f" % d[2],
            "    -" if d is None else "%5.0f" % d[3]))
    pair = visual_neb_closest_pair()
    if pair is not None:
        print("VISUAL NEBULA CLOSEST PAIR  %s and %s are %.0f degrees apart" % pair)
    return len(visual_neb_palette())


def visual_neb_drift_text():
    """One card line naming the worst offender, or saying there isn't one."""
    w = visual_neb_worst_drift()
    if w is None:
        return "every preset is within reach of its own name"
    return "worst drift: %s renders at hue %.0f, the name implies %.0f" % (w[0], w[1], w[2])


def visual_neb_pair_text():
    p = visual_neb_closest_pair()
    if p is None:
        return "no two icons to compare"
    return "closest pair: %s and %s, %.0f degrees apart" % p


def visual_neb_icon_of(obj):
    """The icon a SPAWNED nebula actually ended up with - read back off its blob."""
    try:
        return obj.data_set.get("radar_color_override") or ""
    except Exception:                                    # noqa: BLE001
        return ""


# How far a spawned cloud's icon may sit from its preset's canonical hue. The per-object
# jitter holds hue exactly in float and then rounds to 8-bit channels, which moves it a
# little - measured at most 0.68 degrees across 4000 seeds and every preset, worst on
# `yellow`. So this is a rounding allowance, not a tolerance for drift.
NEB_ICON_HUE_TOLERANCE = 1.0


def visual_neb_icons_match(objs):
    """True when every spawned cloud carries an icon of its own preset's HUE.

    Saturation and value are jittered per object on purpose, so only the hue is checked -
    that is the part the library promises to hold exactly.

    A NEUTRAL preset (white) has no hue to hold, and asking for one is how this check
    first failed: `visual_neb_hue` correctly answers None for grey, and comparing that to
    anything is a mismatch by construction. For a neutral the promise is the other way
    round - the icon must come back neutral too - so that is what is checked.

    Prints what it saw. A bare False here means "one of seven is wrong" and sends the
    reader back to the code to find out which, which is the failure this range exists to
    avoid making people do.
    """
    want = {n: visual_neb_hue(h) for n, _e, h in visual_neb_palette()}
    ok = True
    for name, obj in objs:
        icon = visual_neb_icon_of(obj)
        got = visual_neb_hue(icon)
        exp = want.get(name)
        if exp is None:
            if got is not None:
                print("VISUAL NEBULA MISMATCH  %s is neutral but spawned %s (hue %.0f)"
                      % (name, icon, got))
                ok = False
            continue
        if got is None:
            print("VISUAL NEBULA MISMATCH  %s expected hue %.0f but spawned %s (no hue)"
                  % (name, exp, icon or "nothing"))
            ok = False
            continue
        d = _hue_gap(got, exp)
        if d > NEB_ICON_HUE_TOLERANCE:
            print("VISUAL NEBULA MISMATCH  %s expected hue %.0f, spawned %s at hue %.0f (%.1f off)"
                  % (name, exp, icon, got, d))
            ok = False
    return ok


# ---------------------------------------------------------------------------
# Does an emission over 1.0 change the color, or only the brightness?
# ---------------------------------------------------------------------------

# One hue, four exposures. The shader has no tonemap: rayIntegral's accumulated rgb is
# returned straight to the target, so a channel over 1.0 clips there. The icon divides
# by the largest channel, which is scale-invariant - so if the theory is right, all four
# swatches below are the SAME hex and only the clouds differ.
NEB_EMISSION_LADDER = (0.25, 1.0, 2.0, 4.0)
NEB_EMISSION_BASE = (1.0, 0.30, 0.10)     # the "red" entry's ratio


def visual_neb_emission_specs(gap=5200.0):
    """[(label, x, y, z, seed, er, eg, eb, icon_hex)] - one cloud per exposure."""
    from sbs_utils.procedural.terrain import terrain_nebula_icon_color
    n = len(NEB_EMISSION_LADDER)
    x0 = -(n - 1) * gap / 2.0
    out = []
    for i, k in enumerate(NEB_EMISSION_LADDER):
        e = tuple(c * k for c in NEB_EMISSION_BASE)
        entry = {"emission_red": e[0], "emission_green": e[1], "emission_blue": e[2]}
        out.append(("x%.2f" % k, x0 + i * gap, 0.0, 0.0, 7700 + i * 53,
                    e[0], e[1], e[2], terrain_nebula_icon_color(entry)))
    return out


def visual_neb_emission_swatches():
    rows = []
    for spec in visual_neb_emission_specs():
        rows.append(["%-6s %4.2f/%4.2f/%4.2f  %s" % (spec[0], spec[5], spec[6], spec[7], spec[8]),
                     spec[8]])
    return rows


def visual_neb_emission_icons_identical():
    """True when every exposure derived the SAME icon - the scale-invariance claim."""
    icons = {spec[8] for spec in visual_neb_emission_specs()}
    return len(icons) == 1


def visual_neb_emission_clipping():
    """Which exposures have a channel over 1.0, i.e. clip in the render target."""
    out = []
    for spec in visual_neb_emission_specs():
        if max(spec[5], spec[6], spec[7]) > 1.0:
            out.append(spec[0])
    return out


def visual_neb_emission_text():
    clip = visual_neb_emission_clipping()
    if not clip:
        return "no exposure here exceeds 1.0"
    return "over 1.0, so clipping at the target: " + ", ".join(clip)

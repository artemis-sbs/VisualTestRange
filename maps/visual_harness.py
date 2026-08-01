"""Shared harness for the Visual Test Range.

A specimen is a label tagged `metadata: type: visual/<name>`. It does three things:

    visual_case("Black hole", ["what you should see", ...], notes=..., data=...)
    _anchor = visual_anchor(0, 0, 0)              # invisible camera post
    visual_camera(_anchor, eye=(0, 900, -2600))   # pin the frame

and then spawns its subject. The console renders the card over the 3dview and applies
the camera for its OWN client, so a specimen never needs to know client ids.

Everything here is deliberately renderer-agnostic: the same specimen runs in the engine
and in the browser mock, and the card says which one you are looking at. A mock frame is
not evidence about the engine, so the range never pretends otherwise.

Where a fact can be checked without eyes, use visual_expect() as well - it prints a
greppable VISUAL PASS/FAIL line, so a headless run still catches the data regressions
(a body that stopped streaming, an art root that stopped resolving) even though nobody
is looking at the picture.
"""
from sbs_utils.procedural.execution import log
from sbs_utils.helpers import FrameContext


# ---------------------------------------------------------------------------
# The card: what this specimen is, and what you should be seeing.
# ---------------------------------------------------------------------------
_CARD = {"title": "", "subtitle": "", "expect": [], "notes": "", "data": "", "seq": 0}


def visual_case(title, expect, notes="", data="", subtitle=""):
    """Declare the specimen. `expect` is the list of things a correct frame shows.

    Keep every string ASCII and brace-free: it is engine-rendered text, and a stray
    brace in a MAST assignment is an f-string SyntaxError reported against the caller.
    """
    _CARD["title"] = str(title)
    _CARD["subtitle"] = str(subtitle)
    _CARD["expect"] = [str(e) for e in expect]
    _CARD["notes"] = str(notes)
    _CARD["data"] = str(data)
    _CARD["seq"] += 1
    # One machine-readable line, so a headless run records what WOULD have been drawn.
    line = f"VISUAL CASE {title}"
    if data:
        line += f"  [{data}]"
    print(line)
    log(line, "visual")


def visual_card():
    """The current card as a plain dict (title, subtitle, expect, notes, data, seq)."""
    return dict(_CARD)


def visual_card_seq():
    """Bumped by every visual_case(); the console watches this to know to repaint."""
    return _CARD["seq"]


def visual_card_lines():
    """The card as ready-to-draw style strings, so no MAST f-string ever touches the text.

    Returned in draw order. Each entry is a complete `$text:...;` widget style.
    """
    out = []
    out.append(_style(_CARD["title"] or "(no specimen)", "gui-3", "#dfe8f5"))
    if _CARD["subtitle"]:
        out.append(_style(_CARD["subtitle"], "gui-1", "#8fa4bd"))
    out.append(_style("YOU SHOULD SEE", "gui-1", "#7fd08a"))
    for line in _CARD["expect"]:
        out.append(_style("- " + line, "gui-1", "#cfd8e3"))
    if _CARD["notes"]:
        out.append(_style("NOTE  " + _CARD["notes"], "gui-1", "#d8c07a"))
    if _CARD["data"]:
        out.append(_style("DATA  " + _CARD["data"], "gui-1", "#8fa4bd"))
    out.append(_style("RENDERER  " + visual_renderer(), "gui-1", "#8fa4bd"))
    return out


def _style(text, font, color):
    # Backtick-quote the literal so punctuation in the text can't terminate the style.
    return "$text:`" + text.replace("`", "'") + "`;font:" + font + ";color:" + color + ";"


def visual_text(text, font="gui-1", color="#cfd8e3"):
    """A styled label for a specimen's own on-screen text (same escaping as the card)."""
    return _style(str(text), font, color)


# ---------------------------------------------------------------------------
# Which renderer am I looking at?
# ---------------------------------------------------------------------------
def visual_renderer():
    """'engine', 'browser mock' or 'headless mock' - printed on every card.

    The engine's sbs is the Pybind module (plain name 'sbs'); cosmos_dev's stand-ins are
    packages, so the module name tells them apart without importing cosmos_dev (which does
    not exist in a real session).
    """
    sbs_mod = getattr(FrameContext.context, "sbs", None)
    name = getattr(sbs_mod, "__name__", "") or ""
    if "mockgui" in name:
        return "browser mock"
    if "mock" in name:
        return "headless mock"
    return "engine"


# ---------------------------------------------------------------------------
# Camera: pinned to an object with an offset, identical in engine and mock.
# ---------------------------------------------------------------------------
_CAM = {"dolly": 0, "eye": (0.0, 900.0, -2600.0), "target": 0, "look": (0.0, 0.0, 0.0), "seq": 0}


def visual_camera(dolly_id, eye=(0.0, 900.0, -2600.0), target_id=None, look=(0.0, 0.0, 0.0)):
    """Pin the frame: camera at `dolly_id` + `eye`, looking at `target_id` + `look`.

    Both offsets are world-space, so the frame is reproducible run to run - which is the
    whole point: two runs of a specimen must be comparable, and engine vs mock must be
    comparable. `target_id` defaults to the dolly, i.e. look at what you are pinned to.
    """
    from sbs_utils.procedural.query import to_id
    _CAM["dolly"] = to_id(dolly_id) or 0
    _CAM["eye"] = (float(eye[0]), float(eye[1]), float(eye[2]))
    _CAM["target"] = (to_id(target_id) if target_id is not None else _CAM["dolly"]) or 0
    _CAM["look"] = (float(look[0]), float(look[1]), float(look[2]))
    _CAM["seq"] += 1


def visual_camera_seq():
    """Bumped by every visual_camera(); the console watches this to re-pin."""
    return _CAM["seq"]


def visual_camera_apply(client_id):
    """Point one client's cinematic camera at the current pin. Called by the console."""
    if not _CAM["dolly"]:
        return False
    from sbs_utils.procedural.gui.cinematic import gui_cinematic_full_control
    from sbs_utils.vec import Vec3
    gui_cinematic_full_control(client_id, _CAM["dolly"], Vec3(*_CAM["eye"]),
                               _CAM["target"], Vec3(*_CAM["look"]))
    return True


def visual_anchor(x, y, z, name=None):
    """An invisible object to hang the camera on, so a specimen can frame empty space.

    'invisible' art is the detached-camera pattern the admiral/GM consoles already use:
    the engine never draws it and the mock drops it from the radar stream, so it adds
    nothing to the picture it is there to frame.
    """
    from sbs_utils.procedural.spawn import terrain_spawn
    from sbs_utils.procedural.query import to_id
    return to_id(terrain_spawn(x, y, z, name, "#,visual_anchor", "invisible", "behav_selection"))


# ---------------------------------------------------------------------------
# Assertions that don't need eyes.
# ---------------------------------------------------------------------------
_RESULTS = []


def visual_expect(name, cond, detail=""):
    """Record one machine-checkable fact about the specimen. Greppable as VISUAL PASS/FAIL."""
    ok = bool(cond)
    _RESULTS.append((name, ok))
    line = f"VISUAL {'PASS' if ok else 'FAIL'}: {name}"
    if detail:
        line += f"  ({detail})"
    print(line)
    log(line, "visual")
    return ok


def visual_report(strict=False):
    """Summarize the assertions collected so far; optionally fail the run's verdict."""
    total = len(_RESULTS)
    passed = sum(1 for _, ok in _RESULTS if ok)
    failed = total - passed
    line = f"VISUAL REPORT: {passed}/{total} checks passed, {failed} failed"
    print(line)
    log(line, "visual")
    if failed:
        names = ", ".join(n for n, ok in _RESULTS if not ok)
        print(f"VISUAL FAILURES: {names}")
        log(f"VISUAL FAILURES: {names}", "visual")
        if strict:
            raise AssertionError(f"VISUAL: {failed} check(s) failed")
    return failed


def visual_results_clear():
    _RESULTS.clear()


# ---------------------------------------------------------------------------
# The specimen registry + scene reset.
# ---------------------------------------------------------------------------
def visual_specimens():
    """Every `type: visual/*` label, sorted by name - the picker's and slideshow's list."""
    from sbs_utils.procedural.execution import labels_get_type
    labels = list(labels_get_type("visual/"))
    labels.sort(key=lambda l: getattr(l, "name", ""))
    return labels


def visual_specimen_names():
    return [getattr(l, "name", "?").replace("run_visual_", "") for l in visual_specimens()]


# Which specimen the stage is on. Kept here rather than in a MAST shared var so the console
# and the runner label agree without passing it around.
_IDX = {"i": 0}


def visual_index():
    return _IDX["i"]


def visual_step(delta):
    """Move the stage by +/-1, wrapping. Returns the new index."""
    n = len(visual_specimens())
    _IDX["i"] = 0 if n == 0 else (_IDX["i"] + int(delta)) % n
    return _IDX["i"]


def visual_set_index(i):
    n = len(visual_specimens())
    _IDX["i"] = 0 if n == 0 else int(i) % n
    return _IDX["i"]


def visual_set_index_by_name(name):
    """Keep the stage controls in step when a specimen is entered directly via --map."""
    names = visual_specimen_names()
    if name in names:
        _IDX["i"] = names.index(name)
    return _IDX["i"]


def visual_ship_keys():
    """Every shipData key, sorted - the art census walks this."""
    from sbs_utils.procedural.ship_data import get_ship_index
    index = get_ship_index() or {}
    return sorted(index.keys())


def visual_art_root(ship_key):
    """The artfileroot a ship key resolves to (falls back to the key, as the engine does)."""
    from sbs_utils.procedural.ship_data import get_ship_data_for
    info = get_ship_data_for(ship_key) or {}
    return info.get("artfileroot", ship_key)


def visual_planet_spawn(x, y, z, radius=1200, base=(0.55, 0.16, 0.28),
                        emissive=(0.48, 0.24, 0.16), clouds=(1.19, 1.18, 1.2),
                        band=3.72, cloud_strength=3.12, cloud_exponent=3.96, name=None):
    """A gas giant, built exactly the way LM prefab_planetoid / OU worldlet_spawn build one.

    A planet has no shipData entry and no mesh - it is the engine's own surface renderer
    (shader-gasgiant.ps), driven entirely by these planet_* values. Keeping the whole knob
    set in one place means a specimen can vary ONE of them and the difference on screen is
    attributable.
    """
    from sbs_utils.procedural.spawn import terrain_spawn
    from sbs_utils.procedural.query import to_object
    co = to_object(terrain_spawn(x, y, z, name, "#,visual_planet", "planet", "behav_planet"))
    if co is None:
        return 0
    co.engine_object.exclusion_radius = radius
    ds = co.data_set
    sim = FrameContext.sim
    if sim is not None:
        ds.set("planet_last_changed", sim.time_tick_counter, 0)
    ds.set("planet_radius", radius, 0)
    ds.set("planet_baseColorR", base[0])
    ds.set("planet_baseColorG", base[1])
    ds.set("planet_baseColorB", base[2])
    ds.set("planet_emissiveColorR", emissive[0])
    ds.set("planet_emissiveColorG", emissive[1])
    ds.set("planet_emissiveColorB", emissive[2])
    ds.set("planet_upperCloudColorR", clouds[0])
    ds.set("planet_upperCloudColorG", clouds[1])
    ds.set("planet_upperCloudColorB", clouds[2])
    ds.set("planet_bandScale", band, 0)
    ds.set("planet_upperCloudStrength", cloud_strength)
    ds.set("planet_upperCloudExponent", cloud_exponent)
    ds.set("planet_fresnel", 11.96)
    ds.set("planet_fresnelBias", 0.42)
    ds.set("planet_windSpeed1", 1000)
    ds.set("planet_windSpeed2", 1000)
    return co.id


def visual_label_at(i=None):
    """The specimen label at an index (default: the current one), or None if there are none."""
    labels = visual_specimens()
    if not labels:
        return None
    return labels[(_IDX["i"] if i is None else int(i)) % len(labels)]


def visual_stage_position():
    """'3 of 11   blackhole' - the one line the stage controls need."""
    names = visual_specimen_names()
    if not names:
        return "no specimens found"
    i = _IDX["i"] % len(names)
    return f"{i + 1} of {len(names)}   {names[i]}"


def visual_reset_objects():
    """Delete every space object from the previous specimen. Sides survive - they are the
    diplomacy baseline registered once at start, not actors.

    Deletion is DEFERRED (a tombstone now, the native free later) and sim_create() restarts
    the object-id counter, so the two are kept apart with a tick between them rather than
    fused: a scene built in the same breath as the blanking would be handed ids that are
    still queued for freeing. Belt and braces - it has not been observed biting here.

    Callers: visual_reset_objects() -> await delay_sim(1) -> visual_reset_sim() -> delay.
    """
    from sbs_utils.procedural.query import is_space_object_id, is_client_id
    from sbs_utils.procedural.space_objects import delete_object
    from sbs_utils.agent import Agent
    for _id in list(Agent.all.keys()):
        if not is_space_object_id(_id) or is_client_id(_id):
            continue
        a = Agent.all.get(_id)
        if a is not None and a.has_role("__side__"):
            continue
        delete_object(_id)
    _CARD["expect"] = []
    _CARD["title"] = ""
    _CARD["data"] = ""
    _CAM["dolly"] = 0


def visual_reset_sim():
    """Blank the sim itself (nav points, projectiles, contact pairs, spatial hash).

    The sim handle is stale for the rest of the frame afterwards, so the caller must give it
    a tick before anything spawns into it.
    """
    from sbs_utils.procedural.cosmos import sim_create, sim_resume
    sim_create()
    sim_resume()

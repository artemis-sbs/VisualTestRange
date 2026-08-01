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
_CARD = {"title": "", "subtitle": "", "expect": [], "notes": "", "data": "", "seq": 0, "hold": None}


def visual_case(title, expect, notes="", data="", subtitle="", hold=None):
    """Declare the specimen. `expect` is the list of things a correct frame shows.

    Keep every string ASCII and brace-free: it is engine-rendered text, and a stray
    brace in a MAST assignment is an f-string SyntaxError reported against the caller.

    `hold` is how many seconds a SWEEP should leave this one on screen. Default is the
    stage's own VISUAL_HOLD_SECONDS, but a specimen that plays out over time has to say so:
    the camera spikes reach their second half at t+10s and t+12s, and at the default 6s hold
    a sweep tore them down first - so their most interesting half silently never ran.
    """
    _CARD["hold"] = None if hold is None else float(hold)
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


def visual_case_note(note):
    """Replace the card's NOTE line mid-specimen and repaint - for a spike that reaches a
    moment worth calling out ("the live camera post was just deleted")."""
    _CARD["notes"] = str(note)
    _CARD["seq"] += 1
    print(f"VISUAL NOTE {note}")
    log(f"VISUAL NOTE {note}", "visual")


# Widgets a specimen wants drawn under its card. Most specimens are about the 3D view and
# declare none; a specimen about a CONTROL's appearance has nowhere else to put it, because
# only the console builds GUI. Kept declarative (data, not a builder label) so the console can
# draw it without a way to call a label for its layout.
_WIDGETS = []


def visual_widgets(specs):
    """Declare controls to draw under the card. Each spec is [label, background_or_empty]."""
    _WIDGETS.clear()
    for s in specs:
        _WIDGETS.append([str(s[0]), str(s[1]) if len(s) > 1 else ""])
    _CARD["seq"] += 1


def visual_widget_specs():
    return list(_WIDGETS)


def visual_hold(default_seconds):
    """Seconds the sweep should hold the current specimen - its own request, or the default."""
    h = _CARD.get("hold")
    return float(default_seconds) if h is None else h


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

    A single-object shot pins BOTH ids to that object (`target_id` defaults to the dolly), and
    the offsets are then measured relative to it.

    THREE PLACEMENT RULES, all learned the hard way:

    * **Never pin a SHIP at zero offset.** The camera lands inside the hull mesh and you see
      the inside of the model. Only `visual_anchor` (invisible, no mesh) is safe at (0,0,0),
      which is why every specimen frames through an anchor rather than through its subject.
    * **Keep the rig off the sightline.** An offset that puts the dolly object between the
      camera and what it is looking at means you filmed the back of the dolly. Offset toward
      the subject and above, so the hull sits behind the lens.
    * **The dolly must be an assignable object.** See `visual_camera_apply` - the engine wants
      the client assigned to whatever the camera rides, so the dolly cannot be terrain.
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
    """Point one client's cinematic camera at the current pin. Called by the console.

    ASSIGNMENT AND DOLLY ARE DIFFERENT THINGS. The engine needs the client assigned to a space
    object for the console to work at all, but that object is the console's IDENTITY, not the
    lens position - LM's Game Master assigns its client once to an invisible cambot and then
    points the cinematic camera at whatever is selected
    ([gamemaster.mast:623](../../LegendaryMissions/gamemaster/gamemaster.mast#L623)).

    So the console keeps one cambot for its whole life (`visual_client_cambot`) and this only
    moves the lens. Re-assigning per shot would change the console's identity mid-specimen -
    and would quietly break `fx_client_scope`, whose entire subject is what a client's
    assigned ship can see.
    """
    if not _CAM["dolly"]:
        return False
    from sbs_utils.procedural.gui.cinematic import gui_cinematic_full_control
    from sbs_utils.vec import Vec3
    gui_cinematic_full_control(client_id, _CAM["dolly"], Vec3(*_CAM["eye"]),
                               _CAM["target"], Vec3(*_CAM["look"]))
    return True


# client_id -> its cambot. A specimen never knows client ids, but a CUT may need to move the
# camera ship or re-assign the client, so the harness keeps the mapping the console builds.
_CAMBOTS = {}


def visual_cambot_move(x, y, z):
    """Cut by JUMPING THE CAMERA SHIP: teleport every console's cambot. The lens rides it."""
    from sbs_utils.procedural.query import to_object
    from sbs_utils.vec import Vec3
    moved = 0
    for cam_id in list(_CAMBOTS.values()):
        o = to_object(cam_id)
        if o is not None:
            o.pos = Vec3(x, y, z)
            moved += 1
    return moved


def visual_client_assign(obj_id):
    """Cut by RE-ASSIGNMENT: put every console on a different space object."""
    from sbs_utils.procedural.query import to_id
    oid = to_id(obj_id)
    done = 0
    for cid in list(_CAMBOTS.keys()):
        try:
            FrameContext.context.sbs.assign_client_to_ship(cid, oid)
            done += 1
        except Exception:
            pass
    return done


def visual_cambots():
    return dict(_CAMBOTS)


def visual_client_cambot(client_id):
    """Give this console its own invisible cambot and assign the client to it, once.

    The engine requires the assignment; the mock does not, which is exactly why forgetting it
    would survive every headless run and only surface in an engine session.
    """
    from sbs_utils.procedural.query import to_object
    from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
    existing = get_inventory_value(client_id, "visual_cambot", None)
    if existing is not None and to_object(existing) is not None:
        return existing
    cam = visual_anchor(0, 0, 0, "")
    if not cam:
        return None
    set_inventory_value(client_id, "visual_cambot", cam)
    _CAMBOTS[client_id] = cam
    try:
        FrameContext.context.sbs.assign_client_to_ship(client_id, cam)
    except Exception:
        pass
    return cam


def visual_anchor(x, y, z, name=None):
    """An invisible object to hang the camera on, so a specimen can frame empty space.

    Spawned the way LM's Game Master spawns its cambot - `player_spawn` with the 'invisible'
    art, then `__player__` removed ([gamemaster.mast:64](../../LegendaryMissions/gamemaster/gamemaster.mast#L64)).
    It has to be a PLAYER-family object, not terrain: the engine requires the client to be
    ASSIGNED to the object the camera rides, and a terrain object is not assignable. An
    earlier version of this used terrain_spawn, which works fine in the mock and would have
    silently failed in the engine - for a reason having nothing to do with what the camera
    spikes are trying to measure.

    Invisible on both sides: the engine never draws it, and the mock drops it from the radar
    stream, so it adds nothing to the picture it exists to frame.
    """
    from sbs_utils.procedural.spawn import player_spawn
    from sbs_utils.procedural.query import to_object, to_id
    from sbs_utils.procedural.roles import remove_role
    cam = to_object(player_spawn(x, y, z, name or "", "#,visual_anchor", "invisible"))
    if cam is None:
        return 0
    remove_role(cam, "__player__")   # rides the camera, but is not a player ship
    return to_id(cam)


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


# ---------------------------------------------------------------------------
# Drivers: things that move on their own for the duration of one specimen.
#
# Every driver MUST be registered here, because the scene is torn down under it when the
# stage moves on - a survivor would keep writing to deleted objects in the next specimen.
# ---------------------------------------------------------------------------
_DRIVERS = []

# Bumped by every teardown. A long-running MAST task cannot prove it still belongs to the
# scene it was started in by checking an object id: ids are RECYCLED after a sim reset, so a
# stale id happily matches some unrelated object in a later specimen and the task carries on
# spawning ships and re-pointing the camera in someone else's scene. Observed exactly that -
# camera_rate's second pass fired after the whole sweep had finished. Capture the generation
# at start, compare it in the loop.
_GEN = {"n": 0}


def visual_generation():
    """Scene generation. Changes on every teardown; a driver whose generation is stale must end."""
    return _GEN["n"]


def visual_driver(cb, seconds=0.2, count=None):
    """Run `cb(task)` on a repeating tick for as long as this specimen is on stage."""
    from sbs_utils.tickdispatcher import TickDispatcher
    return _register_driver(TickDispatcher.do_interval(cb, seconds, count))


def _register_driver(task):
    _DRIVERS.append(task)
    return task


def visual_drivers_stop():
    """Stop every driver this specimen started. Called by the teardown, first."""
    for t in _DRIVERS:
        try:
            t.stop()
        except Exception:
            pass
    _DRIVERS.clear()


def visual_spin(obj_id, seconds_per_turn=12.0, radius=8000.0):
    """Yaw an object in place, forever, without moving it.

    Steers by DESTINATION rather than by writing a heading: `target_pos_*` is the documented
    navigation lever and both renderers honor it, where a directly-written orientation is not
    reliably settable from script. Throttle stays 0, so the ship turns without translating.
    """
    import math
    from sbs_utils.procedural.query import to_object
    from sbs_utils.tickdispatcher import TickDispatcher
    o = to_object(obj_id)
    if o is None:
        return None
    o.data_set.set("throttle", 0.0, 0)
    base = (o.pos.x, o.pos.y, o.pos.z)
    state = {"t": 0.0}

    def _step(task):
        state["t"] += 0.2
        a = (state["t"] / max(seconds_per_turn, 0.1)) * 2.0 * math.pi
        oo = to_object(obj_id)
        if oo is None:
            task.stop()
            return
        oo.data_set.set("target_pos_x", base[0] + math.sin(a) * radius, 0)
        oo.data_set.set("target_pos_y", base[1], 0)
        oo.data_set.set("target_pos_z", base[2] + math.cos(a) * radius, 0)

    return _register_driver(TickDispatcher.do_interval(_step, 0.2))


def visual_drive_anchor(anchor_id, to_xyz, seconds):
    """Walk an anchor from where it is to `to_xyz` by WRITING ITS POSITION each tick.

    This is the driver whose smoothness is in question (Q3): MAST/tick writes land at a few
    Hz while the view runs at 60, so the engine may show this as a series of jumps. The
    alternative - letting a real object move under its own physics - is what it is measured
    against.
    """
    from sbs_utils.procedural.query import to_object
    from sbs_utils.tickdispatcher import TickDispatcher
    from sbs_utils.vec import Vec3
    o = to_object(anchor_id)
    if o is None:
        return None
    start = (o.pos.x, o.pos.y, o.pos.z)
    state = {"t": 0.0}
    step = 0.2

    def _step(task):
        state["t"] += step
        f = state["t"] / max(seconds, 0.001)
        if f >= 1.0:
            f = 1.0
            task.stop()
        oo = to_object(anchor_id)
        if oo is None:
            task.stop()
            return
        oo.pos = Vec3(start[0] + (to_xyz[0] - start[0]) * f,
                      start[1] + (to_xyz[1] - start[1]) * f,
                      start[2] + (to_xyz[2] - start[2]) * f)

    return _register_driver(TickDispatcher.do_interval(_step, step))


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
    visual_drivers_stop()   # FIRST: a surviving driver would write to the objects being deleted
    _GEN["n"] += 1          # ...and any MAST task still awaiting must see that it is stale
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
    _WIDGETS.clear()
    _CAMBOTS.clear()    # the cambots are space objects too; the console remakes one on repaint
    _CAM["dolly"] = 0


def visual_reset_sim():
    """Blank the sim itself (nav points, projectiles, contact pairs, spatial hash).

    The sim handle is stale for the rest of the frame afterwards, so the caller must give it
    a tick before anything spawns into it.
    """
    from sbs_utils.procedural.cosmos import sim_create, sim_resume
    sim_create()
    sim_resume()

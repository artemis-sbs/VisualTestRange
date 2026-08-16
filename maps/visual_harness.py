"""Shared harness for the Visual Test Range.

A specimen is a label tagged `metadata: type: visual/<name>`. It does three things:

    visual_case("Black hole", ["what you should see", ...], notes=..., data=...)
    _anchor = visual_anchor(0, 0, 0)              # invisible camera post
    visual_camera(_anchor, lens=(0, 900, -2600))   # pin the frame

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
# NOTE (learned the hard way): importing a name here does NOT make it a MAST global.
# Only functions DEFINED in a mission .py become globals; sbs_utils functions become
# globals only by being registered in mast_sbs_procedural.py. amd_cutscene is now
# registered there, so specimens can call cutscene_cast / cutscene_amd directly.


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


# Dropdowns a specimen wants drawn, plus the LIVE widgets the console built from them.
# Buttons can be declared and forgotten; a dropdown specimen is about what happens when a
# script WRITES to one after it is on screen, so the specimen needs the widget back. The
# console registers each one here as it builds it, and re-registers on every rebuild, so a
# specimen always holds the widget that is currently presenting rather than a dead one.
_DROPDOWNS = []
_DROPDOWN_LIVE = {}


def visual_dropdowns(specs):
    """Declare dropdowns to draw under the card.

    Each spec is [name, caption, props, style]. `name` is how the specimen asks for the
    live widget back; `props` is the dropdown's own `text:`/`list:` string; `style` carries
    layout and any `tag:` alias a specimen wants to reach it by.
    """
    _DROPDOWNS.clear()
    _DROPDOWN_LIVE.clear()
    for s in specs:
        _DROPDOWNS.append([str(s[0]), str(s[1]), str(s[2]),
                           str(s[3]) if len(s) > 3 else ""])
    _CARD["seq"] += 1


def visual_dropdown_specs():
    return list(_DROPDOWNS)


def visual_dropdown_register(name, widget):
    """The console handing back the widget it just built. Last build wins."""
    _DROPDOWN_LIVE[str(name)] = widget
    return widget


def visual_dropdown(name):
    """The live widget for `name`, or None before the console has built it."""
    return _DROPDOWN_LIVE.get(str(name))


def visual_dropdown_shown(name):
    """The label a dropdown is currently SENDING to the engine.

    Read from the props string `_present` transmits, not from `.value` -- the two
    disagreeing is the whole subject of LM #568, so a check that trusted `.value` would
    pass while the screen still said something else.
    """
    from sbs_utils.helpers import props_display_text
    w = visual_dropdown(name)
    if w is None:
        return None
    return props_display_text(w.values)


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


# Which consoles have hidden the card. Per CLIENT, not global: two people looking at the
# same range should not fight over each other's screen. Keyed by client id, and a client
# absent from the set is showing the card - so the default survives a mission restart
# without anything having to clear it.
_TEXT_HIDDEN = set()


def visual_text_hidden(client_id):
    """Whether this console has hidden the description card."""
    return client_id in _TEXT_HIDDEN


def visual_text_toggle(client_id):
    """Hide/show the description card on this console. Returns the new state."""
    if client_id in _TEXT_HIDDEN:
        _TEXT_HIDDEN.discard(client_id)
        return False
    _TEXT_HIDDEN.add(client_id)
    return True


def visual_mission_restart():
    """Reload and restart THIS mission from scratch.

    The same call the engine's own error screen uses for its rerun button. Distinct from
    replaying a specimen: this throws away every object, task and camera in the range and
    starts over, which is the only way to clear state a specimen left behind.
    """
    from sbs_utils.fs import get_mission_name
    from sbs_utils.helpers import FrameContext
    FrameContext.context.sbs.run_next_mission(get_mission_name())


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
_CAM = {"dolly": 0, "lens": (0.0, 900.0, -2600.0), "target": 0, "look": (0.0, 0.0, 0.0), "seq": 0, "pushed": 0, "mode": "none", "assign": True}


def visual_camera(dolly_id, lens=(0.0, 900.0, -2600.0), target_id=None, look=(0.0, 0.0, 0.0), assign=True):
    """Pin the frame: camera at `dolly_id` + `lens`, looking at `target_id` + `look`.

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
    # NEVER fall back to id 0. It is a sentinel whose meaning is not yet established (world
    # position? the assigned ship? no camera at all?) - see visual_camera_zero_id - so an
    # object that fails to resolve must be a loud no-op, not a camera pointed at a mystery.
    dolly = to_id(dolly_id)
    if not dolly:
        log(f"visual: camera pin ignored - dolly {dolly_id!r} did not resolve", "visual")
        print(f"VISUAL WARN camera pin ignored - dolly {dolly_id!r} did not resolve")
        return
    _CAM["mode"] = "object"
    _CAM["assign"] = bool(assign)   # False = point WITHOUT assigning (the cut spike's control)
    _CAM["dolly"] = dolly
    _CAM["lens"] = (float(lens[0]), float(lens[1]), float(lens[2]))
    _CAM["target"] = (to_id(target_id) if target_id is not None else dolly) or dolly
    _CAM["look"] = (float(look[0]), float(look[1]), float(look[2]))
    _CAM["seq"] += 1
    _camera_push()


def visual_camera_world(ex, ey, ez, lx, ly, lz):
    """Pin the camera with dolly/target id 0 and the offsets as ABSOLUTE coordinates.

    Exists to test what id 0 means (see visual_camera_zero_id). If the engine reads it as a
    world position this is the most useful call in the camera API - a shot names coordinates
    and needs no anchor object - and if it does not, this is the call that proves it.
    """
    _CAM["mode"] = "world"      # the ONLY deliberate use of id 0 in the range
    _CAM["dolly"] = 0
    _CAM["lens"] = (float(ex), float(ey), float(ez))
    _CAM["target"] = 0
    _CAM["look"] = (float(lx), float(ly), float(lz))
    _CAM["seq"] += 1
    _camera_push()


def _camera_push():
    """Send the pin to every console we know about, NOW.

    The camera used to reach a client only when its console repainted (`on change
    visual_camera_seq()` -> rebuild -> apply). That is enough for the FIRST pin of a specimen,
    which is exactly why every STATIC specimen looked right in the engine while every one that
    moves the camera afterwards did not. A camera is a per-client engine call, not a piece of
    page layout; it should not wait on a GUI rebuild to be delivered.
    """
    n = 0
    for cid in list(_CAMBOTS.keys()):
        if visual_camera_apply(cid):
            n += 1
    _CAM["pushed"] = n


def visual_camera_delivered():
    """How many consoles the last pin actually reached.

    Renderer-agnostic, so it is a real check in both: zero means the camera was set and went
    nowhere, which is precisely the failure that made every dynamic specimen look broken in
    the engine while passing headless. A specimen that MOVES its camera should assert this.
    """
    return _CAM["pushed"]


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
    # NOTE: id 0 is NOT "no camera" here - it is the case under test (visual_camera_zero_id).
    # Only an unset pin should be skipped, so the sentinel is the sequence, not the id.
    if _CAM["mode"] == "none":
        return False
    from sbs_utils.procedural.gui.cinematic import gui_cinematic_full_control
    from sbs_utils.procedural.query import to_object
    from sbs_utils.vec import Vec3

    dolly = _CAM["dolly"]
    target = _CAM["target"]
    lens = _CAM["lens"]
    look = _CAM["look"]

    # ENGINE CONSTRAINT: dolly and target must be the SAME object, or the frame is black.
    # Confirmed with everything else held constant. Nearly every specimen in this range pins an
    # anchor and looks at a subject - two objects - which is why the camera work here looked
    # broken in ways that had nothing to do with what each specimen was testing.
    #
    # Re-express it: keep the SUBJECT, and turn the anchor's position into the lens offset.
    # The shot is unchanged; only its spelling is.
    if _CAM["mode"] == "object" and target and dolly != target:
        _d = to_object(dolly)
        _t = to_object(target)
        if _d is not None and _t is not None:
            lens = ((_d.pos.x + lens[0]) - (_t.pos.x + look[0]),
                   (_d.pos.y + lens[1]) - (_t.pos.y + look[1]),
                   (_d.pos.z + lens[2]) - (_t.pos.z + look[2]))
            look = (0.0, 0.0, 0.0)
        dolly = target

    # ...and never sit exactly on the look-at point: a zero-length view vector has no
    # direction, so the frame is black.
    if dolly == target and lens == look:
        lens = (lens[0], lens[1], lens[2] - 50.0)
    # ASSIGN THE CLIENT TO THE DOLLY. Engine-observed: a camera change only takes when the
    # console is assigned to the object the lens rides. Re-pointing alone left a black screen;
    # so did moving the object the lens was already on. Assigning and then pointing worked.
    #
    # This reverses what I took from the Game Master - that assignment is the console's
    # identity and the dolly is merely where the lens sits. GM does point at objects it is not
    # assigned to, so something there is still unaccounted for; but on the evidence in front of
    # us, the assignment is what makes a change take, and the range follows the evidence.
    if _CAM["mode"] == "object" and dolly and _CAM.get("assign", True):
        try:
            FrameContext.context.sbs.assign_client_to_ship(client_id, dolly)
        except Exception:
            pass
    gui_cinematic_full_control(client_id, dolly, Vec3(*lens), dolly, Vec3(*look))
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


def visual_client_assign_back():
    """Put every console back on its own cambot - so a beat that tested reassignment does not
    leave the next beat testing something else."""
    n = 0
    for cid in list(_CAMBOTS.keys()):
        if visual_client_assign_one(cid, _CAMBOTS[cid]):
            n += 1
    return n


def visual_cambots():
    return dict(_CAMBOTS)


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

def visual_client_cambot(client_id):
    """Spawn (or reuse) this console's invisible cambot. Does NOT assign the client.

    Assignment is deliberately separate so it can be given its own tick: LM's Game Master
    waits a full `delay_sim(1)` between spawning its cambot and assigning a client to it, and
    only sets the view up afterwards. This console did all three inside one build, which is a
    plausible cause of a camera that works sometimes. See visual_client_camera_setup.
    """
    from sbs_utils.procedural.query import to_object
    from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
    existing = get_inventory_value(client_id, "visual_cambot", None)
    if existing is not None and to_object(existing) is not None:
        _CAMBOTS[client_id] = existing
        return existing
    # WHERE the cambot sits is not cosmetic: the console is ASSIGNED to it, and the engine
    # scopes what a console receives around its assigned object - so a cambot parked in deep
    # space is a console that gets culled away from its own scene. LM keeps its cambots in the
    # area of interest (the GM pans its own on click). Parking one 100km up was mine, and it
    # survived the mock only because the mock BROADCASTS terrain to every client and culls
    # only the dynamic stream - so a terrain-heavy range looked fine with the console nowhere
    # near the scene.
    #
    # Near the scenes, above the plane, and clear of the gravity wells this range spawns:
    # 6708u from the hole at the origin (radius 1500), 11225u from the one at x=9000
    # (radius 4000). An object at a well's exact centre has no direction to be pulled in, its
    # position goes NaN, and the engine asserts.
    cam = visual_anchor(CAMBOT_HOME[0], CAMBOT_HOME[1], CAMBOT_HOME[2], "")
    if not cam:
        return None
    set_inventory_value(client_id, "visual_cambot", cam)
    _CAMBOTS[client_id] = cam
    return cam


def visual_client_assign_one(client_id, cam_id):
    """Assign one console to its cambot. Its own step, one tick after the spawn."""
    from sbs_utils.procedural.query import to_id
    oid = to_id(cam_id)
    if not oid:
        return False
    try:
        FrameContext.context.sbs.assign_client_to_ship(client_id, oid)
    except Exception:
        return False
    return True


_SETUP_STARTED = set()

# Which clients have a console. Survives a scene reset - the CAMBOTS do not (sim_create wipes
# every object), so after each teardown the stage rebuilds one per console from this list.
_CONSOLE_CLIENTS = []

# Where a cambot lives when nothing is borrowing it: near the scenes, above the plane, clear
# of the gravity wells this range spawns.
CAMBOT_HOME = (0.0, 3000.0, -6000.0)


def visual_console_clients():
    return list(_CONSOLE_CLIENTS)


def visual_camera_needs_setup(client_id):
    """True once per console - the stage uses it to start the setup task exactly once."""
    if client_id not in _CONSOLE_CLIENTS:
        _CONSOLE_CLIENTS.append(client_id)
    if client_id in _SETUP_STARTED:
        return False
    _SETUP_STARTED.add(client_id)
    return True


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

    Uses `engine_object.steer_yaw` - a rotation RATE the engine applies itself, with nothing
    to drive per tick. It is how LM tumbles its asteroids (gamemaster/move_to_lib.py).

    It previously circled a `target_pos` around the object, which is how the MOCK's steering
    works: its physics reads target_pos and turns toward it. The engine does not steer an NPC
    from that alone, so the subject sat perfectly still - and a motionless ship reads exactly
    like a world-space camera, so the Q1 spike would have returned a confident wrong answer.
    `radius` is kept so callers do not break, and is unused.
    """
    from sbs_utils.procedural.query import to_object
    o = to_object(obj_id)
    if o is None:
        return None
    o.data_set.set("throttle", 0.0, 0)
    # rad/s for one full turn in `seconds_per_turn`. This used to carry a fudge factor of
    # 0.35 that made a "14 second turn" take 251 seconds - slow enough to look like nothing
    # happening unless you happened to watch for a minute. Compute it, do not guess it.
    import math
    o.engine_object.steer_yaw = 2.0 * math.pi / max(seconds_per_turn, 0.1)
    return obj_id


def visual_heading(obj_id):
    """Compass heading in degrees from an object's forward vector."""
    import math
    from sbs_utils.procedural.query import to_object
    o = to_object(obj_id)
    if o is None:
        return 0.0
    f = o.engine_object.forward_vector()
    return math.degrees(math.atan2(f.x, f.z))


def visual_rate_text(h0, h1, seconds):
    """'25.7 deg/s - one turn every 14.0s' from two headings and the gap between them.

    The units of steer_yaw are not documented anywhere, so the honest thing is to MEASURE
    what the renderer actually did and put the number on the card. A spin that reads as
    "nothing is happening" then says so in degrees instead of being argued about.
    """
    d = (h1 - h0 + 540.0) % 360.0 - 180.0
    rate = abs(d) / max(seconds, 0.001)
    if rate < 0.05:
        return "measured 0.0 deg/s - NOT ROTATING"
    return f"measured {rate:.1f} deg/s - one turn every {360.0 / rate:.1f}s"


def visual_rate_value(h0, h1, seconds):
    d = (h1 - h0 + 540.0) % 360.0 - 180.0
    return abs(d) / max(seconds, 0.001)


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


def visual_console_restore():
    """Put every console back the way a specimen found it: cambot home, client assigned to it.

    A specimen is allowed to borrow console state - the cut spike deliberately reassigns the
    client and teleports the cambot to see what a cut does. Before this range ran on ONE sim
    that was self-correcting, because the cambots were rebuilt each time. Now they persist, so
    a borrowed cambot stays borrowed and the next specimen runs with its console assigned to
    somebody else's ship, parked in the middle of a scene it has nothing to do with.

    Restoring here rather than per-specimen means a specimen cannot forget, and a specimen
    that CRASHES mid-sequence cannot poison the rest of the run.
    """
    from sbs_utils.procedural.query import to_object
    from sbs_utils.vec import Vec3
    for cid in list(_CAMBOTS.keys()):
        cam_id = _CAMBOTS[cid]
        o = to_object(cam_id)
        if o is None:
            continue
        o.pos = Vec3(*CAMBOT_HOME)
        visual_client_assign_one(cid, cam_id)


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
    visual_console_restore()   # ...and a specimen must not leave a console borrowed
    _GEN["n"] += 1          # ...and any MAST task still awaiting must see that it is stale
    keep = set(_CAMBOTS.values())
    for _id in list(Agent.all.keys()):
        if not is_space_object_id(_id) or is_client_id(_id):
            continue
        a = Agent.all.get(_id)
        if a is not None and a.has_role("__side__"):
            continue
        if _id in keep:
            continue        # a console's cambot is INFRASTRUCTURE, not scene
        delete_object(_id)
    _CARD["expect"] = []
    _CARD["title"] = ""
    _CARD["data"] = ""
    _WIDGETS.clear()
    # No pin between specimens. This used to leave dolly 0 live, so any console repaint during
    # a transition sent a camera aimed at the sentinel - which, depending on what 0 means,
    # jumps to the origin, to the parked cambot, or disables the view. A blank frame at every
    # switch would look exactly like the reset bug it is not.
    _CAM["mode"] = "none"
    _CAM["dolly"] = 0


def visual_reset_sim():
    """Blank the sim itself (nav points, projectiles, contact pairs, spatial hash).

    NOT USED between specimens, deliberately. This range runs on ONE sim for the whole
    session: sim_create() destroys every object including each console's cambot, which left
    the client assigned to a deleted object and forced a rebuild - and the rebuild needs a
    tick between assigning and pointing the camera, so the race came back at every single
    specimen switch. Deleting the scene's own objects is enough, and console infrastructure
    then simply never goes away.

    Kept for a caller who genuinely wants a blank sim. The sim handle is stale for the rest
    of the frame afterwards, so give it a tick before anything spawns into it.
    """
    from sbs_utils.procedural.cosmos import sim_create, sim_resume
    sim_create()
    sim_resume()


def mod_art_declare():
    """Declare the mod-art candidates, the same call an add-on makes.

    Kept in the harness rather than the specimen because `import <file>.py` merges only
    FUNCTIONS into MAST's namespace and every one becomes a MAST global - a second .py just
    to hold this would be one more name to collide with.
    """
    import os
    from sbs_utils.fs import get_mission_dir
    from sbs_utils.procedural.ship_data_mod import ship_data_merge_mod
    path = os.path.join(get_mission_dir(), "maps", "mod_art_ships.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        log("mod art: cannot read " + path + ": " + str(e), "visual", "warning")
        return None
    return ship_data_merge_mod(text, "VisualTestRangeModArt")


# --- mod-carried art: which combination actually resolves? -------------------
#
# Engine 1.3.5 added two things that bear on this: `sbs.add_extra_ship_data(file, path)`,
# which loads ship data straight out of a mod folder (measured working - the engine read
# shields [110,90] from anime_ships/mod_ships.json with nothing written into the mission),
# and `art_file_path`, a PATH sibling to the name-based `artfileroot`, available on hullmap
# AND in ship data files.
#
# On 1.3.4 no arrangement worked: artfileroot resolves relative to data/graphics/ships and
# would not walk out of it. The question now is which COMBINATION of the two fields, and
# which spelling of the path, the engine actually honors - so each variant below changes
# exactly one thing and they are judged side by side in a single frame.
_MOD_PACK = "__lib__/media/artemis-sbs.Anime-Fan-Mod.media.v1.0.0/ships"

MOD_ART_VARIANTS = (
    # RETARGETED for engine 1.3.6, which changed the question underneath this specimen.
    #
    # `artfileroot` IS A PATH now: the engine's own shipData.yaml reads `ships/<name>` for
    # all 184 entries, so the base moved up from data/graphics/ships to data/graphics, and
    # a BARE root no longer resolves - it asserts (`false && "the artfileroot of this ship
    # was not found."`, ObjectTypeDrawData.cpp:44, measured one hull per run).
    # `artfilepath` is gone from the engine's data, so every variant spells the whole path
    # in `artfileroot` alone.
    #
    # ONE COPY OF THE ART PER SPELLING (GP_exe / GP_gfx / GP_data). Three spellings of the
    # SAME file are indistinguishable by access time, and the first run of this retarget
    # proved only "one of these three worked" - which is not an answer. Each variant now
    # names its own mesh, so the filesystem attributes it.
    ("control_ok",  "stock hull, new ships/ spelling",     "ships/tsn_light_cruiser"),
    ("root_exe",    "path from the EXE folder",            "data/missions/%s/GP_exe" % _MOD_PACK),
    ("root_gfx",    "RELATIVE to data/graphics",           "../missions/%s/GP_gfx" % _MOD_PACK),
    ("root_data",   "RELATIVE to the data folder",         "missions/%s/GP_data" % _MOD_PACK),
    ("root_bare",   "BARE name - expected to assert",      "God_Phoenix"),
    ("control_bad", "a name that exists nowhere",          "ships/God_Phoenix_nope"),
)


def mod_art_mark(stage, detail=""):
    """Leave a breadcrumb on disk, so a variant that ASSERTS the engine still names itself.

    An assert kills the process before any report is written, so the usual "run it and read
    the output" loop reports nothing at all - the crash is invisible and unattributable.
    Writing the stage BEFORE attempting it means the last line on disk is the thing that
    killed it.
    """
    import os
    from sbs_utils.fs import get_mission_dir
    try:
        with open(os.path.join(get_mission_dir(), "mod_art_progress.txt"), "a",
                  encoding="utf-8") as f:
            f.write(stage + ("  " + detail if detail else "") + chr(10))
    except OSError:
        pass


def mod_art_only():
    """One variant name from the launch argument `variant=`, or None for all of them.

        Artemis3-x64-release.exe autostartserver defaultmission=VisualTestRange             map=visual_mod_art variant=abs_obj

    Bisecting a crash needs one variant per process, and this is what makes that a loop a
    script can drive instead of ten hand edits.
    """
    from sbs_utils.procedural.command_line import command_line_get
    only = command_line_get("variant")
    return only.strip() if only else None


def mod_art_key():
    """Which KEY spells the art path in a ship data file - `artkey=` on the command line.

    Defaults to `artfilepath`, because shipData spells every key without underscores:
    `artfileroot`, `meshscale`, `meshrotate`, `torpedostart`. The pybind PROPERTY is
    `art_file_root`, so the pyi's new `art_file_path` is the property name, and the file
    key that feeds it should be `artfilepath`.

    Several close-up runs were spent writing `art_file_path` into the file and concluding
    the engine ignored it. It was the wrong key, not the wrong engine - hence making the
    spelling a launch argument, so the next guess costs a relaunch and not an edit.
    """
    from sbs_utils.procedural.command_line import command_line_get
    return (command_line_get("artkey") or "artfilepath").strip()


def mod_art_build_and_load():
    """Write the variant ship data, then hand it to the engine by PATH.

    Generated rather than committed because `art_file_path` may need to be absolute, and an
    absolute path baked into a repo file is wrong on every other machine.

    Returns a (loaded, note) pair so the specimen can say what happened rather than just
    looking broken.
    """
    import json
    import os
    from sbs_utils.fs import get_mission_dir
    from sbs_utils.procedural.ship_data import get_ship_data_for

    mission = get_mission_dir()
    base = get_ship_data_for("tsn_light_cruiser")
    if base is None:
        return False, "no tsn_light_cruiser in ship data to base the variants on"
    only = mod_art_only()
    wanted = _mod_art_select(only)
    if not wanted:
        return False, "variant=" + str(only) + " matched none of " + ",".join(
            v[0] for v in MOD_ART_VARIANTS)
    entries = []
    for key, _why, root in wanted:
        e = dict(base)
        e["key"] = "modart_" + key
        e["name"] = key
        e["meshscale"] = 0.17 if key == "closeup" else 0.2
        e["artfileroot"] = root
        # `artfilepath` is deliberately NOT written. It is gone from the engine's own
        # data, and artfileroot carries the whole path now - so a variant that set both
        # would not be testing one thing.
        e.pop(mod_art_key(), None)
        entries.append(e)

    # The 2026-08-15 engine takes ONE argument, the fully-pathed file. (It still searches
    # for a missing extension, measured - but naming the file we just wrote means the
    # engine and this harness cannot end up reading different ones.)
    stem = "mod_art_variants"
    name = stem + ".json"
    try:
        with open(os.path.join(mission, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"#ship-list": entries}, indent=4) + "\n")
    except OSError as e:
        return False, "could not write " + name + ": " + str(e)

    sbs = FrameContext.context.sbs
    fn = getattr(sbs, "add_extra_ship_data", None)
    if fn is None:
        return False, "add_extra_ship_data absent - engine older than 1.3.5"
    mod_art_mark("LOADING", ",".join(e["key"] for e in entries))
    try:
        fn(os.path.join(mission, name).replace("\\", "/"))
    except Exception as e:
        return False, "add_extra_ship_data raised: " + str(e)
    mod_art_mark("LOADED")
    return True, "loaded " + str(len(entries)) + " variants from " + name


# Variants whose artfileroot names art the engine CANNOT resolve. On engine 1.3.5 that
# segfaults at render time (exit 0xC0000005, reproduced 4/4 across two rounds) - the object
# spawns fine and the process dies when it is drawn. On 1.3.4 the same condition drew the
# `unknown` placeholder, so this is a regression, reported separately.
#
# They are kept in the list because they are the honest test of "art the engine does not
# have", and they must go back in the moment the crash is fixed. `variant=safe` is how the
# REST of the specimen stays runnable meanwhile: without it one engine bug makes the whole
# art question unanswerable.
MOD_ART_CRASHERS = ("root_bare", "control_bad")   # both MEASURED to assert on 1.3.6

# --- turning the crash into an ORACLE ---------------------------------------
#
# Whether an `art_file_path` resolved is normally a question only an eye can answer: if it
# fails, the ship falls back to its `artfileroot` and still draws a hull, so "worked" and
# "did not work" look equally fine to any script.
#
# Unless the fallback is fatal. An unresolvable `artfileroot` segfaults 1.3.5 at render, so
# an entry with a DELIBERATELY BROKEN root plus a candidate path answers itself:
#
#     engine still alive  -> art_file_path resolved and was drawn
#     engine died         -> it did not, and the broken root was reached
#
# That converts six by-eye comparisons into a loop a script can run unattended. It depends
# on a bug, so it stops working the day the crash is fixed - which is fine, because a
# guarded miss will draw the placeholder again and the eye test comes back.
MOD_ART_ORACLE_ROOT = "God_Phoenix_definitely_not_here"

MOD_ART_ORACLES = (
    ("none",        None),                       # control: MUST die, or the oracle is void
    ("abs_noext",   "{ships}/God_Phoenix"),
    ("abs_obj",     "{ships}/God_Phoenix.obj"),
    ("rel_gfx",     "../../missions/anime_mods/anime_ships/graphics/ships/God_Phoenix"),
    ("rel_mission", "../anime_mods/anime_ships/graphics/ships/God_Phoenix"),
    ("rel_data",    "missions/anime_mods/anime_ships/graphics/ships/God_Phoenix"),
    ("rel_exe",     "data/missions/anime_mods/anime_ships/graphics/ships/God_Phoenix"),
)


# ONE ship, framed close, at the mod's own meshscale - `variant=closeup_<form>`.
#
# This exists because a comparison row is the wrong instrument for "did this work". The row
# forces every hull to meshscale 0.2 and sits the camera 5800 units back, and at that size a
# God Phoenix and a TSN light cruiser are both a grey speck. A hedged read of one of those
# specks was recorded as a confirmed result, and the close-up flatly contradicted it. Judge
# a hull from close range or do not judge it.
#
# artfileroot stays VALID in every close-up, so nothing here can hit the unresolvable-art
# segfault - the ship falls back to a TSN cruiser instead of killing the engine, which is
# also what makes the readout unambiguous: TSN cruiser = the path did nothing.
# WHAT A MOD'S ART FOLDER HOLDS
#
#   <root>.obj  _diffuse  _emissive  _normal  _specular      authored source
#   <root>.mtl                                               source too - KEEP IT
#   .paxmesh  .pointcube  <root>1024.png  <root>256.png      baked (see variant=bake)
#
# The engine ignores `.mtl`: its own art references an `artemis.mtl` that is not even in
# the folder. But ignored is not unwanted - the meshes are Blender exports carrying an
# `mtllib` line, so anyone reopening the source art in Blender needs it. Source art and
# shipped art are different sets, and the engine's needs are only half the story.


# THE ENGINE TEAM'S OWN WORKING EXAMPLE - data/missions/BeamArcTest/extraShipDataAAA.json:
#
#     "artfileroot": "tsn_light_cr",
#     "artfilepath": "data/missions/BeamArcTest/extraShipGraphicData",
#
# Two things that no amount of guessing here arrived at. `artfilepath` is the FOLDER and
# `artfileroot` stays the file's base NAME - they work together, rather than one replacing
# the other - and the path is relative to the EXE folder. Every earlier attempt put a file
# path into artfilepath and dropped artfileroot, which is neither half right.
#
# The second lesson is in the folder listing, not the json. Their art ships the FULL set:
#
#     tsn_light_cr.obj .paxmesh .pointcube .rawbitmap .png
#     tsn_light_cr1024.png tsn_light_cr256.png
#     _diffuse _emissive _normal _specular
#
# The anime mod carries only .obj/.mtl and the four maps - no paxmesh, pointcube, rawbitmap
# or the 1024/256 bitmaps. That gap is the leading suspect for the render crashes, and it is
# why `example` below is run FIRST: it uses art that is known complete, so it separates "the
# mechanism is wrong" from "this particular art is incomplete".
MOD_ART_TWO_FIELD = {
    # name           artfileroot        artfilepath (folder, relative to the exe)
    "example":      ("tsn_light_cr",    "data/missions/BeamArcTest/extraShipGraphicData"),
    "anime_exe":    ("God_Phoenix",     "data/missions/anime_mods/anime_ships/graphics/ships"),
    "anime_abs":    ("God_Phoenix",     "{ships}"),
    # The SAME art with its mesh flattened to one object / one material. God_Phoenix.obj is
    # a 16-object, 16-material Blender export; every mesh the engine ships is 1/1. This is
    # the discriminator for whether the loader handles multi-object OBJ at all.
    "anime_flat":   ("God_Phoenix_flat", "data/missions/anime_mods/anime_ships/graphics/ships"),
    # THE DISCRIMINATOR for the render crash. The engine's OWN art, copied into a mod
    # folder with the derived files (.paxmesh .pointcube .rawbitmap 1024 256) stripped, so
    # the engine has to generate them exactly as it must for any real mod.
    #   crashes -> generation is broken for everyone; their BeamArcTest never hits it only
    #              because its derived files are already committed
    #   renders -> generation works and the anime .obj itself is what the engine chokes on
    "gen_test":     ("tsn_light_cr",    "data/missions/VisualTestRange/art_gen_test"),
}

MOD_ART_PATH_FORMS = {
    "abs_noext":   "{ships}/God_Phoenix",
    "abs_obj":     "{ships}/God_Phoenix.obj",
    "abs_dir":     "{ships}",
    "rel_gfx":     "../../missions/anime_mods/anime_ships/graphics/ships/God_Phoenix",
    "rel_mission": "../anime_mods/anime_ships/graphics/ships/God_Phoenix",
    "rel_data":    "missions/anime_mods/anime_ships/graphics/ships/God_Phoenix",
    "rel_exe":     "data/missions/anime_mods/anime_ships/graphics/ships/God_Phoenix",
    "none":        None,
}


def _mod_art_select(only):
    # BAKE: spawn one ship by artfileroot ALONE, with the art sitting in data/graphics/ships,
    # so the engine generates its derived files there. That path does not crash - only
    # generating into a mod folder does - so it is the workaround while the crash is open:
    # bake once as the author, then ship the generated files with the mod.
    #
    #   variant=bake bakeroot=<artfileroot>
    if only == "bake":
        from sbs_utils.procedural.command_line import command_line_get
        root = (command_line_get("bakeroot") or "").strip()
        if not root:
            return []
        return [("bake", "bake " + root, root, None)]
    # The engine team's shape: BOTH fields, artfilepath a folder. `variant=two_example`.
    if only is not None and only.startswith("two_"):
        name = only[len("two_"):]
        pair = MOD_ART_TWO_FIELD.get(name)
        if pair is None:
            return []
        root, folder = pair
        return [("closeup", "two-field: root=" + root + " folder=" + folder, root, folder)]
    if only is not None and only.startswith("closeup"):
        form = only[len("closeup"):].lstrip("_") or "rel_gfx"
        path = MOD_ART_PATH_FORMS.get(form, "MISSING-FORM")
        root = "God_Phoenix" if form == "abs_dir" else "tsn_light_cruiser"
        return [("closeup", "close-up: art_file_path = " + str(path), root, path)]
    if only is not None and only.startswith("oracle_"):
        want = only[len("oracle_"):]
        return [("oracle_" + name, "oracle: broken root + " + str(path),
                 MOD_ART_ORACLE_ROOT, path)
                for name, path in MOD_ART_ORACLES if name == want]
    if only is None:
        return list(MOD_ART_VARIANTS)
    if only == "safe":
        return [v for v in MOD_ART_VARIANTS if v[0] not in MOD_ART_CRASHERS]
    if only == "crashers":
        return [v for v in MOD_ART_VARIANTS if v[0] in MOD_ART_CRASHERS]
    return [v for v in MOD_ART_VARIANTS if v[0] == only]


def mod_art_variant_keys():
    return ["modart_" + v[0] for v in _mod_art_select(mod_art_only())]

# Specimens in this range's own extraShipData.json that point at art ON PURPOSE not there,
# so the missing-art path itself can be looked at. They are not failures.
VISUAL_ART_DELIBERATELY_MISSING = ("modart_bare",)


def visual_art_roots_missing():
    """Every (ship_key, artfileroot) in the catalog whose art is not in the install.

    The census puts one object per key in a grid so a missing art root shows as a HOLE -
    which works, and needs an eye on it. This is the same question asked of the filesystem,
    so a headless run can fail on it too.

    It matters most for ADD-ON hulls, whose art roots nobody has ever seen render: LM's
    turret entries asked for `tsn-fighter` when the art is `TSNfighter`, and the first
    client to draw one got a modal assert out of ObjectTypeDrawData.cpp. Empty when there
    is no install to check against."""
    import os
    from sbs_utils.procedural.ship_data import get_ship_index, get_ship_data_for
    try:
        from sbs_utils.fs import get_artemis_dir
        ships = os.path.join(get_artemis_dir(), "data", "graphics", "ships")
        if not os.path.isdir(ships):
            return []
        have = set()
        for name in os.listdir(ships):
            have.add(name.split(".")[0].lower())
    except Exception:                               # noqa: BLE001
        return []
    missing = []
    for key in sorted((get_ship_index() or {}).keys()):
        if key in VISUAL_ART_DELIBERATELY_MISSING:
            continue
        root = str((get_ship_data_for(key) or {}).get("artfileroot", key) or "")
        # A PATH is a mod keeping art outside the install. It resolves somewhere this
        # check does not look, so a bare-name catalog says nothing about it.
        if "/" in root or "\\" in root:
            continue
        if root and root.lower() not in have:
            missing.append((key, root))
    return missing

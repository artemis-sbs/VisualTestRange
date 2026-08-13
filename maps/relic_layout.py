"""The demo relic: a branching interior authored declaratively and dressed as shells.

Two things this exists to show.

**The layout is data, and it is not in this file.** The whole dungeon lives in
`ossuary.amd` - eight chambers, seven passages, a box hall and two subtracted solids.
This module only DRESSES what that file describes.

It began as a YAML string right here, which is the shape this project keeps converting
away from: nothing about it was discoverable, lintable, or reachable by tooling. As AMD
it gets schema-backed fields, `sbs lint` rules, LSP completion and hover, and the VS Code
relic plan can draw it and drag its chambers.

**A chamber is a SHELL OF PROPS, not one giant mesh.** Measured by eye in the engine:
a single asteroid scaled 80x reads as "more of a tunnel than a room", and scaling one
mesh up to room size gives terrible texel density and one obvious repeated silhouette
anyway. So the volume defines the space and ordinary-scale props are scattered over
its boundary, which is what the player actually sees. S1 proved the engine draws a
mesh from inside it, so a shell reads as an enclosing wall.

Every prop is TERRAIN with `exclusion_radius = 0`: visible, not solid, and passive.
Passive matters - an AI behavior carrying a zero radius NaNs the engine and asserts
(`Simulation.cpp:739`, `SpaceObjectAITyphon.cpp:111`). Containment is entirely
script-side, so the engine's collision system is not involved at any point.

Chamber spacing is kept under ~3500u because `render-distance-objects` is 5000: a
relic whose chambers sit further apart than that stops drawing its own far side.
"""

import math
import random

from sbs_utils.procedural.amd_relics import relics_build, relic_record
from sbs_utils.procedural.volume import (volume_get, volume_surface_points,
                                          volume_inside_points, volume_solid_points)
from sbs_utils.procedural.spawn import terrain_spawn
from sbs_utils.procedural.space_objects import set_pos, clear_target
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.terrain import (
    terrain_sow_begin, terrain_sow_end, terrain_sow_pending,
    terrain_spawn_nebula_sphere, terrain_setup_nebula,
    terrain_set_nebula_object_size,
)

# The volume name IS the relic's key in ossuary.amd. See relic_define.
VOLUME = "ossuary"

# The relic. Branching, three-dimensional (the shaft and crypt are off the ecliptic,
# so this is a dungeon rather than a floor plan).
#
# TWO SIZE RULES shape these numbers:
#   * Neighbouring chambers stay under ~3500u apart, because
#     `render-distance-objects` is 5000 - space them wider and the relic stops
#     drawing its own far side.
#   * The WHOLE relic stays inside ~11200u across, so its bounding sphere fits in ONE
#     nebula (a single nebula can be ~12000 with the new shader). That keeps the
#     atmosphere at one object. The first draft was 13463 across and the `core`
#     chamber poked out of its own air.
# The relic itself lives in ossuary.amd, NOT here.
#
# It used to be a YAML string in this file, which is the shape this project keeps
# converting away from: nothing about it was discoverable, lintable, or editable by
# tooling. As AMD it gets schema-backed fields, `sbs lint` checks, LSP completion, and
# the VS Code relic plan can draw and drag it.
RELIC_FILE = "maps/ossuary.amd"

# Art with no interior detail of its own reads best as raw rock wall.
#
# VERIFY THESE AGAINST shipData. An unknown key does not fail - it silently falls back
# to the shipData `unknown` mesh, so a typo shows up as a relic built out of question
# marks. `plain_asteroid_4` and `_5` do NOT exist (the plain set starts at 6); inventing
# them made two thirds of the props draw as unknowns.
_PROP_ART = ("plain_asteroid_6", "plain_asteroid_7", "plain_asteroid_8",
             "plain_asteroid_9", "plain_asteroid_10", "plain_asteroid_11")


def relic_define():
    """Build the volume from the authored AMD file. Returns the RECORD.

    One call: `relics_build` loads the document with the relic fence handler wired in,
    walks the section, registers the records and builds the volume. The fence handler is
    the part that is easy to forget - without it every field falls through to the default
    coercion and the relic builds as nothing.

    Building under the relic's OWN key rather than a name of our own is what lets the rest
    of the library address it: `relic_contain` and the live-preview reload both resolve
    from the record, and a mission that renames the volume silently opts out of both. That
    is not hypothetical - while this file passed `name="relic"`, the Ossuary's authored
    `Scrape band: 120` never once reached its watcher.
    """
    from sbs_utils.fs import get_mission_dir_filename
    rec, vol = relics_build(get_mission_dir_filename(RELIC_FILE))
    return rec


def _prop(rng, art_keys, x, y, z, scale):
    """One piece of wall: terrain, non-solid, never an AI behavior."""
    art = art_keys[rng.randrange(len(art_keys))]
    p = terrain_spawn(x, y, z, "", "#,relic_wall", art, "behav_asteroid")
    s = scale * rng.uniform(0.75, 1.35)
    p.blob.set("local_scale_x_coeff", s, 0)
    p.blob.set("local_scale_y_coeff", s * rng.uniform(0.8, 1.2), 0)
    p.blob.set("local_scale_z_coeff", s * rng.uniform(0.8, 1.2), 0)
    p.engine_object.exclusion_radius = 0
    return p


def relic_dress(seed=None, props=600, fill=0, over=6):
    """Scatter the wall props over the volume boundary. Returns how many were made.

    THE MATHS IS NOT HERE ANY MORE. `volume_surface_points` and `volume_solid_points` do
    the sampling - evenly over a sphere, around a capsule at any orientation, on the faces
    of a box, clipped to the outside of the union - and this picks art, scale and roles.
    That split is the point: the geometry was general and every relic mission would have
    copied it, while the look is this demo's and nobody should inherit it.

    IDENTITY, not "run once": if the walls are already here, this is a no-op. The mock
    runner and the LM server console can BOTH launch a @map, which doubled the prop count
    on a restart soak - 454 became 908. Building only what is missing makes that harmless,
    the same reason the house pattern is `player_ensure` rather than a once-flag.

    `seed` and the art list default to what the RELIC AUTHORED (`Seed:` and `Art:` in the
    .amd), so the file says how it looks rather than this module deciding for it.
    """
    vol = volume_get(VOLUME)
    if vol is None:
        return 0
    existing = len(role("relic_wall"))
    if existing:
        return existing
    rec = relic_record(VOLUME)
    if seed is None:
        seed = int(rec.get("seed") or 7) if rec is not None else 7
    art = _relic_art(rec)
    rng = random.Random(seed)
    made = 0
    # NOT SOWN, and the bracket that used to be here was a lie: the sower intercepts only
    # `terrain_spawn_asteroid_scatter` and the nebula path, so wrapping direct
    # `terrain_spawn` calls queued nothing and `relic_sow_pending()` was always 0. It
    # cannot simply be made real either - under a sow scope the spawn is queued and returns
    # nothing, so there is no object to tag, and these props need their role for undress.
    # Measured cost is ~0.08 ms per asteroid, so ~600 props is ~50 ms: worth sowing when
    # that shows, and worth solving the tagging problem properly rather than by accident.
    for (x, y, z, nx, ny, nz) in volume_surface_points(VOLUME, props, seed=seed):
        # Scale with the room, so a big chamber does not read as gravel. The divisor is
        # calibration against the asteroid meshes, whose nominal radius is ~90 units.
        near = _nearest_size(vol, (x, y, z))
        _prop(rng, art, x, y, z, scale=near / 90.0)
        made += 1
    # A subtracted solid MUST be dressed or it is an invisible obstacle - containment stops
    # you at something with nothing there to see.
    for (x, y, z, nx, ny, nz) in volume_solid_points(VOLUME, max(8, props // 12), seed=seed):
        _prop(rng, art, x, y, z, scale=110.0 / 90.0)
        made += 1
    # Optional debris floating in the rooms rather than lining them.
    for (x, y, z) in volume_inside_points(VOLUME, fill, seed=seed, margin=200.0):
        _prop(rng, art, x, y, z, scale=0.6)
        made += 1
    return made


def _relic_art(rec):
    """The prop art keys: whatever the relic authored, else the plain asteroid set.

    VERIFY ANY AUTHORED KEY AGAINST shipData. An unknown key does not fail - it silently
    falls back to the `unknown` mesh, so a typo shows up as a relic built out of question
    marks. `plain_asteroid_4` and `_5` do NOT exist; the plain set starts at 6, which is
    why the library's own `plain_asteroid_keys()` is the safer default than a hand-typed
    tuple.
    """
    authored = (rec.get("art") if rec is not None else None) or ""
    keys = [k.strip() for k in str(authored).split(",") if k.strip()]
    if keys:
        return tuple(keys)
    try:
        from sbs_utils.procedural.ship_data import plain_asteroid_keys
        got = tuple(plain_asteroid_keys() or ())
        if got:
            return got
    except Exception:
        pass
    return _PROP_ART


def _nearest_size(vol, p):
    """The size of the feature this point belongs to, for scaling a prop to its room.

    Nearest-primitive rather than exact ownership: a prop at a junction could belong to
    either shape, and picking the closer one is both cheap and what the eye expects.
    """
    best = 600.0
    bestd = float("inf")
    for prim in vol.primitives():
        if prim[0] == "sphere":
            d = abs(_dist3(p, prim[1]) - prim[2])
            size = prim[2]
        elif prim[0] == "capsule":
            d = abs(_dist3(p, prim[1]) - prim[3])
            size = prim[3]
        else:
            d = _dist3(p, prim[1])
            size = min(prim[2])
        if d < bestd:
            bestd, best = d, size
    return best


def _dist3(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


RELIC_ATMOSPHERE = {
    "color": "purple",
    "density_coef": 0.6,      # thin enough to see the walls you are trying not to hit
    "density_scale": 0.35,    # COUNT multiplier - see the perf note in relic_atmosphere
}


def relic_atmosphere(size_cap=12000):
    """Fill the relic with ONE nebula so the engine caps warp inside it.

    THE POINT IS NOT THE LOOK. The engine caps warp for a ship inside a nebula by
    itself, so the interior needs no script throttle governor: no per-tick
    `playerThrottle` writes, nothing for the helm to fight, and no client
    disagreement. The engine already owns this, so scripting it was the wrong layer.
    The ship-side signal is `inside_nebula_count` (LM reads it in
    `damage/extra_signals.mast`) if a mission wants to react to being in the murk.

    ONE object, not one per chamber. A single nebula can be ~12000 across with the new
    shader, and the relic's own bounding sphere is smaller than that - so
    `Volume.bound()` gives the exact centre and radius to cover the whole structure in
    one. Count is the only real perf lever (nebula is ~5x an asteroid apiece, almost
    all of it ~20 shader data_set writes), and 1 is as few as it gets.

    A consequence worth having: the sphere covers a little space OUTSIDE the walls too,
    so a ship cannot warp right up to the relic and punch through - it slows on
    approach.

    Not sown: at one object there is nothing to spread, and sowing would BREAK the
    role tagging anyway - under `terrain_sow_begin` the spawn is queued, so the
    function returns an EMPTY list and there is nothing to tag.
    """
    vol = volume_get(VOLUME)
    if vol is None:
        return 0
    if len(role("relic_atmos")):          # identity, same as the walls
        return len(role("relic_atmos"))
    (cx, cy, cz), radius = vol.bound()
    span = min(radius, size_cap * 0.5)
    # CAVEAT: a GLOBAL - it changes nebula sizing for all terrain in the mission. Fine
    # for a demo with no other terrain; a mission that also builds a normal field should
    # set this deliberately, once.
    terrain_set_nebula_object_size(int(min(radius * 2.0, size_cap)))
    made = []
    neb = terrain_spawn_nebula_sphere(
        cx, cy, cz, radius=int(span),
        density_scale=RELIC_ATMOSPHERE["density_scale"],
        density=RELIC_ATMOSPHERE["density_coef"], height=int(span),
        cluster_color=RELIC_ATMOSPHERE["color"], marker=False)
    for n in (neb or []):
        # terrain_* hands back SpawnData, not an Agent - the agent is .py_object (the
        # same idiom terrain.py uses on its own nebula marker).
        agent = getattr(n, "py_object", None)
        if agent is not None:
            agent.add_role("relic_atmos")
            made.append(agent)
    return len(made)


def relic_atmos_count():
    return len(role("relic_atmos"))


def relic_place_players():
    """Put every player in the hub, off-center.

    Off-center on purpose: `set_pos` teleports bypass collision separation, and
    landing exactly on another object's center is the zero-distance case that NaNs
    the engine.
    """
    set_pos(role("__player__"), 0, 0, 250)


def relic_undress():
    """Delete this mission's relic ART. Returns how many objects went.

    Geometry is the LIBRARY's job now - `relic_reload` re-reads the .amd and rebuilds the
    volume with no mission code at all, then emits `relic_rebuilt` so a mission that
    scatters props over the walls can put them back. This is that half, and it is the only
    half a relic mission has to write.

    Two things this file learned the hard way, kept here because they are easy to redo:
    deletion is `space_objects.delete_object`, NOT `sim.delete_object` - the simulation has
    no such method, and the old call sat inside a bare `except: pass` so it deleted nothing
    while every Preview stacked another ~600 props on the last set. And `delete_object`
    tombstones the agent SYNCHRONOUSLY, so `role("relic_wall")` is empty the moment this
    returns - which is exactly what the identity guards in relic_dress need to rebuild
    rather than no-op.
    """
    from sbs_utils.procedural.space_objects import delete_object
    ids = set(role("relic_wall")) | set(role("relic_atmos"))
    delete_object(ids)
    return len(ids)


def relic_report():
    """Write what actually got built to a file beside the mission.

    A FILE, because that is the only channel that survives an engine run: `log()` to a
    named logger never reaches mast.runtime.log and engine `print()` goes to an
    uncaptured stdout. Without this an engine run can only show that nothing CRASHED -
    and a relic that silently built nothing looks exactly the same.
    """
    import os
    from sbs_utils.fs import get_mission_dir
    from sbs_utils.procedural.volume import volume_get
    vol = volume_get(VOLUME)
    lines = ["relic build report", ""]
    if vol is None:
        lines.append("NO VOLUME - the relic did not build")
    else:
        (c, rad) = vol.bound()
        lines.append(f"source        {RELIC_FILE}")
        lines.append(f"chambers      {len(vol.chambers)}")
        lines.append(f"passages      {len(vol.passages)}")
        lines.append(f"boxes         {len(vol.boxes)}")
        lines.append(f"solids        {len(vol.solids)}")
        lines.append(f"wall props    {relic_prop_count()}")
        lines.append(f"nebula        {relic_atmos_count()}")
        lines.append(f"across        {rad * 2:.0f} u")
    text = chr(10).join(lines) + chr(10)
    try:
        with open(os.path.join(get_mission_dir(), "relic_report.txt"), "w",
                  encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass
    return text


def relic_prop_count():
    """How many wall props exist. Used by the demo's own reporting."""
    return len(role("relic_wall"))


def relic_sow_pending():
    """Queued props still to spawn - the soak fingerprint fails if this never drains."""
    return terrain_sow_pending()

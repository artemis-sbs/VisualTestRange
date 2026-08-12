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

from sbs_utils.procedural.amd_relics import relics_build
from sbs_utils.procedural.volume import volume_get
from sbs_utils.procedural.spawn import terrain_spawn
from sbs_utils.procedural.space_objects import set_pos, clear_target
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.terrain import (
    terrain_sow_begin, terrain_sow_end, terrain_sow_pending,
    terrain_spawn_nebula_sphere, terrain_setup_nebula,
    terrain_set_nebula_object_size,
)

VOLUME = "relic"

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
    """Build the volume from the authored AMD file. Returns it.

    One call: `relics_build` loads the document with the relic fence handler wired in,
    walks the section, registers the records and builds the volume. The fence handler is
    the part that is easy to forget - without it every field falls through to the default
    coercion and the relic builds as nothing.
    """
    from sbs_utils.fs import get_mission_dir_filename
    rec, vol = relics_build(get_mission_dir_filename(RELIC_FILE), name=VOLUME)
    return vol


def _prop(rng, x, y, z, scale):
    """One piece of wall: terrain, non-solid, never an AI behavior."""
    art = _PROP_ART[rng.randrange(len(_PROP_ART))]
    p = terrain_spawn(x, y, z, "", "#,relic_wall", art, "behav_asteroid")
    s = scale * rng.uniform(0.75, 1.35)
    p.blob.set("local_scale_x_coeff", s, 0)
    p.blob.set("local_scale_y_coeff", s * rng.uniform(0.8, 1.2), 0)
    p.blob.set("local_scale_z_coeff", s * rng.uniform(0.8, 1.2), 0)
    p.engine_object.exclusion_radius = 0
    return p


def _sphere_points(rng, n):
    """`n` roughly-even directions on a unit sphere (golden-angle spiral).

    Even beats random here: uniform sampling clumps, and a clumped shell has holes
    you can see straight out through.
    """
    out = []
    step = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(n):
        y = 1.0 - (2.0 * i + 1.0) / n
        r = math.sqrt(max(0.0, 1.0 - y * y))
        a = step * i
        out.append((math.cos(a) * r, y, math.sin(a) * r))
    return out


def relic_dress(seed=7, per_chamber=26, per_passage_segment=6, over=6):
    """Scatter the wall props over the volume boundary.

    Sown through the DripQueue rather than spawned inline: the engine costs ~280 ms
    in ONE frame for a terrain block this size, and sowing takes that to ~110 ms.
    """
    vol = volume_get(VOLUME)
    if vol is None:
        return 0
    # IDENTITY, not "run once": if the walls are already here, this is a no-op.
    #
    # The mock runner and the LM server console can BOTH launch a @map (the runner
    # falls back to auto-start when the console is slow, then the console starts it
    # too), which doubled the prop count on a restart soak - 454 became 908. Building
    # only what is missing makes that harmless, and is the same reason the house
    # pattern is `player_ensure` / `side_ensure` rather than a once-flag: it also
    # survives a deliberate rebuild, a re-emitted init signal, and a late joiner.
    existing = len(role("relic_wall"))
    if existing:
        return existing
    rng = random.Random(seed)
    made = 0
    terrain_sow_begin(over=over, focus=(0, 0, 0))
    try:
        for (x, y, z, r) in vol.chambers.values():
            for (dx, dy, dz) in _sphere_points(rng, per_chamber):
                jitter = r * rng.uniform(1.0, 1.12)   # sit ON the wall, slightly out
                _prop(rng, x + dx * jitter, y + dy * jitter, z + dz * jitter,
                      scale=r / 90.0)
                made += 1
        for (c, h) in vol.boxes.values():
            # Faces, not a shell: a box dressed with a sphere of props would read as a
            # cave again and hide the corners that are the whole point.
            for axis in range(3):
                for sign in (-1, 1):
                    for _i in range(per_chamber // 3):
                        pt = [c[k] + rng.uniform(-h[k], h[k]) for k in range(3)]
                        pt[axis] = c[axis] + sign * h[axis] * rng.uniform(1.0, 1.10)
                        _prop(rng, pt[0], pt[1], pt[2], scale=min(h) / 90.0)
                        made += 1
        for solid in vol.solids:
            # A subtracted shape MUST be dressed or it is an invisible obstacle - the
            # containment will stop you at something you cannot see.
            if solid[0] == "sphere":
                (sx, sy, sz), sr = solid[1], solid[2]
                for (dx, dy, dz) in _sphere_points(rng, per_chamber):
                    j = sr * rng.uniform(0.88, 1.0)      # just INSIDE its own surface
                    _prop(rng, sx + dx * j, sy + dy * j, sz + dz * j, scale=sr / 110.0)
                    made += 1
            elif solid[0] == "capsule":
                sa, sb, sr = solid[1], solid[2], solid[3]
                length = math.sqrt(sum((sb[i] - sa[i]) ** 2 for i in range(3)))
                rings = max(2, int(length / max(sr * 2.2, 1.0)))
                for ring in range(rings + 1):
                    t = ring / float(rings)
                    cx, cy, cz = [sa[i] + (sb[i] - sa[i]) * t for i in range(3)]
                    for k in range(4):
                        ang = (math.pi * 0.5 * k) + ring * 0.5
                        _prop(rng, cx + math.cos(ang) * sr * 0.9, cy,
                              cz + math.sin(ang) * sr * 0.9, scale=sr / 90.0)
                        made += 1
        for (a, b, r, _an, _bn) in vol.passages:
            length = math.sqrt(sum((b[i] - a[i]) ** 2 for i in range(3)))
            rings = max(2, int(length / (r * 1.6)))
            # A frame for the ring: any two axes perpendicular to the passage.
            ux, uy, uz = [(b[i] - a[i]) / max(length, 1e-6) for i in range(3)]
            hx, hy, hz = (0.0, 1.0, 0.0) if abs(uy) < 0.9 else (1.0, 0.0, 0.0)
            px, py, pz = (uy * hz - uz * hy, uz * hx - ux * hz, ux * hy - uy * hx)
            pl = math.sqrt(px * px + py * py + pz * pz) or 1.0
            px, py, pz = px / pl, py / pl, pz / pl
            qx, qy, qz = (uy * pz - uz * py, uz * px - ux * pz, ux * py - uy * px)
            for ring in range(rings + 1):
                t = ring / float(rings)
                cx, cy, cz = [a[i] + (b[i] - a[i]) * t for i in range(3)]
                for k in range(per_passage_segment):
                    ang = (2.0 * math.pi * k / per_passage_segment) + ring * 0.4
                    rr = r * rng.uniform(1.0, 1.15)
                    _prop(rng,
                          cx + (px * math.cos(ang) + qx * math.sin(ang)) * rr,
                          cy + (py * math.cos(ang) + qy * math.sin(ang)) * rr,
                          cz + (pz * math.cos(ang) + qz * math.sin(ang)) * rr,
                          scale=r / 70.0)
                    made += 1
    finally:
        terrain_sow_end()
    return made


# The relic's own "atmosphere" - a nebula type, not just a colour.
#
# THE POINT IS NOT THE LOOK. The engine caps warp for a ship inside a nebula, all by
# itself, which means the interior does not need a script throttle governor at all:
# no per-tick playerThrottle writes, nothing for the helm to fight, and no client
# disagreement. Doug's call - the engine already owns this, so scripting it was the
# wrong layer.
#
# The ship-side signal is `inside_nebula_count` (LM reads it in
# damage/extra_signals.mast), so a mission can also react to being in the murk.
RELIC_ATMOSPHERE = {
    "color": "purple",
    "density_coef": 0.6,      # thin enough to see the walls you are trying not to hit
    "density_scale": 0.35,    # COUNT multiplier - see the perf note in relic_atmosphere
}


def relic_atmosphere(size_cap=12000, over=6):
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
        cx, cy, cz, radius=int(span), density_scale=1.0,
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


def relic_reload():
    """Tear the relic down and rebuild it from the file. The live-preview hook.

    Edit ossuary.amd in VS Code, hit Preview, and the running session rebuilds - no
    restart, no reload of the mission. That closes the loop the whole declarative layer
    was for: the file IS the relic, so re-reading the file IS rebuilding it.

    Deletes by ID, never by object: `delete_object` frees the C++ side synchronously, so
    a live object reference in the loop is a use-after-free waiting to happen.
    """
    from sbs_utils.helpers import FrameContext
    from sbs_utils.procedural.query import to_object_list
    from sbs_utils.procedural.roles import remove_role
    from sbs_utils.procedural.volume import volume_unwatch
    walls = to_object_list(role("relic_wall"))
    atmos = to_object_list(role("relic_atmos"))
    ids = [o.id for o in walls] + [o.id for o in atmos]
    # DROP THE ROLES FIRST, in this frame. `delete_object` frees the engine object, but
    # the AGENT - and so its role membership - lives until GarbageCollector.collect()
    # runs at the end of cosmos_event_handler. We are still inside the emit, so
    # `role("relic_wall")` would answer with the objects we just deleted, and the
    # identity guards in relic_dress / relic_atmosphere would read that as "already
    # built" and rebuild NOTHING. The preview then showed the OLD relic and looked like
    # the file had been ignored.
    #
    # Removing the role is also the honest statement: these are no longer the relic's
    # walls, whatever the collector has got round to.
    remove_role(walls, "relic_wall")
    remove_role(atmos, "relic_atmos")
    sim = FrameContext.context.sim
    for i in ids:
        try:
            sim.delete_object(i)
        except Exception:
            pass
    volume_unwatch(VOLUME)
    # The dressing guards on identity (`if the props are here, do nothing`), and the
    # props are now gone - so these rebuild rather than no-op.
    relic_define()
    made = relic_dress()
    atmos = relic_atmosphere()
    relic_report()
    return f"relic reloaded: {made} props, {atmos} nebula"


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

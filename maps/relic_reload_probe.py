"""Does Preview actually REBUILD the relic, or just say it did?

Run it:  python maps/relic_reload_probe.py

Not a unittest: it needs a real Cosmos install (shipData) and this mission's folder, so
it would fail in sbs_utils' suite for reasons that have nothing to do with the relic. It
lives here for the same reason LM_TestRange keeps `relic_engine_probe.py` - a run you can
repeat, next to the thing it measures.

WHAT IT CATCHES. `relic_dress` and `relic_atmosphere` guard on IDENTITY - if the walls
are already here, do nothing - which is what keeps a double-launched @map from building
the relic twice. But `delete_object` frees the engine object while the AGENT, and so its
role membership, lives until GarbageCollector.collect() runs at the end of
cosmos_event_handler. A reload runs INSIDE the emit, so it deleted 654 props and then
asked `role("relic_wall")`, which still answered 654. The guards read that as "already
built", rebuilt nothing, and Preview showed the OLD relic.

The volume rebuilt correctly the whole time - containment moved, the visible relic did
not - which is exactly why it looked like Preview was ignored rather than broken.

So COUNTING props proves nothing: per_chamber is fixed, and 654 stale props and 654 fresh
ones look identical. The discriminator is IDENTITY - a genuine rebuild shares no object
with the build before it. Comment out the two `remove_role` calls in `relic_reload` and
this flips to STALE with an overlap of 654.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MISSION = os.path.dirname(HERE)
MISSIONS_ROOT = os.path.dirname(MISSION)
sys.path.insert(0, os.path.join(MISSIONS_ROOT, "sbs_utils"))

from sbs_utils import fs
fs.script_dir = MISSION
# missions root is <install>/data/missions, so the install is two levels up - the same
# derivation cosmos_dev.mission_runner uses.
fs.exe_dir = os.path.dirname(os.path.dirname(MISSIONS_ROOT))

from sbs_utils.helpers import FrameContext, Context, FakeEvent
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.volume import volume_get
from sbs_utils.procedural.terrain import terrain_sow_pending
from sbs_utils.tickdispatcher import TickDispatcher
from cosmos_dev.mock import sbs

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "relic_layout", os.path.join(HERE, "relic_layout.py"))
relic_layout = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(relic_layout)

AMD = os.path.join(HERE, "ossuary.amd")


def _drain():
    """Run the sower out - props are dripped over frames, not spawned inline."""
    for _ in range(400):
        if not terrain_sow_pending():
            return
        TickDispatcher.do_tick(sbs.sim, sbs)


def main():
    sbs.create_new_sim()
    FrameContext.context = Context(sbs.sim, sbs, FakeEvent())
    SpaceObject.clear()

    relic_layout.relic_define()
    relic_layout.relic_dress()
    _drain()
    vol = volume_get(relic_layout.VOLUME)
    before = set(role("relic_wall"))
    print("build   : chambers=%d  hub r=%s  walls=%d"
          % (len(vol.chambers), vol.chambers["hub"][3], len(before)))

    original = io.open(AMD, encoding="utf-8", newline="").read()
    edited = original.replace("Chamber: 0, 0, 0, 900", "Chamber: 0, 0, 0, 1450", 1)
    if edited == original:
        print("SKIP    : the hub's authored radius is not 900 any more - update the probe")
        return 2
    try:
        io.open(AMD, "w", encoding="utf-8", newline="").write(edited)
        print("reload  :", relic_layout.relic_reload())
        _drain()
    finally:
        io.open(AMD, "w", encoding="utf-8", newline="").write(original)

    vol = volume_get(relic_layout.VOLUME)
    after = set(role("relic_wall"))
    overlap = len(before & after)
    print("after   : chambers=%d  hub r=%s  walls=%d"
          % (len(vol.chambers), vol.chambers["hub"][3], len(after)))
    print("props   : shared with the previous build = %d" % overlap)
    ok = vol.chambers["hub"][3] == 1450 and after and overlap == 0
    print("VERDICT : %s" % ("REBUILT" if ok else "STALE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

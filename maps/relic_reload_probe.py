"""Does Preview actually REBUILD the relic, or just say it did?

Run it:  python maps/relic_reload_probe.py

Not a unittest: it needs a real Cosmos install (shipData) and this mission's folder, so it
would fail in sbs_utils' suite for reasons that have nothing to do with the relic. It lives
here for the same reason LM_TestRange keeps `relic_engine_probe.py` - a run you can repeat,
next to the thing it measures.

WHAT IT DRIVES. The two halves of a live preview, in the order the real thing runs them:
`relic_reload` (the LIBRARY's - re-read the .amd, replace the volume, re-apply the authored
containment) and then this mission's `relic_rebuilt` art, which is all a relic mission has
to write. It edits a COPY of ossuary.amd, so it can prove the file is genuinely re-read
without touching the mission's own asset.

WHAT IT CATCHES. `relic_dress` and `relic_atmosphere` guard on IDENTITY - if the walls are
already here, do nothing - which is what keeps a double-launched @map from building the
relic twice. Teardown has to actually delete, or the guards see the old props and rebuild
nothing. Two separate bugs lived in that gap: `sim.delete_object` is not a method (it threw
into a bare `except: pass`, so nothing was ever deleted), and before that the guards were
consulted while the deleted agents were still in their roles.

So COUNTING props proves nothing: per_chamber is fixed, and 600 stale props and 600 fresh
ones look identical. Two discriminators are needed and both are here - IDENTITY, because a
genuine rebuild shares no object with the build before it, and the TOTAL OBJECT COUNT,
because an object whose delete failed is invisible to `role(...)` while still very much in
the world and drawn. The first version of this probe had only the roles, and passed while
every Preview stacked another 595 props on the last set.
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
from sbs_utils.procedural.amd_relics import relics_build, relic_reload
from cosmos_dev.mock import sbs

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "relic_layout", os.path.join(HERE, "relic_layout.py"))
relic_layout = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(relic_layout)

AMD = os.path.join(HERE, "ossuary.amd")


def _object_count():
    """Every space object the sim still holds - the only view that sees an orphan.

    Roles cannot answer this on their own: a rebuild re-populates `relic_wall` to the
    same count either way, so the old props are only visible as a rise in the total.
    """
    from sbs_utils.agent import Agent
    return len(Agent.all)


def _drain():
    """Run the sower out - props are dripped over frames, not spawned inline."""
    for _ in range(400):
        if not terrain_sow_pending():
            return
        TickDispatcher.do_tick(sbs.sim, sbs)


def main():
    import shutil
    import tempfile
    sbs.create_new_sim()
    FrameContext.context = Context(sbs.sim, sbs, FakeEvent())
    SpaceObject.clear()

    # A COPY, so the edit below is a real edit to a real file and the mission's own asset
    # is never touched. This is what the old probe could not do: it drove a mission
    # function that read a hard-coded path, so it could only ever show that SOMETHING was
    # rebuilt, never that the file had been re-read.
    tmp = tempfile.mkdtemp(prefix="relic_probe_")
    amd = os.path.join(tmp, "ossuary.amd")
    shutil.copyfile(AMD, amd)
    try:
        original = io.open(amd, encoding="utf-8", newline="").read()
        edited = original.replace("Chamber: 0, 0, 0, 900", "Chamber: 0, 0, 0, 1450", 1)
        if edited == original:
            print("SKIP    : the hub's authored radius is not 900 any more - update the probe")
            return 2

        rec, vol = relics_build(amd)
        relic_layout.relic_dress()
        # The atmosphere too - a re-dress rebuilds it, so a baseline without one reports
        # the nebula as an orphan and the probe accuses the teardown of a leak it did not
        # cause.
        relic_layout.relic_atmosphere()
        _drain()
        vol = volume_get(rec.get("key"))
        before = set(role("relic_wall"))
        live0 = _object_count()
        print("build   : chambers=%d  hub r=%s  walls=%d  objects=%d"
              % (len(vol.chambers), vol.chambers["hub"][3], len(before), live0))

        io.open(amd, "w", encoding="utf-8", newline="").write(edited)

        # HALF ONE - the library's. No mission code; this is what the Preview button gets
        # for free in any mission that authored a relic in AMD.
        out = relic_reload(rec.get("key"))
        print("reload  : %s" % (out,))
        # HALF TWO - the mission's art, which is what //shared/signal/relic_rebuilt runs.
        # Called directly here because a probe has no MAST context to emit into.
        gone = relic_layout.relic_undress()
        props = relic_layout.relic_dress()
        atmos = relic_layout.relic_atmosphere()
        _drain()
        print("redress : %d removed, %d props, %d nebula" % (gone, props, atmos))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    vol = volume_get(rec.get("key"))
    after = set(role("relic_wall"))
    overlap = len(before & after)
    live1 = _object_count()
    print("after   : chambers=%d  hub r=%s  walls=%d  objects=%d"
          % (len(vol.chambers), vol.chambers["hub"][3], len(after), live1))
    print("props   : shared with the previous build = %d" % overlap)
    print("orphans : %+d objects left behind by the teardown" % (live1 - live0))
    ok = (vol.chambers["hub"][3] == 1450 and after and overlap == 0
          and live1 == live0)
    print("VERDICT : %s" % ("REBUILT" if ok else "STALE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

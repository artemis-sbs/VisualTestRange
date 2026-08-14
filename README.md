# Visual Test Range

Framed specimens for confirming **what the renderer actually draws**.

LM Test Range asserts behavior headlessly and fails a build. This range is the opposite
case: the things only an eye can settle. Each map is one subject, framed identically every
run, with a card on screen saying what a correct frame shows — so a wrong result is visible
without reading any code, and anyone can judge it, not only whoever wrote it.

It exists because the alternative kept costing sessions: a bug reported as "wrecks not
showing up" was actually `planet` and `maelstrom` having no art to load, and settling that
took an afternoon of reading shaders. The art census answers it in one glance.

## Running it

```
# from data/missions
python -m cosmos_dev.mission_runner VisualTestRange --gui
    then open http://localhost:8765/server      picker, then view + card
    and (only for the per-client specimens)     http://localhost:8765/client

python -m cosmos_dev.mission_runner VisualTestRange --gui --map visual_blackhole
python -m cosmos_dev.mission_runner VisualTestRange --map visual_all --test 150
```

The last form is headless: no picture, but every specimen's machine-checkable half still
runs and prints `VISUAL PASS` / `VISUAL FAIL`, so the data regressions (a body that stopped
streaming, an art root that stopped resolving) are CI-able even though the picture is not.

The server tab opens on the **mission picker**, which comes from the
`LegendaryMissions.consoles` mastlib — the same way LM Test Range gets one. Nothing here
draws it: `server_console` lists the `@map` roster, applies the map's Defaults, launches the
choice and handles `--map` / `AUTO_START`. Pick a specimen and the tab becomes the stage,
where **Prev / Re-run / Next** walk the rest without restarting the runner and the card
repaints with each one.

The cost, and it is the same one LM Test Range pays: the range loads the **built** LM
mastlibs, so a working-tree LM edit is not visible until you rebuild —
`python sbs.pyz lib LegendaryMissions`. Edits to the range's own `.mast` files need no
rebuild.

## Specimens

| Map | Subject | What a failure looks like |
|---|---|---|
| `visual_art_census` | every shipData art in one grid | a hole in the grid, or a gray placeholder sphere |
| `visual_blackhole` | two maelstroms, stock and wide/tinted | no disc, no ring, or a ring that does not fade at both edges |
| `visual_planet` | four gas giants, one knob apart each | two planets sharing a face; clouds on the wrong one |
| `visual_torpedo` | a ship firing on a loop, broadside | no projectile, a late one, or one sliding along y=0 |
| `visual_beam_arcs` | three fixed shooters, target at three bearings | a beam to the astern target; beams from the model center |
| `visual_fx_client_scope` | two fights, further apart than the cull radius | a client seeing the fight it cannot reach |
| `visual_terrain_field` | every asteroid art, plus the local_scale ruler | rocks missing; the four scaled copies all one size |
| `visual_scale_ladder` | wreck → rock → fighter → cruiser → base → worldlet | the wreck absent or a speck; the ladder out of order |
| `visual_nebula` | five color presets, then three densities | one cloud in five tints; density changing nothing |
| `visual_motion` | three ships crossing at documented speeds | stutter, teleporting, or speeds that do not scale |
| `visual_shield_rings` | pinned shield fractions, plus a lopsided ship | wrong color bands; fore/aft halves swapped |
| `visual_button_chrome` | plain button vs `background_color` at five tones, over the live view | tells you whether a colorbutton is skinned or flat, and which fills the hover highlight still reads over |
| `visual_dropdown_select` | three script writers moving a dropdown's selection, plus a control that nothing writes to | a cell stuck on One (its writer never reached the props string the renderer reads -- LM #568); the control moving too, which would mean the panel is rebuilding rather than updating in place |

### Camera spikes (CINEMATIC_PLAN.md Phase 0)

These three are **experiments, not regression tests** — they exist to be run in the *engine*
and have their answers written down. Each is unambiguous by construction: there is no reading
of the picture that leaves the question open.

| Map | Question | How to read it |
|---|---|---|
| `visual_camera_offsets` | **Q1** — are the offsets world-space or dolly-local? | a ship yaws in place with the camera pinned abeam. Ship holds its pose while the rocks sweep → **local**. Ship turns in front of fixed rocks → **world** |
| `visual_camera_cut` | **Q2** cut vs blend, **Q4** dangling dolly | alternates two very different angles every 3s; then deletes the live camera post at ~12s and the card says so |
| `visual_camera_rate` | **Q3** — what can drive a move | the same 9000u move twice: written per tick, then carried by a ship under throttle. If pass 1 stutters and pass 2 does not, the mover must ride an object |

**Q1 and Q3 turned out to be answered already**, by shipped code rather than by these spikes:
LM's Game Master orbits its 3D view by rotating the offset vector *itself*
(`Vec3(0,0,dolly*10).rotate_around(...)`, `gamemaster.mast:623`) before handing it to
`gui_cinematic_full_control`. If the engine rotated offsets into the dolly's frame that would
be unnecessary — so offsets are **world-space** — and the GM re-applies the camera on every
selection change, so **per-tick re-application is fine**. `visual_camera_offsets` and
`visual_camera_rate` are now confirmations rather than open questions.

`visual_camera_cut` still earns its keep: **Q2** (cut vs blend) and **Q4** (dangling dolly)
have no shipped answer, and both are cheap to read.

Two engine rules these spikes exist downstream of, both easy to get wrong:

- The client must be **assigned to a space object** for the cinematic camera to mean anything —
  but that object is the console's *identity*, not the lens. The GM assigns one invisible
  cambot and then points the camera at whatever it likes; the range does the same via
  `visual_client_cambot()`.
- A camera pinned to a **ship** at zero offset sits **inside its mesh**. Only `visual_anchor`
  (invisible, no mesh) is safe at `(0,0,0)`, and an anchor has to be a `player_spawn`-family
  object because terrain is not assignable.

## Writing a specimen

A specimen is a label tagged `metadata: type: visual/<name>`, with a thin `@map/visual_<name>`
wrapper so it can also be entered directly. `visual_all` discovers them by that tag — adding
one needs **no edit** to the sweep, only an `import` line in `story.mast`.

```
=== run_visual_thing
metadata: ``` yaml
type: visual/thing
```
    _subject = npc_spawn(0, 0, 0, "Thing", "tsn", "tsn_light_cruiser", "behav_npcship")
    _anchor = visual_anchor(0, 0, 0)
    visual_camera(_anchor, eye=(0, 900, 0 - 2600))
    _expect = ~~[
        "what a correct frame shows",
        "one line per checkable claim",
    ]~~
    visual_case("Thing", _expect, notes="...", data="...")
    visual_expect("thing: something checkable without eyes", _cond)
    ->END
```

Harness (`maps/visual_harness.py`):

| Call | Does |
|---|---|
| `visual_case(title, expect, notes, data, subtitle)` | declares the card; also prints one machine-readable `VISUAL CASE` line |
| `visual_camera(dolly, eye=(x,y,z), target_id, look)` | pins the frame — camera at an object + offset, looking at another |
| `visual_anchor(x, y, z)` | an invisible object to hang the camera on, for framing empty space |
| `visual_expect(name, cond, detail)` | one eyes-free assertion, greppable as `VISUAL PASS/FAIL` |
| `visual_planet_spawn(...)` | a gas giant with the whole `planet_*` knob set in one call |
| `visual_reset_objects()` / `visual_reset_sim()` | tear the scene down (see the tick between them) |
| `visual_widgets([[label, background], ...])` | draw controls under the card — for a specimen about how a CONTROL looks |
| `visual_dropdowns([[name, caption, props, style], ...])` | same, for dropdowns — and the console hands each built widget back |
| `visual_dropdown(name)` / `visual_dropdown_shown(name)` | the live widget, and the label it is currently SENDING (read from its props, not from `.value` — the two disagreeing is the bug) |
| `visual_case(..., hold=20)` | how long a sweep should leave this one up; a specimen that plays out over time must say so |
| `visual_generation()` | the scene counter a long-running driver checks — object ids are recycled, this is not |

## Rules the range holds itself to

- **Deterministic.** Autoplay and default player ships are off in `settings.yaml`; a specimen
  spawns exactly the actors it needs and nothing drifts on its own.
- **Framed identically every run**, via `gui_cinematic_full_control` — camera pinned to an
  object with a world-space offset, which works the same in the engine and in the mock. Two
  runs are comparable, and so are the two renderers.
- **Says which renderer drew it.** Every card carries `RENDERER engine | browser mock`. A
  mock frame is not evidence about the engine, and the range never lets you forget which
  one you are looking at.
- **No golden images.** Pixel baselines flap on GPU, driver and AA differences, and a red
  test nobody trusts is worse than no test. The picture is judged by a person; only the
  data half is automated.
- **Repaint by re-entering the label**, never by updating a child in place — an in-place
  child update inside an absolutely-positioned region ghosts in the engine, which is exactly
  the class of bug this range exists to catch. It must not be the range's own bug.

## An engine trap: gravity and NaN

An object sitting at a gravity source's **centre** has no direction left to be pulled in. Its
position goes NaN and the engine asserts outright:

```
Assertion failed!  Expression: !isnan(so->pos.x)
File: Simulation.cpp  Line: 668
```

The range hit this twice in one specimen, both self-inflicted and both easy to repeat:

- the console's invisible **cambot spawned at the world origin**, which is exactly where
  `visual_blackhole` puts hole A. It is now parked far above the plane — its position never
  affects the picture, since the lens rides the specimen's own anchor.
- the scale-reference ship sat **exactly on** hole A's gravity radius, was dragged in, and
  arrived at the centre. It now sits in the gap between the two wells.

The rule for a specimen: **do not place anything inside a gravity well you do not intend to
lose.** LM's lethal-proximity watch, which destroys craft near a hole before they reach the
centre, lives in an addon this range does not load — so here they fall all the way in.

## Two MAST traps this range walked into

Both cost real time here, so they are written down rather than rediscovered.

**Loop state collides by variable name across a schedule chain.** The art census spawned 10
objects instead of 184 with no error, because the sweep that scheduled it was itself inside
a `for _i`, and the census's `for _i` resumed *that* iterator at 1 of 11. Every loop in this
mission has its own variable name. Suspect this whenever a loop silently runs the wrong
number of times.

**The runner double-launches a map unless something sets `GAME_STARTED`.** `--map <name>`
hands the launch to the story via `WORLD_SELECT` + `AUTO_START`, then falls back to its own
auto-start if `GAME_STARTED` never appears — so the sweep ran twice, interleaved, one copy
resetting the sim while the other was mid-spawn. The consoles addon's `start` label sets the
flag, which is one more reason not to hand-roll the launch. A headless run logs `map started
by the server console` when the addon won the race; if you ever see the map run twice, that
line is the first thing to check for.

## Known gaps

- **Not yet seen in a browser.** Every specimen is verified headless (it builds, and its
  `visual_expect` checks pass); the pictures themselves are unconfirmed, including whether
  the pinned camera frames each subject well. Expect to tune `eye=` offsets on first look.
- **`visual_fx_client_scope` needs two tabs** and is the only specimen that cannot be judged
  from the server alone.
- **No capture button.** Saving the canvas plus the HUD to a PNG belongs in
  `cosmos_dev/mockgui`; until then, a finding travels as a screenshot you take. (This was
  blocked on a parallel session owning those files; it has since landed, so it is now free
  to do.)
- **The backdrop is a flat neutral fill.** The mock's procedural starfield is gone — every
  star the same size and brightness read as static and swallowed dark hulls, which is
  intolerable in a range whose job is judging art. Both renderers draw a real cube-cross
  skybox when a mission sets one, and `start_server` does call `skybox_schedule_random()` —
  but the `consoles` mastlib declares no `@media/skybox` labels (those live in LM's
  `basic_random_skybox`), so today there is nothing for it to pick and the fill stays. Add
  that mastlib, or declare the labels here, if a specimen should be judged against a real
  sky. Neutral is the better default for the art specimens either way.
- **Nothing here has run in the engine yet.** That is the whole point of the range being
  engine-runnable, and it is the next thing worth doing — starting with `visual_blackhole`,
  which exists to answer whether the engine draws a maelstrom in 3D at all.

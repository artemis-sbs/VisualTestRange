# Engine bug: generating derived art from a bare `.obj` crashes (1.3.5)

**Summary.** When a ship's art folder contains only source files, the engine begins
generating the derived set, writes `<root>1024.png`, and then dies with an access
violation. Art that already has its derived files renders normally.

**Impact.** A mod cannot ship a plain `.obj`. Every mod would have to ship engine-generated
files it has no way to produce, which blocks mod-carried art entirely — the rest of the
path works.

| | build | exit |
|---|---|---|
| release | `Artemis3-x64-release.exe` | `-1073741819` = `0xC0000005` access violation |
| debug | `Artemis3-x64-debug.exe` | assert, then null deref if the assert is ignored |

## Repro

1. Copy `data/missions/BeamArcTest/extraShipGraphicData` somewhere else. (A ready-made
   copy is committed here as `art_gen_test/`.)
2. Delete the derived files from the copy — `.paxmesh`, `.pointcube`, `.rawbitmap`,
   `<root>1024.png`, `<root>256.png`. Keep `.obj`, `.png` and the four maps.
3. Declare a ship pointing at the copy, using the same two fields as
   `extraShipDataAAA.json`:

   ```json
   "artfileroot": "tsn_light_cr",
   "artfilepath": "data/missions/<your copy>/graphics/ships"
   ```

4. Spawn it and let it render.

**Result:** the engine writes `tsn_light_cr1024.png` into the folder and then crashes.
Nothing else in the derived set is produced.

Reproduced 2/2 in the release build. The controlled comparison is the point: the *same*
art in its *unstripped* folder, same mission, same code path, renders with no crash. The
only variable is whether the derived files were already present.

**It is not one file.** Supplying every derived file except one, in turn, crashes on every
omission — `.paxmesh`, `.pointcube`, `.rawbitmap`, `1024.png`, `256.png` alike. The engine
cannot generate *any* of them; the complete set has to be present.

Not content-specific — it fails identically on a completely different mesh
(`anime_mods/anime_ships/graphics/ships/God_Phoenix.obj`), also stopping right after
writing `God_Phoenix1024.png`.

**In this repo:** `variant=two_gen_test` in the `visual_mod_art` specimen.

```
Artemis3-x64-release.exe autostartserver defaultmission=VisualTestRange \
    map=visual_mod_art variant=two_gen_test
```

`variant=two_example` is the passing control (their folder, untouched).

## ROOT CAUSE: `.paxmesh` hardcodes texture paths under `data/graphics/`

This is the finding that explains the rest, and it is the specific thing to fix.

A generated `.paxmesh` stores its texture references as length-prefixed strings rooted at
`data/graphics/`:

```
ships/<root>_diffuse   ships/<root>_emissive   ships/<root>_normal   ships/<root>_specular
```

They are resolved from the game's graphics folder — **not from the folder the mesh was
loaded out of**. So `artfilepath` relocates the MESH but not its TEXTURES, and a mod that
carries its own art has a mesh whose textures cannot be found.

**`BeamArcTest`'s own art demonstrates it.** Its `tsn_light_cr.paxmesh` contains
`ships/tsn_light_cruiser_diffuse` — the STOCK cruiser's textures, which are always present
in the install. That art is the stock cruiser renamed, so it works by borrowing from
`data/graphics/ships`; it never exercised mod-carried textures at all.

Confirmed by construction: with the God Phoenix mesh in a mod folder and only its four
textures copied into `data/graphics/ships`, it loads. Remove them and it fails.

**The ask:** make paxmesh texture lookup honor `artfilepath`, or store texture paths
relative to the mesh.

### Still unexplained

With the COMPLETE art set installed in `data/graphics/ships` — byte-identical copies in
both locations — `BeamArcTest` still **hangs** rather than rendering. The same art loads
fine through `VisualTestRange`. That difference is not accounted for here, and the earlier
crash-versus-hang distinction should not be read as meaningful until it is.

## Second bug: `<root>256.png` is written to the EXE ROOT

The 256 bitmap is generated into the **current working directory** — `F:\Cosmos-1-3-0\`
— rather than beside the art it belongs to. It lands as a stray `God_Phoenix256.png` /
`tsn_light_cr256.png` next to the executable.

Two consequences. The art folder never becomes complete on its own, so the next load
regenerates it and drops another copy in the root; and it made the file look
*ungeneratable* while investigating, because looking beside the art showed nothing.

## Which files the engine actually generates

Measured while baking art in `data/graphics/ships` (the path that does NOT crash):

| file | generated? | where |
|---|---|---|
| `.paxmesh` | yes | beside the art |
| `.pointcube` | yes | beside the art |
| `<root>1024.png` | yes | beside the art |
| `<root>256.png` | yes | **the exe root** (bug above) |
| `.rawbitmap` | not observed | — |

`.rawbitmap` never appeared under any trigger tried: NPC spawn, player spawn, or repeat
runs. Art renders correctly without it, so it may be optional or produced by some other
path.

## The workaround this enables

Until the crash is fixed, a mod's art can be **baked**: put the source art in
`data/graphics/ships` temporarily, spawn the ship by `artfileroot` alone, let the engine
generate the derived files, then ship those with the mod and remove the art from the
install. Confirmed working — the baked hull rendered in-engine.

## Note on `add_extra_ship_data`

Pass the filename **without an extension** — the engine tries `.yaml` then `.json` itself,
as your own example does (`sbs.add_extra_ship_data("extraShipDataAAA",
"data/missions/BeamArcTest")` for a `.json` file). Loading works either way; the
extensionless form is the one to document, since it lets a mod switch format without the
caller changing.

## A second, probably related crash

An **unresolvable `artfileroot`** — a name with no matching art — also segfaults at render,
reproduced 4/4. On **1.3.4 the same condition drew the `unknown` placeholder**, so this is
a regression. A missing asset should not be fatal; a mod with one bad reference currently
takes the whole engine down rather than showing a placeholder someone can notice and fix.

`variant=crashers` in the same specimen covers these.

## Question

If generation crashes for everyone, how were `BeamArcTest`'s derived files produced — an
earlier engine, or separate tooling? If it is tooling, mod authors need access to it or
the answer is "mods cannot ship art" regardless of this crash.

## What already works, for context

Nothing else here is blocked. `sbs.add_extra_ship_data(file, path)` loads ship data
straight from a mod folder — measured, the engine read `shields [110, 90]` from
`anime_mods/anime_ships/mod_ships.json` with nothing written into the mission. And
`artfilepath` + `artfileroot` does reach a mod's art: the crash above is *proof* it got
there, since the engine wrote a generated file into the mod folder before dying.

## RE-MEASURED on the 2026-08-05 dev build — still open, and now WORSE

Re-run of the same reproducer against `Artemis3-x64-release.exe` dated 2026-08-05.
Every run below is the release build, launched from the exe folder, 75s timeout.

| run | variant | art | exit | verdict |
|---|---|---|---|---|
| control | `map=visual_motion` | stock only | 124 (timed out = alive) | engine is healthy |
| **`two_example`** | BeamArcTest's own **complete** set | `artfilepath` | **139 segfault, 2/2** | **REGRESSION** |
| `two_gen_test` | stripped to source | `artfilepath` | 139 segfault | bug unchanged |
| `bake` | source in `data/graphics/ships` | `artfileroot` only | 124 (alive) | workaround still works |

Two things changed since the 1.3.5 measurement above.

**1. The passing control no longer passes.** `two_example` is the engine team's OWN art
with the full derived set (`.paxmesh .pointcube .rawbitmap 1024 256`) in a mod folder — the
case this document recorded as rendering fine. On this build it segfaults, reproduced 2/2.
So `artfilepath` art is now fatal *regardless* of whether the derived files are present,
which is a strictly larger failure than "generation crashes". There is no longer any
combination that reaches a mod's own meshes.

Both crashes die at the same place in the log: the engine parses the `.obj`
(`find materials in: <folder>/artemis.mtl`, then vertices/texcoords/normals/triangles up to
`material17`) and dies there. Note it parses the OBJ even in `two_example`, where a
`.paxmesh` sits beside it.

**2. `two_gen_test` is otherwise unchanged** — it writes `tsn_light_cr1024.png` into the mod
folder and then dies, exactly as described above.

**The bake workaround is intact.** `variant=bake bakeroot=tsn_light_cr bakeplayer=1` with the
source art staged in `data/graphics/ships` ran the full 75s and generated `.paxmesh` and
`.pointcube` beside the art, plus `tsn_light_cr256.png` in the exe root (the second bug,
also unchanged). `.rawbitmap` and `1024.png` did not appear on this run.

So today the ONLY way a mod's custom hull renders is to install its art into
`data/graphics/ships` — which, combined with the paxmesh texture-path root cause above,
means mod-carried art is not shippable at all until the engine side is fixed.

### One thing worth checking on the engine side

`script_documentation.txt` documents `art_file_path` / `art_file_root` only as **`sbs.hullmap`**
data descriptors — "used to get top-down image from disk", i.e. the interior grid's top-down
picture, not the 3D mesh. The ship-data key `artfilepath` that `extraShipDataAAA.json` uses is
not documented anywhere in that file. Whether those are the same plumbing or two unrelated
fields with confusingly similar names would be worth confirming before more spellings get
guessed at from this side.

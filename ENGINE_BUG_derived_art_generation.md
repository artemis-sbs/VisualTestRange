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

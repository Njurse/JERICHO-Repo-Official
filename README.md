# JERICHO Mods — official store index

The official mod feed for [JERICHO](https://github.com/Njurse/JERICHO).

The game's **Options → JERICHO → Mods → Mod Repo** screen reads:

    https://raw.githubusercontent.com/Njurse/JERICHO-Repo-Official/main/mods.json

`mods.json` lists the packages and their SHA-256 hashes; `packages/` holds the
zips. The store downloads a zip, verifies it against the index, and installs it
into `JERICHO/MODS/<id>/`. Nothing is installed unless the hash matches.

## Sources

| mod | source repository |
|---|---|
| `mp` | https://github.com/Njurse/JERICHO-Mod-MP |
| `carhacks` | https://github.com/Njurse/JERICHO-Mod-carhacks |
| `crumple` | https://github.com/Njurse/Jericho-Mod-CRUMPLE |
| `bake` | https://github.com/Njurse/BAKE (formerly `d1cars` / JERICHO-D1) |
| `fulltwist` | https://github.com/Njurse/JERICHO at `JERICHO/MODS/fulltwist` |
| `yarisbounce` | https://github.com/Njurse/JERICHO at `JERICHO/MODS/yarisbounce` |
| `hallgarthcars` | https://github.com/Njurse/JERICHO-Mod-HallgarthCars |
| `antfarm` | https://github.com/Njurse/JERICHO-Mod-Antfarm |
| `chicagobigrig` | the JERICHO tree at `JERICHO/MODS/chicagobigrig` (no source repo yet) |

`mp`, `carhacks`, `crumple` and `bake` are also git submodules of JERICHO,
mounted at `JERICHO/MODS/<id>`. `fulltwist` and `yarisbounce` are in-tree
modules. `hallgarthcars` and `antfarm` are store-only and are not shipped in
the JERICHO Release zip.

## Keeping the store current

The store compares `version`, so a rebuilt package with an unchanged version is
invisible to anyone who already installed it. Do not check each repository by
hand — `tools/sync_store.py` asks every source for its newest semver release tag
(else the branch head), reads the `mod.toml` there, and compares its content
with the published package. `tools/sources.json` is the authority for where
each mod comes from.

1. See what is stale:

   ```sh
   python3 tools/sync_store.py --jericho ../REDRIVER2
   ```

   It prints `mod | ref | source version | published version | content | action`:

   - `up to date` — nothing to do.
   - `UPDATE` — the source has a newer version; publish it.
   - `BUMP NEEDED` — the content changed but the manifest version did not. Bump
     `version` in the listed `mod.toml`, commit and push that repository, then
     re-run. A same-version rebuild will never reach an existing install.
   - `OLDER THAN PUBLISHED` / `BAD VERSION` — fix the manifest or the index; do
     not publish.
   - `MISSING FROM INDEX` — a new mod; `--publish` adds it.

   Pass `--only <id>` to check one mod. `--jericho <checkout>` is required for
   mods that still live in the JERICHO tree.

2. Publish every genuinely newer version:

   ```sh
   python3 tools/sync_store.py --publish --jericho ../REDRIVER2
   ```

   It builds each package from the resolved source with the same exclusions as
   `make_mod_package.sh` (no `.git`, `D1CARS`, `obj/`, `lib/`, `.pdb`, `.ilk`,
   `.exp`, `.o`, or root `.lib`/`.obj`), copies it into `packages/`, and writes
   the version, file name, SHA-256 and size into `mods.json`. It refuses to
   write while any mod says `BUMP NEEDED`. A `runtime = "dll"` mod must have its
   `<id>.dll` (or `.so`) in the source first — build it with
   `JERICHO/sdk/build_mods.sh <folder>`.

3. Validate the index against the previous one:

   ```sh
   python3 JERICHO/CORE/modstore/check_mod_repo.py mods.json \
       --packages packages --previous <the-old-index> --interface 3
   ```

4. Commit `mods.json` and the new `packages/*.zip`, then push.

The manual path still works: bump `version` in the mod's `mod.toml`, package
with `JERICHO/CORE/modstore/make_mod_package.sh` (or `gen_mods_json.sh` for a
whole set), and merge the entry. Never hand-write a hash.

Keep old packages online: someone on an older version may still ask for that
file.

## Layout

    mods.json           the index the game reads
    packages/           the published zips, named <id>-<version>.zip
    tools/sync_store.py the newest-source check and publisher
    tools/sources.json  where each mod comes from
    docs/STRUCTURE.md   the mod folder/manifest reference
    MODS/example        a reference module scaffold

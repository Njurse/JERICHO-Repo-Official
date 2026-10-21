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
| `d1cars` | https://github.com/Njurse/JERICHO-D1 |
| `JerAI` | https://github.com/Njurse/JERICHO/tree/main/JERICHO/MODS/JerAI |

`mp`, `carhacks` and `crumple` are also git submodules of JERICHO, mounted at
`JERICHO/MODS/<id>`.

## Publishing

The index and packages are generated from the sources; never hand-edit a hash.

1. Bump `version` in the mod's `mod.toml` and push the source repository.
2. From a JERICHO checkout, package the mods and rebuild the index:

   ```sh
   sh JERICHO/CORE/modstore/gen_mods_json.sh --out out --url packages \
       --repo-id official --repo-name "JERICHO Mods" \
       --homepage https://github.com/Njurse/JERICHO-Repo-Official \
       mp carhacks crumple d1cars JerAI
   ```

3. Validate against the published index:

   ```sh
   python3 JERICHO/CORE/modstore/check_mod_repo.py out/mods.json \
       --packages out --previous mods.json --interface 2
   ```

4. Copy `out/mods.json` here and `out/*.zip` into `packages/`, then commit and
   push.

The store compares `version`, so a rebuilt package with an unchanged version is
invisible to anyone who already installed it. Bump the version for every change.
Keep old packages online: someone on an older version may still ask for that file.

## Layout

    mods.json           the index the game reads
    packages/           the published zips, named <id>-<version>.zip
    docs/STRUCTURE.md   the mod folder/manifest reference
    MODS/example        a reference module scaffold

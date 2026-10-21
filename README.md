# JERICHO Mods Official

Official and curated modules for [JERICHO](https://github.com/Njurse/JERICHO) (the Driver 2 / REDRIVER2 mod host).

## Expected layout (matches what the in-game mod store / loader expects)

Drop any module folder into your game install at `JERICHO/MODS/<id>/`. The loader scans every folder that contains a valid `mod.toml`.

```
JERICHO-Mods-Official/
├── README.md
├── MODS/
│   ├── <mod-id>/
│   │   ├── mod.toml          # required metadata
│   │   ├── <mod-id>.c         # source (compiled-in or external)
│   │   ├── README.md          # optional but recommended
│   │   └── textures/          # optional TGA art
│   └── ...
└── docs/
    └── STRUCTURE.md
```

### mod.toml minimum

```toml
id = "example"
name = "Example Module"
version = "0.1.0"
author = "Njurse"
description = "What it does."
default-enabled = false
# runtime = "dll"   # omit for compiled-in (deep) mods; set for external DLLs
```

See the main JERICHO repo for the full contract:
- https://github.com/Njurse/JERICHO/blob/main/README.md
- https://github.com/Njurse/JERICHO/blob/main/src_rebuild/Game/C/JERICHO/docs/HOOKS.md

## Usage

1. Clone or download this repo.
2. Copy the desired `MODS/<id>/` folder into your game’s `JERICHO/MODS/`.
3. Enable it under **Options → JERICHO** (state is written to `JERICHO/CONFIG/modlist.ini`).

External modules (`runtime = "dll"`) also need to be built against the JERICHO SDK / import library.

## Official modules

Place official modules under `MODS/`. They follow exactly the same rules as any third-party mod so they can be mixed, reordered, or removed without rebuilding the game.

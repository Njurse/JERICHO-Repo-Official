# Module folder structure expected by Jericho

This repository is the official **store** repo: `mods.json` is the index and
`packages/` holds the published zips. A source repository keeps the module at its
root, or under `MODS/<id>/` in the `new_mod_repo.sh` layout. See `README.md`.

Each module is a directory named after its `id`:

```
MODS/<id>/
├── mod.toml
├── <id>.c
├── <id>.h          # optional
├── README.md
└── textures/
    └── *.tga
```

### mod.toml fields

| Key               | Required | Notes                                      |
|-------------------|----------|--------------------------------------------|
| id                | yes      | Must match folder name                     |
| name              | yes      | Display name                               |
| version           | yes      | Semver-style string                        |
| author            | no       |                                            |
| description       | no       |                                            |
| default-enabled   | no       | true/false; absent = disabled             |
| runtime           | no       | "dll" = external; omit = compiled-in       |
| dependencies      | no       | list or comma-separated                    |
| incompatible      | no       | list or comma-separated                    |

Compiled-in modules are auto-discovered by premake and linked into the executable.
External modules are built separately and loaded via LoadLibrary/dlopen at runtime.

The in-game Mods menu reads these folders and the corresponding `CONFIG/modlist.ini` / `<id>.ini` files.

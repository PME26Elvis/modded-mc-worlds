# Modded Minecraft Worlds
Just my worlds.

## Modpacks

| Modpack | Folder | Minecraft | Pack Version | Launcher | World Folder | Notes |
|---|---|---:|---:|---|---|---|
| SkyFactory 4 | `packs/skyfactory-4` | 1.12.2 | 4.2.4 | CurseForge | `worlds/main` | Crash Landing 開局 |
| FTB Presents Stoneblock 2 | `packs/ftb-presents-stoneblock-2` | 1.12.2 | 1.16.1 | CurseForge | `worlds/main` | 幾乎完全完結 |
| Cuboid Outpost (Luxury Edition) | `packs/cuboid-outpost-luxury-edition` | 1.20.1 | 0.5.5 | CurseForge | `worlds/main` | END: Creative Item Cell & Energy |
| Ozone Skyblock Reborn | `packs/ozone-skyblock-reborn` | 1.20.1 | 1.19.1 | CurseForge | `worlds/main` | 玩到後期 |
| FTB StoneBlock 4 | `packs/ftb-stoneblock-4` | 1.21.1 | 1.11.1 | CurseForge | `worlds/main` | 與 Shiwan 一起遊玩，玩到一半，雞、作物、科技大致成熟，也已經解鎖很多升級，也在某些探索關卡上卡住 |
| Project Arc Light: The Hanging Pavilion | `packs/project-arc-light-the-hanging-pavilion` | 1.20.1 | 1.2.6 | CurseForge | `worlds/main` | 有點太肝了，玩不下去 |

## Structure

```text
packs/<modpack-folder>/
├─ README.md
├─ worlds/
│  └─ main/
│     └─ <put the world save here>
└─ extras/
   └─ <optional minimap, waypoint, screenshots, or notes>
```

Recommended save layout:

```text
packs/skyfactory-4/worlds/main/level.dat
packs/skyfactory-4/worlds/main/region/
packs/skyfactory-4/worlds/main/playerdata/
```

If the uploaded folder becomes `worlds/main/New World/level.dat`, the packaging workflow can still detect it and package the real world folder.

## Packaging current repo worlds

The workflow `.github/workflows/package-worlds.yml` runs `python tools/worlds_tool.py package --out dist` and generates:

- `dist/all/modded-mc-worlds-all-checkpoint-YYYY-MM-DD-HHmm.zip` (combined all-worlds archive)
- `dist/worlds/<pack-slug>-main-checkpoint-YYYY-MM-DD-HHmm.zip` (one checkpoint archive per pack, with `world-main/` and `extras/` folders)
- `dist/manifest.json` (machine-readable output paths and artifact-safe names)

The combined archive contains each pack in its own top-level folder (`<pack-slug>/world-main/...` and `<pack-slug>/extras/...`) to avoid collisions.

Packaging includes the main world save plus each pack's `extras/` folder.

## Add a new modpack folder in Codespaces

```bash
python tools/worlds_tool.py new-pack
```

## Package locally

```bash
python tools/worlds_tool.py package --out dist
```

## Upload old staged checkpoints to Releases (manual)

For old archives that should not be committed, stage files under:

```text
.local-checkpoints/<pack-slug>/
```

Then run:

```bash
python tools/release_checkpoints.py
```

This helper is interactive and uses `gh` CLI to create or upload to checkpoint-style releases (without moving/deleting staged files).

## Release current checkpoint from GitHub Actions (manual)

Use the **Release Current Checkpoint** workflow:

- Workflow file: `.github/workflows/release-current-checkpoint.yml`
- Trigger: `workflow_dispatch`
- Optional input: notes
- Behavior: re-packages current repo state and uploads both the combined archive and all per-pack checkpoint archives into a GitHub Release. Each per-pack archive contains `world-main/` and `extras/`.

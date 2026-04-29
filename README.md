# Modded Minecraft Worlds
Just my worlds.

## Modpacks

| Modpack | Folder | Minecraft | Pack Version | Launcher | World Folder | Notes |
|---|---|---:|---:|---|---|---|
| SkyFactory 4 | `packs/skyfactory-4` | 1.12.2 | 4.2.4 | CurseForge | `worlds/main` | Crash Landing 開局 |
| FTB Presents Stoneblock 2 | `packs/ftb-presents-stoneblock-2` | 1.12.2 | 1.16.1 | CurseForge | `worlds/main` | 幾乎完全完結 |
| Cuboid Outpost (Luxury Edition) | `packs/cuboid-outpost-luxury-edition` | 1.20.1 | 0.5.5 | CurseForge | `worlds/main` | END: Creative Item Cell & Energy |
| Ozone Skyblock Reborn | `packs/ozone-skyblock-reborn` | 1.20.1 | 1.19.1 | CurseForge | `worlds/main` | 玩到後期 |

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

## Packaging

The workflow `.github/workflows/package-worlds.yml` scans `packs/*/worlds/*`, detects valid Minecraft worlds by `level.dat`, and uploads zip files as a GitHub Actions artifact.

It packages world saves only. Files under `extras/` are intentionally not included.

## Add a new modpack folder in Codespaces

```bash
python tools/worlds_tool.py new-pack
```

## Package locally

```bash
python tools/worlds_tool.py package --out dist
```

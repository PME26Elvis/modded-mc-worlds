from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
PACKS_DIR = ROOT / "packs"

IGNORED_DIRS = {"logs", "crash-reports", ".mixin.out", "cache", ".git", "__pycache__"}
IGNORED_FILES = {".gitkeep", "session.lock", ".DS_Store", "Thumbs.db", "desktop.ini", "server-icon.png"}
ARCHIVE_SUFFIXES = (".zip", ".7z", ".rar", ".tar", ".tar.gz", ".tgz")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "new-modpack"


def title_from_folder(folder: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[-_]+", folder) if part)


def safe_name(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-_.") or "world"


def choose_launcher(raw: str) -> str:
    value = raw.strip().lower()
    match value:
        case "" | "1" | "cf" | "curseforge":
            return "CurseForge"
        case "2" | "ftb" | "ftb app" | "ftb-app":
            return "FTB App"
        case "3" | "prism" | "prism launcher" | "prism-launcher":
            return "Prism Launcher"
        case "4" | "modrinth":
            return "Modrinth"
        case _:
            return raw.strip()


def prompt(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value if value else (default or "")


def write_pack_readme(pack_dir: Path, title: str, folder: str, pack_version: str, mc_version: str, launcher: str, notes: str) -> None:
    text = f"""# {title}

| Field | Value |
|---|---|
| Folder | `{folder}` |
| Minecraft version | `{mc_version or 'TBD'}` |
| Pack version | `{pack_version or 'TBD'}` |
| Launcher | `{launcher or 'CurseForge'}` |
| Main world folder | `worlds/main` |
| Extras folder | `extras` |

## Where to put the world

Put the world save contents under:

```text
packs/{folder}/worlds/main/
```

Best layout:

```text
packs/{folder}/worlds/main/level.dat
packs/{folder}/worlds/main/region/
packs/{folder}/worlds/main/playerdata/
```

Also accepted by the packaging tool:

```text
packs/{folder}/worlds/main/New World/level.dat
```

## Notes

{notes or '_No notes yet._'}
"""
    (pack_dir / "README.md").write_text(text, encoding="utf-8")


def new_pack() -> int:
    raw_name = prompt("Folder name under packs")
    folder = slugify(raw_name)
    title = prompt("Display name", title_from_folder(folder))
    pack_version = prompt("Modpack version")
    mc_version = prompt("Minecraft version")
    launcher_raw = prompt("Launcher: Enter=CurseForge, 2=FTB App, 3=Prism Launcher, 4=Modrinth", "CurseForge")
    launcher = choose_launcher(launcher_raw)
    notes = prompt("Notes")

    pack_dir = PACKS_DIR / folder
    readme_path = pack_dir / "README.md"

    if readme_path.exists():
        answer = prompt(f"{readme_path.relative_to(ROOT)} exists. Overwrite README? y/N", "N")
        if answer.lower() not in {"y", "yes"}:
            print("Canceled.")
            return 1

    (pack_dir / "worlds" / "main").mkdir(parents=True, exist_ok=True)
    (pack_dir / "extras").mkdir(parents=True, exist_ok=True)
    (pack_dir / "worlds" / "main" / ".gitkeep").touch(exist_ok=True)
    (pack_dir / "extras" / ".gitkeep").touch(exist_ok=True)
    write_pack_readme(pack_dir, title, folder, pack_version, mc_version, launcher, notes)

    print(f"Created {pack_dir.relative_to(ROOT)}")
    print(f"Put the save in {pack_dir.relative_to(ROOT)}/worlds/main")
    return 0


def is_ignored(path: Path) -> bool:
    if any(part in IGNORED_DIRS for part in path.parts):
        return True
    if path.name in IGNORED_FILES:
        return True
    if re.fullmatch(r"hs_err_pid\d+\.log", path.name):
        return True
    return False


def has_real_files(path: Path) -> bool:
    return any(p.is_file() and not is_ignored(p.relative_to(path)) for p in path.rglob("*"))


def archive_suffix(path: Path) -> str | None:
    name = path.name.lower()
    for suffix in ARCHIVE_SUFFIXES:
        if name.endswith(suffix):
            return suffix
    return None


def find_world_roots(world_slot: Path) -> list[Path]:
    if (world_slot / "level.dat").is_file():
        return [world_slot]
    roots = sorted({p.parent for p in world_slot.rglob("level.dat") if p.is_file()})
    return roots


def add_world_to_zip(source: Path, output: Path) -> None:
    with ZipFile(output, "w", ZIP_DEFLATED) as zf:
        for file in sorted(p for p in source.rglob("*") if p.is_file()):
            rel = file.relative_to(source)
            if is_ignored(rel):
                continue
            zf.write(file, rel.as_posix())


def copy_existing_archive(pack_name: str, archive: Path, worlds_dir: Path, out_dir: Path) -> Path:
    suffix = archive_suffix(archive)
    rel = archive.relative_to(worlds_dir)
    stem = rel.as_posix()[: -len(suffix)] if suffix else rel.as_posix()
    output = out_dir / f"{safe_name(pack_name)}-{safe_name(stem)}{suffix or archive.suffix}"
    shutil.copy2(archive, output)
    return output


def package_worlds(out_dir: Path) -> int:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not PACKS_DIR.exists():
        print("No packs directory found.")
        return 1

    made: list[Path] = []
    warnings: list[str] = []

    for pack_dir in sorted(p for p in PACKS_DIR.iterdir() if p.is_dir()):
        pack_name = pack_dir.name
        worlds_dir = pack_dir / "worlds"
        if not worlds_dir.exists():
            warnings.append(f"{pack_name}: missing worlds/")
            continue

        for archive in sorted(p for p in worlds_dir.rglob("*") if p.is_file() and archive_suffix(p)):
            if is_ignored(archive.relative_to(worlds_dir)):
                continue
            output = copy_existing_archive(pack_name, archive, worlds_dir, out_dir)
            made.append(output)

        slots = sorted(p for p in worlds_dir.iterdir() if p.is_dir())
        for slot in slots:
            if not has_real_files(slot):
                continue

            roots = find_world_roots(slot)
            if not roots:
                warnings.append(f"{pack_name}/{slot.name}: non-empty folder, but no level.dat found")
                continue

            for root in roots:
                if root == slot:
                    world_name = slot.name
                else:
                    world_name = f"{slot.name}-{root.name}"
                output = out_dir / f"{safe_name(pack_name)}-{safe_name(world_name)}.zip"
                add_world_to_zip(root, output)
                made.append(output)

    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    if not made:
        print("No world folders or archive files were packaged.")
        return 0

    print("Packaged files:")
    for output in made:
        print(f"- {output.relative_to(ROOT)}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("new-pack")

    package_parser = subparsers.add_parser("package")
    package_parser.add_argument("--out", default="dist")

    args = parser.parse_args()

    match args.command:
        case "new-pack":
            return new_pack()
        case "package":
            return package_worlds((ROOT / args.out).resolve())
        case _:
            parser.print_help()
            return 1


if __name__ == "__main__":
    raise SystemExit(main())

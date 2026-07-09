from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
PACKS_DIR = ROOT / "packs"

IGNORED_DIRS = {"logs", "crash-reports", ".mixin.out", "cache", ".git", "__pycache__"}
IGNORED_FILES = {".gitkeep", "session.lock", ".DS_Store", "Thumbs.db", "desktop.ini", "server-icon.png"}
ARCHIVE_SUFFIXES = (".zip", ".7z", ".rar", ".tar", ".tar.gz", ".tgz")

# Most files under extras/local are launcher/client caches. Keep FTB client
# progression-adjacent data (map tiles, waypoints, chunk/team client state), but
# exclude unrelated dev/client scratch data plus launch/account artifacts.
PACKAGE_EXCLUDED_DIRS = {"crash_assistant", "minetogether"}
PACKAGE_EXCLUDED_SUFFIXES = (".jar", ".dll")
PACKAGE_EXCLUDED_FILENAMES = {"username.info"}
PACKAGE_EXCLUDED_PATTERNS = (re.compile(r".*_args\.info$", re.IGNORECASE),)
LOCAL_ALLOWED_DIRS = {"ftbchunks", "ftbquests", "ftbutilities", "ftbechoes"}
LOCAL_ALLOWED_FILENAMES = {"ftblibrary-client.snbt", "ftbultimine-client.snbt", "ftblib.cfg", "ftbutilities.cfg"}

SENSITIVE_FILENAMES = {
    "launcher_accounts.json",
    "accounts.json",
    "servers.dat",
    "realms_persistence.json",
    "username.info",
}
SENSITIVE_NAME_PATTERNS = (
    re.compile(r".*_args\.info$", re.IGNORECASE),
    re.compile(r".*\.(jar|dll)$", re.IGNORECASE),
)
SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"accessToken", re.IGNORECASE),
    re.compile(r"clientToken", re.IGNORECASE),
    re.compile(r"refreshToken", re.IGNORECASE),
    re.compile(r"launcher_accounts", re.IGNORECASE),
    re.compile(r"servers\.dat", re.IGNORECASE),
    re.compile(r"oauth", re.IGNORECASE),
    re.compile(r"bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
)
SCAN_TEXT_SUFFIXES = {".txt", ".md", ".json", ".snbt", ".info", ".toml", ".cfg", ".properties", ".yml", ".yaml", ".xml", ".log"}


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


def is_allowed_local_extra(path: Path) -> bool:
    parts = path.parts
    if "local" not in parts:
        return True

    local_index = parts.index("local")
    if len(parts) <= local_index + 1:
        return False

    first_local_part = parts[local_index + 1]
    return first_local_part in LOCAL_ALLOWED_DIRS or path.name in LOCAL_ALLOWED_FILENAMES


def is_package_excluded(path: Path) -> bool:
    if is_ignored(path):
        return True
    if any(part in PACKAGE_EXCLUDED_DIRS for part in path.parts):
        return True
    if not is_allowed_local_extra(path):
        return True
    if path.name in PACKAGE_EXCLUDED_FILENAMES:
        return True
    if path.name.lower().endswith(PACKAGE_EXCLUDED_SUFFIXES):
        return True
    if any(pattern.fullmatch(path.name) for pattern in PACKAGE_EXCLUDED_PATTERNS):
        return True
    return False


def has_real_files(path: Path) -> bool:
    return any(p.is_file() and not is_package_excluded(p.relative_to(path)) for p in path.rglob("*"))


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


def add_directory_to_zip(zf: ZipFile, source: Path, prefix: str) -> None:
    if not source.is_dir():
        return
    for file in sorted(p for p in source.rglob("*") if p.is_file()):
        rel = file.relative_to(source)
        if is_package_excluded(rel):
            continue
        zf.write(file, (Path(prefix) / rel).as_posix())


def add_pack_checkpoint_to_zip(world_root: Path, extras_dir: Path, output: Path) -> None:
    with ZipFile(output, "w", ZIP_DEFLATED) as zf:
        add_directory_to_zip(zf, world_root, "world-main")
        add_directory_to_zip(zf, extras_dir, "extras")


def copy_existing_archive(pack_name: str, archive: Path, worlds_dir: Path, out_dir: Path) -> Path:
    suffix = archive_suffix(archive)
    rel = archive.relative_to(worlds_dir)
    stem = rel.as_posix()[: -len(suffix)] if suffix else rel.as_posix()
    output = out_dir / f"{safe_name(pack_name)}-{safe_name(stem)}{suffix or archive.suffix}"
    shutil.copy2(archive, output)
    return output


def find_main_world_root(pack_dir: Path) -> Path | None:
    main_dir = pack_dir / "worlds" / "main"
    if not main_dir.is_dir() or not has_real_files(main_dir):
        return None
    roots = find_world_roots(main_dir)
    return roots[0] if roots else None


def package_worlds(out_dir: Path) -> int:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not PACKS_DIR.exists():
        print("No packs directory found.")
        return 1

    all_dir = out_dir / "all"
    worlds_dir = out_dir / "worlds"
    archives_dir = out_dir / "archives"
    all_dir.mkdir(parents=True, exist_ok=True)
    worlds_dir.mkdir(parents=True, exist_ok=True)
    archives_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
    all_zip_name = f"modded-mc-worlds-all-checkpoint-{timestamp}.zip"
    all_zip = all_dir / all_zip_name

    warnings: list[str] = []
    copied_archives: list[Path] = []
    per_pack: list[dict[str, str]] = []

    for pack_dir in sorted(p for p in PACKS_DIR.iterdir() if p.is_dir()):
        pack_name = pack_dir.name
        pack_worlds_dir = pack_dir / "worlds"
        if not pack_worlds_dir.exists():
            warnings.append(f"{pack_name}: missing worlds/")
            continue

        for archive in sorted(p for p in pack_worlds_dir.rglob("*") if p.is_file() and archive_suffix(p)):
            if is_package_excluded(archive.relative_to(pack_worlds_dir)):
                continue
            copied = copy_existing_archive(pack_name, archive, pack_worlds_dir, archives_dir)
            copied_archives.append(copied)

        main_root = find_main_world_root(pack_dir)
        if main_root is None:
            warnings.append(f"{pack_name}/main: skipped (no detectable level.dat)")
            continue

        per_pack_name = f"{safe_name(pack_name)}-main-checkpoint-{timestamp}.zip"
        per_pack_output = worlds_dir / per_pack_name
        add_pack_checkpoint_to_zip(main_root, pack_dir / "extras", per_pack_output)

        per_pack.append(
            {
                "pack_slug": pack_name,
                "archive": str(per_pack_output.relative_to(ROOT)),
                "artifact_name": f"minecraft-world-{safe_name(pack_name)}-main",
                "world_root": str(main_root.relative_to(ROOT)),
            }
        )

    if per_pack:
        with ZipFile(all_zip, "w", ZIP_DEFLATED) as zf:
            for entry in per_pack:
                world_root = ROOT / entry["world_root"]
                pack_dir = PACKS_DIR / entry["pack_slug"]
                prefix = entry["pack_slug"]
                add_directory_to_zip(zf, world_root, f"{prefix}/world-main")
                add_directory_to_zip(zf, pack_dir / "extras", f"{prefix}/extras")

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "combined_archive": str(all_zip.relative_to(ROOT)) if per_pack else None,
        "combined_artifact_name": "minecraft-worlds-all" if per_pack else None,
        "per_pack_archives": per_pack,
        "copied_existing_archives": [str(p.relative_to(ROOT)) for p in copied_archives],
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    print("Generated manifest:")
    print(f"- {manifest_path.relative_to(ROOT)}")

    if per_pack:
        print("Generated world archives:")
        print(f"- {all_zip.relative_to(ROOT)}")
        for entry in per_pack:
            print(f"- {entry['archive']}")
    if copied_archives:
        print("Copied existing archives:")
        for copied in copied_archives:
            print(f"- {copied.relative_to(ROOT)}")

    return 0


def scan_paths(paths: Iterable[Path]) -> list[str]:
    findings: list[str] = []
    for base in paths:
        if not base.exists():
            continue
        files = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file())
        for file in files:
            try:
                rel = file.relative_to(ROOT)
            except ValueError:
                rel = file
            rel_text = rel.as_posix()
            name = file.name

            if name in SENSITIVE_FILENAMES or any(pattern.fullmatch(name) for pattern in SENSITIVE_NAME_PATTERNS):
                findings.append(f"sensitive file name: {rel_text}")

            if "extras/local" in rel_text or "crash_assistant" in rel.parts:
                if name in SENSITIVE_FILENAMES or any(pattern.fullmatch(name) for pattern in SENSITIVE_NAME_PATTERNS):
                    findings.append(f"sensitive local/cache file: {rel_text}")

            if file.suffix.lower() not in SCAN_TEXT_SUFFIXES:
                continue

            try:
                text = file.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                findings.append(f"could not read {rel_text}: {exc}")
                continue

            for pattern in SENSITIVE_TEXT_PATTERNS:
                if pattern.search(text):
                    findings.append(f"sensitive text '{pattern.pattern}': {rel_text}")
                    break
    return findings


def scan_repo() -> int:
    findings = scan_paths([PACKS_DIR, ROOT / ".github", ROOT / "tools"])
    if findings:
        print("Sensitive packaging scan failed:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1
    print("Sensitive packaging scan passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("new-pack")
    subparsers.add_parser("scan-sensitive")

    package_parser = subparsers.add_parser("package")
    package_parser.add_argument("--out", default="dist")

    args = parser.parse_args()

    match args.command:
        case "new-pack":
            return new_pack()
        case "package":
            scan_result = scan_repo()
            if scan_result != 0:
                return scan_result
            return package_worlds((ROOT / args.out).resolve())
        case "scan-sensitive":
            return scan_repo()
        case _:
            parser.print_help()
            return 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKS_DIR = ROOT / "packs"
STAGING_DIR = ROOT / ".local-checkpoints"
ARCHIVE_SUFFIXES = (".zip", ".7z", ".rar", ".tar", ".tar.gz", ".tgz")


def title_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.replace("_", "-").split("-") if part)


def choose(options: list[str], label: str) -> str:
    for idx, option in enumerate(options, start=1):
        print(f"[{idx}] {option}")
    while True:
        raw = input(f"{label} [1-{len(options)}]: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("Invalid choice.")


def run_checked(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def list_archives(path: Path) -> list[Path]:
    return sorted([p for p in path.iterdir() if p.is_file() and p.name.lower().endswith(ARCHIVE_SUFFIXES)])


def ensure_gh_ready() -> bool:
    if shutil.which("gh") is None:
        print("Error: gh CLI is not installed. Install GitHub CLI and try again.")
        return False
    try:
        subprocess.run(["gh", "auth", "status"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("Error: gh CLI is not authenticated. Run 'gh auth login' and try again.")
        return False
    return True


def main() -> int:
    if not ensure_gh_ready():
        return 1

    packs = sorted([p.name for p in PACKS_DIR.iterdir() if p.is_dir()])
    if not packs:
        print("No packs found in packs/.")
        return 1

    print("Choose pack slug:")
    pack_slug = choose(packs, "Pack")
    display_name = title_from_slug(pack_slug)

    staged_dir = STAGING_DIR / pack_slug
    if not staged_dir.exists():
        print(f"No staging folder found: {staged_dir.relative_to(ROOT)}")
        return 1

    archives = list_archives(staged_dir)
    if not archives:
        print(f"No archive files found in {staged_dir.relative_to(ROOT)}")
        return 1

    print("Staged archives:")
    for path in archives:
        print(f"- {path.name}")

    today = date.today().isoformat()
    checkpoint_date = input(f"Checkpoint date [default: {today}]: ").strip() or today

    default_tag = f"checkpoint-{pack_slug}-archive-{checkpoint_date}"
    default_title = f"{display_name} Checkpoint Archive - {checkpoint_date}"

    mode = choose(["Create new release", "Upload to existing release"], "Mode")

    notes = input("Optional notes (leave blank for default message): ").strip()
    body = notes or (
        f"Minecraft world checkpoints for {display_name}.\n"
        "Source: manually staged checkpoint archives."
    )

    if mode == "Create new release":
        tag = input(f"Release tag [default: {default_tag}]: ").strip() or default_tag
        title = input(f"Release title [default: {default_title}]: ").strip() or default_title
        cmd = [
            "gh",
            "release",
            "create",
            tag,
            "--title",
            title,
            "--notes",
            body,
        ] + [str(p) for p in archives]
    else:
        tag = input(f"Existing release tag [default: {default_tag}]: ").strip() or default_tag
        cmd = ["gh", "release", "upload", tag, "--clobber"] + [str(p) for p in archives]

    try:
        run_checked(cmd)
    except subprocess.CalledProcessError as exc:
        print(f"gh command failed with exit code {exc.returncode}")
        return exc.returncode

    print("Done. Staged files were not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

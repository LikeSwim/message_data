#!/usr/bin/env python3
from __future__ import annotations

import argparse
import filecmp
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DATE_DIR_LENGTH = 10
SPECIAL_TOP_LEVEL_DIRS = {"exports", ".git", "__pycache__"}


@dataclass
class Summary:
    planned_moves: int = 0
    executed_moves: int = 0
    duplicate_files: int = 0
    conflicts: int = 0
    skipped_legacy: int = 0
    removed_empty_dirs: int = 0
    logs: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        self.logs.append(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize run folders into the structure 场景/日期/sessionid/文件 by "
            "merging data from exports/YYYY-MM-DD/场景/sessionid and legacy 场景/sessionid."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Workspace root containing scene folders and the exports directory.",
    )
    parser.add_argument(
        "--exports-dir",
        type=Path,
        default=Path("exports"),
        help="Exports directory path, relative to --root when not absolute.",
    )
    parser.add_argument(
        "--skip-legacy",
        action="store_true",
        help="Do not normalize existing legacy scene/sessionid directories in the root.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute moves. Without this flag the script only prints the plan.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print only the final summary instead of every planned operation.",
    )
    return parser.parse_args()


def is_date_dir(name: str) -> bool:
    if len(name) != DATE_DIR_LENGTH:
        return False
    try:
        datetime.strptime(name, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def looks_like_session_dir(path: Path) -> bool:
    return path.is_dir() and (path / "run.json").is_file()


def resolve_date_from_run(session_dir: Path) -> str | None:
    run_file = session_dir / "run.json"
    if not run_file.is_file():
        return None

    try:
        data = json.loads(run_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    for key in ("startedAt", "finishedAt"):
        value = data.get(key)
        if not value or not isinstance(value, str):
            continue
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc).date().isoformat()

    return None


def ensure_dir(path: Path, apply_changes: bool) -> None:
    if apply_changes:
        path.mkdir(parents=True, exist_ok=True)


def remove_if_empty(path: Path, stop_at: Path, apply_changes: bool, summary: Summary) -> None:
    current = path
    while current != stop_at and current.exists():
        if not current.is_dir():
            return
        try:
            next(current.iterdir())
        except StopIteration:
            summary.log(f"REMOVE EMPTY DIR {current}")
            if apply_changes:
                current.rmdir()
                summary.removed_empty_dirs += 1
            current = current.parent
            continue
        return


def files_are_identical(source: Path, target: Path) -> bool:
    try:
        return filecmp.cmp(source, target, shallow=False)
    except OSError:
        return False


def merge_tree(
    source: Path,
    target: Path,
    apply_changes: bool,
    summary: Summary,
    cleanup_stop: Path,
) -> None:
    if source.resolve() == target.resolve():
        return

    if not target.exists():
        summary.planned_moves += 1
        summary.log(f"MOVE DIR  {source} -> {target}")
        if apply_changes:
            ensure_dir(target.parent, apply_changes=True)
            shutil.move(str(source), str(target))
            summary.executed_moves += 1
            remove_if_empty(source.parent, cleanup_stop, apply_changes=True, summary=summary)
        return

    if source.is_file():
        if target.is_dir():
            summary.conflicts += 1
            summary.log(f"CONFLICT  file-vs-dir {source} -> {target}")
            return
        if files_are_identical(source, target):
            summary.duplicate_files += 1
            summary.log(f"DUPLICATE {source} == {target}")
            if apply_changes:
                source.unlink()
                remove_if_empty(source.parent, cleanup_stop, apply_changes=True, summary=summary)
            return
        summary.conflicts += 1
        summary.log(f"CONFLICT  file mismatch {source} -> {target}")
        return

    if not target.is_dir():
        summary.conflicts += 1
        summary.log(f"CONFLICT  dir-vs-file {source} -> {target}")
        return

    for child in sorted(source.iterdir(), key=lambda item: item.name):
        merge_tree(child, target / child.name, apply_changes, summary, cleanup_stop)

    if apply_changes:
        remove_if_empty(source, cleanup_stop, apply_changes=True, summary=summary)


def iter_exports_sessions(exports_dir: Path) -> Iterable[tuple[str, Path, Path]]:
    if not exports_dir.is_dir():
        return

    for date_dir in sorted(exports_dir.iterdir(), key=lambda item: item.name):
        if not date_dir.is_dir() or not is_date_dir(date_dir.name):
            continue
        for scene_dir in sorted(date_dir.iterdir(), key=lambda item: item.name):
            if not scene_dir.is_dir():
                continue
            for session_dir in sorted(scene_dir.iterdir(), key=lambda item: item.name):
                if session_dir.is_dir():
                    yield date_dir.name, scene_dir, session_dir


def process_exports(root: Path, exports_dir: Path, apply_changes: bool, summary: Summary) -> None:
    for date_str, scene_dir, session_dir in iter_exports_sessions(exports_dir):
        target = root / scene_dir.name / date_str / session_dir.name
        merge_tree(
            source=session_dir,
            target=target,
            apply_changes=apply_changes,
            summary=summary,
            cleanup_stop=exports_dir,
        )


def iter_legacy_sessions(root: Path) -> Iterable[tuple[Path, Path]]:
    for scene_dir in sorted(root.iterdir(), key=lambda item: item.name):
        if not scene_dir.is_dir():
            continue
        if scene_dir.name in SPECIAL_TOP_LEVEL_DIRS or scene_dir.name.startswith("."):
            continue

        for child in sorted(scene_dir.iterdir(), key=lambda item: item.name):
            if not child.is_dir():
                continue
            if is_date_dir(child.name):
                continue
            yield scene_dir, child


def process_legacy(root: Path, apply_changes: bool, summary: Summary) -> None:
    for scene_dir, session_dir in iter_legacy_sessions(root):
        if not looks_like_session_dir(session_dir):
            summary.skipped_legacy += 1
            summary.log(f"SKIP      {session_dir} (missing run.json)")
            continue

        date_str = resolve_date_from_run(session_dir)
        if not date_str:
            summary.skipped_legacy += 1
            summary.log(f"SKIP      {session_dir} (cannot infer date)")
            continue

        target = scene_dir / date_str / session_dir.name
        merge_tree(
            source=session_dir,
            target=target,
            apply_changes=apply_changes,
            summary=summary,
            cleanup_stop=scene_dir,
        )


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    exports_dir = args.exports_dir
    if not exports_dir.is_absolute():
        exports_dir = root / exports_dir
    exports_dir = exports_dir.resolve()

    summary = Summary()
    process_exports(root, exports_dir, args.apply, summary)
    if not args.skip_legacy:
        process_legacy(root, args.apply, summary)

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] root={root}")
    print(f"[{mode}] exports={exports_dir}")
    if not args.summary_only:
        for line in summary.logs:
            print(line)
    print(
        "SUMMARY "
        f"planned_moves={summary.planned_moves} "
        f"executed_moves={summary.executed_moves} "
        f"duplicate_files={summary.duplicate_files} "
        f"conflicts={summary.conflicts} "
        f"skipped_legacy={summary.skipped_legacy} "
        f"removed_empty_dirs={summary.removed_empty_dirs}"
    )
    return 0 if summary.conflicts == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

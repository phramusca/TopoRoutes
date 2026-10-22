#!/usr/bin/env python3
"""
Chaîne locale Komoot → GPX → organisation dans komoot-library/tours/<id>/ + meta.json.

Prérequis : environnement du projet géré avec `uv`.

Exemples :

  # Sync initiale puis incrémentale (équivalent komootgpx : -a -S -I)
  ./scripts/komoot_library.py sync

  # Arguments transmis tels quels à komootgpx (le script force -I si absent)
  ./scripts/komoot_library.py sync -- -a -S --start-date 2026-01-01

  # Enregistrer une nouvelle version issue de gpx.studio (copie + meta.json)
  ./scripts/komoot_library.py add-gpxstudio --tour-id 12345 --source ~/Downloads/route.gpx

komootgpx utilise le répertoire de travail `komoot-library/` pour ses opérations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .library_web import serve as serve_library_web

GPX_NS = "http://www.topografix.com/GPX/1/1"


def _repo_komoot_library() -> Path:
    return Path(__file__).resolve().parent.parent / "komoot-library"


def resolve_library(path: str | None) -> Path:
    base = Path(path or os.environ.get("KOMOOT_LIBRARY", _repo_komoot_library()))
    return base.resolve()


def parse_tour_id_from_gpx_filename(filename: str) -> str | None:
    """komootgpx avec -I : `12345.gpx` ou `2022-01-02_12345.gpx` avec -D."""
    m = re.match(r"^(?:\d{4}-\d{2}-\d{2}_)?(\d+)\.gpx$", filename)
    return m.group(1) if m else None


def gpx_first_name(path: Path) -> str | None:
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        if root.tag == f"{{{GPX_NS}}}gpx":
            for child in root:
                if child.tag == f"{{{GPX_NS}}}metadata":
                    for m in child:
                        if m.tag == f"{{{GPX_NS}}}name" and m.text:
                            return m.text.strip()
                if child.tag == f"{{{GPX_NS}}}trk":
                    for t in child:
                        if t.tag == f"{{{GPX_NS}}}name" and t.text:
                            return t.text.strip()
        # fallback : premier <name> quelconque
        for el in root.iter():
            if el.tag.endswith("name") and el.text:
                return el.text.strip()
    except (ET.ParseError, OSError):
        pass
    return None


def komoot_url(tour_id: str) -> str:
    return f"https://www.komoot.com/tour/{tour_id}"


def target_komoot_filename(tour_type: str) -> tuple[str, str]:
    """(nom de fichier, rôle meta.json)"""
    if tour_type == "planned":
        return "01_komoot_planned.gpx", "planned"
    if tour_type == "recorded":
        return "02_komoot_recorded.gpx", "recorded"
    return "01_komoot_sync.gpx", "komoot_export"


def load_meta(tour_dir: Path) -> dict[str, Any]:
    p = tour_dir / "meta.json"
    if not p.is_file():
        return {
            "komoot_id": tour_dir.name,
            "title": None,
            "url": komoot_url(tour_dir.name),
            "last_sync": None,
            "source_tool": "komootgpx",
            "files": [],
        }
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("files", [])
    data.setdefault("source_tool", "komootgpx")
    return data


def save_meta(tour_dir: Path, data: dict[str, Any]) -> None:
    tour_dir.mkdir(parents=True, exist_ok=True)
    with open(tour_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def upsert_file_entry(files: list[dict[str, Any]], path: str, role: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for e in files:
        if e.get("path") == path:
            e["role"] = role
            e["updated_at"] = now
            return
    files.append({"path": path, "role": role, "updated_at": now})


def copy_gpx_to_tours(
    library: Path,
    staging: Path,
    tour_type: str,
    filenames: set[str] | None = None,
    preserve_source: bool = False,
) -> list[str]:
    """Range les GPX reconnus et met à jour meta.json."""
    if not staging.is_dir():
        return []

    target_name, role = target_komoot_filename(tour_type)
    processed: list[str] = []

    for item in sorted(staging.iterdir()):
        if not item.is_file() or item.suffix.lower() != ".gpx":
            continue
        if filenames is not None and item.name not in filenames:
            continue
        tour_id = parse_tour_id_from_gpx_filename(item.name)
        if not tour_id:
            continue

        tour_dir = library / "tours" / tour_id
        tour_dir.mkdir(parents=True, exist_ok=True)
        dest = tour_dir / target_name
        if preserve_source:
            shutil.copy2(item, dest)
        else:
            shutil.move(str(item), str(dest))
        processed.append(tour_id)

        title = gpx_first_name(dest)
        meta = load_meta(tour_dir)
        meta["komoot_id"] = tour_id
        meta["url"] = komoot_url(tour_id)
        if title:
            meta["title"] = title
        meta["last_sync"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        upsert_file_entry(meta["files"], target_name, role)
        save_meta(tour_dir, meta)

    return processed


def gpx_fingerprints(directory: Path) -> dict[str, str]:
    """Empreinte du contenu des GPX présents dans un répertoire."""
    if not directory.is_dir():
        return {}
    return {
        item.name: hashlib.sha256(item.read_bytes()).hexdigest()
        for item in directory.iterdir()
        if item.is_file() and item.suffix.lower() == ".gpx"
    }


def run_komootgpx(library: Path, staging: Path, extra: list[str]) -> int:
    staging.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "komootgpx", "-o", str(staging)]
    if "-I" not in extra and "--id-filename" not in extra:
        cmd.append("-I")
    cmd.extend(extra)
    env = os.environ.copy()
    return subprocess.call(cmd, cwd=str(library), env=env)


def cmd_sync(args: argparse.Namespace) -> int:
    library = resolve_library(args.library)
    staging = library / ".sync_cache"
    before = gpx_fingerprints(staging)
    extra = list(args.komootgpx_args)
    if not extra:
        extra = ["-a", "-S"]

    rc = run_komootgpx(library, staging, extra)
    if rc != 0:
        return rc

    after = gpx_fingerprints(staging)
    target_name, _ = target_komoot_filename(args.tour_type)
    changed_or_missing = {
        filename
        for filename, fingerprint in after.items()
        if before.get(filename) != fingerprint
        or not (
            library
            / "tours"
            / (parse_tour_id_from_gpx_filename(filename) or "")
            / target_name
        ).is_file()
    }
    copy_gpx_to_tours(
        library,
        staging,
        args.tour_type,
        filenames=changed_or_missing,
        preserve_source=True,
    )
    return 0


def next_version_index(tour_dir: Path) -> int:
    """Prochain préfixe numérique NN pour tout fichier `NN_*.gpx` du dossier."""
    pat = re.compile(r"^(\d{2})_.+\.gpx$")
    best = 0
    for p in tour_dir.iterdir():
        if p.is_file():
            m = pat.match(p.name)
            if m:
                best = max(best, int(m.group(1)))
    return best + 1


def cmd_add_gpxstudio(args: argparse.Namespace) -> int:
    library = resolve_library(args.library)
    tour_id = args.tour_id.strip()
    tour_dir = library / "tours" / tour_id
    src = Path(args.source).expanduser().resolve()
    if not src.is_file():
        print(f"Fichier introuvable : {src}", file=sys.stderr)
        return 1

    date_s = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tour_dir.mkdir(parents=True, exist_ok=True)
    idx = next_version_index(tour_dir)
    dest_name = f"{idx:02d}_gpxstudio_{date_s}.gpx"
    dest = tour_dir / dest_name
    shutil.copy2(src, dest)

    meta = load_meta(tour_dir)
    meta["komoot_id"] = tour_id
    meta.setdefault("url", komoot_url(tour_id))
    title = gpx_first_name(dest)
    if title:
        meta["title"] = title
    upsert_file_entry(meta["files"], dest_name, "edited_gpxstudio")
    save_meta(tour_dir, meta)
    print(dest)
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    library = resolve_library(args.library)
    serve_library_web(
        library,
        host=args.host,
        port=args.port,
        gpx_studio_base_url=args.gpx_studio_base_url,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Komoot → komoot-library + meta.json")
    parser.add_argument(
        "--library",
        default=None,
        help="Racine komoot-library (défaut : KOMOOT_LIBRARY ou ./komoot-library)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_sync = sub.add_parser("sync", help="Lance komootgpx puis organise les GPX")
    p_sync.add_argument(
        "--tour-type",
        choices=("planned", "recorded", "all"),
        default="all",
        help="Influence le nom du fichier Komoot et le rôle dans meta.json",
    )
    p_sync.add_argument(
        "komootgpx_args",
        nargs="*",
        help="Arguments komootgpx (défaut sans argument : -a -S)",
    )
    p_sync.set_defaults(func=cmd_sync)

    p_add = sub.add_parser("add-gpxstudio", help="Enregistre une version éditée (nouveau fichier)")
    p_add.add_argument("--tour-id", required=True, help="Identifiant numérique Komoot du parcours")
    p_add.add_argument("--source", required=True, help="Fichier GPX exporté depuis gpx.studio")
    p_add.add_argument("--date", default=None, help="Suffixe date YYYY-MM-DD (défaut : aujourd’hui UTC)")
    p_add.set_defaults(func=cmd_add_gpxstudio)

    p_web = sub.add_parser("web", help="Affiche la bibliothèque GPX dans un navigateur")
    p_web.add_argument("--host", default="127.0.0.1", help="Interface réseau (défaut : 127.0.0.1)")
    p_web.add_argument("--port", type=int, default=8765, help="Port HTTP (défaut : 8765)")
    p_web.add_argument(
        "--gpx-studio-base-url",
        default=os.environ.get("GPX_STUDIO_BASE_URL", "https://gpx.studio"),
        help="URL gpx.studio (vide si l’éditeur est servi sous la même origine)",
    )
    p_web.set_defaults(func=cmd_web)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

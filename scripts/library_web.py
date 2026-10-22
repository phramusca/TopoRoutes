from __future__ import annotations

import html
import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

GPX_STUDIO_URL = "https://gpx.studio"
TOUR_ID_PATTERN = re.compile(r"^\d+$")


def _file_role(meta: dict, filename: str) -> str:
    entries = meta.get("files", [])
    if not isinstance(entries, list):
        return ""
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("path") == filename:
            return str(entry.get("role", ""))
    return ""


def _library_page(library: Path) -> bytes:
    tours_dir = library / "tours"
    cards: list[str] = []
    tour_count = 0
    file_count = 0

    if tours_dir.is_dir():
        for tour_dir in sorted(tours_dir.iterdir()):
            if tour_dir.is_symlink() or not tour_dir.is_dir():
                continue
            gpx_files = sorted(
                path for path in tour_dir.iterdir()
                if not path.is_symlink() and path.is_file() and path.suffix.lower() == ".gpx"
            )
            if not gpx_files:
                continue

            tour_count += 1
            meta_path = tour_dir / "meta.json"
            meta = {}
            metadata_error = ""
            if meta_path.is_file():
                try:
                    loaded = json.loads(meta_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        meta = loaded
                    else:
                        metadata_error = "meta.json doit contenir un objet JSON."
                except (OSError, json.JSONDecodeError) as error:
                    metadata_error = f"meta.json illisible : {error}"

            title = str(meta.get("title") or f"Parcours {tour_dir.name}")
            file_count += len(gpx_files)
            file_rows = []
            for gpx_file in gpx_files:
                filename = html.escape(gpx_file.name)
                role = html.escape(_file_role(meta, gpx_file.name))
                download_url = (
                    f"/files/{quote(tour_dir.name, safe='')}/"
                    f"{quote(gpx_file.name, safe='')}"
                )
                role_markup = f'<span class="role">{role}</span>' if role else ""
                file_rows.append(
                    f"""
                    <li class="file-row">
                      <div class="file-info">
                        <span class="file-name">{filename}</span>
                        {role_markup}
                      </div>
                      <a class="button download" href="{download_url}" download>
                        Télécharger
                      </a>
                    </li>
                    """
                )

            error_markup = (
                f'<p class="warning">{html.escape(metadata_error)}</p>'
                if metadata_error
                else ""
            )
            search_text = html.escape(
                " ".join((title, tour_dir.name, *(path.name for path in gpx_files))),
                quote=True,
            )
            tour_url = f"https://www.komoot.com/tour/{quote(tour_dir.name, safe='')}"
            cards.append(
                f"""
                <article class="tour-card" data-search="{search_text}">
                  <header class="tour-header">
                    <div>
                      <h2>{html.escape(title)}</h2>
                      <a class="tour-id" href="{tour_url}" target="_blank"
                         rel="noopener noreferrer">Parcours Komoot {html.escape(tour_dir.name)}</a>
                    </div>
                    <a class="button editor" href="{GPX_STUDIO_URL}" target="_blank"
                       rel="noopener noreferrer">Ouvrir gpx.studio</a>
                  </header>
                  {error_markup}
                  <ul class="file-list">{''.join(file_rows)}</ul>
                  <p class="import-hint">
                    Téléchargez une version, puis importez-la dans gpx.studio
                    avec son bouton d’ouverture de fichier.
                  </p>
                </article>
                """
            )

    if cards:
        content = "".join(cards)
        empty_class = "hidden"
    else:
        content = ""
        empty_class = ""

    page = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bibliothèque GPX</title>
  <style>
    :root {{ color-scheme: light; font-family: system-ui, sans-serif; color: #1f2933; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f3f5f7; }}
    main {{ width: min(960px, calc(100% - 32px)); margin: 40px auto; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(1.8rem, 4vw, 2.5rem); }}
    .subtitle {{ margin: 0 0 24px; color: #52606d; }}
    .toolbar {{ display: flex; gap: 16px; align-items: center; margin-bottom: 20px; }}
    .search {{ flex: 1; min-width: 0; padding: 12px 14px; border: 1px solid #cbd2d9;
      border-radius: 8px; font: inherit; background: white; }}
    .counts {{ color: #52606d; white-space: nowrap; }}
    .tour-card {{ margin: 14px 0; padding: 20px; background: white; border: 1px solid #d9e2ec;
      border-radius: 12px; box-shadow: 0 2px 5px #102a4310; }}
    .tour-header {{ display: flex; justify-content: space-between; align-items: start; gap: 16px; }}
    h2 {{ margin: 0 0 4px; font-size: 1.2rem; overflow-wrap: anywhere; }}
    a {{ color: #175cd3; }}
    .tour-id {{ font-size: .9rem; color: #52606d; }}
    .button {{ display: inline-block; padding: 9px 12px; border-radius: 7px; font-weight: 650;
      text-decoration: none; white-space: nowrap; }}
    .editor {{ color: white; background: #175cd3; }}
    .download {{ color: #175cd3; background: #eff8ff; }}
    .file-list {{ margin: 16px 0 0; padding: 0; list-style: none; }}
    .file-row {{ display: flex; justify-content: space-between; align-items: center; gap: 12px;
      padding: 10px 0; border-top: 1px solid #eef1f4; }}
    .file-info {{ min-width: 0; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    .file-name {{ overflow-wrap: anywhere; }}
    .role {{ padding: 2px 7px; border-radius: 999px; background: #f0f4f8; color: #52606d;
      font-size: .78rem; }}
    .import-hint {{ margin: 12px 0 0; color: #52606d; font-size: .88rem; }}
    .warning {{ color: #9a3412; background: #fff7ed; padding: 10px; border-radius: 6px; }}
    .empty {{ padding: 28px; text-align: center; background: white; border-radius: 12px;
      color: #52606d; }}
    .hidden {{ display: none; }}
    @media (max-width: 560px) {{
      main {{ margin: 24px auto; }}
      .toolbar, .tour-header {{ align-items: stretch; flex-direction: column; }}
      .counts {{ white-space: normal; }}
      .editor {{ text-align: center; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>Bibliothèque GPX</h1>
    <p class="subtitle">Parcours locaux — téléchargez une version pour l’ouvrir dans gpx.studio.</p>
    <div class="toolbar">
      <input id="search" class="search" type="search" placeholder="Rechercher un parcours ou un fichier…"
             aria-label="Rechercher un parcours ou un fichier">
      <span id="counts" class="counts">{tour_count} parcours · {file_count} fichiers GPX</span>
    </div>
    <section id="tour-list">{content}</section>
    <p id="no-results" class="empty {empty_class}">Aucun GPX dans la bibliothèque.</p>
    <p id="no-match" class="empty hidden">Aucun résultat pour cette recherche.</p>
  </main>
  <script>
    const search = document.querySelector("#search");
    const cards = [...document.querySelectorAll(".tour-card")];
    const noResults = document.querySelector("#no-results");
    const noMatch = document.querySelector("#no-match");
    search.addEventListener("input", () => {{
      const query = search.value.trim().toLocaleLowerCase();
      let visible = 0;
      for (const card of cards) {{
        const match = card.dataset.search.toLocaleLowerCase().includes(query);
        card.classList.toggle("hidden", !match);
        if (match) visible++;
      }}
      noResults.classList.toggle("hidden", cards.length > 0);
      noMatch.classList.toggle("hidden", cards.length === 0 || visible > 0);
    }});
  </script>
</body>
</html>
"""
    return page.encode("utf-8")


def _download_file(library: Path, tour_id: str, filename: str) -> Path | None:
    if not TOUR_ID_PATTERN.fullmatch(tour_id):
        return None
    if Path(filename).name != filename or Path(filename).suffix.lower() != ".gpx":
        return None

    tours_root = (library / "tours").resolve()
    candidate = library / "tours" / tour_id / filename
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(tours_root)
    except (FileNotFoundError, OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


def make_handler(library: Path) -> type[BaseHTTPRequestHandler]:
    library = library.resolve()

    class LibraryHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            request = urlsplit(self.path)
            if request.path == "/":
                body = _library_page(library)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(body)
                return

            parts = [unquote(part) for part in request.path.split("/")]
            if len(parts) == 4 and parts[1] == "files":
                file_path = _download_file(library, parts[2], parts[3])
                if file_path is not None:
                    body = file_path.read_bytes()
                    content_type = mimetypes.guess_type(file_path.name)[0] or "application/gpx+xml"
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header(
                        "Content-Disposition",
                        f"attachment; filename*=UTF-8''{quote(file_path.name)}",
                    )
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(body)
                    return

            self.send_error(404, "Fichier introuvable")

        def log_message(self, format: str, *args: object) -> None:
            super().log_message(format, *args)

    return LibraryHandler


def serve(library: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(library))
    print(f"Bibliothèque GPX : http://{host}:{port} (Ctrl+C pour arrêter)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur.")
    finally:
        server.server_close()

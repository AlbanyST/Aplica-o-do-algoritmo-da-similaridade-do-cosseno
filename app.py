from __future__ import annotations

import csv
import json
import math
import os
import re
import tempfile
from collections import Counter, defaultdict
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "raw" / "games.csv"
CACHE_PATH = ROOT / "data" / "processed" / "games.json"
CATALOG_VERSION = 1
WEB_DIR = ROOT / "web"
PORT = int(os.environ.get("PORT", "8000"))


def parse_number(value: str) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


def parse_game(row: list[str]) -> dict | None:
    if len(row) < 38:
        return None

    app_id, name = row[0].strip(), row[1].strip()
    tags = list(dict.fromkeys(tag.strip() for tag in row[37].split(",") if tag.strip()))
    if not app_id.isdigit() or not name or not tags:
        return None

    image = row[13].strip()
    if not image:
        image = (
            "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/"
            f"{app_id}/header.jpg"
        )

    positive, negative = parse_number(row[23]), parse_number(row[24])
    total_reviews = positive + negative
    return {
        "id": app_id,
        "name": name,
        "price": parse_number(row[6]),
        "tags": tags,
        "image": image,
        "positive": int(positive),
        "negative": int(negative),
        "rating": round(positive / total_reviews * 100) if total_reviews else None,
    }


def build_tag_index(games: list[dict]) -> dict[str, list[int]]:
    tag_index: dict[str, list[int]] = defaultdict(list)
    for game_index, game in enumerate(games):
        for tag in game["tags"]:
            tag_index[tag].append(game_index)
    return dict(tag_index)


def write_cache(path: Path, games: list[dict], source_stat: os.stat_result) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as cache_file:
            temporary_path = Path(cache_file.name)
            json.dump(
                {
                    "version": CATALOG_VERSION,
                    "source_size": source_stat.st_size,
                    "source_mtime_ns": source_stat.st_mtime_ns,
                    "games": games,
                },
                cache_file,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def load_games(
    path: Path, cache_path: Path = CACHE_PATH
) -> tuple[list[dict], dict[str, list[int]], bool]:
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo de dados não encontrado: {path}")

    source_stat = path.stat()
    if cache_path.is_file():
        try:
            with cache_path.open("r", encoding="utf-8") as cache_file:
                cached = json.load(cache_file)
            if (
                isinstance(cached, dict)
                and cached.get("version") == CATALOG_VERSION
                and cached.get("source_size") == source_stat.st_size
                and cached.get("source_mtime_ns") == source_stat.st_mtime_ns
                and isinstance(cached.get("games"), list)
                and cached["games"]
                and all(
                    isinstance(game, dict)
                    and isinstance(game.get("id"), str)
                    and isinstance(game.get("name"), str)
                    and isinstance(game.get("tags"), list)
                    and game["tags"]
                    for game in cached["games"]
                )
            ):
                games = cached["games"]
                return games, build_tag_index(games), True
        except (json.JSONDecodeError, UnicodeDecodeError):
            print("Cache tratado inválido; reconstruindo a partir do CSV original.")

    games: list[dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        rows = iter(csv.reader(source))
        header = next(rows, None)
        if not header or "AppID" not in header or "Name" not in header:
            raise ValueError("O CSV não possui um cabeçalho válido de jogos da Steam.")

        for row in rows:
            game = parse_game(row)
            if game is None:
                continue
            games.append(game)

    if not games:
        raise ValueError("Nenhum jogo com nome e tags válidas foi encontrado no CSV.")
    write_cache(cache_path, games, source_stat)
    return games, build_tag_index(games), False


def recommend(
    selected_index: int,
    games: list[dict],
    tag_index: dict[str, list[int]],
    limit: int = 12,
) -> list[dict]:
    selected = games[selected_index]
    shared_counts: Counter[int] = Counter()
    for tag in selected["tags"]:
        for candidate_index in tag_index[tag]:
            if candidate_index != selected_index:
                shared_counts[candidate_index] += 1

    selected_norm = math.sqrt(len(selected["tags"]))
    ranked = []
    for candidate_index, shared_count in shared_counts.items():
        candidate = games[candidate_index]
        score = shared_count / (selected_norm * math.sqrt(len(candidate["tags"])))
        ranked.append((score, shared_count, candidate_index))

    ranked.sort(key=lambda result: (result[0], result[1]), reverse=True)
    recommendations = []
    for score, shared_count, candidate_index in ranked[:limit]:
        candidate = games[candidate_index].copy()
        candidate["similarity"] = round(score * 100, 1)
        candidate["sharedTags"] = [
            tag for tag in selected["tags"] if tag in games[candidate_index]["tags"]
        ]
        candidate["sharedCount"] = shared_count
        recommendations.append(candidate)
    return recommendations


GAMES: list[dict] = []
TAG_INDEX: dict[str, list[int]] = {}
BY_ID: dict[str, int] = {}
SEARCH_NAMES: list[str] = []


class RecommenderHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/api/stats":
            self.send_json({"games": len(GAMES), "tags": len(TAG_INDEX)})
        elif parsed.path == "/api/search":
            self.search_games(params.get("q", [""])[0])
        elif parsed.path == "/api/recommend":
            self.recommend_games(params.get("id", [""])[0])
        else:
            super().do_GET()

    def search_games(self, query: str) -> None:
        query = re.sub(r"\s+", " ", query.strip().casefold())
        if len(query) < 2:
            self.send_json({"results": []})
            return

        starts, contains = [], []
        for index, normalized_name in enumerate(SEARCH_NAMES):
            if normalized_name.startswith(query):
                starts.append(index)
            elif query in normalized_name:
                contains.append(index)
        matches = (starts + contains)[:10]
        self.send_json({"results": [GAMES[index] for index in matches]})

    def recommend_games(self, app_id: str) -> None:
        selected_index = BY_ID.get(app_id)
        if selected_index is None:
            self.send_json({"error": "Jogo não encontrado na base de dados."}, status=404)
            return

        self.send_json(
            {
                "selected": GAMES[selected_index],
                "recommendations": recommend(selected_index, GAMES, TAG_INDEX),
            }
        )

    def send_json(self, payload: dict, status: int = 200) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}")


if __name__ == "__main__":
    GAMES, TAG_INDEX, cache_hit = load_games(DATA_PATH)
    BY_ID = {game["id"]: index for index, game in enumerate(GAMES)}
    SEARCH_NAMES = [re.sub(r"\s+", " ", game["name"].casefold()) for game in GAMES]
    server = ThreadingHTTPServer(("127.0.0.1", PORT), RecommenderHandler)
    action = "Cache tratado reutilizado" if cache_hit else "CSV tratado e cache criado"
    print(f"{action}: {len(GAMES):,} jogos e {len(TAG_INDEX):,} tags.".replace(",", "."))
    print(f"Abra http://127.0.0.1:{PORT} no navegador. Use Ctrl+C para encerrar.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()

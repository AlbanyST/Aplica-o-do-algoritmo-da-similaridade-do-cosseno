import csv
import json
import tempfile
import unittest
from pathlib import Path

from app import load_games


class CatalogCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.raw_path = self.root / "games.csv"
        self.cache_path = self.root / "processed" / "games.json"

    def write_game(self, app_id, name, tags):
        header = ["AppID", "Name"] + [f"Column {index}" for index in range(2, 37)]
        row = [""] * 38
        row[0] = app_id
        row[1] = name
        row[6] = "9.99"
        row[23] = "8"
        row[24] = "2"
        row[37] = tags
        with self.raw_path.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(header)
            writer.writerow(row)

    def test_creates_and_reuses_clean_catalog(self):
        self.write_game("101", "Test Game", "Action,Puzzle,Action")

        games, tag_index, cache_hit = load_games(self.raw_path, self.cache_path)

        self.assertFalse(cache_hit)
        self.assertEqual(games[0]["tags"], ["Action", "Puzzle"])
        self.assertEqual(games[0]["rating"], 80)
        self.assertEqual(tag_index["Action"], [0])
        self.assertTrue(self.cache_path.is_file())

        cached_games, cached_index, cache_hit = load_games(self.raw_path, self.cache_path)

        self.assertTrue(cache_hit)
        self.assertEqual(cached_games, games)
        self.assertEqual(cached_index, tag_index)

    def test_rebuilds_cache_when_raw_data_changes(self):
        self.write_game("101", "Original Game", "Action")
        load_games(self.raw_path, self.cache_path)
        self.write_game("202", "Updated Game", "Indie")

        games, tag_index, cache_hit = load_games(self.raw_path, self.cache_path)

        self.assertFalse(cache_hit)
        self.assertEqual(games[0]["id"], "202")
        self.assertEqual(tag_index["Indie"], [0])

    def test_rebuilds_invalid_json_cache(self):
        self.write_game("101", "Test Game", "Action")
        self.cache_path.parent.mkdir(parents=True)
        self.cache_path.write_text(json.dumps(["invalid"]), encoding="utf-8")

        games, _, cache_hit = load_games(self.raw_path, self.cache_path)

        self.assertFalse(cache_hit)
        self.assertEqual(games[0]["id"], "101")


if __name__ == "__main__":
    unittest.main()

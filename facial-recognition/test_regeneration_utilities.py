import importlib
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np


def _load_utility(name):
    # These scripts configure optional file logging at import. Keep tests
    # isolated.
    with patch("logging.FileHandler", return_value=logging.NullHandler()):
        return importlib.import_module(name)


regenerate_embeddings = _load_utility("regenerate_embeddings")
regenerate_scoped = _load_utility("regenerate_scoped")


class RegenerationUtilityTests(unittest.TestCase):
    def test_image_discovery_is_sorted_and_ignores_non_images(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "b.JPG").touch()
            (root / "a.png").touch()
            (root / "notes.txt").touch()

            self.assertEqual(
                [path.name for path in regenerate_embeddings.get_images(root)],
                ["a.png", "b.JPG"],
            )
            self.assertEqual(
                regenerate_embeddings.get_images(root / "missing"), []
            )

    def test_backup_preserves_existing_cache_and_missing_cache_is_a_noop(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "embeddings"
            cache.mkdir()
            (cache / "known.npy").write_bytes(b"fixture")
            with patch.object(regenerate_embeddings, "CACHE_DIR", cache):
                backup = regenerate_embeddings.backup_embeddings()
            self.assertEqual((backup / "known.npy").read_bytes(), b"fixture")
            self.assertEqual((cache / "known.npy").read_bytes(), b"fixture")

            with patch.object(
                regenerate_embeddings, "CACHE_DIR", root / "absent"
            ):
                self.assertIsNone(regenerate_embeddings.backup_embeddings())

    def test_identity_regeneration_writes_only_to_requested_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identity = root / "dataset" / "person"
            identity.mkdir(parents=True)
            for index in range(6):
                (identity / f"{index}.jpg").touch()
            output = root / "cache"
            stats = regenerate_embeddings.RegenerationStats()
            with patch.object(
                regenerate_embeddings,
                "safe_extract_embedding",
                side_effect=[np.array([1.0, 0.0], dtype=np.float32)] * 6,
            ):
                self.assertTrue(
                    regenerate_embeddings.regenerate_identity_embeddings(
                        identity, output, stats
                    )
                )
            self.assertEqual(len(list((output / "person").glob("*.npy"))), 6)
            self.assertEqual(
                {path.name for path in identity.iterdir()},
                {f"{index}.jpg" for index in range(6)},
            )
            np.testing.assert_array_equal(
                np.load(output / "person" / "0.npy"), [1.0, 0.0]
            )

    def test_insufficient_successes_remove_partial_identity_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identity = root / "dataset" / "person"
            identity.mkdir(parents=True)
            for index in range(6):
                (identity / f"{index}.jpg").touch()
            output = root / "cache"
            stats = regenerate_embeddings.RegenerationStats()
            with patch.object(
                regenerate_embeddings,
                "safe_extract_embedding",
                side_effect=[np.array([1.0]), None, None, None, None, None],
            ):
                self.assertFalse(
                    regenerate_embeddings.regenerate_identity_embeddings(
                        identity, output, stats
                    )
                )
            self.assertFalse((output / "person").exists())
            self.assertEqual(len(stats.insufficient_enrollments), 1)
            self.assertEqual(len(list(identity.iterdir())), 6)

    def test_scoped_lookup_uses_temp_fixture_and_reports_missing_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            identity = Path(temporary) / "person"
            identity.mkdir()
            expected = identity / "Image01.JPEG"
            expected.touch()
            self.assertEqual(
                regenerate_scoped.find_image_file(identity, "image01"),
                expected,
            )
            with self.assertRaises(FileNotFoundError):
                regenerate_scoped.find_image_file(identity, "missing")
            with self.assertRaises(FileNotFoundError):
                regenerate_scoped.find_image_file(
                    identity / "absent", "image01"
                )


if __name__ == "__main__":
    unittest.main()

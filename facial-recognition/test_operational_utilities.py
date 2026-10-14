"""Deterministic safety tests for the retained dataset maintenance utilities."""

import builtins
import importlib
import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np


def _load_utility(name):
    # These utilities configure optional file logging at import time.
    with patch("logging.FileHandler", return_value=logging.NullHandler()):
        return importlib.import_module(name)


audit_dataset = _load_utility("audit_dataset")
regenerate_embeddings = _load_utility("regenerate_embeddings")
regenerate_scoped = _load_utility("regenerate_scoped")


class DatasetAuditTests(unittest.TestCase):
    def test_image_discovery_recurses_sorts_and_filters_extensions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "identity"
            nested.mkdir()
            (nested / "z.JPG").touch()
            (root / "a.png").touch()
            (root / "notes.txt").touch()

            self.assertEqual(
                [path.name for path in audit_dataset.get_images_in_directory(root)],
                ["a.png", "z.JPG"],
            )
            self.assertEqual(audit_dataset.get_images_in_directory(root / "missing"), [])

    def test_single_image_reports_single_no_face_and_multi_face_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "train" / "person" / "frame.jpg"
            image.parent.mkdir(parents=True)
            image.touch()
            with patch.object(audit_dataset, "DATASET_ROOT", root):
                with patch.object(audit_dataset, "get_face_details", return_value=[{"area": 100}]) as detect:
                    single = audit_dataset.audit_single_image(image)
                detect.assert_called_once_with(str(image), "retinaface")
                self.assertEqual(single["identity"], "person")
                self.assertFalse(single["is_multi_face"])
                self.assertFalse(single["has_detection_failure"])

                with patch.object(audit_dataset, "get_face_details", return_value=[]):
                    no_face = audit_dataset.audit_single_image(image)
                self.assertTrue(no_face["has_detection_failure"])

                with patch.object(
                    audit_dataset,
                    "get_face_details",
                    return_value=[{"area": 100}, {"area": 90}],
                ):
                    ambiguous = audit_dataset.audit_single_image(image)
                self.assertEqual(ambiguous["area_ratio"], 0.9)
                self.assertTrue(ambiguous["is_ambiguous"])

                with patch.object(
                    audit_dataset,
                    "get_face_details",
                    return_value=[{"area": 100}, {"area": 40}],
                ):
                    clear = audit_dataset.audit_single_image(image)
                self.assertFalse(clear["is_ambiguous"])

                with patch.object(
                    audit_dataset,
                    "get_face_details",
                    return_value=[{"area": 0}, {"area": 0}],
                ):
                    zero_area = audit_dataset.audit_single_image(image)
                self.assertEqual(zero_area["area_ratio"], 0)
                self.assertFalse(zero_area["is_ambiguous"])

    def test_single_image_detection_exception_is_reported_safely(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "train" / "person" / "bad.jpg"
            image.parent.mkdir(parents=True)
            image.touch()
            with patch.object(audit_dataset, "DATASET_ROOT", root), patch.object(
                audit_dataset, "get_face_details", side_effect=RuntimeError("detector failed")
            ):
                result = audit_dataset.audit_single_image(image)

            self.assertEqual(result["num_faces"], -1)
            self.assertEqual(result["identity"], "error")
            self.assertIn("detector failed", result["error"])

    def test_parallel_audit_handles_missing_empty_and_worker_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(audit_dataset.audit_dataset_parallel(root / "missing"), [])
            empty = root / "empty"
            empty.mkdir()
            self.assertEqual(audit_dataset.audit_dataset_parallel(empty), [])

            images = root / "images"
            images.mkdir()
            (images / "one.jpg").touch()
            (images / "two.jpg").touch()
            with patch.object(audit_dataset, "audit_single_image", side_effect=[{"name": "one"}, RuntimeError("worker")]):
                results = audit_dataset.audit_dataset_parallel(images, max_workers=1)
            self.assertEqual(results, [{"name": "one"}])

    def test_parallel_audit_emits_progress_at_fifty_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index in range(50):
                (root / f"{index:02}.jpg").touch()
            with patch.object(audit_dataset, "audit_single_image", return_value={"ok": True}), patch.object(
                audit_dataset.logger, "info"
            ) as info:
                results = audit_dataset.audit_dataset_parallel(root, max_workers=2)
            self.assertEqual(len(results), 50)
            self.assertTrue(
                any(call.args == ("Processed 50/50 images...",) for call in info.call_args_list)
            )

    def test_statistics_count_failures_and_rank_problem_identities(self):
        self.assertEqual(audit_dataset.generate_audit_statistics([]), {})
        results = [
            {"identity": "clean", "num_faces": 1},
            {"identity": "clean", "num_faces": 1},
            {"identity": "clean", "num_faces": 1},
            {"identity": "problem", "num_faces": 2, "is_multi_face": True, "is_ambiguous": True},
            {"identity": "problem", "num_faces": 0, "has_detection_failure": True},
            {"identity": "problem", "num_faces": 1},
            {"identity": "small", "num_faces": 0, "has_detection_failure": True},
        ]
        report = audit_dataset.generate_audit_statistics(results)
        self.assertEqual(report["summary"]["successful_single_face"], 4)
        self.assertEqual(report["summary"]["ambiguous_multi_face"], 1)
        self.assertEqual(report["per_identity_stats"]["problem"]["detection_failures"], 1)
        self.assertEqual([entry["identity"] for entry in report["problematic_identities"]], ["problem"])

    def test_main_writes_valid_report_for_empty_dataset_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            original_open = builtins.open

            def isolated_open(filename, mode="r", *args, **kwargs):
                return original_open(Path(temporary) / Path(filename).name, mode, *args, **kwargs)

            with patch.object(audit_dataset, "TRAIN_DIR", Path(temporary) / "missing-train"), patch.object(
                audit_dataset, "VAL_DIR", Path(temporary) / "missing-val"
            ), patch("builtins.open", side_effect=isolated_open):
                report_name = audit_dataset.main()

            report_path = Path(temporary) / Path(report_name).name
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["statistics"], {})
            self.assertEqual(report["all_results"], [])
            self.assertEqual(report["multi_face_images"], [])


class EmbeddingRegenerationTests(unittest.TestCase):
    @staticmethod
    def _fixture(root):
        dataset = root / "dataset"
        identity = dataset / "person"
        identity.mkdir(parents=True)
        for index in range(6):
            (identity / f"{index}.jpg").write_bytes(f"fixture-{index}".encode())
        return dataset, identity

    def test_safe_extract_records_success_and_invalid_or_missing_embeddings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset, identity = self._fixture(root)
            stats = regenerate_embeddings.RegenerationStats()
            with patch.object(regenerate_embeddings, "DATASET_ROOT", dataset), patch.object(
                regenerate_embeddings, "extract_primary_face_embedding", return_value=np.array([1, 2])
            ):
                valid = regenerate_embeddings.safe_extract_embedding(identity / "0.jpg", "person", stats)
            np.testing.assert_array_equal(valid, np.array([1, 2], dtype=np.float32))
            self.assertEqual(stats.successful, 1)

            for invalid in (None, np.array([]), np.array([[1.0]]), np.array([np.nan])):
                with self.subTest(invalid=invalid):
                    with patch.object(regenerate_embeddings, "DATASET_ROOT", dataset), patch.object(
                        regenerate_embeddings, "extract_primary_face_embedding", return_value=invalid
                    ), patch.object(regenerate_embeddings, "get_face_details", return_value=[]):
                        self.assertIsNone(
                            regenerate_embeddings.safe_extract_embedding(identity / "1.jpg", "person", stats)
                        )
            self.assertEqual(stats.failed, 4)
            self.assertEqual(len(stats.other_failures), 4)

    def test_model_exception_is_recorded_even_if_diagnostic_call_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset, identity = self._fixture(root)
            stats = regenerate_embeddings.RegenerationStats()
            with patch.object(regenerate_embeddings, "DATASET_ROOT", dataset), patch.object(
                regenerate_embeddings, "extract_primary_face_embedding", side_effect=RuntimeError("model failed")
            ), patch.object(regenerate_embeddings, "get_face_details", side_effect=RuntimeError("diagnostic failed")):
                self.assertIsNone(regenerate_embeddings.safe_extract_embedding(identity / "0.jpg", "person", stats))
            self.assertEqual(stats.processed, 1)
            self.assertEqual(stats.failed, 1)

    def test_insufficient_regeneration_preserves_previous_cache_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, identity = self._fixture(root)
            cache = root / "cache"
            previous = cache / "person" / "previous.npy"
            previous.parent.mkdir(parents=True)
            previous.write_bytes(b"existing-cache")
            stats = regenerate_embeddings.RegenerationStats()
            with patch.object(regenerate_embeddings, "DATASET_ROOT", root / "dataset"), patch.object(
                regenerate_embeddings,
                "safe_extract_embedding",
                side_effect=[np.array([1.0]), None, None, None, None, None],
            ):
                result = regenerate_embeddings.regenerate_identity_embeddings(identity, cache, stats)

            self.assertFalse(result)
            self.assertEqual(previous.read_bytes(), b"existing-cache")
            self.assertEqual(list((cache / "person").iterdir()), [previous])
            self.assertEqual(list(cache.glob(".*.staging-*")), [])
            self.assertEqual(len(stats.insufficient_enrollments), 1)

    def test_successful_regeneration_replaces_cache_only_after_complete_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, identity = self._fixture(root)
            cache = root / "cache"
            old = cache / "person" / "old.npy"
            old.parent.mkdir(parents=True)
            np.save(old, np.array([-1.0]))
            stats = regenerate_embeddings.RegenerationStats()
            vector = np.array([0.25, 0.75], dtype=np.float32)
            with patch.object(regenerate_embeddings, "DATASET_ROOT", root / "dataset"), patch.object(
                regenerate_embeddings, "safe_extract_embedding", return_value=vector
            ):
                self.assertTrue(regenerate_embeddings.regenerate_identity_embeddings(identity, cache, stats))

            self.assertFalse(old.exists())
            self.assertEqual(len(list((cache / "person").glob("*.npy"))), 6)
            np.testing.assert_array_equal(np.load(cache / "person" / "0.npy"), vector)
            self.assertEqual(list(cache.glob(".*.staging-*")), [])
            self.assertEqual(list(cache.glob(".*.backup-*")), [])

    def test_failed_embedding_write_leaves_existing_cache_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, identity = self._fixture(root)
            cache = root / "cache"
            previous = cache / "person" / "old.npy"
            previous.parent.mkdir(parents=True)
            previous.write_bytes(b"existing-cache")
            stats = regenerate_embeddings.RegenerationStats()
            with patch.object(regenerate_embeddings, "DATASET_ROOT", root / "dataset"), patch.object(
                regenerate_embeddings, "safe_extract_embedding", return_value=np.array([1.0])
            ), patch.object(regenerate_embeddings.np, "save", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    regenerate_embeddings.regenerate_identity_embeddings(identity, cache, stats)
            self.assertEqual(previous.read_bytes(), b"existing-cache")
            self.assertEqual(list(cache.glob(".*.staging-*")), [])

    def test_regenerate_all_skips_missing_split_and_continues_after_identity_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = root / "train"
            dataset.mkdir()
            (dataset / "broken").mkdir()
            (dataset / "healthy").mkdir()
            cache = root / "cache"
            stats = regenerate_embeddings.RegenerationStats()
            with patch.object(regenerate_embeddings, "regenerate_identity_embeddings", side_effect=[RuntimeError("bad"), True]):
                regenerate_embeddings.regenerate_all_embeddings(dataset, cache, stats)
            self.assertTrue(cache.is_dir())
            regenerate_embeddings.regenerate_all_embeddings(root / "missing", cache, stats)

    def test_main_restores_original_cache_when_bulk_regeneration_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "embeddings"
            cache.mkdir()
            original = cache / "old.npy"
            original.write_bytes(b"original-cache")
            with patch.object(regenerate_embeddings, "CACHE_DIR", cache), patch.object(
                regenerate_embeddings, "TRAIN_CACHE", cache / "train"
            ), patch.object(regenerate_embeddings, "VAL_CACHE", cache / "val"), patch.object(
                regenerate_embeddings, "TRAIN_DIR", root / "train"
            ), patch.object(regenerate_embeddings, "VAL_DIR", root / "val"), patch.object(
                regenerate_embeddings, "regenerate_all_embeddings", side_effect=RuntimeError("split failed")
            ):
                with self.assertRaisesRegex(RuntimeError, "split failed"):
                    regenerate_embeddings.main()
            self.assertEqual(original.read_bytes(), b"original-cache")
            self.assertFalse((cache / "train").exists())
            self.assertEqual(len(list(root.glob("embeddings_backup_*/old.npy"))), 1)

    def test_main_writes_json_report_after_both_splits_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "embeddings"
            cache.mkdir()
            (cache / "old.npy").write_bytes(b"old-cache")
            original_open = builtins.open

            def regenerate_split(dataset_dir, cache_dir, stats):
                stats.processed += 1
                stats.successful += 1
                cache_dir.mkdir(parents=True, exist_ok=True)
                (cache_dir / "fixture.npy").write_bytes(b"new-cache")

            def isolated_open(filename, mode="r", *args, **kwargs):
                if Path(filename).name.startswith("embedding_regeneration_report_"):
                    filename = root / Path(filename).name
                return original_open(filename, mode, *args, **kwargs)

            with patch.object(regenerate_embeddings, "CACHE_DIR", cache), patch.object(
                regenerate_embeddings, "TRAIN_CACHE", cache / "train"
            ), patch.object(regenerate_embeddings, "VAL_CACHE", cache / "val"), patch.object(
                regenerate_embeddings, "TRAIN_DIR", root / "train"
            ), patch.object(regenerate_embeddings, "VAL_DIR", root / "val"), patch.object(
                regenerate_embeddings, "regenerate_all_embeddings", side_effect=regenerate_split
            ), patch("builtins.open", side_effect=isolated_open):
                regenerate_embeddings.main()

            report_path = next(root.glob("embedding_regeneration_report_*.json"))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["total_processed"], 2)
            self.assertEqual(report["summary"]["successful"], 2)
            self.assertEqual((cache / "train" / "fixture.npy").read_bytes(), b"new-cache")
            self.assertEqual((cache / "val" / "fixture.npy").read_bytes(), b"new-cache")
            self.assertEqual(len(list(root.glob("embeddings_backup_*/old.npy"))), 1)

    def test_statistics_report_contains_counts_and_categorized_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset, identity = self._fixture(root)
            stats = regenerate_embeddings.RegenerationStats()
            with patch.object(regenerate_embeddings, "DATASET_ROOT", dataset):
                stats.add_success(identity / "0.jpg", "person")
                stats.add_failure(
                    identity / "1.jpg", "person", regenerate_embeddings.FaceExtractionError("No faces detected")
                )
                stats.add_failure(
                    identity / "2.jpg", "person", regenerate_embeddings.FaceExtractionError("Ambiguous multi-face")
                )
                stats.add_failure(identity / "3.jpg", "person", RuntimeError("unknown"))
            report = stats.generate_report()
            self.assertEqual(report["summary"]["total_processed"], 4)
            self.assertEqual(report["summary"]["success_rate"], 0.25)
            self.assertEqual(report["failure_breakdown"]["detection_failures"], 1)
            self.assertEqual(report["failure_breakdown"]["ambiguous_multi_face"], 1)
            self.assertEqual(report["failure_breakdown"]["other_failures"], 1)


class ScopedRegenerationTests(unittest.TestCase):
    def test_scoped_regeneration_processes_only_selected_files_and_records_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identity = root / "train" / "person"
            identity.mkdir(parents=True)
            selected = identity / "selected.jpg"
            selected.touch()
            (identity / "not-selected.jpg").touch()
            cache = root / "cache" / "train"
            with patch.object(regenerate_scoped, "ORIGINAL_FILES", {"person": ["selected", "missing"]}), patch.object(
                regenerate_scoped, "TRAIN_DIR", root / "train"
            ), patch.object(regenerate_scoped, "TRAIN_CACHE", cache), patch.object(
                regenerate_scoped, "extract_primary_face_embedding", side_effect=[np.array([3.0, 4.0]), RuntimeError("no such file")]
            ), patch.object(regenerate_scoped, "get_face_details", return_value=[]):
                stats = regenerate_scoped.regenerate_scoped_embeddings()

            output = cache / "person_selected.npy"
            np.testing.assert_array_equal(np.load(output), np.array([3.0, 4.0], dtype=np.float32))
            self.assertEqual(stats.successful, 1)
            self.assertEqual(stats.failed, 1)
            self.assertEqual(len(stats.file_not_found), 1)
            self.assertTrue(selected.exists())
            self.assertTrue((identity / "not-selected.jpg").exists())
            self.assertFalse((cache / "person_not-selected.npy").exists())

    def test_scoped_invalid_embedding_preserves_existing_cache_and_uses_fresh_error_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identity = root / "train" / "person"
            identity.mkdir(parents=True)
            image = identity / "selected.jpg"
            image.touch()
            cache = root / "cache" / "train"
            cache.mkdir(parents=True)
            target = cache / "person_selected.npy"
            target.write_bytes(b"previous-cache")
            with patch.object(regenerate_scoped, "ORIGINAL_FILES", {"person": ["selected"]}), patch.object(
                regenerate_scoped, "TRAIN_DIR", root / "train"
            ), patch.object(regenerate_scoped, "TRAIN_CACHE", cache), patch.object(
                regenerate_scoped, "extract_primary_face_embedding", return_value=np.array([np.inf])
            ), patch.object(regenerate_scoped, "get_face_details", side_effect=RuntimeError("diagnostic failure")):
                stats = regenerate_scoped.regenerate_scoped_embeddings()
            self.assertEqual(target.read_bytes(), b"previous-cache")
            self.assertEqual(stats.failed, 1)
            self.assertEqual(len(list(cache.glob("*.tmp"))), 0)

    def test_scoped_write_failure_preserves_existing_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identity = root / "train" / "person"
            identity.mkdir(parents=True)
            (identity / "selected.jpg").touch()
            cache = root / "cache" / "train"
            cache.mkdir(parents=True)
            target = cache / "person_selected.npy"
            target.write_bytes(b"previous-cache")
            with patch.object(regenerate_scoped, "ORIGINAL_FILES", {"person": ["selected"]}), patch.object(
                regenerate_scoped, "TRAIN_DIR", root / "train"
            ), patch.object(regenerate_scoped, "TRAIN_CACHE", cache), patch.object(
                regenerate_scoped, "extract_primary_face_embedding", return_value=np.array([1.0])
            ), patch.object(regenerate_scoped.np, "save", side_effect=OSError("write failed")), patch.object(
                regenerate_scoped, "get_face_details", return_value=[]
            ):
                stats = regenerate_scoped.regenerate_scoped_embeddings()
            self.assertEqual(target.read_bytes(), b"previous-cache")
            self.assertEqual(stats.failed, 1)
            self.assertEqual(list(cache.glob("*.tmp")), [])

    def test_scoped_statistics_classify_errors_and_report_expected_file_count(self):
        stats = regenerate_scoped.ScopedRegenerationStats()
        stats.add_failure("person", "missing", None, FileNotFoundError("missing"))
        stats.add_failure("person", "detection", None, regenerate_scoped.FaceExtractionError("No faces detected"))
        stats.add_failure("person", "ambiguous", None, regenerate_scoped.FaceExtractionError("Ambiguous multi-face"))
        stats.add_failure("person", "other-face", None, regenerate_scoped.FaceExtractionError("model error"))
        stats.add_failure("person", "other", None, RuntimeError("unexpected"))
        report = stats.generate_report()
        self.assertEqual(report["summary"]["failed"], 5)
        self.assertEqual(report["summary"]["success_rate"], 0)
        self.assertEqual(report["failure_breakdown"]["file_not_found"], 1)
        self.assertEqual(report["failure_breakdown"]["detection_failures"], 1)
        self.assertEqual(report["failure_breakdown"]["ambiguous_multi_face"], 1)
        self.assertEqual(report["failure_breakdown"]["other_failures"], 2)
        self.assertEqual(report["summary"]["expected_files"], sum(map(len, regenerate_scoped.ORIGINAL_FILES.values())))

    def test_scoped_main_writes_parseable_json_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            original_open = builtins.open
            stats = regenerate_scoped.ScopedRegenerationStats()
            stats.processed = 1
            stats.successful = 1

            def isolated_open(filename, mode="r", *args, **kwargs):
                return original_open(Path(temporary) / Path(filename).name, mode, *args, **kwargs)

            with patch.object(regenerate_scoped, "regenerate_scoped_embeddings", return_value=stats), patch(
                "builtins.open", side_effect=isolated_open
            ):
                report_name = regenerate_scoped.main()
            report_path = Path(temporary) / report_name
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["successful"], 1)
            self.assertEqual(report["summary"]["total_processed"], 1)


if __name__ == "__main__":
    unittest.main()

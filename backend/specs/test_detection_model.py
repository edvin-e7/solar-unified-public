"""Adversarial matrix for the detection layer.

Three test classes:
- TestGeometry          — pure math, always runs
- TestErrorPaths        — image-decode + missing-weights, always runs
- TestStrategySelection — DETECTION_BACKEND env routing
- TestGeminiFallback    — Gemini path with mocked client
- TestInferenceWithWeights — ML inference, only runs when ONNX weights present

Run: python3 backend/specs/test_detection_model.py
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import (
    detection_embed,
    detection_gemini,
    detection_geom,
    detection_label_log,
    detection_ml,
    detection_model,
    detection_moondream,
)


def _have(mod_name: str) -> bool:
    try:
        __import__(mod_name)
        return True
    except ImportError:
        return False


HAVE_NUMPY = _have("numpy")
HAVE_PIL = _have("PIL")
HAVE_ORT = _have("onnxruntime")
HAVE_MODEL = detection_ml.MODEL_PATH.exists()
CAN_INFER = HAVE_NUMPY and HAVE_PIL and HAVE_ORT and HAVE_MODEL


def _png_bytes(width: int, height: int, fill: tuple[int, int, int] = (0, 0, 0)) -> bytes:
    from PIL import Image  # type: ignore[import-not-found]

    img = Image.new("RGB", (width, height), fill)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestGeometry(unittest.TestCase):
    """Pure math — always runs."""

    def test_zero_pixels_is_zero_m2(self) -> None:
        self.assertEqual(
            detection_geom.mask_pixels_to_m2(
                0, lat=60.0, zoom=20, tile_size_px=512, model_size_px=640
            ),
            0.0,
        )

    def test_negative_pixels_is_zero(self) -> None:
        self.assertEqual(
            detection_geom.mask_pixels_to_m2(
                -5, lat=60.0, zoom=20, tile_size_px=512, model_size_px=640
            ),
            0.0,
        )

    def test_known_tile_area_at_uppsala(self) -> None:
        area = detection_geom.mask_pixels_to_m2(
            640 * 640, lat=60.0, zoom=20, tile_size_px=512, model_size_px=640
        )
        self.assertAlmostEqual(area, 1462.0, delta=10.0)

    def test_lat_clamped_to_mercator_range(self) -> None:
        a = detection_geom.mask_pixels_to_m2(
            1000, lat=100.0, zoom=20, tile_size_px=512, model_size_px=640
        )
        b = detection_geom.mask_pixels_to_m2(
            1000, lat=85.0, zoom=20, tile_size_px=512, model_size_px=640
        )
        self.assertAlmostEqual(a, b, delta=1e-9)

    def test_invalid_sizes_raise(self) -> None:
        with self.assertRaises(ValueError):
            detection_geom.mask_pixels_to_m2(
                100, lat=60.0, zoom=20, tile_size_px=0, model_size_px=640
            )
        with self.assertRaises(ValueError):
            detection_geom.mask_pixels_to_m2(
                100, lat=60.0, zoom=20, tile_size_px=512, model_size_px=0
            )


class TestErrorPaths(unittest.TestCase):
    """ML path error handling — always runs (forces DETECTION_BACKEND=ml)."""

    def setUp(self) -> None:
        self._env = mock.patch.dict(os.environ, {"DETECTION_BACKEND": "ml"})
        self._env.start()
        detection_ml.reset_session_for_tests()

    def tearDown(self) -> None:
        self._env.stop()

    @unittest.skipUnless(HAVE_PIL and HAVE_NUMPY and HAVE_MODEL, "weights + Pillow + numpy required")
    def test_empty_bytes_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            asyncio.run(detection_model.detect(b"", lat=60.0))

    @unittest.skipUnless(HAVE_PIL and HAVE_NUMPY and HAVE_MODEL, "weights + Pillow + numpy required")
    def test_non_image_bytes_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            asyncio.run(detection_model.detect(b"not an image", lat=60.0))

    @unittest.skipUnless(HAVE_PIL and HAVE_NUMPY and HAVE_MODEL, "weights + Pillow + numpy required")
    def test_truncated_jpeg_raises(self) -> None:
        bogus = b"\xff\xd8\xff\xe0" + b"\x00" * 60
        with self.assertRaises(RuntimeError):
            asyncio.run(detection_model.detect(bogus, lat=60.0))

    def test_missing_model_file_raises(self) -> None:
        original = detection_ml.MODEL_PATH
        detection_ml.MODEL_PATH = Path("/tmp/__definitely_missing_solar.onnx")
        try:
            detection_ml.reset_session_for_tests()
            with self.assertRaises(RuntimeError) as ctx:
                detection_ml._get_session()
            self.assertIn("missing", str(ctx.exception).lower())
        finally:
            detection_ml.MODEL_PATH = original
            detection_ml.reset_session_for_tests()


class TestStrategySelection(unittest.TestCase):
    """Dispatcher routing logic — backend selection by env + weights."""

    def test_explicit_ml(self) -> None:
        with mock.patch.dict(os.environ, {"DETECTION_BACKEND": "ml"}):
            self.assertEqual(detection_model.select_backend(), "ml")

    def test_explicit_gemini(self) -> None:
        with mock.patch.dict(os.environ, {"DETECTION_BACKEND": "gemini"}):
            self.assertEqual(detection_model.select_backend(), "gemini")

    def test_unknown_value_raises(self) -> None:
        with mock.patch.dict(os.environ, {"DETECTION_BACKEND": "magic"}), \
             self.assertRaises(RuntimeError):
            detection_model.select_backend()

    def test_auto_uses_ml_when_weights_present(self) -> None:
        with mock.patch.dict(os.environ, {"DETECTION_BACKEND": "auto"}), \
             mock.patch.object(detection_ml, "is_available", return_value=True):
            self.assertEqual(detection_model.select_backend(), "ml")

    def test_auto_falls_back_to_embed_when_only_embed_available(self) -> None:
        with mock.patch.dict(os.environ, {"DETECTION_BACKEND": "auto"}), \
             mock.patch.object(detection_ml, "is_available", return_value=False), \
             mock.patch.object(detection_embed, "is_available", return_value=True):
            self.assertEqual(detection_model.select_backend(), "embed")

    def test_auto_prefers_ml_over_embed(self) -> None:
        with mock.patch.dict(os.environ, {"DETECTION_BACKEND": "auto"}), \
             mock.patch.object(detection_ml, "is_available", return_value=True), \
             mock.patch.object(detection_embed, "is_available", return_value=True):
            self.assertEqual(detection_model.select_backend(), "ml")

    def test_auto_falls_through_to_gemini_when_nothing_else(self) -> None:
        with mock.patch.dict(os.environ, {"DETECTION_BACKEND": "auto"}), \
             mock.patch.object(detection_ml, "is_available", return_value=False), \
             mock.patch.object(detection_embed, "is_available", return_value=False), \
             mock.patch.object(detection_moondream, "is_available", return_value=False):
            self.assertEqual(detection_model.select_backend(), "gemini")

    def test_auto_prefers_moondream_over_gemini(self) -> None:
        with mock.patch.dict(os.environ, {"DETECTION_BACKEND": "auto"}), \
             mock.patch.object(detection_ml, "is_available", return_value=False), \
             mock.patch.object(detection_embed, "is_available", return_value=False), \
             mock.patch.object(detection_moondream, "is_available", return_value=True):
            self.assertEqual(detection_model.select_backend(), "moondream")

    def test_explicit_moondream(self) -> None:
        with mock.patch.dict(os.environ, {"DETECTION_BACKEND": "moondream"}):
            self.assertEqual(detection_model.select_backend(), "moondream")

    def test_explicit_embed(self) -> None:
        with mock.patch.dict(os.environ, {"DETECTION_BACKEND": "embed"}):
            self.assertEqual(detection_model.select_backend(), "embed")

    def test_select_backend_safe_returns_error_for_bad_env(self) -> None:
        with mock.patch.dict(os.environ, {"DETECTION_BACKEND": "garbage"}):
            backend, err = detection_model.select_backend_safe()
            self.assertIsNone(backend)
            self.assertIn("garbage", err or "")

    def test_select_backend_safe_passes_through_valid(self) -> None:
        with mock.patch.dict(os.environ, {"DETECTION_BACKEND": "ml"}):
            backend, err = detection_model.select_backend_safe()
            self.assertEqual(backend, "ml")
            self.assertIsNone(err)

    def test_default_when_unset(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "DETECTION_BACKEND"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(detection_ml, "is_available", return_value=False), \
             mock.patch.object(detection_embed, "is_available", return_value=False), \
             mock.patch.object(detection_moondream, "is_available", return_value=False):
            self.assertEqual(detection_model.select_backend(), "gemini")


class TestGeminiFallback(unittest.TestCase):
    """Gemini path — input/output contract via mocked client."""

    def test_missing_api_key_raises(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(detection_gemini.detect(b"x", lat=60.0))
            self.assertIn("GEMINI_API_KEY", str(ctx.exception))

    def test_extract_json_with_fence(self) -> None:
        text = '```json\n{"has_panels": true, "confidence": 0.9}\n```'
        out = detection_gemini._extract_json(text)
        self.assertTrue(out["has_panels"])

    def test_extract_json_bare(self) -> None:
        text = 'noise {"has_panels": false, "confidence": 0.1} trailing'
        out = detection_gemini._extract_json(text)
        self.assertFalse(out["has_panels"])

    def test_extract_json_invalid_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            detection_gemini._extract_json("totally not json")

    def test_low_confidence_forces_negative(self) -> None:
        # has_panels true but confidence < THRESHOLD → must be False.
        result = detection_gemini._parse_response(
            '{"has_panels": true, "confidence": 0.3, "panel_area_m2": 25}',
            started_at=0.0,
        )
        self.assertFalse(result["has_panels"])
        self.assertEqual(result["confidence"], 0.3)
        self.assertIsNone(result["panel_area_m2"])
        self.assertEqual(result["backend"], "gemini")

    def test_positive_with_area(self) -> None:
        result = detection_gemini._parse_response(
            '{"has_panels": true, "confidence": 0.85, "panel_area_m2": 32.5}',
            started_at=0.0,
        )
        self.assertTrue(result["has_panels"])
        self.assertEqual(result["panel_area_m2"], 32.5)
        self.assertEqual(result["roof_area_m2"], 32.5)

    def test_positive_without_area_is_withheld(self) -> None:
        # Invariant I4: panel_area_m2 must be > 0 when has_panels=True.
        result = detection_gemini._parse_response(
            '{"has_panels": true, "confidence": 0.9, "panel_area_m2": null}',
            started_at=0.0,
        )
        self.assertFalse(result["has_panels"])  # withheld
        self.assertIsNone(result["panel_area_m2"])

    def test_confidence_clamped(self) -> None:
        # Invariant I2: 0.0 <= confidence <= 1.0.
        result = detection_gemini._parse_response(
            '{"has_panels": false, "confidence": 5.5}', started_at=0.0
        )
        self.assertEqual(result["confidence"], 1.0)
        result = detection_gemini._parse_response(
            '{"has_panels": false, "confidence": -0.4}', started_at=0.0
        )
        self.assertEqual(result["confidence"], 0.0)

    def test_empty_response_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            detection_gemini._parse_response("", started_at=0.0)

    def test_structured_mode_plain_json(self) -> None:
        # Structured JSON mode returns bare JSON, no fences.
        result = detection_gemini._parse_response(
            '{"has_panels": false, "confidence": 0.42, "reasoning": "snö"}',
            started_at=0.0,
        )
        self.assertFalse(result["has_panels"])
        self.assertAlmostEqual(result["confidence"], 0.42, places=3)

    def test_is_transient_true_for_known_signals(self) -> None:
        for msg in ["429 Too Many Requests", "503 Service Unavailable",
                    "Deadline exceeded", "Connection reset by peer"]:
            self.assertTrue(detection_gemini._is_transient(RuntimeError(msg)),
                            f"should be transient: {msg}")

    def test_is_transient_false_for_permanent_errors(self) -> None:
        for msg in ["400 Bad Request", "401 Unauthorized",
                    "403 Forbidden", "Invalid argument"]:
            self.assertFalse(detection_gemini._is_transient(RuntimeError(msg)),
                             f"should NOT be transient: {msg}")

    def test_model_env_override(self) -> None:
        with mock.patch.dict(os.environ, {"GEMINI_MODEL": "gemini-2.5-pro"}):
            self.assertEqual(detection_gemini._model_name(), "gemini-2.5-pro")

    def test_timeout_env_override(self) -> None:
        with mock.patch.dict(os.environ, {"GEMINI_TIMEOUT_S": "60"}):
            self.assertEqual(detection_gemini._timeout_s(), 60.0)

    def test_timeout_env_invalid_falls_back(self) -> None:
        with mock.patch.dict(os.environ, {"GEMINI_TIMEOUT_S": "not-a-number"}):
            self.assertEqual(detection_gemini._timeout_s(), 30.0)

    def test_panel_area_zero_is_treated_as_missing(self) -> None:
        # 0 m² means "no panels detected"; invariant I4 → has_panels withheld.
        result = detection_gemini._parse_response(
            '{"has_panels": true, "confidence": 0.9, "panel_area_m2": 0}',
            started_at=0.0,
        )
        self.assertFalse(result["has_panels"])
        self.assertIsNone(result["panel_area_m2"])

    def test_panel_area_negative_is_treated_as_missing(self) -> None:
        result = detection_gemini._parse_response(
            '{"has_panels": true, "confidence": 0.9, "panel_area_m2": -10}',
            started_at=0.0,
        )
        self.assertFalse(result["has_panels"])
        self.assertIsNone(result["panel_area_m2"])


class TestGeminiRetry(unittest.TestCase):
    """End-to-end retry behaviour with a mocked client."""

    def setUp(self) -> None:
        # Cancel any real sleep so retries are instant in tests.
        self._sleep_patch = mock.patch.object(detection_gemini.time, "sleep", lambda _s: None)
        self._sleep_patch.start()

    def tearDown(self) -> None:
        self._sleep_patch.stop()

    @staticmethod
    def _ok_response(text: str = '{"has_panels": false, "confidence": 0.1}'):
        resp = mock.Mock()
        resp.text = text
        resp.candidates = []
        return resp

    def test_succeeds_on_first_attempt(self) -> None:
        client = mock.Mock()
        client.models.generate_content.return_value = self._ok_response()
        result = detection_gemini._call_with_retry(
            client, "gemini-2.5-flash", contents=[], config=None, started_at=0.0
        )
        self.assertEqual(client.models.generate_content.call_count, 1)
        self.assertEqual(result["backend"], "gemini")

    def test_retries_then_succeeds_on_transient(self) -> None:
        client = mock.Mock()
        client.models.generate_content.side_effect = [
            RuntimeError("503 Service Unavailable"),
            RuntimeError("429 Too Many Requests"),
            self._ok_response('{"has_panels": true, "confidence": 0.8, "panel_area_m2": 25}'),
        ]
        result = detection_gemini._call_with_retry(
            client, "gemini-2.5-flash", contents=[], config=None, started_at=0.0
        )
        self.assertEqual(client.models.generate_content.call_count, 3)
        self.assertTrue(result["has_panels"])

    def test_does_not_retry_permanent_errors(self) -> None:
        client = mock.Mock()
        client.models.generate_content.side_effect = RuntimeError("400 Bad Request")
        with self.assertRaises(RuntimeError) as ctx:
            detection_gemini._call_with_retry(
                client, "gemini-2.5-flash", contents=[], config=None, started_at=0.0
            )
        self.assertEqual(client.models.generate_content.call_count, 1)
        self.assertIn("400", str(ctx.exception))

    def test_keyboard_interrupt_propagates(self) -> None:
        # P0: KeyboardInterrupt must NOT be caught by the retry loop.
        client = mock.Mock()
        client.models.generate_content.side_effect = KeyboardInterrupt("user cancelled")
        with self.assertRaises(KeyboardInterrupt):
            detection_gemini._call_with_retry(
                client, "gemini-2.5-flash", contents=[], config=None, started_at=0.0
            )

    def test_system_exit_propagates(self) -> None:
        client = mock.Mock()
        client.models.generate_content.side_effect = SystemExit(1)
        with self.assertRaises(SystemExit):
            detection_gemini._call_with_retry(
                client, "gemini-2.5-flash", contents=[], config=None, started_at=0.0
            )

    def test_exhausts_attempts_then_fails(self) -> None:
        client = mock.Mock()
        client.models.generate_content.side_effect = RuntimeError("503 Service Unavailable")
        with self.assertRaises(RuntimeError) as ctx:
            detection_gemini._call_with_retry(
                client, "gemini-2.5-flash", contents=[], config=None, started_at=0.0
            )
        self.assertEqual(client.models.generate_content.call_count, detection_gemini.MAX_ATTEMPTS)
        self.assertIn(str(detection_gemini.MAX_ATTEMPTS), str(ctx.exception))

    def test_empty_response_surfaces_finish_reason(self) -> None:
        client = mock.Mock()
        cand = mock.Mock()
        cand.finish_reason = "SAFETY"
        resp = mock.Mock()
        resp.text = ""
        resp.candidates = [cand]
        client.models.generate_content.return_value = resp
        with self.assertRaises(RuntimeError) as ctx:
            detection_gemini._call_with_retry(
                client, "gemini-2.5-flash", contents=[], config=None, started_at=0.0
            )
        self.assertIn("SAFETY", str(ctx.exception))


class TestLabelLog(unittest.TestCase):
    """Label-log corpus building — append-only JSONL."""

    def setUp(self) -> None:
        self.tmp_dir = Path("/tmp/_solar_label_log_test")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self._patches = [
            mock.patch.object(detection_label_log, "LOG_DIR", self.tmp_dir),
            mock.patch.object(
                detection_label_log, "INFERENCE_LOG", self.tmp_dir / "inferences.jsonl"
            ),
            mock.patch.object(
                detection_label_log, "LABEL_LOG", self.tmp_dir / "labels.jsonl"
            ),
        ]
        for p in self._patches:
            p.start()
        for f in (
            self.tmp_dir / "inferences.jsonl",
            self.tmp_dir / "labels.jsonl",
        ):
            if f.exists():
                f.unlink()

    def tearDown(self) -> None:
        for p in self._patches:
            p.stop()

    def test_records_round_trip(self) -> None:
        detection_label_log.record_inference(
            image_path="img/abc.jpg",
            backend="ml",
            has_panels=True,
            confidence=0.83,
            inference_ms=120,
            address="Storgatan 1",
        )
        detection_label_log.record_label(
            image_path="img/abc.jpg",
            has_panels_truth=True,
            note="confirmed visually",
        )
        self.assertEqual(detection_label_log.inference_count(), 1)
        self.assertEqual(detection_label_log.label_count(), 1)

    def test_concurrent_appends_dont_corrupt(self) -> None:
        import threading

        def writer(n: int) -> None:
            for i in range(50):
                detection_label_log.record_inference(
                    image_path=f"img/{n}-{i}.jpg",
                    backend="ml",
                    has_panels=False,
                    confidence=0.1,
                    inference_ms=10,
                )

        ts = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual(detection_label_log.inference_count(), 200)


class TestEmbedBackend(unittest.TestCase):
    """Embed backend — pure-numpy logic. Encoder mocked, no real ONNX needed."""

    def setUp(self) -> None:
        detection_embed.reset_session_for_tests()

    def tearDown(self) -> None:
        detection_embed.reset_session_for_tests()

    def test_is_available_false_without_files(self) -> None:
        # Force missing files via path-override so test is deterministic
        # regardless of whether fixture-weights exist in this environment.
        import pathlib
        from unittest.mock import patch
        missing = pathlib.Path("/nonexistent/test-fixture")
        with patch.object(detection_embed, "ENCODER_PATH", missing), \
             patch.object(detection_embed, "HEAD_PATH", missing):
            self.assertFalse(detection_embed.is_available())

    @unittest.skipUnless(HAVE_NUMPY, "numpy required")
    def test_predict_with_known_head(self) -> None:
        import numpy as np

        # Inject a synthetic head: weights all-positive → confident yes.
        embedding = np.ones(8, dtype=np.float32) / np.sqrt(8)  # unit-norm
        weights = np.ones(8, dtype=np.float32)
        bias = -0.5  # logit = √8 - 0.5 ≈ 2.33 → sigmoid ≈ 0.91
        with mock.patch.object(
            detection_embed, "_get_head",
            return_value={"weights": weights, "bias": bias},
        ):
            p = detection_embed._predict(embedding)
        self.assertGreater(p, 0.85)
        self.assertLess(p, 1.0)

    @unittest.skipUnless(HAVE_NUMPY, "numpy required")
    def test_predict_dim_mismatch_raises(self) -> None:
        import numpy as np

        bad_embedding = np.ones(4, dtype=np.float32)
        head = {"weights": np.ones(8, dtype=np.float32), "bias": 0.0}
        with mock.patch.object(detection_embed, "_get_head", return_value=head):
            with self.assertRaises(RuntimeError) as ctx:
                detection_embed._predict(bad_embedding)
            self.assertIn("dim", str(ctx.exception).lower())

    @unittest.skipUnless(HAVE_PIL and HAVE_NUMPY, "Pillow + numpy required")
    def test_preprocess_shape(self) -> None:
        import numpy as np

        # Build a real PNG so PIL decode succeeds.
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (300, 200), (255, 0, 0)).save(buf, format="PNG")
        tensor = detection_embed._preprocess(buf.getvalue())
        # Expected: NCHW 1x3x224x224 float32
        self.assertEqual(tensor.shape, (1, 3, 224, 224))
        self.assertEqual(tensor.dtype, np.float32)

    def test_preprocess_empty_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            detection_embed._preprocess(b"")

    def test_get_session_missing_encoder_raises(self) -> None:
        original = detection_embed.ENCODER_PATH
        detection_embed.ENCODER_PATH = Path("/tmp/__missing_encoder.onnx")
        try:
            detection_embed.reset_session_for_tests()
            with self.assertRaises(RuntimeError) as ctx:
                detection_embed._get_session()
            self.assertIn("encoder", str(ctx.exception).lower())
        finally:
            detection_embed.ENCODER_PATH = original
            detection_embed.reset_session_for_tests()

    def test_get_head_missing_raises(self) -> None:
        original = detection_embed.HEAD_PATH
        detection_embed.HEAD_PATH = Path("/tmp/__missing_head.npz")
        try:
            detection_embed.reset_session_for_tests()
            with self.assertRaises(RuntimeError) as ctx:
                detection_embed._get_head()
            self.assertIn("head", str(ctx.exception).lower())
        finally:
            detection_embed.HEAD_PATH = original
            detection_embed.reset_session_for_tests()


class TestGeminiClientCache(unittest.TestCase):
    """S1 — verify _get_client caches per api_key."""

    def setUp(self) -> None:
        detection_gemini.reset_client_cache_for_tests()

    def tearDown(self) -> None:
        detection_gemini.reset_client_cache_for_tests()

    def test_same_key_returns_same_instance(self) -> None:
        sentinel = object()
        with mock.patch.object(detection_gemini, "_build_client", return_value=sentinel) as bc:
            a = detection_gemini._get_client("k1")
            b = detection_gemini._get_client("k1")
        self.assertIs(a, b)
        self.assertEqual(bc.call_count, 1)  # built only once

    def test_different_keys_invalidate_cache(self) -> None:
        s1, s2 = object(), object()
        with mock.patch.object(detection_gemini, "_build_client", side_effect=[s1, s2]):
            a = detection_gemini._get_client("k1")
            b = detection_gemini._get_client("k2")
        self.assertIsNot(a, b)
        self.assertIs(a, s1)
        self.assertIs(b, s2)


@unittest.skipUnless(CAN_INFER, "real ONNX weights + onnxruntime required")
class TestInferenceWithWeights(unittest.TestCase):
    """End-to-end ML inference — only runs when weights are present."""

    def setUp(self) -> None:
        self._env = mock.patch.dict(os.environ, {"DETECTION_BACKEND": "ml"})
        self._env.start()
        detection_ml.reset_session_for_tests()

    def tearDown(self) -> None:
        self._env.stop()

    def test_tiny_image_does_not_crash(self) -> None:
        result = asyncio.run(detection_model.detect(_png_bytes(1, 1), lat=60.0))
        self.assertIn("has_panels", result)
        self.assertEqual(result["backend"], "ml")

    def test_huge_image_downsamples_ok(self) -> None:
        result = asyncio.run(detection_model.detect(_png_bytes(4096, 4096), lat=60.0))
        self.assertIn("confidence", result)

    def test_all_black_no_panels(self) -> None:
        result = asyncio.run(detection_model.detect(_png_bytes(512, 512, (0, 0, 0)), lat=60.0))
        self.assertFalse(result["has_panels"])
        self.assertIsNone(result["panel_area_m2"])

    def test_all_white_no_panels(self) -> None:
        result = asyncio.run(detection_model.detect(_png_bytes(512, 512, (255, 255, 255)), lat=60.0))
        self.assertFalse(result["has_panels"])

    def test_invariant_i4_area_sentinel(self) -> None:
        result = asyncio.run(detection_model.detect(_png_bytes(512, 512, (10, 10, 10)), lat=60.0))
        if result["has_panels"]:
            self.assertIsNotNone(result["panel_area_m2"])
            self.assertGreater(result["panel_area_m2"], 0.0)
        else:
            self.assertIsNone(result["panel_area_m2"])

    def test_concurrent_calls_share_session(self) -> None:
        async def runner() -> list[dict]:
            tile = _png_bytes(512, 512, (50, 50, 50))
            return await asyncio.gather(
                *(detection_model.detect(tile, lat=60.0) for _ in range(10))
            )

        results = asyncio.run(runner())
        self.assertEqual(len(results), 10)
        self.assertTrue(all(r["confidence"] == results[0]["confidence"] for r in results))


class TestMoondreamParser(unittest.TestCase):
    """Moondream/Ollama path — pure parser tests, no daemon required."""

    def test_parse_clean_json_with_panels(self) -> None:
        result = detection_moondream._parse_response(
            '{"has_panels": true, "confidence": 0.85, "panel_area_m2": 12.5}',
            started_at=0.0,
        )
        self.assertTrue(result["has_panels"])
        self.assertEqual(result["confidence"], 0.85)
        self.assertEqual(result["panel_area_m2"], 12.5)
        self.assertEqual(result["backend"], "moondream")

    def test_parse_no_panels(self) -> None:
        result = detection_moondream._parse_response(
            '{"has_panels": false, "confidence": 0.92, "panel_area_m2": null}',
            started_at=0.0,
        )
        self.assertFalse(result["has_panels"])
        self.assertIsNone(result["panel_area_m2"])

    def test_low_confidence_overrides_positive(self) -> None:
        result = detection_moondream._parse_response(
            '{"has_panels": true, "confidence": 0.3, "panel_area_m2": 8.0}',
            started_at=0.0,
        )
        self.assertFalse(result["has_panels"], "confidence < 0.5 must zero out has_panels")

    def test_invariant_i4_missing_area_zeroes_panels(self) -> None:
        result = detection_moondream._parse_response(
            '{"has_panels": true, "confidence": 0.9}',
            started_at=0.0,
        )
        self.assertFalse(result["has_panels"])
        self.assertIsNone(result["panel_area_m2"])

    def test_parse_fenced_json(self) -> None:
        text = '```json\n{"has_panels": false, "confidence": 0.7}\n```'
        result = detection_moondream._parse_response(text, started_at=0.0)
        self.assertFalse(result["has_panels"])

    def test_parse_empty_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            detection_moondream._parse_response("", started_at=0.0)

    def test_confidence_clamped(self) -> None:
        high = detection_moondream._parse_response(
            '{"has_panels": false, "confidence": 9.9}', started_at=0.0,
        )
        self.assertEqual(high["confidence"], 1.0)
        low = detection_moondream._parse_response(
            '{"has_panels": false, "confidence": -3.0}', started_at=0.0,
        )
        self.assertEqual(low["confidence"], 0.0)

    def test_is_available_returns_false_when_daemon_unreachable(self) -> None:
        # No ollama daemon on this box → is_available must return False, not raise.
        with mock.patch.dict(os.environ, {"OLLAMA_HOST": "http://127.0.0.1:1"}):
            self.assertFalse(detection_moondream.is_available())


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""El archivo conserva su tiempo original; fixtures generados, sin personas."""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from harmocap.identity import Detection
from harmocap.schema import FEATURE_ORDER
from harmocap.webapp import processing
from harmocap.webapp.exports import export_csv
from harmocap.webapp.offline_time import (
    probe_video_timeline, select_source_indices, validate_timeline,
)


@pytest.fixture(params=[("cfr", "PTS+2/TB", [2.0, 2.1, 2.2, 2.3]),
                        ("vfr", "PTS+gte(N\\,2)*1/TB+2/TB",
                         [2.0, 2.1, 3.2, 3.3])])
def clip(request, tmp_path):
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg y ffprobe necesarios para video sintético")
    name, expr, seconds = request.param
    path = tmp_path / f"{name}.mkv"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=64x64:rate=10:duration=0.4", "-vf",
                    f"setpts={expr}", "-fps_mode", "passthrough", "-c:v",
                    "ffv1", str(path)], check=True)
    return path, seconds


def test_pts_original_y_recorte(clip):
    path, seconds = clip
    timeline = probe_video_timeline(path)
    assert [timeline.seconds(i) for i in range(4)] == seconds
    assert timeline.time_base_text == "1/1000"
    assert len(timeline.source_sha256) == 64
    indices, eligible, outside = select_source_indices(timeline, 2.05, 3.25, 1)
    expected = [i for i, t in enumerate(seconds) if 2.05 <= t < 3.25]
    assert indices == expected
    assert eligible == len(expected)
    assert outside + eligible == 4
    selected, eligible, _ = select_source_indices(timeline, 0, 0, 2)
    assert selected == [0, 2] and eligible == 4


@pytest.mark.parametrize("frames, error", [
    ([{"pts": 0}, {}], "ausente"),
    ([{"pts": 0}, {"pts": 0}], "creciente"),
    ([{"pts": 2}, {"pts": 1}], "creciente"),
])
def test_pts_invalidos_se_rechazan(frames, error):
    with pytest.raises(ValueError, match=error):
        validate_timeline({"streams": [{"time_base": "1/1000"}],
                           "frames": frames}, "0" * 64)


def test_pipeline_csv_y_derivados_reciben_delta_pts_real(clip, tmp_path, monkeypatch):
    path, seconds = clip
    seen_t_us = []
    det = Detection(track_id=1, bbox_xywhn=(.5, .5, .3, .5),
                    keypoints_iso=[(.5, .5, .9)] * 17)

    class FakeSlots:
        focused_slot = 0

        def update(self, _dets, t_us, **_kwargs):
            seen_t_us.append(t_us)
            return [SimpleNamespace(slot_id=0, detection=det)]

    class FakeState:
        def __init__(self, _run):
            self.slots = FakeSlots()
            self.backend = SimpleNamespace(track_frame=lambda _f: ([], [], None, None),
                                           info=lambda: {"test": "sin modelo"})
            self.density = self.crowd = None
            self.device = "fake"

        def person(self, _ev, t_us):
            # Feature temporal ficticia: permite detectar si llega índice/FPS.
            return [t_us / 1e6] * len(FEATURE_ORDER), [0] * len(FEATURE_ORDER)

    monkeypatch.setattr(processing, "_PipelineState", FakeState)
    run = processing.RunConfig(t_start=2.05, t_end=3.25, crowd=False)
    render = processing.RenderConfig(overlays=[], write_video=False)
    result = processing.process_video(path, run, render, tmp_path)
    expected = [t for t in seconds if 2.05 <= t < 3.25]
    assert seen_t_us == [round(t * 1e6) for t in expected]
    rows = [json.loads(line) for line in result.jsonl_path.read_text().splitlines()]
    assert [row["t_s"] for row in rows] == expected
    assert [row["source_frame_index"] for row in rows] == [seconds.index(t) for t in expected]
    assert [row["source_pts_origin_ticks"] for row in rows] == [2000] * len(expected)
    assert [(row["source_pts_ticks"] - row["source_pts_origin_ticks"]) / 1000
            for row in rows] == pytest.approx([t - seconds[0] for t in expected])
    assert [row["frame"] for row in rows] == list(range(1, len(expected) + 1))
    assert rows[0]["source_video_sha256"] == rows[-1]["source_video_sha256"]
    assert [row["persons"][0]["features"][0] for row in rows] == expected
    assert [p[0] for p in result.feature_series[FEATURE_ORDER[0]]] == expected
    manifest = json.loads(result.config_path.read_text())
    assert manifest["video"]["pts_origin_ticks"] == 2000
    assert manifest["video"]["time_origin"] == "first_decoded_pts"
    assert manifest["frame_accounting"] == {
        "source_frames": 4, "outside_pts_crop": 4 - len(expected),
        "eligible_pts_crop": len(expected), "skipped_frame_stride": 0,
        "selected": len(expected), "processed": len(expected),
        "decode_failures": 0, "duplicate_pts": 0}
    assert manifest["render_timing"] is None
    persons_csv, crowd_csv = export_csv(result.jsonl_path, tmp_path)
    for file in (persons_csv, crowd_csv):
        with file.open(newline="") as f:
            exported = list(csv.DictReader(f))
        assert [int(row["source_frame_index"]) for row in exported] == [
            seconds.index(t) for t in expected]
        assert [float(row["t_s"]) for row in exported] == expected
        assert [int(row["source_pts_origin_ticks"]) for row in exported] == [2000] * len(expected)
        assert all(row["source_video_sha256"] == rows[0]["source_video_sha256"]
                   for row in exported)


def test_decodificacion_incompleta_deja_estado_explicito(clip, tmp_path, monkeypatch):
    path, _ = clip
    real_capture = processing.cv2.VideoCapture

    class InterruptedCapture:
        def __init__(self, filename):
            self.inner = real_capture(filename)
            self.reads = 0

        def isOpened(self):
            return self.inner.isOpened()

        def get(self, prop):
            return self.inner.get(prop)

        def read(self):
            self.reads += 1
            return (False, None) if self.reads == 3 else self.inner.read()

        def release(self):
            self.inner.release()

    class FakeState:
        def __init__(self, _run):
            self.backend = SimpleNamespace(track_frame=lambda _f: ([], [], None, None),
                                           info=lambda: {})
            self.slots = SimpleNamespace(update=lambda *_a, **_kw: [],
                                         focused_slot=0)
            self.density = self.crowd = None
            self.device = "fake"

    monkeypatch.setattr(processing.cv2, "VideoCapture", InterruptedCapture)
    monkeypatch.setattr(processing, "_PipelineState", FakeState)
    with pytest.raises(ValueError, match="cuadro fuente 2"):
        processing.process_video(path, processing.RunConfig(),
                                 processing.RenderConfig(write_video=False), tmp_path)
    stem = f"{path.stem}__grupo"
    manifest = json.loads((tmp_path / f"{stem}__run_config.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["frame_accounting"]["decode_failures"] == 1
    assert manifest["frame_accounting"]["processed"] == 2
    assert not (tmp_path / f"{stem}.jsonl").exists()
    assert (tmp_path / f"{stem}.partial.jsonl").exists()

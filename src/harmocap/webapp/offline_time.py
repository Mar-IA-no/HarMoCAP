"""Cronología del medio original para análisis offline de video."""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


@dataclass(frozen=True)
class VideoTimeline:
    ticks: tuple[int, ...]
    time_base: Fraction
    source_sha256: str

    @property
    def time_base_text(self) -> str:
        return f"{self.time_base.numerator}/{self.time_base.denominator}"

    def seconds(self, index: int) -> float:
        return float(self.ticks[index] * self.time_base)

    def microseconds(self, index: int) -> int:
        return round(self.ticks[index] * self.time_base * 1_000_000)


def validate_timeline(data: dict, source_sha256: str) -> VideoTimeline:
    """Valida PTS observados; jamás reemplaza ausencias por índice/FPS."""
    streams = data.get("streams", [])
    if len(streams) != 1:
        raise ValueError("ffprobe no informó exactamente un stream de video")
    try:
        time_base = Fraction(streams[0]["time_base"])
    except (KeyError, ValueError, ZeroDivisionError) as exc:
        raise ValueError("el video no tiene base de tiempo PTS válida") from exc
    if time_base <= 0:
        raise ValueError("el video no tiene base de tiempo PTS positiva")
    frames = data.get("frames", [])
    if not frames:
        raise ValueError("el video no tiene cuadros con PTS observables")
    ticks = []
    for i, frame in enumerate(frames):
        raw = frame.get("pts")
        try:
            tick = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"PTS ausente o inválido en cuadro fuente {i}") from exc
        if ticks and tick <= ticks[-1]:
            raise ValueError(f"PTS no estrictamente creciente en cuadro fuente {i}")
        ticks.append(tick)
    timeline = VideoTimeline(tuple(ticks), time_base, source_sha256)
    if any(timeline.microseconds(i) <= timeline.microseconds(i - 1)
           for i in range(1, len(ticks))):
        raise ValueError("PTS distintos colapsan a la misma marca en microsegundos")
    return timeline


def probe_video_timeline(video: str | Path) -> VideoTimeline:
    """Lee PTS en orden de presentación y vincula el resultado al archivo."""
    video = Path(video)
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-show_streams", "-show_frames", "-show_entries",
               "stream=time_base:frame=pts", "-of", "json",
               str(video)]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffprobe es necesario para analizar video offline") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"ffprobe no pudo leer el video: {exc.stderr.strip()}") from exc
    digest = hashlib.sha256()
    with video.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return validate_timeline(json.loads(result.stdout), digest.hexdigest())


def select_source_indices(timeline: VideoTimeline, t_start: float, t_end: float,
                          frame_stride: int) -> tuple[list[int], int, int]:
    """Devuelve índices procesables y denominadores de recorte/stride."""
    if t_start < 0 or t_end < 0 or (t_end > 0 and t_end <= t_start):
        raise ValueError("recorte temporal inválido: usar 0 <= inicio < fin")
    if frame_stride < 1:
        raise ValueError("frame_stride debe ser al menos 1")
    start = Fraction(str(t_start))
    end = Fraction(str(t_end)) if t_end > 0 else None
    eligible = [i for i, tick in enumerate(timeline.ticks)
                if tick * timeline.time_base >= start and
                (end is None or tick * timeline.time_base < end)]
    selected = eligible[::frame_stride]
    return selected, len(eligible), len(timeline.ticks) - len(eligible)

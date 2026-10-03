"""Núcleo de procesamiento de la interfaz web — una sola pasada por el video.

Corre el pipeline REAL de features (percepción → identidad → suavizado →
features + multitud/densidad), dibuja el render elegido y, en la misma pasada,
graba la sesión a .jsonl y acumula las variables para exportar a CSV y graficar.
Reutiliza los mismos componentes que el pipeline en vivo, así que lo que se
exporta son las variables del contrato, no detecciones crudas.

Todo lo que cuesta hardware está en `RunConfig` y todo lo que se ve está en
`RenderConfig`: la interfaz web no hace más que armar esos dos objetos. Los
presets son puntos conocidos de ese espacio, no ramas de código.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import cv2
import numpy as np
import yaml

from harmocap.crowd import CrowdAggregator
from harmocap.features import CalibrationManager, FeatureExtractor
from harmocap.identity import SlotManager
from harmocap.perception import PoseBackend, resolve_device
from harmocap.schema import CROWD_FIELDS, FEATURE_ORDER, KpState
from harmocap.smoothing import KeypointSmoother
from harmocap.webapp.offline_time import probe_video_timeline, select_source_indices

REPO = Path(__file__).resolve().parent.parent.parent.parent

PALETTE = [(66, 133, 244), (52, 168, 83), (251, 188, 5), (234, 67, 53),
           (171, 71, 188), (0, 172, 193), (255, 112, 67), (158, 157, 36)]
EDGES = ((0, 1), (0, 2), (1, 3), (2, 4), (5, 6), (5, 7), (7, 9), (6, 8),
         (8, 10), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15),
         (12, 14), (14, 16))
KPT_CONF = 0.35

# ─────────────────────────── catálogos de opciones ──────────────────────────
OVERLAYS = ("points", "skeleton", "bbox", "ids", "homunculus", "density")
OVERLAY_LABELS = {
    "points": "Puntos", "skeleton": "Esqueleto (líneas)", "bbox": "Caja (bbox)",
    "ids": "Número de identidad", "homunculus": "Silueta (homúnculo)",
    "density": "Mapa de densidad (masa)",
}

# modelo de pose: el costo por cuadro depende sobre todo de esto y de imgsz
MODELS = {
    "n": ("Nano — el más rápido (recomendado sin placa)",
          "yolo26n-pose.pt", "outputs/yolo26n-pose.engine"),
    "m": ("Medium ft2 — el más preciso (default del proyecto)",
          "harmocap-m-pose-ft2.pt", "outputs/harmocap-m-pose-ft2.engine"),
}

# tracker: ReID lanza una segunda red por cada caja detectada — es la perilla
# que más cuesta cuando `max_det` es alto y no hay placa NVIDIA.
TRACKERS = {
    "bytetrack": ("ByteTrack — el más barato, sin apariencia",
                  "bytetrack.yaml"),
    "botsort": ("BoT-SORT liviano — sin ReID ni compensación de cámara",
                "configs/tracker_light.yaml"),
    "botsort_reid": ("BoT-SORT + ReID — identidad máxima (caro)",
                     "configs/tracker_group.yaml"),
}

BACKGROUNDS = {"video": "Video original", "dim": "Video oscurecido",
               "black": "Fondo negro (solo el render)"}

IMGSZ_CHOICES = (320, 384, 448, 512, 576, 640, 768, 896, 1024, 1280)


@dataclass
class RunConfig:
    """Todo lo que define el costo y la calidad del procesamiento."""
    preset: str = "grupo"
    model_size: str = "m"
    imgsz: int = 640
    conf: float = 0.05
    max_det: int = 300
    max_slots: int = 8
    tracker: str = "botsort_reid"
    reacquisition: bool = True
    crowd: bool = True             # agregados de multitud (barato)
    density: bool = False          # mapa de densidad (caro)
    density_stride: int = 5
    density_min_edge: int = 448
    frame_stride: int = 1          # procesar 1 de cada N cuadros
    t_start: float = 0.0           # recorte temporal (s), solo video
    t_end: float = 0.0             # 0 = hasta el final
    mincutoff: float = 1.0         # suavizado One-Euro
    beta: float = 0.15

    @property
    def mode(self) -> str:
        """Modo del contrato: los presets de masa reportan `crowd`."""
        return "crowd" if self.density or self.max_det >= 200 else "group"


@dataclass
class RenderConfig:
    """Todo lo que se ve. No afecta las variables medidas."""
    overlays: list[str] = field(default_factory=lambda: ["skeleton", "ids"])
    background: str = "video"
    dim: float = 0.75              # cuánto se oscurece el fondo en modo `dim`
    line_w: int = 3
    point_r: int = 5
    trail_ms: int = 0              # 0 = sin estelas
    color_by_slot: bool = True
    solid_color: tuple = (255, 255, 255)
    hud: bool = False
    scale: float = 1.0             # escala del video/imagen de salida
    write_video: bool = True


# ───────────────────────────────── presets ──────────────────────────────────
PRESETS: dict[str, tuple[str, RunConfig]] = {
    "esencial": (
        "Esencial — trackeo básico en tiempo real (hardware modesto)",
        RunConfig(preset="esencial", model_size="n", imgsz=512, conf=0.30,
                  max_det=6, max_slots=2, tracker="bytetrack",
                  reacquisition=False, crowd=False, density=False)),
    "duo": (
        "Pocas personas — identidad firme, 1 a 4",
        RunConfig(preset="duo", model_size="m", imgsz=640, conf=0.25,
                  max_det=8, max_slots=4, tracker="botsort_reid",
                  reacquisition=True, crowd=False, density=False)),
    "grupo": (
        "Grupo — hasta 8 personas, identidad sagrada",
        RunConfig(preset="grupo", model_size="m", imgsz=640, conf=0.05,
                  max_det=300, max_slots=8, tracker="botsort_reid",
                  reacquisition=True, crowd=True, density=False)),
    "masa": (
        "Masa — multitud, recall máximo + mapa de densidad",
        RunConfig(preset="masa", model_size="m", imgsz=1280, conf=0.05,
                  max_det=300, max_slots=8, tracker="bytetrack",
                  reacquisition=False, crowd=True, density=True)),
}
PRESET_ORDER = ("esencial", "duo", "grupo", "masa")


def preset_config(name: str) -> RunConfig:
    return replace(PRESETS.get(name, PRESETS["grupo"])[1])


def suggested_preset(device: str) -> str:
    """Preset por defecto según el hardware detectado."""
    return "grupo" if device.startswith("cuda") else "esencial"


@dataclass
class ProcessResult:
    video_path: Path | None     # mp4 con el render (None si no se pidió video)
    jsonl_path: Path            # sesión grabada
    config_path: Path           # run_config.json — reproducibilidad
    frames: int
    seconds: float
    fps_proc: float
    device: str
    mode: str
    backend_info: dict
    feature_series: dict        # {feature: [(t_s, slot, valor)]}
    crowd_series: dict          # {campo: [(t_s, valor)]}


def hardware_info() -> dict:
    dev = resolve_device("auto")
    label = {"cuda:0": "Placa NVIDIA (rápido)",
             "mps": "Apple Silicon (moderado)",
             "cpu": "Procesador, sin placa (lento)"}.get(dev, dev)
    return {"device": dev, "label": label}


def _load_cfgs():
    def cfg(n):
        return yaml.safe_load((REPO / "configs" / f"{n}.yaml").read_text())
    return cfg("smoothing"), cfg("features"), cfg("identity")


def _build(run: RunConfig):
    """RunConfig → componentes del pipeline. Única puerta de entrada."""
    cfg_smooth, cfg_feat, cfg_ident = _load_cfgs()
    fallback, engine = MODELS.get(run.model_size, MODELS["m"])[1:]
    tracker = TRACKERS.get(run.tracker, TRACKERS["bytetrack"])[1]
    if "/" in tracker:
        tracker = str(REPO / tracker)
    backend = PoseBackend(
        realtime_checkpoint=str(REPO / engine), fallback_checkpoint=fallback,
        device="auto", imgsz=run.imgsz, conf=run.conf, max_det=run.max_det,
        tracker=tracker)
    reacq = dict(cfg_ident.get("reacquisition", {}))
    reacq["enabled"] = run.reacquisition
    slots = SlotManager(
        max_slots=run.max_slots,
        occlusion_grace_ms=cfg_ident["slot"]["occlusion_grace_ms"],
        release_timeout_ms=cfg_ident["slot"]["release_timeout_ms"],
        acquire_rule=cfg_ident["slot"]["acquire_rule"],
        auto_focus_switch_ratio=cfg_ident["slot"].get("auto_focus_switch_ratio", 1.2),
        tombstone_repeat_frames=cfg_ident["slot"]["tombstone_repeat_frames"],
        reacquisition=reacq)
    calib = CalibrationManager(cfg_feat["calibration"]["fallback"],
                               period_ms=cfg_feat["calibration"]["period_ms"])
    crowd = CrowdAggregator() if run.crowd else None

    density = density_crowd = None
    if run.density:
        onnx = REPO / "outputs" / "density" / "zip_qnrf_n.onnx"
        if onnx.is_file():
            from harmocap.density import DensityBackend
            from harmocap.density_crowd import DensityCrowdAggregator
            density = DensityBackend(onnx, min_edge=run.density_min_edge)
            density_crowd = DensityCrowdAggregator()
    cfg_smooth = dict(cfg_smooth)
    cfg_smooth["one_euro"] = dict(cfg_smooth["one_euro"],
                                  mincutoff=run.mincutoff, beta=run.beta)
    return (backend, slots, calib, crowd, density, density_crowd,
            cfg_smooth, cfg_feat, backend.device)


def _iso_to_px(kps_iso, h):
    """Isotrópico (x/h, y/h) → píxeles. Devuelve [(x_px, y_px, conf)]."""
    return [(k[0] * h, k[1] * h, k[2]) for k in kps_iso]


class Renderer:
    """Dibuja el cuadro de salida: fondo, estelas, esqueletos, HUD."""

    def __init__(self, cfg: RenderConfig):
        self.cfg = cfg
        self._trail = None      # lienzo persistente de estelas (uint8)
        self._t_prev = None

    def color(self, slot_id: int):
        return PALETTE[slot_id % 8] if self.cfg.color_by_slot \
            else tuple(int(c) for c in self.cfg.solid_color)

    def background(self, frame_bgr):
        """Aplica el fondo elegido. Devuelve el lienzo donde se dibuja."""
        if self.cfg.background == "black":
            return np.zeros_like(frame_bgr)
        if self.cfg.background == "dim":
            return (frame_bgr.astype(np.float32)
                    * (1.0 - self.cfg.dim)).astype(np.uint8)
        return frame_bgr

    def draw_person(self, canvas, slot_id, det, w, h, focused, layer=None):
        """Dibuja una persona en `canvas` (y en `layer` si hay estelas)."""
        cfg = self.cfg
        col = self.color(slot_id)
        kpx = _iso_to_px(det.keypoints_iso, h)
        pts = {i: (int(x), int(y)) for i, (x, y, c) in enumerate(kpx)
               if c >= KPT_CONF}
        targets = [canvas] if layer is None else [canvas, layer]
        if "homunculus" in cfg.overlays and len(pts) >= 3:
            hull = cv2.convexHull(np.array(list(pts.values()), np.int32))
            ov = canvas.copy()
            cv2.fillConvexPoly(ov, hull, col)
            cv2.addWeighted(ov, 0.35, canvas, 0.65, 0, canvas)
            cv2.polylines(canvas, [hull], True, col, max(1, cfg.line_w - 1),
                          cv2.LINE_AA)
        if "skeleton" in cfg.overlays:
            for t in targets:
                for a, b in EDGES:
                    if a in pts and b in pts:
                        cv2.line(t, pts[a], pts[b], col, cfg.line_w, cv2.LINE_AA)
        if ("points" in cfg.overlays or "skeleton" in cfg.overlays) \
                and cfg.point_r > 0:
            for t in targets:
                for p in pts.values():
                    cv2.circle(t, p, cfg.point_r, col, -1, cv2.LINE_AA)
            for p in pts.values():
                cv2.circle(canvas, p, cfg.point_r, (255, 255, 255), 1, cv2.LINE_AA)
        cx, cy, bw, bh = det.bbox_xywhn
        x1, y1 = int((cx - bw / 2) * w), int((cy - bh / 2) * h)
        x2, y2 = int((cx + bw / 2) * w), int((cy + bh / 2) * h)
        if "bbox" in cfg.overlays:
            cv2.rectangle(canvas, (x1, y1), (x2, y2), col,
                          cfg.line_w + 1 if focused else max(1, cfg.line_w - 1))
        if "ids" in cfg.overlays:
            tag = f"P{slot_id}" + (" *" if focused else "")
            cv2.putText(canvas, tag, (x1, max(16, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2, cv2.LINE_AA)

    def new_layer(self, frame):
        """Capa vacía para acumular estelas, o None si están apagadas."""
        return np.zeros_like(frame) if self.cfg.trail_ms > 0 else None

    def compose_trail(self, canvas, layer, dt_s: float):
        """Decae el lienzo de estelas, le suma la capa nueva y la compone."""
        if layer is None:
            return canvas
        if self._trail is None or self._trail.shape != layer.shape:
            self._trail = np.zeros_like(layer)
        tau = max(self.cfg.trail_ms, 1) / 1000.0
        decay = math.exp(-max(dt_s, 1e-3) / tau)
        self._trail = (self._trail.astype(np.float32) * decay).astype(np.uint8)
        np.maximum(self._trail, layer, out=self._trail)
        return np.maximum(canvas, self._trail)

    def draw_hud(self, canvas, lines: list[str]):
        if not self.cfg.hud:
            return canvas
        y = 24
        for ln in lines:
            cv2.putText(canvas, ln, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(canvas, ln, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (255, 255, 255), 1, cv2.LINE_AA)
            y += 24
        return canvas

    def rescale(self, canvas):
        s = self.cfg.scale
        if abs(s - 1.0) < 1e-3:
            return canvas
        h, w = canvas.shape[:2]
        return cv2.resize(canvas, (max(2, int(w * s) // 2 * 2),
                                   max(2, int(h * s) // 2 * 2)),
                          interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)


def _density_overlay(canvas, dmap, w, h):
    hm = cv2.resize(dmap, (w, h))
    hm = np.clip(hm / (hm.max() + 1e-9), 0, 1)
    hm = cv2.applyColorMap((hm * 255).astype(np.uint8), cv2.COLORMAP_JET)
    return cv2.addWeighted(canvas, 0.6, hm, 0.4, 0)


def _open_writer(path: Path, fps: float, size: tuple[int, int]):
    """mp4v (siempre presente en el OpenCV de pip) con avc1 como alternativa."""
    for fourcc in ("mp4v", "avc1"):
        vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*fourcc),
                             fps, size)
        if vw.isOpened():
            return vw, fourcc
        vw.release()
    raise RuntimeError("no se pudo abrir el escritor de video")


class _PipelineState:
    """Estado compartido entre cuadros: smoothers y extractores por slot."""

    def __init__(self, run: RunConfig):
        (self.backend, self.slots, self.calib, self.crowd, self.density,
         self.density_crowd, cfg_smooth, self.cfg_feat, self.device) = _build(run)
        self.run = run
        self.oe, self.ks = cfg_smooth["one_euro"], cfg_smooth["keypoint_state"]
        self.smoothers: dict[int, KeypointSmoother] = {}
        self.extractors: dict[int, FeatureExtractor] = {}

    def person(self, ev, t_us):
        sid = ev.slot_id
        if ev.slot_reset or sid not in self.smoothers:
            self.smoothers[sid] = KeypointSmoother(
                mincutoff=self.oe["mincutoff"], beta=self.oe["beta"],
                dcutoff=self.oe["dcutoff"],
                conf_threshold=self.ks["conf_threshold"],
                held_timeout_ms=self.ks["held_timeout_ms"],
                conf_decay_per_s=self.ks["conf_decay_per_s"])
            self.extractors[sid] = FeatureExtractor(
                self.cfg_feat["windows"], self.calib)
        sm = self.smoothers[sid].update(ev.detection.keypoints_iso, t_us)
        return self.extractors[sid].extract(sm, t_us)


_EMPTY_CROWD = {k: 0.0 for k in CROWD_FIELDS}


class StreamProcessor:
    """Procesa la webcam en vivo, un cuadro por llamada, manteniendo el estado
    del pipeline entre cuadros (identidad, suavizado, tempo, multitud).

    Uso: `annotated_bgr, readout = sp.step(frame_bgr)`. El tiempo avanza con el
    reloj real, así las features time-aware (velocidades, tempo) son correctas
    aunque la tasa de cuadros del stream sea irregular.
    """

    LIVE_FEATS = ("qom", "expansion", "contraction", "verticality",
                  "vel_center", "tempo_bpm", "tempo_conf")

    def __init__(self, run: RunConfig | None = None,
                 render: RenderConfig | None = None):
        self.run = run or preset_config("grupo")
        self.render_cfg = render or RenderConfig()
        self.st = _PipelineState(self.run)
        self.renderer = Renderer(self.render_cfg)
        self.device = self.st.device
        self._t0 = time.monotonic()
        self._t_prev = None
        self._density_i = 0
        self._dmap = None
        self._last_mass = {"mass_present": 0.0, "mass_active": 0.0}
        self._fps = 0.0

    # la webapp reconstruye el procesador cuando cambia la configuración
    @property
    def signature(self):
        return (asdict(self.run), asdict(self.render_cfg))

    def step(self, frame_bgr):
        t_now = time.monotonic()
        t_us = int((t_now - self._t0) * 1e6)
        dt = (t_now - self._t_prev) if self._t_prev else 1 / 30
        self._t_prev = t_now
        self._fps = 0.8 * self._fps + 0.2 * (1.0 / max(dt, 1e-3))
        h, w = frame_bgr.shape[:2]
        aspect = w / h if h else 16 / 9
        st, cfg = self.st, self.render_cfg

        dets, raw, _sp, _wh = st.backend.track_frame(frame_bgr)
        canvas = self.renderer.background(frame_bgr)

        if st.density is not None:
            if self._density_i % max(1, self.run.density_stride) == 0:
                rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                dmap = st.density.infer(rgb)
                dc = st.density_crowd.update(dmap, rgb, t_us)
                self._last_mass = {"mass_present": dc["mass_present"],
                                   "mass_active": dc["mass_active"]}
                self._dmap = dmap
            if "density" in cfg.overlays and self._dmap is not None:
                canvas = _density_overlay(canvas, self._dmap, w, h)
            self._density_i += 1

        events = st.slots.update(dets, t_us, aspect=aspect)
        focused = st.slots.focused_slot
        crowd_out = dict(_EMPTY_CROWD)
        if st.crowd is not None:
            crowd_out = st.crowd.update(raw, t_us, aspect=aspect)
        crowd_out.update(self._last_mass)

        layer = self.renderer.new_layer(canvas)
        focal_readout, n_present = {}, 0
        idx = {f: i for i, f in enumerate(FEATURE_ORDER)}
        for ev in events:
            if ev.detection is None:
                continue
            n_present += 1
            vals, states = st.person(ev, t_us)
            self.renderer.draw_person(canvas, ev.slot_id, ev.detection, w, h,
                                      ev.slot_id == focused, layer)
            if ev.slot_id == focused:
                for f in self.LIVE_FEATS:
                    i = idx[f]
                    focal_readout[f] = (None if states[i] == int(KpState.INVALID)
                                        else round(vals[i], 3))
        canvas = self.renderer.compose_trail(canvas, layer, dt)
        canvas = self.renderer.draw_hud(canvas, [
            f"{self._fps:4.1f} fps  ·  {self.run.preset}  ·  {self.device}",
            f"personas: {n_present}  ·  foco: P{focused}"])
        canvas = self.renderer.rescale(canvas)

        readout = {"fps": round(self._fps, 1), "personas": n_present,
                   "focal": focused, "focal_features": focal_readout,
                   "multitud": {k: crowd_out[k] for k in
                                ("crowd_count", "crowd_qom", "mass_present",
                                 "mass_active")}}
        return canvas, readout


def benchmark(video: str | Path, run: RunConfig, n_frames: int = 12) -> dict:
    """Mide fps reales con esta config sobre los primeros cuadros del video.

    Sirve para estimar cuánto va a tardar ANTES de lanzar la pasada completa.
    """
    st = _PipelineState(run)
    cap = cv2.VideoCapture(str(video))
    fps_src = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    ok, frame = cap.read()
    if not ok:
        cap.release()
        return {"error": "no se pudo leer el video"}
    st.backend.track_frame(frame)            # warm-up fuera de la medición
    t0, n = time.time(), 0
    while n < n_frames:
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        t_us = int(n * 1e6 / fps_src)
        dets, raw, _s, _wh = st.backend.track_frame(frame)
        if st.density is not None and n % max(1, run.density_stride) == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            st.density_crowd.update(st.density.infer(rgb), rgb, t_us)
        events = st.slots.update(dets, t_us, aspect=w / h if h else 16 / 9)
        if st.crowd is not None:
            st.crowd.update(raw, t_us, aspect=w / h if h else 16 / 9)
        for ev in events:
            if ev.detection is not None:
                st.person(ev, t_us)
        n += 1
    dt = max(time.time() - t0, 1e-6)
    cap.release()
    fps_proc = n / dt
    to_do = max(total // max(1, run.frame_stride), 1) if total else 0
    return {"fps_proc": round(fps_proc, 1),
            "ms_frame": round(1000 * dt / max(n, 1), 1),
            "device": st.device,
            "realtime": fps_proc >= fps_src * 0.95,
            "eta_s": round(to_do / fps_proc, 1) if to_do else None,
            "loaded": st.backend.info()}


def process_video(video: str | Path, run: RunConfig, render: RenderConfig,
                  out_dir: str | Path, progress=None) -> ProcessResult:
    """Analiza un archivo con sus PTS originales. `progress`: callable o None."""
    video = Path(video)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timeline = probe_video_timeline(video)
    selected, n_eligible, n_outside = select_source_indices(
        timeline, run.t_start, run.t_end, run.frame_stride)
    if not selected:
        raise ValueError("el recorte temporal no contiene cuadros para procesar")
    selected_set = set(selected)

    st = _PipelineState(run)
    renderer = Renderer(render)

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("OpenCV no pudo abrir el video")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_src = len(timeline.ticks)
    to_do = len(selected)

    stem = f"{video.stem}__{run.preset}"
    out_video = out_dir / f"{stem}.mp4"
    vw = fourcc = None
    jsonl = out_dir / f"{stem}.jsonl"
    cfg_path = out_dir / f"{stem}__run_config.json"
    fj = jsonl.open("w", encoding="utf-8")

    feat_series = {f: [] for f in FEATURE_ORDER}
    crowd_series = {c: [] for c in CROWD_FIELDS}
    t0, frames, last_t_us = time.monotonic(), 0, None
    density_i, last_mass = 0, {"mass_present": 0.0, "mass_active": 0.0}
    dmap = None
    idx = {f: i for i, f in enumerate(FEATURE_ORDER)}

    def abort_decode(reason: str, source_index: int, extra_frames: int = 0):
        """Deja evidencia del fallo sin presentar el JSONL parcial como sesión."""
        cap.release()
        if vw is not None:
            vw.release()
        fj.close()
        jsonl.replace(jsonl.with_suffix(".partial.jsonl"))
        if out_video.exists():
            out_video.replace(out_video.with_suffix(".partial.mp4"))
        cfg_path.write_text(json.dumps({
            "status": "failed", "reason": reason,
            "source_frame_index": source_index,
            "video": {"name": video.name, "sha256": timeline.source_sha256,
                      "time_base": timeline.time_base_text,
                      "pts_origin_ticks": timeline.ticks[0],
                      "time_origin": "first_decoded_pts",
                      "timestamp_state": "observed_ffprobe_pts"},
            "frame_accounting": {"source_frames": total_src,
                                 "outside_pts_crop": n_outside,
                                 "eligible_pts_crop": n_eligible,
                                 "skipped_frame_stride": n_eligible - to_do,
                                 "selected": to_do, "processed": frames,
                                 "decoded_before_failure": source_index,
                                 "decode_failures": int(not extra_frames),
                                 "extra_decoded_frames": extra_frames,
                                 "duplicate_pts": 0},
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        raise ValueError(reason)

    for src_i in range(total_src):
        ok, frame = cap.read()
        if not ok:
            abort_decode(f"fallo de decodificación en cuadro fuente {src_i}; "
                         f"se habían procesado {frames}/{to_do}", src_i)
        if src_i not in selected_set:
            continue
        frames += 1
        t_us = timeline.microseconds(src_i)
        t_s = timeline.seconds(src_i)
        dets, raw, _sp, _wh = st.backend.track_frame(frame)
        canvas = renderer.background(frame)

        if st.density is not None:
            if density_i % max(1, run.density_stride) == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                dmap = st.density.infer(rgb)
                dc = st.density_crowd.update(dmap, rgb, t_us)
                last_mass = {"mass_present": dc["mass_present"],
                             "mass_active": dc["mass_active"]}
            if "density" in render.overlays and dmap is not None:
                canvas = _density_overlay(canvas, dmap, w, h)
            density_i += 1

        events = st.slots.update(dets, t_us, aspect=w / h if h else 16 / 9)
        focused = st.slots.focused_slot
        crowd_out = dict(_EMPTY_CROWD)
        if st.crowd is not None:
            crowd_out = st.crowd.update(raw, t_us, aspect=w / h if h else 16 / 9)
        crowd_out.update(last_mass)

        layer = renderer.new_layer(canvas)
        frame_persons = []
        for ev in events:
            if ev.detection is None:
                continue
            sid = ev.slot_id
            vals, states = st.person(ev, t_us)
            frame_persons.append({"slot": sid, "focused": sid == focused,
                                  "features": vals, "feature_states": states})
            renderer.draw_person(canvas, sid, ev.detection, w, h,
                                 sid == focused, layer)
            for fname in FEATURE_ORDER:
                fi = idx[fname]
                if states[fi] != int(KpState.INVALID):
                    feat_series[fname].append((t_s, sid, vals[fi]))

        for cname in CROWD_FIELDS:
            crowd_series[cname].append((t_s, crowd_out[cname]))
        fj.write(json.dumps({"t_s": t_s, "t_us": t_us, "frame": frames,
                             "source_frame_index": src_i,
                             "source_pts_ticks": timeline.ticks[src_i],
                             "source_pts_origin_ticks": timeline.ticks[0],
                             "source_time_base": timeline.time_base_text,
                             "source_video_sha256": timeline.source_sha256,
                             "timestamp_state": "observed_ffprobe_pts",
                             "persons": frame_persons, "crowd": crowd_out}) + "\n")

        if render.write_video:
            dt_s = (t_us - last_t_us) / 1e6 if last_t_us is not None else 0.0
            canvas = renderer.compose_trail(canvas, layer, dt_s)
            canvas = renderer.draw_hud(canvas, [
                f"t={t_s:6.2f}s  ·  {run.preset}  ·  personas: {len(frame_persons)}"])
            canvas = renderer.rescale(canvas)
            if vw is None:
                vw, fourcc = _open_writer(out_video, fps / max(1, run.frame_stride),
                                          (canvas.shape[1], canvas.shape[0]))
            vw.write(canvas)
        if progress and frames % 10 == 0:
            progress(frames / to_do, f"Procesando… {frames}/{to_do} cuadros")
        last_t_us = t_us

    extra, _ = cap.read()
    if extra:
        abort_decode("OpenCV decodificó más cuadros que los informados por "
                     "ffprobe", total_src, extra_frames=1)

    cap.release()
    if vw is not None:
        vw.release()
    fj.close()
    dt = max(time.monotonic() - t0, 1e-6)

    cfg_path.write_text(json.dumps({
        "status": "complete",
        "run": asdict(run), "render": asdict(render),
        "backend": st.backend.info(), "device": st.device,
        "video": {"name": video.name, "sha256": timeline.source_sha256,
                  "fps_nominal": fps, "w": w, "h": h,
                  "frames_src": total_src, "time_base": timeline.time_base_text,
                  "pts_origin_ticks": timeline.ticks[0],
                  "time_origin": "first_decoded_pts",
                  "timestamp_state": "observed_ffprobe_pts"},
        "frame_accounting": {"source_frames": total_src,
                             "outside_pts_crop": n_outside,
                             "eligible_pts_crop": n_eligible,
                             "skipped_frame_stride": n_eligible - len(selected),
                             "selected": len(selected), "processed": frames,
                             "decode_failures": 0, "duplicate_pts": 0},
        "render_timing": "constant_fps_preview" if render.write_video else None,
        "frames_processed": frames, "fps_proc": round(frames / dt, 1),
        "video_codec": fourcc}, indent=2, ensure_ascii=False), encoding="utf-8")

    return ProcessResult(
        video_path=out_video if (render.write_video and vw is not None) else None,
        jsonl_path=jsonl, config_path=cfg_path, frames=frames,
        seconds=round(dt, 1), fps_proc=round(frames / dt, 1), device=st.device,
        mode=run.mode, backend_info=st.backend.info(),
        feature_series=feat_series, crowd_series=crowd_series)

"""Representación del movimiento — keypoints → variables (plan M3).

Todo CAUSAL, trailing y time-aware: derivadas con Δt real de captured_at
(r4 #3), ventanas en milisegundos, nunca se mira el futuro. Fórmulas y
decisiones de diseño documentadas en docs/FEATURES.md (fuente canónica).

Sistema de coordenadas: isotrópico (x_px/h, y_px/h), origen arriba-izquierda,
y hacia ABAJO (la vertical "arriba" es -y). Normalización espacial por altura
de torso; áreas por torso² (finding #7). Prioridad posturales > cinemáticas.

Estados por feature (r4 #1): observed/held/invalid propagados desde los
keypoints que la componen; invalid → sentinel 0.0 en el wire (r5 #5), nunca NaN.
"""
from __future__ import annotations

import math
from collections import deque

from harmocap.schema import (
    CALIBRATION_PARAM_ORDER, CalibrationProfile, CalibrationState,
    FEATURE_ORDER, KpState, N_KEYPOINTS,
)

# Índices COCO-17
NOSE, L_EYE, R_EYE, L_EAR, R_EAR = 0, 1, 2, 3, 4
L_SHO, R_SHO, L_ELB, R_ELB, L_WRI, R_WRI = 5, 6, 7, 8, 9, 10
L_HIP, R_HIP, L_KNE, R_KNE, L_ANK, R_ANK = 11, 12, 13, 14, 15, 16

# Keypoints requeridos por cada feature (para propagar validez, r4 #1)
_FEATURE_DEPS: dict[str, tuple[int, ...]] = {
    "qom": tuple(range(N_KEYPOINTS)),
    "contraction": (L_WRI, R_WRI, L_ANK, R_ANK, L_SHO, R_SHO, L_HIP, R_HIP),
    "expansion": tuple(range(N_KEYPOINTS)),
    "vel_hand_l": (L_WRI,), "vel_hand_r": (R_WRI,),
    "vel_center": (L_HIP, R_HIP),
    "smoothness_l": (L_WRI,), "smoothness_r": (R_WRI,),
    "symmetry": (L_SHO, R_SHO, L_ELB, R_ELB, L_WRI, R_WRI, L_HIP, R_HIP),
    "verticality": (L_SHO, R_SHO, L_HIP, R_HIP),
    "angle_elbow_l": (L_SHO, L_ELB, L_WRI), "angle_elbow_r": (R_SHO, R_ELB, R_WRI),
    "angle_knee_l": (L_HIP, L_KNE, L_ANK), "angle_knee_r": (R_HIP, R_KNE, R_ANK),
    "angle_shoulder_l": (L_ELB, L_SHO, L_HIP), "angle_shoulder_r": (R_ELB, R_SHO, R_HIP),
    "angle_hip_l": (L_KNE, L_HIP, L_SHO), "angle_hip_r": (R_KNE, R_HIP, R_SHO),
    "laban_weight_proxy": tuple(range(N_KEYPOINTS)),
    "laban_time_proxy": (L_WRI, R_WRI, L_HIP, R_HIP),
    "laban_space_proxy": (L_WRI, R_WRI),
}


def _clip01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _angle_at(a, vertex, c) -> float:
    """Ángulo en `vertex` entre los segmentos vertex→a y vertex→c, en [0, π]."""
    v1 = (a[0] - vertex[0], a[1] - vertex[1])
    v2 = (c[0] - vertex[0], c[1] - vertex[1])
    n1 = math.hypot(*v1); n2 = math.hypot(*v2)
    if n1 < 1e-9 or n2 < 1e-9:
        return 0.0
    cosang = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    return math.acos(max(-1.0, min(1.0, cosang)))


def _convex_hull_area(points: list[tuple[float, float]]) -> float:
    """Área del hull convexo (monotone chain + shoelace)."""
    pts = sorted(set(points))
    if len(pts) < 3:
        return 0.0
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    area = 0.0
    for i in range(len(hull)):
        x1, y1 = hull[i]
        x2, y2 = hull[(i + 1) % len(hull)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


class _TrailBuffer:
    """Buffer trailing (t_us, valor) acotado por ventana en ms. Causal."""

    def __init__(self, window_ms: float):
        self.window_us = window_ms * 1000.0
        self._buf: deque[tuple[int, object]] = deque()

    def push(self, t_us: int, value) -> None:
        self._buf.append((t_us, value))
        while self._buf and t_us - self._buf[0][0] > self.window_us:
            self._buf.popleft()

    def oldest(self):
        return self._buf[0] if self._buf else None

    def items(self):
        return list(self._buf)

    def clear(self):
        self._buf.clear()


class CalibrationManager:
    """Perfil por generaciones (r5 #4, r6 #1, r7 #4).

    Durante `calibrating` se aplica el fallback FIJO (las escalas NO se
    recalculan por frame). Al congelar se crea una generación nueva con la
    altura de torso medida (mediana), una sola vez.
    """

    def __init__(self, fallback: dict[str, float], period_ms: float = 5000.0):
        self.period_us = period_ms * 1000.0
        self._fallback = tuple(fallback[k] for k in CALIBRATION_PARAM_ORDER)
        self._samples: list[float] = []
        self._t0_us: int | None = None
        self.profile = CalibrationProfile(
            generation=1, state=CalibrationState.CALIBRATING,
            effective_from_frame_id=0, params=self._fallback)

    def observe(self, torso_height: float, t_us: int, frame_id: int) -> bool:
        """Acumula muestras; devuelve True el frame en que congela (gen nueva)."""
        if self.profile.state == CalibrationState.FROZEN:
            return False
        if self._t0_us is None:
            self._t0_us = t_us
        if torso_height > 1e-6:
            self._samples.append(torso_height)
        if t_us - self._t0_us >= self.period_us and self._samples:
            med = sorted(self._samples)[len(self._samples) // 2]
            params = list(self._fallback)
            params[CALIBRATION_PARAM_ORDER.index("torso_height_norm")] = med
            self.profile = CalibrationProfile(
                generation=self.profile.generation + 1,
                state=CalibrationState.FROZEN,
                effective_from_frame_id=frame_id, params=tuple(params))
            return True
        return False

    def param(self, name: str) -> float:
        return self.profile.params[CALIBRATION_PARAM_ORDER.index(name)]


class FeatureExtractor:
    """Extrae el vector de features v1 (K=21) de una persona. Causal."""

    def __init__(self, windows: dict[str, float], calib: CalibrationManager):
        self.calib = calib
        self._pos = {  # buffers de posición por keypoint usado en derivadas
            "hand_l": _TrailBuffer(windows.get("velocity_ms", 120)),
            "hand_r": _TrailBuffer(windows.get("velocity_ms", 120)),
            "center": _TrailBuffer(windows.get("velocity_ms", 120)),
        }
        self._vel = {
            "hand_l": _TrailBuffer(windows.get("accel_ms", 200)),
            "hand_r": _TrailBuffer(windows.get("accel_ms", 200)),
            "center": _TrailBuffer(windows.get("accel_ms", 200)),
        }
        self._acc = {
            "hand_l": _TrailBuffer(windows.get("jerk_ms", 300)),
            "hand_r": _TrailBuffer(windows.get("jerk_ms", 300)),
        }
        self._all_pos = _TrailBuffer(windows.get("qom_ms", 400))
        self._path = {  # trayectoria de manos para directness (laban_space_proxy)
            "hand_l": _TrailBuffer(windows.get("jerk_ms", 300)),
            "hand_r": _TrailBuffer(windows.get("jerk_ms", 300)),
        }

    def reset(self) -> None:
        for group in (self._pos, self._vel, self._acc, self._path):
            for buf in group.values():
                buf.clear()
        self._all_pos.clear()

    # -- helpers cinemáticos ---------------------------------------------------

    def _trail_velocity(self, buf: _TrailBuffer, current: tuple[float, float],
                        t_us: int) -> float | None:
        old = buf.oldest()
        buf.push(t_us, current)
        if old is None:
            return None
        t0, p0 = old
        dt = (t_us - t0) / 1e6
        if dt < 1e-3:
            return None
        return _dist(current, p0) / dt

    @staticmethod
    def _trail_delta(buf: _TrailBuffer, current: float, t_us: int) -> float | None:
        old = buf.oldest()
        buf.push(t_us, current)
        if old is None:
            return None
        t0, v0 = old
        dt = (t_us - t0) / 1e6
        if dt < 1e-3:
            return None
        return abs(current - v0) / dt

    # -- extracción ------------------------------------------------------------

    def extract(self, kps: list[tuple[float, float, float, int, int, int]],
                t_us: int) -> tuple[list[float], list[int]]:
        """kps: salida del KeypointSmoother (x, y, conf, estado, age_f, age_us).

        Devuelve (valores[K], estados[K]) en FEATURE_ORDER.
        """
        pts = [(k[0], k[1]) for k in kps]
        states = [k[3] for k in kps]
        torso = self._torso_height(pts, states)
        torso_n = torso if torso > 1e-6 else self.calib.param("torso_height_norm")

        mid_hip = self._mid(pts, L_HIP, R_HIP)
        vals: dict[str, float] = {}

        # --- cinemáticas (normalizadas por torso → unidades torso/s) ---------
        v_hl = self._trail_velocity(self._pos["hand_l"], pts[L_WRI], t_us)
        v_hr = self._trail_velocity(self._pos["hand_r"], pts[R_WRI], t_us)
        v_ce = self._trail_velocity(self._pos["center"], mid_hip, t_us)
        vmax_h = self.calib.param("vmax_hand")
        vmax_c = self.calib.param("vmax_center")
        vals["vel_hand_l"] = _clip01((v_hl or 0.0) / torso_n / vmax_h)
        vals["vel_hand_r"] = _clip01((v_hr or 0.0) / torso_n / vmax_h)
        vals["vel_center"] = _clip01((v_ce or 0.0) / torso_n / vmax_c)

        # aceleración y jerk (encadenando buffers trailing; time-aware)
        a_hl = self._trail_delta(self._vel["hand_l"], (v_hl or 0.0) / torso_n, t_us)
        a_hr = self._trail_delta(self._vel["hand_r"], (v_hr or 0.0) / torso_n, t_us)
        a_ce = self._trail_delta(self._vel["center"], (v_ce or 0.0) / torso_n, t_us)
        j_hl = self._trail_delta(self._acc["hand_l"], a_hl or 0.0, t_us)
        j_hr = self._trail_delta(self._acc["hand_r"], a_hr or 0.0, t_us)
        jerk_ref = self.calib.param("jerk_ref")
        vals["smoothness_l"] = 1.0 / (1.0 + (j_hl or 0.0) / jerk_ref)
        vals["smoothness_r"] = 1.0 / (1.0 + (j_hr or 0.0) / jerk_ref)

        # QoM: media de velocidades de todos los keypoints válidos (proxy del
        # QoM de silueta de Camurri; ver FEATURES.md)
        old_all = self._all_pos.oldest()
        self._all_pos.push(t_us, list(pts))
        qom = 0.0
        if old_all is not None:
            t0, pts0 = old_all
            dt = (t_us - t0) / 1e6
            if dt >= 1e-3:
                ds = [_dist(pts[i], pts0[i]) for i in range(N_KEYPOINTS)
                      if states[i] != int(KpState.INVALID)]
                if ds:
                    qom = (sum(ds) / len(ds)) / dt / torso_n
        vals["qom"] = _clip01(qom / vmax_h)

        # --- posturales -------------------------------------------------------
        ext_d = [_dist(pts[i], mid_hip) / torso_n
                 for i in (L_WRI, R_WRI, L_ANK, R_ANK)
                 if states[i] != int(KpState.INVALID)]
        # contraído=1 cuando las extremidades están cerca del CoM (~<0.5 torso);
        # expandido→0 (brazos/piernas estirados llegan a ~2 torsos del CoM)
        mean_ext = sum(ext_d) / len(ext_d) if ext_d else 1.0
        vals["contraction"] = _clip01(1.0 - (mean_ext - 0.5) / 1.5)

        valid_pts = [pts[i] for i in range(N_KEYPOINTS)
                     if states[i] != int(KpState.INVALID)]
        hull = _convex_hull_area(valid_pts) / (torso_n * torso_n)  # área/torso² (finding #7)
        vals["expansion"] = _clip01(hull / 6.0)   # ~6 torso² = cuerpo en estrella

        # simetría: pares homólogos reflejados sobre el eje x del cuerpo
        axis_x = (pts[L_SHO][0] + pts[R_SHO][0] + pts[L_HIP][0] + pts[R_HIP][0]) / 4.0
        pairs = ((L_SHO, R_SHO), (L_ELB, R_ELB), (L_WRI, R_WRI), (L_HIP, R_HIP))
        asym = [abs(abs(pts[l][0] - axis_x) - abs(pts[r][0] - axis_x)) / torso_n
                for l, r in pairs]
        vals["symmetry"] = _clip01(1.0 - (sum(asym) / len(asym)) / 1.0)

        # verticalidad: coseno del eje torso (mid_hip→mid_sho) contra "arriba" (-y)
        mid_sho = self._mid(pts, L_SHO, R_SHO)
        tx, ty = mid_sho[0] - mid_hip[0], mid_sho[1] - mid_hip[1]
        tn = math.hypot(tx, ty)
        vals["verticality"] = (-ty / tn) if tn > 1e-9 else 0.0  # [-1,1]; 1=erguido

        # ángulos articulares normalizados a [0,1] (ángulo/π)
        vals["angle_elbow_l"] = _angle_at(pts[L_SHO], pts[L_ELB], pts[L_WRI]) / math.pi
        vals["angle_elbow_r"] = _angle_at(pts[R_SHO], pts[R_ELB], pts[R_WRI]) / math.pi
        vals["angle_knee_l"] = _angle_at(pts[L_HIP], pts[L_KNE], pts[L_ANK]) / math.pi
        vals["angle_knee_r"] = _angle_at(pts[R_HIP], pts[R_KNE], pts[R_ANK]) / math.pi
        vals["angle_shoulder_l"] = _angle_at(pts[L_ELB], pts[L_SHO], pts[L_HIP]) / math.pi
        vals["angle_shoulder_r"] = _angle_at(pts[R_ELB], pts[R_SHO], pts[R_HIP]) / math.pi
        vals["angle_hip_l"] = _angle_at(pts[L_KNE], pts[L_HIP], pts[L_SHO]) / math.pi
        vals["angle_hip_r"] = _angle_at(pts[R_KNE], pts[R_HIP], pts[R_SHO]) / math.pi

        # --- proxies Laban (operacionalizaciones, NO Laban canónico; addendum #7)
        energy_ref = self.calib.param("energy_ref")
        accel_ref = self.calib.param("accel_ref")
        v_all = [(v_hl or 0.0), (v_hr or 0.0), (v_ce or 0.0)]
        vals["laban_weight_proxy"] = _clip01(
            sum((v / torso_n) ** 2 for v in v_all) / len(v_all) / energy_ref)
        a_all = [(a_hl or 0.0), (a_hr or 0.0), (a_ce or 0.0)]
        vals["laban_time_proxy"] = _clip01(sum(a_all) / len(a_all) / accel_ref)

        # directness de manos: desplazamiento/trayectoria (1=directo)
        directness = []
        for key, idx in (("hand_l", L_WRI), ("hand_r", R_WRI)):
            buf = self._path[key]
            buf.push(t_us, pts[idx])
            items = buf.items()
            if len(items) >= 3:
                path = sum(_dist(items[i][1], items[i + 1][1])
                           for i in range(len(items) - 1))
                disp = _dist(items[0][1], items[-1][1])
                if path > 1e-6:
                    directness.append(disp / path)
        vals["laban_space_proxy"] = (sum(directness) / len(directness)
                                     if directness else 0.0)

        # --- propagación de validez por feature (r4 #1) ----------------------
        out_vals, out_states = [], []
        for name in FEATURE_ORDER:
            deps = _FEATURE_DEPS[name]
            dep_states = [states[i] for i in deps]
            if any(s == int(KpState.INVALID) for s in dep_states):
                st = int(KpState.INVALID)
            elif any(s == int(KpState.HELD) for s in dep_states):
                st = int(KpState.HELD)
            else:
                st = int(KpState.OBSERVED)
            v = vals[name]
            if st == int(KpState.INVALID):
                v = 0.0   # sentinel wire-safe (r5 #5); el receptor DEBE ignorarlo
            if v != v:    # NaN interno = error detectado (r4 #14), nunca al wire
                raise ValueError(f"NaN interno en feature {name}")
            out_vals.append(float(v))
            out_states.append(st)
        return out_vals, out_states

    # -- geometría -------------------------------------------------------------

    @staticmethod
    def _mid(pts, i, j) -> tuple[float, float]:
        return ((pts[i][0] + pts[j][0]) / 2.0, (pts[i][1] + pts[j][1]) / 2.0)

    def _torso_height(self, pts, states) -> float:
        ok = lambda i: states[i] != int(KpState.INVALID)
        if all(ok(i) for i in (L_SHO, R_SHO, L_HIP, R_HIP)):
            return _dist(self._mid(pts, L_SHO, R_SHO), self._mid(pts, L_HIP, R_HIP))
        return 0.0

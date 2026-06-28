#!/usr/bin/env python3
"""Generate exam variants 5–16 with readable task-7 plots and print blanks."""

from __future__ import annotations

import json
import math
import os
import re
from fractions import Fraction
from pathlib import Path

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT

# ---------------------------------------------------------------------------
# Task 7 region definitions
# ---------------------------------------------------------------------------

REGION_FILL_COLORS = ("#b8d4f0", "#c8e6c9", "#ffe0b2")
REGION_STROKE_COLORS = ("#2c5f8a", "#2e7d32", "#e65100")


def _region_bounds(x: float, cfg: dict, sub: dict | None = None) -> tuple[float, float]:
    lower_idxs = (
        sub["lower"]
        if sub and "lower" in sub
        else list(range(len(cfg["lower_fns"])))
    )
    upper_idxs = (
        sub["upper"]
        if sub and "upper" in sub
        else list(range(len(cfg["upper_fns"])))
    )
    lo = max(cfg["lower_fns"][i](x) for i in lower_idxs)
    hi = min(cfg["upper_fns"][i](x) for i in upper_idxs)
    return lo, hi


def _combined_x_intervals(cfg: dict, n: int = 2000) -> list[tuple[float, float]]:
    x_lo, x_hi = cfg["x_range"]
    intervals: list[tuple[float, float]] = []
    start: float | None = None
    step = (x_hi - x_lo) / n
    x = x_lo
    while x <= x_hi + 1e-9:
        lo, hi = _region_bounds(x, cfg)
        ok = lo <= hi + 1e-9
        if ok and start is None:
            start = x
        elif not ok and start is not None:
            intervals.append((start, x - step))
            start = None
        x += step
    if start is not None:
        intervals.append((start, x_hi))
    return intervals


def compute_regions(cfg: dict) -> list[dict]:
    """Разные подобласти как разные системы неравенств."""
    if cfg.get("regions"):
        return cfg["regions"]
    n_lower = len(cfg["lower_fns"])
    n_upper = len(cfg["upper_fns"])
    if n_lower == 1 and n_upper >= 2:
        return [
            {"lower": [0], "upper": [ui], "active_upper": ui}
            for ui in range(n_upper)
        ]
    if n_upper == 1 and n_lower >= 2:
        return [
            {"lower": [li], "upper": [0], "active_lower": li}
            for li in range(n_lower)
        ]
    return [{"lower": list(range(n_lower)), "upper": list(range(n_upper))}]


def in_region(x: float, y: float, cfg: dict) -> bool:
    lo, hi = _region_bounds(x, cfg)
    return lo - 1e-9 <= y <= hi + 1e-9


def _in_subregion_x(x: float, cfg: dict, sub: dict, eps: float = 1e-9) -> bool:
    if "active_upper" in sub:
        i = sub["active_upper"]
        fx = cfg["upper_fns"][i](x)
        for j, fn in enumerate(cfg["upper_fns"]):
            if j != i and fx > fn(x) + eps:
                return False
    if "active_lower" in sub:
        i = sub["active_lower"]
        fx = cfg["lower_fns"][i](x)
        for j, fn in enumerate(cfg["lower_fns"]):
            if j != i and fx < fn(x) - eps:
                return False
    return True


def _sub_bounds(x: float, cfg: dict, sub: dict) -> tuple[float, float]:
    return _region_bounds(x, cfg, sub)


def find_region_polygons(cfg: dict, sub: dict, n: int = 500) -> list[list[tuple[float, float]]]:
    x_lo, x_hi = cfg["x_range"]
    if x_hi <= x_lo:
        return []
    step = (x_hi - x_lo) / n
    segments: list[list[float]] = []
    xs: list[float] = []
    x = x_lo
    while x <= x_hi + 1e-9:
        lo, hi = _sub_bounds(x, cfg, sub)
        ok = _in_subregion_x(x, cfg, sub) and lo <= hi + 1e-9
        if ok:
            xs.append(x)
        elif xs:
            segments.append(xs)
            xs = []
        x += step
    if xs:
        segments.append(xs)

    polys: list[list[tuple[float, float]]] = []
    for seg in segments:
        if len(seg) < 2:
            continue
        upper_pts = [(x, _sub_bounds(x, cfg, sub)[1]) for x in seg]
        lower_pts = [(x, _sub_bounds(x, cfg, sub)[0]) for x in reversed(seg)]
        polys.append(upper_pts + lower_pts)
    return polys


def find_all_region_polygons(cfg: dict) -> list[list[tuple[float, float]]]:
    polys = []
    for sub in compute_regions(cfg):
        polys.extend(find_region_polygons(cfg, sub))
    return polys


def make_svg(cfg: dict, width: int = 480, height: int = 400) -> str:
    """SVG in mathematical coordinates (как в бланке варианта 4), с авто-масштабом по области."""
    polys = find_all_region_polygons(cfg)
    ty, tn = cfg["test_yes"], cfg["test_no"]

    points: list[tuple[float, float]] = []
    for poly in polys:
        points.extend(poly)
    points += [ty, tn]
    if points:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        span_x = max(xs) - min(xs) or 1
        span_y = max(ys) - min(ys) or 1
        pad_x = max(0.35, span_x * 0.22)
        pad_y = max(0.35, span_y * 0.28)
        x_min = min(xs) - pad_x
        x_max = max(xs) + pad_x
        y_min = min(ys) - pad_y
        y_max = max(ys) + pad_y
    else:
        x_min, x_max = cfg["plot_x"]
        y_min, y_max = cfg["plot_y"]

    vb_w = x_max - x_min
    vb_h = y_max - y_min
    margin_x = vb_w * 0.10
    margin_y = vb_h * 0.12
    x_min_vb = x_min - margin_x
    x_max_vb = x_max + margin_x
    y_min_vb = y_min - margin_y
    y_max_vb = y_max + margin_y
    vb_w_full = x_max_vb - x_min_vb
    vb_h_full = y_max_vb - y_min_vb
    view_box = f"{x_min_vb:.4f} {y_min_vb:.4f} {vb_w_full:.4f} {vb_h_full:.4f}"

    def curve_path(fn, x0, x1, steps=200):
        pts = []
        for i in range(steps + 1):
            x = x0 + (x1 - x0) * i / steps
            pts.append((x, fn(x)))
        if len(pts) < 2:
            return ""
        d = f"M {pts[0][0]:.4f} {pts[0][1]:.4f}"
        for x, y in pts[1:]:
            d += f" L {x:.4f} {y:.4f}"
        return d

    sw_grid = max(vb_w_full, vb_h_full) * 0.004
    sw_axis = sw_grid * 2.2
    sw_curve = sw_grid * 2.8
    sw_region = sw_grid * 1.6
    fs_label = max(vb_w_full, vb_h_full) * 0.055
    fs_tick = max(vb_w_full, vb_h_full) * 0.042
    r_pt = max(vb_w_full, vb_h_full) * 0.018

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="{view_box}" role="img" aria-label="График задания 7" '
        f'style="border:1px solid #333;background:#fff">',
    ]

    # сетка
    x_step = 0.5 if vb_w <= 4 else 1.0
    y_step = 0.5 if vb_h <= 4 else 1.0
    xi = math.floor(x_min / x_step) * x_step
    while xi <= x_max + 1e-9:
        parts.append(
            f'<line x1="{xi:.4f}" y1="{y_min:.4f}" x2="{xi:.4f}" y2="{y_max:.4f}" '
            f'stroke="#e0e0e0" stroke-width="{sw_grid:.4f}"/>'
        )
        if abs(xi) > 0.05 or abs(xi) < 1e-9:
            parts.append(
                f'<text x="{xi:.4f}" y="{y_max + vb_h * 0.05:.4f}" text-anchor="middle" '
                f'font-size="{fs_tick:.4f}" font-family="Times New Roman" fill="#444">{xi:g}</text>'
            )
        xi += x_step

    yi = math.floor(y_min / y_step) * y_step
    while yi <= y_max + 1e-9:
        parts.append(
            f'<line x1="{x_min:.4f}" y1="{yi:.4f}" x2="{x_max:.4f}" y2="{yi:.4f}" '
            f'stroke="#e0e0e0" stroke-width="{sw_grid:.4f}"/>'
        )
        if abs(yi) > 0.05:
            parts.append(
                f'<text x="{x_min - vb_w * 0.04:.4f}" y="{yi + fs_tick * 0.3:.4f}" text-anchor="end" '
                f'font-size="{fs_tick:.4f}" font-family="Times New Roman" fill="#444">{yi:g}</text>'
            )
        yi += y_step

    # закрашенные области
    for idx, poly in enumerate(polys):
        fill = REGION_FILL_COLORS[idx % len(REGION_FILL_COLORS)]
        stroke = REGION_STROKE_COLORS[idx % len(REGION_STROKE_COLORS)]
        pd = " ".join(
            f"{'L' if i else 'M'} {x:.4f} {y:.4f}" for i, (x, y) in enumerate(poly)
        )
        parts.append(
            f'<path d="{pd} Z" fill="{fill}" fill-opacity="0.82" '
            f'stroke="{stroke}" stroke-width="{sw_region:.4f}"/>'
        )

    # кривые
    curve_defs = [
        (cfg["lower_fns"][0], "#1a5fb4", cfg["labels"][0]),
        (cfg["upper_fns"][0], "#c01c28", cfg["labels"][1]),
        (cfg["line_fn"], "#26a269", cfg["labels"][2]),
    ]
    label_positions = [
        (x_min + vb_w * 0.05, None),
        (x_max - vb_w * 0.28, None),
        (x_max - vb_w * 0.32, None),
    ]
    for i, (fn, color, label) in enumerate(curve_defs):
        d = curve_path(fn, x_min, x_max)
        if d:
            parts.append(
                f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw_curve:.4f}" '
                f'stroke-linecap="round"/>'
            )
            lx = label_positions[i][0]
            ly = fn(lx)
            if y_min <= ly <= y_max:
                parts.append(
                    f'<text x="{lx:.4f}" y="{ly - vb_h * 0.04:.4f}" font-size="{fs_label:.4f}" '
                    f'font-family="Times New Roman" fill="{color}">{label}</text>'
                )

    # оси
    if x_min <= 0 <= x_max:
        parts.append(
            f'<line x1="0" y1="{y_min:.4f}" x2="0" y2="{y_max:.4f}" '
            f'stroke="#888" stroke-width="{sw_axis:.4f}"/>'
        )
    if y_min <= 0 <= y_max:
        parts.append(
            f'<line x1="{x_min:.4f}" y1="0" x2="{x_max:.4f}" y2="0" '
            f'stroke="#888" stroke-width="{sw_axis:.4f}"/>'
        )
    parts.append(
        f'<line x1="{x_min:.4f}" y1="{y_max:.4f}" x2="{x_max:.4f}" y2="{y_max:.4f}" '
        f'stroke="#000" stroke-width="{sw_axis:.4f}"/>'
    )
    parts.append(
        f'<line x1="{x_min:.4f}" y1="{y_min:.4f}" x2="{x_min:.4f}" y2="{y_max:.4f}" '
        f'stroke="#000" stroke-width="{sw_axis:.4f}"/>'
    )
    parts.append(
        f'<text x="{x_max + vb_w * 0.03:.4f}" y="{y_max + vb_h * 0.02:.4f}" '
        f'font-size="{fs_label:.4f}" font-style="italic" font-family="Times New Roman">x</text>'
    )
    parts.append(
        f'<text x="{x_min - vb_w * 0.02:.4f}" y="{y_min - vb_h * 0.03:.4f}" '
        f'font-size="{fs_label:.4f}" font-style="italic" font-family="Times New Roman">y</text>'
    )

    # тестовые точки
    for pt, col, mark in [(ty, "#1a7f37", "A"), (tn, "#b91c1c", "B")]:
        if x_min <= pt[0] <= x_max and y_min <= pt[1] <= y_max:
            parts.append(
                f'<circle cx="{pt[0]:.4f}" cy="{pt[1]:.4f}" r="{r_pt:.4f}" fill="{col}" '
                f'stroke="#fff" stroke-width="{sw_grid:.4f}"/>'
            )
            parts.append(
                f'<text x="{pt[0] + r_pt * 1.5:.4f}" y="{pt[1] - r_pt * 1.2:.4f}" '
                f'font-size="{fs_tick:.4f}" font-weight="bold" font-family="Times New Roman" '
                f'fill="{col}">{mark}</text>'
            )

    parts.append("</svg>")
    return "\n".join(parts)


REGION_CONFIGS = [
    {
        "lower_fns": [lambda x: x**2 - 4],
        "upper_fns": [lambda x: 5 - x**2, lambda x: 3 - 2 * x],
        "line_fn": lambda x: 3 - 2 * x,
        "labels": ["y = x² − 4", "y = 5 − x²", "y = 3 − 2x"],
        "x_range": (-2.2, 2.0), "plot_x": (-3, 3), "plot_y": (-4, 5),
        "test_yes": (-1, 2), "test_no": (2.5, 1.5),
    },
    {
        "lower_fns": [lambda x: x**2 - 3],
        "upper_fns": [lambda x: 4 - x**2, lambda x: 2 - x],
        "line_fn": lambda x: 2 - x,
        "labels": ["y = x² − 3", "y = 4 − x²", "y = 2 − x"],
        "x_range": (-1.9, 1.85), "plot_x": (-3, 3), "plot_y": (-4, 5),
        "test_yes": (-1.5, 1.5), "test_no": (2.2, 1.5),
    },
    {
        "lower_fns": [lambda x: -x**2 + 1, lambda x: x - 2],
        "upper_fns": [lambda x: 3 - x**2],
        "line_fn": lambda x: x - 2,
        "labels": ["y = −x² + 1", "y = 3 − x²", "y = x − 2"],
        "x_range": (-2.0, 1.85), "plot_x": (-3, 3), "plot_y": (-4, 4),
        "test_yes": (-1, 1), "test_no": (1.5, 1.5),
    },
    {
        "lower_fns": [lambda x: x**2 - 5],
        "upper_fns": [lambda x: 2 - 2 * x**2, lambda x: 1 - x],
        "line_fn": lambda x: 1 - x,
        "labels": ["y = x² − 5", "y = 2 − 2x²", "y = 1 − x"],
        "x_range": (-1.75, 1.75), "plot_x": (-3, 3), "plot_y": (-6, 4),
        "test_yes": (-0.2, -0.3), "test_no": (-1.9, -5.5),
    },
    {
        "lower_fns": [lambda x: x**2 - 2],
        "upper_fns": [lambda x: 6 - x**2, lambda x: 4 - x],
        "line_fn": lambda x: 4 - x,
        "labels": ["y = x² − 2", "y = 6 − x²", "y = 4 − x"],
        "x_range": (-2.0, 2.0), "plot_x": (-3, 3), "plot_y": (-3, 7),
        "test_yes": (0, 1), "test_no": (2, 3),
    },
    {
        "lower_fns": [lambda x: -x**2 + 2, lambda x: 2 * x - 1],
        "upper_fns": [lambda x: 4 - x**2],
        "line_fn": lambda x: 2 * x - 1,
        "labels": ["y = −x² + 2", "y = 4 − x²", "y = 2x − 1"],
        "x_range": (-1.5, 1.65), "plot_x": (-3, 3), "plot_y": (-3, 5),
        "test_yes": (-0.7, 2.6), "test_no": (-2.0, 1.9),
    },
    {
        "lower_fns": [lambda x: x**2 - 1],
        "upper_fns": [lambda x: 5 - x**2, lambda x: 3 - 1.5 * x],
        "line_fn": lambda x: 3 - 1.5 * x,
        "labels": ["y = x² − 1", "y = 5 − x²", "y = 3 − 1,5x"],
        "x_range": (-2.0, 1.9), "plot_x": (-3, 3), "plot_y": (-2, 6),
        "test_yes": (-1, 2), "test_no": (1.5, 0),
    },
    {
        "lower_fns": [lambda x: x**2 - 6],
        "upper_fns": [lambda x: 3 - x**2, lambda x: -x],
        "line_fn": lambda x: -x,
        "labels": ["y = x² − 6", "y = 3 − x²", "y = −x"],
        "x_range": (-2.1, 2.1), "plot_x": (-3, 3), "plot_y": (-7, 4),
        "test_yes": (0, 0), "test_no": (2, 2),
    },
    {
        "lower_fns": [lambda x: -x**2, lambda x: x - 3],
        "upper_fns": [lambda x: 2 - x**2],
        "line_fn": lambda x: x - 3,
        "labels": ["y = −x²", "y = 2 − x²", "y = x − 3"],
        "x_range": (-1.8, 1.7), "plot_x": (-3, 3), "plot_y": (-4, 3),
        "test_yes": (-1, 0), "test_no": (1.5, 1),
    },
    {
        "lower_fns": [lambda x: x**2 - 3],
        "upper_fns": [lambda x: 5 - 2 * x**2, lambda x: 2 - x],
        "line_fn": lambda x: 2 - x,
        "labels": ["y = x² − 3", "y = 5 − 2x²", "y = 2 − x"],
        "x_range": (-1.6, 1.6), "plot_x": (-3, 3), "plot_y": (-4, 5),
        "test_yes": (-1, 1), "test_no": (1.5, 1.5),
    },
    {
        "lower_fns": [lambda x: x**2 - 4],
        "upper_fns": [lambda x: 4 - x**2, lambda x: 1 - 2 * x],
        "line_fn": lambda x: 1 - 2 * x,
        "labels": ["y = x² − 4", "y = 4 − x²", "y = 1 − 2x"],
        "x_range": (-1.9, 1.5), "plot_x": (-3, 3), "plot_y": (-5, 5),
        "test_yes": (-1, 0), "test_no": (2.5, 1.5),
    },
    {
        "lower_fns": [lambda x: -x**2 + 3, lambda x: x + 1],
        "upper_fns": [lambda x: 5 - x**2],
        "line_fn": lambda x: x + 1,
        "labels": ["y = −x² + 3", "y = 5 − x²", "y = x + 1"],
        "x_range": (-1.7, 1.7), "plot_x": (-3, 3), "plot_y": (-2, 6),
        "test_yes": (-0.5, 4.0), "test_no": (-2.1, 4.7),
    },
]

# ---------------------------------------------------------------------------
# Problem generators
# ---------------------------------------------------------------------------

def _fmt_num(x) -> str:
    if isinstance(x, Fraction):
        if x.denominator == 1:
            return str(x.numerator)
        if x == Fraction(1, 2):
            return "0,5"
        if x == Fraction(3, 2):
            return "1,5"
        if x == Fraction(6, 5):
            return "1,2"
        if x == Fraction(4, 5):
            return "0,8"
        return f"{float(x):g}".replace(".", ",")
    if isinstance(x, float) and x == int(x):
        return str(int(x))
    return str(x).replace(".", ",")


def decompose_ratio(target: int, inv_den: int = 5) -> tuple[int, float | str, int, float]:
    """Return (m1, m2, add, divb) with (m1*m2+add/divb) : (1/inv_den) == target."""
    base = target / inv_den
    for m1 in range(10, 55):
        for m2 in (2, 2.5, 3, "5/2", "8/3", "11/3"):
            mv = float(Fraction(m2)) if isinstance(m2, str) else m2
            for add in (3, 4, 5, 6, 7, 8):
                for divb in (0.04, 0.05, 0.06, 0.07, 0.08):
                    if abs(m1 * mv + add / divb - base) < 0.02:
                        return m1, m2, add, divb
    raise ValueError(f"cannot decompose top {target}")


def decompose_bot(target: int) -> tuple[float, float, float, float, float]:
    for b1 in (2, 2.2, 2.4, 2.5, 2.8, 3, 3.2, 3.5, 4):
        for b2 in (0.2, 0.25, 0.4, 0.5):
            for b3 in (0.4, 0.5, 0.6, 0.8, 1, 1.2, 1.6):
                for b4 in (0.2, 0.25, 0.4, 0.5):
                    for divc in (0.02, 0.04, 0.05):
                        val = (b1 / b2 - b3 / b4) / divc
                        if abs(val - target) < 0.05:
                            return b1, b2, b3, b4, divc
    raise ValueError(f"cannot decompose bot {target}")


def build_task1_spec(ans: int, num: int, div: float, sub_a: int | float, top: int, bot: int, sub) -> dict:
    A = Fraction(int(num), 10) / Fraction(int(div * 10), 10) - sub_a
    inner = Fraction(top, bot) - sub
    if A * inner != ans:
        raise ValueError(f"mismatch {num} {ans}")

    inv_den = None
    m1 = m2 = add = divb = None
    for cand in (5, 6, 8, 4, 10):
        try:
            m1, m2, add, divb = decompose_ratio(top, cand)
            inv_den = cand
            break
        except ValueError:
            continue
    if inv_den is None:
        raise ValueError(f"cannot build top {top}")

    inv = {5: "⅕", 6: "⅙", 8: "⅛", 4: "¼", 10: "⅒"}[inv_den]
    m2s = m2 if isinstance(m2, str) else (str(int(m2)) if float(m2) == int(m2) else str(m2).replace(".", ","))
    b1, b2, b3, b4, divc = decompose_bot(bot)
    sub_s = _fmt_num(sub)
    sub_a_s = f" − {int(sub_a)}" if sub_a else ""

    html = (
        f"( ({num}·10<sup>−1</sup> / {_fmt_num(div)}){sub_a_s.replace(' ', '&nbsp;')} ) : "
        f"( ( ({m1}·{m2s} + {str(add).replace('.',',')}:0,{str(divb).replace('0.','')}){inv} ) / "
        f"( ({_fmt_num(b1)}:{_fmt_num(b2)} − {_fmt_num(b3)}:{_fmt_num(b4)}):{_fmt_num(divc)} ) "
        f"− {sub_s} )<sup>−1</sup>"
    )
    tex = (
        rf"\left(\frac{{{num}\cdot 10^{{-1}}}}{{{div}}}{'-' + str(sub_a) if sub_a else ''}\right)"
        rf":\left(\frac{{\left({m1}\cdot{m2s}+{add}:0.{str(divb).replace('0.','')}\right):\frac{{1}}{{{inv_den}}}}}"
        rf"{{\left({b1}:{b2}-{b3}:{b4}\right):{divc}}}-{_fmt_num(sub).replace(',','.')}\right)^{{-1}}"
    )
    return {"num": num, "div": div, "sub_a": sub_a, "html": html, "tex": tex, "top": top, "bot": bot, "sub": sub, "ans": ans}


TASK1_SPECS = [
    build_task1_spec(75, 720, 2, 0, 1290, 360, Fraction(3, 2)),
    build_task1_spec(50, 480, 2, 0, 1290, 360, Fraction(3, 2)),
    build_task1_spec(105, 600, 2, 0, 1290, 300, Fraction(4, 5)),
    build_task1_spec(38, 640, 2, 0, 1290, 480, Fraction(3, 2)),
    build_task1_spec(97, 800, 2, 0, 1290, 400, Fraction(4, 5)),
    build_task1_spec(45, 660, 2, 0, 1260, 440, Fraction(3, 2)),
    build_task1_spec(61, 500, 1.2, 1, 1260, 420, Fraction(3, 2)),
    build_task1_spec(55, 540, 1.5, 1, 1290, 420, Fraction(3, 2)),
    build_task1_spec(70, 420, 2, 1, 1290, 300, Fraction(4, 5)),
    build_task1_spec(44, 360, 1.2, 2, 1290, 420, Fraction(3, 2)),
    build_task1_spec(93, 450, 1.5, 0, 1290, 300, Fraction(6, 5)),
    build_task1_spec(29, 390, 1.3, 1, 1260, 420, 2),
]


def task1_answer(spec: dict) -> tuple[str, str, int]:
    A = Fraction(int(spec["num"]), 10) / Fraction(int(spec["div"] * 10), 10) - spec["sub_a"]
    inner = Fraction(spec["top"], spec["bot"]) - spec["sub"]
    ans = A * inner
    if ans.denominator != 1 or int(ans) != spec["ans"]:
        raise ValueError(f"bad task1 answer {ans} for {spec}")
    return spec["tex"], spec["html"], int(ans)


TASK2_A = [1849, 1936, 2025, 2116, 2209, 2304, 2401, 2500, 2601, 2704, 2809, 2916]


def task2_count(a: int) -> int:
    cnt = 0
    for xi in range(-200, 200):
        if a * (xi + 1) ** 2 - 1 < 0:
            continue
        if a - (xi - 1) ** 2 < 0:
            continue
        if math.sqrt(a * (xi + 1) ** 2 - 1) > math.sqrt(a - (xi - 1) ** 2):
            cnt += 1
    return cnt


TASK3 = [
    ("Найдите площадь треугольника со сторонами 13, 14 и 15.", "$84$"),
    ("Найдите радиус вписанной окружности треугольника со сторонами 13, 14 и 15.", "$4$"),
    ("В треугольнике $ABC$ угол $C$ равен $90^\\circ$, $AC=9$, $BC=12$. Найдите радиус описанной окружности.", "$7{,}5$"),
    ("В треугольнике $ABC$ $AB=10$, $BC=12$, $AC=8$. Найдите длину медианы $AM$.", "$2\\sqrt{37}$"),
    ("В окружности радиуса 5 хорда имеет длину 8. Найдите расстояние от центра до хорды.", "$3$"),
    ("В треугольнике $ABC$ угол $A$ равен $60^\\circ$, $AB=6$, $AC=10$. Найдите площадь треугольника.", "$15\\sqrt{3}$"),
    ("Найдите радиус окружности, описанной около треугольника со сторонами 7, 8 и 9.", "$\\dfrac{32\\sqrt{5}}{15}$"),
    ("В прямоугольном треугольнике катеты равны 5 и 12. Найдите длину биссектрисы, проведённой из вершины прямого угла.", "$\\dfrac{60\\sqrt{2}}{17}$"),
    ("В равнобедренной трапеции основания равны 6 и 14, боковая сторона равна 5. Найдите высоту трапеции.", "$4$"),
    ("В треугольнике $ABC$ $AB=13$, $BC=14$, $AC=15$. Найдите длину высоты, проведённой к стороне $BC$.", "$12$"),
    ("В треугольнике $ABC$ угол $B$ равен $45^\\circ$, $AB=8$, $BC=6\\sqrt{2}$. Найдите $AC$.", "$2\\sqrt{13}$"),
    ("В окружности радиуса 13 хорда имеет длину 10. Найдите расстояние от центра до хорды.", "$12$"),
]

TASK4 = [
    (sp.Rational(1, 5), sp.Rational(1, 3), 980, 490, 1310, 111),
    (sp.Rational(1, 4), sp.Rational(1, 3), 720, 490, 924, 261),
    (sp.Rational(1, 4), sp.Rational(1, 3), 800, 550, 1004, 321),
    (sp.Rational(1, 4), sp.Rational(1, 3), 760, 520, 964, 291),
    (sp.Rational(1, 5), sp.Rational(2, 7), 875, 525, 875, 525),  # skip degenerate
    (sp.Rational(1, 6), sp.Rational(1, 4), 700, 420, 700, 420),
    (sp.Rational(1, 4), sp.Rational(1, 3), 840, 580, 1044, 351),
    (sp.Rational(1, 4), sp.Rational(1, 3), 880, 610, 1084, 381),
    (sp.Rational(1, 5), sp.Rational(1, 3), 910, 455, 1310, 111),
    (sp.Rational(1, 4), sp.Rational(1, 3), 920, 640, 1124, 411),
    (sp.Rational(1, 4), sp.Rational(1, 3), 960, 620, 1368, 162),
    (sp.Rational(1, 4), sp.Rational(1, 3), 720, 590, 516, 819),
]

TASK5 = [
    ("358", 63, 9, 9, 28261),
    ("358", 54, 0, 7, 17374),
    ("247", 63, 3, 7, 11900),
    ("469", 72, 5, 3, 5718),
    ("136", 87, 3, 1, 461),
    ("578", 81, 9, 2, 4111),
    ("358", 72, 0, 4, 6880),
    ("247", 65, 5, 5, 6578),
    ("469", 81, 8, 9, 39053),
    ("136", 76, 2, 8, 7887),
    ("358", 81, 0, 0, 304),
    ("247", 54, 3, 4, 6374),
]

# Варианты 5, 7, 9, 12, 15 — выражение из 3–4 действий (+, −, ·)
T5_COMPLEX: dict[int, dict] = {
    0: {
        "lead_coeff": 2,
        "ops": ["-", "+", "+"],
        "terms": [("41x", ("x", 63)), ("2x5", ("x", 63)), ("x3", ("x", 63)), ("2", ("x", 63))],
    },
    2: {
        "lead_coeff": 3,
        "ops": ["+", "-", "-"],
        "terms": [("41x", ("x", 63)), ("2x5", ("x", 63)), ("x3", ("x", 63)), ("2", ("x", 63))],
    },
    4: {
        "lead_coeff": 1,
        "ops": ["-", "+", "+"],
        "terms": [("46x", ("x", 87)), ("1x3", ("x", 87)), ("x7", ("x", 87)), ("2", ("x", 87))],
    },
    7: {
        "lead_coeff": 2,
        "ops": ["+", "-", "-"],
        "terms": [("46x", ("x", 65)), ("1x3", ("x", 65)), ("x7", ("x", 65)), ("2", ("x", 65))],
    },
    10: {
        "lead_coeff": 1,
        "ops": ["+", "-", "-"],
        "terms": [("41x", ("x", 81)), ("2x5", ("x", 81)), ("x3", ("x", 81)), ("2", ("x", 81))],
    },
}


def _t5_eval_num(digits: str, base, x: int) -> int:
    if isinstance(base, tuple):
        b = 10 * x + base[1]
    else:
        b = base
    val = 0
    for ch in digits:
        d = x if ch == "x" else int(ch)
        if d < 0 or d >= b:
            raise ValueError("invalid digit")
        val = val * b + d
    return val


def _t5_eval_complex(spec: dict, x: int) -> int:
    vals = [_t5_eval_num(d, b, x) for d, b in spec["terms"]]
    v = spec["lead_coeff"] * vals[0]
    for op, t in zip(spec["ops"], vals[1:]):
        if op == "+":
            v += t
        elif op == "-":
            v -= t
        elif op == "*":
            v *= t
    return v


def _t5_solve_complex(spec: dict) -> tuple[int, int]:
    for x in range(9, -1, -1):
        try:
            v = _t5_eval_complex(spec, x)
            if v > 0 and v % 99 == 0:
                return x, v // 99
        except ValueError:
            pass
    raise ValueError(f"no valid x for task5 complex {spec}")


def _t5_render_complex(spec: dict, x5: int, q5: int) -> dict:
    op_sym = {"+": "+", "-": "−", "*": "·"}
    html_parts: list[str] = []
    tex_parts: list[str] = []
    lead = spec["lead_coeff"]
    d0, b0 = spec["terms"][0]
    first_html = _t5_num_html(d0, b0)
    first_tex = _t5_num_tex(d0, b0)
    if lead != 1:
        html_parts.append(f"{lead} · {first_html}")
        tex_parts.append(f"{lead} \\cdot {first_tex}")
    else:
        html_parts.append(first_html)
        tex_parts.append(first_tex)
    for op, (digits, base) in zip(spec["ops"], spec["terms"][1:]):
        sym = op_sym[op]
        html_parts.append(f" {sym} {_t5_num_html(digits, base)}")
        tex_parts.append(f" {op} {_t5_num_tex(digits, base)}")
    return {
        "complex": True,
        "html": "".join(html_parts),
        "tex": "".join(tex_parts),
        "x5": x5,
        "q5": q5,
        "n_ops": len(spec["ops"]) + (1 if lead != 1 else 0),
    }


def _build_task5_simple_spec(d5: str, suf: int, last: int) -> dict:
    base_var = ("x", suf)
    base_terms = [(d5, base_var), (f"1x{last}", 100)]
    extra_terms = [
        ("x3", base_var),
        ("2x", base_var),
        ("x7", base_var),
        ("3x", base_var),
        ("x4", base_var),
        ("4x", base_var),
        ("x2", base_var),
        ("5x", base_var),
    ]
    ops_options = [
        ["+", "-", "+"],
        ["+", "+", "-"],
        ["-", "+", "+"],
        ["+", "-", "-"],
        ["-", "+", "-"],
        ["-", "-", "+"],
    ]
    best: tuple[int, int, dict] | None = None
    for ops in ops_options:
        for t2 in extra_terms:
            for t3 in extra_terms:
                if t2[0] == t3[0]:
                    continue
                spec = {"lead_coeff": 1, "ops": ops, "terms": [base_terms[0], base_terms[1], t2, t3]}
                try:
                    x5, q5 = _t5_solve_complex(spec)
                except ValueError:
                    continue
                score = (x5, q5)
                if best is None or score > (best[0], best[1]):
                    best = (x5, q5, spec)
    if best is None:
        raise ValueError(f"cannot build 3-op task5 for {d5}, x{suf}, {last}")
    return _t5_render_complex(best[2], best[0], best[1])


def _t5_num_html(digits: str, base) -> str:
    sub = f"x{base[1]}" if isinstance(base, tuple) else str(base)
    body = re.sub(r"x", "<em>x</em>", digits, count=1)
    return f"{body}<sub>{sub}</sub>"


def _t5_num_tex(digits: str, base) -> str:
    sub = f"x{base[1]}" if isinstance(base, tuple) else str(base)
    return f"{digits}_{{{sub}}}"


def build_task5(i: int) -> dict:
    if i in T5_COMPLEX:
        spec = T5_COMPLEX[i]
        x5, q5 = _t5_solve_complex(spec)
        return _t5_render_complex(spec, x5, q5)
    d5, suf, last, _, _ = TASK5[i]
    return _build_task5_simple_spec(d5, suf, last)

TASK6 = [
    {
        "desc": "наименьшую сумму двух соседних цифр",
        "code": """n = 85627413\nmn = 10\nwhile n >= 10:\n    a = n % 10\n    n = n // 10\n    b = n % 10\n    if a + b <= mn:\n        mn = a\nprint(mn)""",
        "errors": "`mn = 10` → `mn = 18`; `if a + b <= mn` → `if a + b < mn`; `mn = a` → `mn = a + b`",
    },
    {
        "desc": "наибольшую разность двух соседних цифр (по модулю)",
        "code": """n = 63829174\nmx = 0\nwhile n >= 10:\n    a = n % 10\n    n = n // 10\n    b = n % 10\n    if abs(a - b) >= mx:\n        mx = a - b\nprint(mx)""",
        "errors": "`mx = 0` → `mx = -1`; `>=` → `>`; `mx = a - b` → `mx = abs(a - b)`",
    },
    {
        "desc": "количество цифр, равных последней цифре числа",
        "code": """n = 52743525\nlast = n % 10\ncnt = 0\nwhile n:\n    if n % 10 == last:\n        cnt = cnt - 1\n    n = n // 10\nprint(cnt)""",
        "errors": "`cnt = cnt - 1` → `cnt = cnt + 1`; цикл должен сохранять `last` до изменения `n` (корректно); при отсутствии совпадений выводится отрицательное — логика верна после исправления знака",
    },
    {
        "desc": "наибольшее произведение двух соседних цифр",
        "code": """n = 47382916\nmx = 0\nwhile n >= 10:\n    a = n % 10\n    n = n // 10\n    b = n % 10\n    if a * b > mx:\n        mx = a + b\nprint(mx)""",
        "errors": "`mx = a + b` → `mx = a * b`",
    },
    {
        "desc": "сумму всех цифр числа",
        "code": """n = 91827364\ns = 1\nwhile n:\n    s = s + n % 10\n    n = n // 10\nprint(s)""",
        "errors": "`s = 1` → `s = 0`",
    },
    {
        "desc": "наибольшую цифру числа",
        "code": """n = 63829174\nmx = 9\nwhile n:\n    d = n % 10\n    if d > mx:\n        mx = d\n    n = n // 10\nprint(mx)""",
        "errors": "`mx = 9` → `mx = 0` (или `mx = -1`)",
    },
    {
        "desc": "количество чётных цифр числа",
        "code": """n = 84625173\ncnt = 0\nwhile n:\n    if n % 2 == 0:\n        cnt = cnt + 1\n    n = n // 10\nprint(cnt)""",
        "errors": "`n % 2 == 0` → `(n % 10) % 2 == 0`",
    },
    {
        "desc": "наименьшую цифру числа",
        "code": """n = 63829174\nmn = 0\nwhile n:\n    d = n % 10\n    if d < mn:\n        mn = d\n    n = n // 10\nprint(mn)""",
        "errors": "`mn = 0` → `mn = 9` (или `mn = 10`)",
    },
    {
        "desc": "количество цифр, больших 5",
        "code": """n = 63829174\ncnt = 0\nwhile n:\n    if n % 10 > 6:\n        cnt = cnt + 1\n    n = n // 10\nprint(cnt)""",
        "errors": "`> 6` → `> 5`",
    },
    {
        "desc": "наибольшую сумму двух соседних цифр",
        "code": """n = 85627413\nmx = 0\nwhile n > 10:\n    a = n % 10\n    n = n // 10\n    b = n % 10\n    if a + b > mx:\n        mx = a\nprint(mx)""",
        "errors": "`while n > 10` → `while n >= 10`; `mx = a` → `mx = a + b`",
    },
    {
        "desc": "произведение всех цифр числа",
        "code": """n = 20348\np = 0\nwhile n:\n    p = p * (n % 10)\n    n = n // 10\nprint(p)""",
        "errors": "`p = 0` → `p = 1`",
    },
    {
        "desc": "количество цифр 7 в числе",
        "code": """n = 7271737\ncnt = 0\nwhile n:\n    if n % 10 = 7:\n        cnt = cnt + 1\n    n = n // 10\nprint(cnt)""",
        "errors": "`n % 10 = 7` → `n % 10 == 7` (синтаксическая ошибка)",
    },
]

NAMES = [
    ("Миша", "Настя", "марок"),
    ("Артём", "Соня", "наклеек"),
    ("Коля", "Лена", "значков"),
    ("Паша", "Катя", "стикеров"),
    ("Игорь", "Маша", "значков"),
    ("Денис", "Алина", "наклеек"),
    ("Рома", "Вика", "марок"),
    ("Саша", "Юля", "стикеров"),
    ("Максим", "Оля", "значков"),
    ("Ваня", "Даша", "наклеек"),
    ("Кирилл", "Аня", "марок"),
    ("Пётр", "Ира", "стикеров"),
]

# ---------------------------------------------------------------------------
# Task 8 — корни уравнений (кубические и биквадратные, не квадратичные)
# ---------------------------------------------------------------------------

_X = sp.Symbol("x")
_SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _pow_html(n: int) -> str:
    if n == 0:
        return ""
    if n == 1:
        return "x"
    return "x" + str(n).translate(_SUP)


def _coeff_html(c) -> str:
    c = int(c) if c == int(c) else c
    if c == 1:
        return ""
    if c == -1:
        return "−"
    if c < 0:
        return f"−{abs(c)}"
    return str(c)


def _poly_terms(expr):
  poly = sp.Poly(sp.expand(expr), _X)
  return sorted(
      ((monom[0] if isinstance(monom, tuple) else monom, coeff) for monom, coeff in poly.as_dict().items()),
      reverse=True,
  )


def expr_to_html(expr) -> str:
    parts: list[str] = []
    for power, coeff in _poly_terms(expr):
        c = _coeff_html(coeff)
        if power == 0:
            if coeff < 0:
                aval = abs(int(coeff)) if coeff == int(coeff) else abs(coeff)
                chunk = f"− {aval}"
            else:
                chunk = str(int(coeff)) if coeff == int(coeff) else str(coeff)
        elif power == 1:
            if coeff < 0:
                aval = abs(int(coeff)) if coeff == int(coeff) else abs(coeff)
                chunk = f"− {aval}x"
            elif coeff == 1:
                chunk = "x"
            else:
                aval = int(coeff) if coeff == int(coeff) else coeff
                chunk = f"{aval}x"
        else:
            if coeff < 0:
                aval = abs(int(coeff)) if coeff == int(coeff) else abs(coeff)
                chunk = f"− {aval}{_pow_html(power)}"
            elif coeff == 1:
                chunk = _pow_html(power)
            else:
                aval = int(coeff) if coeff == int(coeff) else coeff
                chunk = f"{aval}{_pow_html(power)}"
        if not parts:
            parts.append(chunk.lstrip("+"))
        else:
            if str(chunk).startswith("−"):
                parts.append(" " + chunk)
            else:
                parts.append(" + " + chunk)
    return "".join(parts)


def expr_to_tex(expr) -> str:
    return sp.latex(expr, symbol_names={_X: "x"})


def _eval_term(coeff, power, x_reg="r4", dest="r5", exp_reg="r7") -> list[str]:
    """Вычислить coeff·x^power (x в x_reg) и записать в dest."""
    lines: list[str] = []
    c_abs = abs(int(coeff)) if coeff == int(coeff) else abs(coeff)
    if power == 0:
        val = int(coeff) if coeff == int(coeff) else coeff
        if coeff < 0:
            aval = abs(int(coeff)) if coeff == int(coeff) else abs(coeff)
            return [
                f"m {dest} 0",
                f"m {exp_reg} {aval}",
                f"- {dest} {exp_reg}",
            ]
        return [f"m {dest} {val}"]
    lines.append(f"m {dest} {x_reg}")
    if power > 1:
        lines.append(f"m {exp_reg} {power}")
        lines.append(f"^ {dest} {exp_reg}")
    if c_abs != 1:
        val = int(c_abs) if c_abs == int(c_abs) else c_abs
        lines.append(f"m {exp_reg} {val}")
        lines.append(f"* {dest} {exp_reg}")
    if coeff < 0:
        lines.append(f"m {exp_reg} 0")
        lines.append(f"- {exp_reg} {dest}")
        lines.append(f"m {dest} {exp_reg}")
    return lines


def gen_f_fragment(expr, x_cell: int = 0, out_cell: int = 1) -> str:
    """Фрагмент вычисления f(x): x берётся из w[x_cell], результат в w[out_cell]."""
    terms = _poly_terms(expr)
    lines = [f"mr r4 {x_cell}"]
    first = True
    for power, coeff in terms:
        lines += _eval_term(coeff, power)
        if first:
            lines.append("m r0 r5")
            first = False
        elif coeff >= 0:
            lines.append("+ r0 r5")
        else:
            lines.append("- r0 r5")
    lines.append(f"mw {out_cell} r0")
    return "\n".join(lines)


BISECTION_INIT_FRAGMENT = """mw 0 r1
mw 1 r2
mr r0 0
+ r0 r1
mr r4 1
+ r0 r4
m r7 2
/ r0 r7
mw 2 r0"""


def _exact_tex(root) -> str:
    return sp.latex(sp.simplify(root), symbol_names={_X: "x"})


def _exact_html(root) -> str:
    if root == int(root) and abs(root) < 10_000:
        return str(int(root))
    s = sp.latex(sp.simplify(root))
    return (
        s.replace("\\sqrt", "√")
        .replace("{", "")
        .replace("}", "")
        .replace("\\,", " ")
    )


# method, expr, numeric params, exact root (sympy), substitution note for answer key
# ≥7 задач с точным корнем через замену t = x² или t = x − k
TASK8_SPECS = [
    {
        "method": "bisection",
        "expr": _X**4 - 5 * _X**2 + 4,
        "a": 0.5, "b": 1.5, "eps": 0.001,
        "exact_root": sp.Integer(1),
        "substitution_tex": r"t = x^2 \Rightarrow t^2 - 5t + 4 = 0 \Rightarrow t \in \{1;\,4\} \Rightarrow x = \pm 1,\,\pm 2",
        "substitution_plain": "замена t = x² → t² − 5t + 4 = 0 → t = 1 или 4 → x = ±1, ±2",
    },
    {
        "method": "newton",
        "expr": _X**4 - 10 * _X**2 + 9,
        "x0": 0.8, "eps": 0.001, "max_iter": 20,
        "exact_root": sp.Integer(1),
        "substitution_tex": r"t = x^2 \Rightarrow t^2 - 10t + 9 = 0 \Rightarrow t \in \{1;\,9\} \Rightarrow x = \pm 1,\,\pm 3",
        "substitution_plain": "замена t = x² → t² − 10t + 9 = 0 → t = 1 или 9 → x = ±1, ±3",
    },
    {
        "method": "bisection",
        "expr": _X**4 + _X**2 - 6,
        "a": 1.3, "b": 1.5, "eps": 0.001,
        "exact_root": sp.sqrt(2),
        "substitution_tex": r"t = x^2 \Rightarrow t^2 + t - 6 = 0 \Rightarrow t = 2 \Rightarrow x = \pm\sqrt{2}",
        "substitution_plain": "замена t = x² → t² + t − 6 = 0 → t = 2 → x = ±√2",
    },
    {
        "method": "newton",
        "expr": _X**4 - 13 * _X**2 + 36,
        "x0": 1.5, "eps": 0.001, "max_iter": 20,
        "exact_root": sp.Integer(2),
        "substitution_tex": r"t = x^2 \Rightarrow t^2 - 13t + 36 = 0 \Rightarrow t \in \{4;\,9\} \Rightarrow x = \pm 2,\,\pm 3",
        "substitution_plain": "замена t = x² → t² − 13t + 36 = 0 → t = 4 или 9 → x = ±2, ±3",
    },
    {
        "method": "bisection",
        "expr": _X**3 - 6 * _X**2 + 11 * _X - 6,
        "a": 1.5, "b": 2.5, "eps": 0.001,
        "exact_root": sp.Integer(2),
        "substitution_tex": r"t = x - 2 \Rightarrow t^3 - t = 0 \Rightarrow t \in \{-1;\,0;\,1\} \Rightarrow x \in \{1;\,2;\,3\}",
        "substitution_plain": "замена t = x − 2 → t³ − t = 0 → t = −1, 0 или 1 → x = 1, 2 или 3",
    },
    {
        "method": "newton",
        "expr": _X**3 - 7 * _X + 6,
        "x0": 2.5, "eps": 0.001, "max_iter": 20,
        "exact_root": sp.Integer(2),
        "substitution_tex": r"t = x - 1 \Rightarrow t^3 + 3t^2 - 4t = 0 \Rightarrow t \in \{-4;\,0;\,1\} \Rightarrow x \in \{-3;\,1;\,2\}",
        "substitution_plain": "замена t = x − 1 → t³ + 3t² − 4t = 0 → t = −4, 0 или 1 → x = −3, 1 или 2",
    },
    {
        "method": "bisection",
        "expr": _X**4 - 4 * _X**2 + 3,
        "a": 0.5, "b": 1.5, "eps": 0.001,
        "exact_root": sp.Integer(1),
        "substitution_tex": r"t = x^2 \Rightarrow t^2 - 4t + 3 = 0 \Rightarrow t \in \{1;\,3\} \Rightarrow x = \pm 1,\,\pm\sqrt{3}",
        "substitution_plain": "замена t = x² → t² − 4t + 3 = 0 → t = 1 или 3 → x = ±1, ±√3",
    },
    {
        "method": "newton",
        "expr": _X**4 - 8 * _X**2 + 15,
        "x0": 1.5, "eps": 0.001, "max_iter": 20,
        "exact_root": sp.sqrt(3),
        "substitution_tex": r"t = x^2 \Rightarrow t^2 - 8t + 15 = 0 \Rightarrow t \in \{3;\,5\} \Rightarrow x = \pm\sqrt{3},\,\pm\sqrt{5}",
        "substitution_plain": "замена t = x² → t² − 8t + 15 = 0 → t = 3 или 5 → x = ±√3, ±√5",
    },
    # без точной замены — только численный корень
    {"method": "bisection", "expr": _X**3 - 3 * _X - 1, "a": 1, "b": 2, "eps": 0.001},
    {"method": "newton", "expr": _X**3 - 2 * _X - 5, "x0": 2.5, "eps": 0.001, "max_iter": 20},
    {"method": "bisection", "expr": _X**4 - 3 * _X - 1, "a": 1, "b": 2, "eps": 0.001},
    {"method": "newton", "expr": _X**4 - 2 * _X - 1, "x0": 1.6, "eps": 0.001, "max_iter": 20},
]


def _task8_answer_meta(spec: dict, num_root: float) -> dict:
    approx = _fmt_num(round(num_root, 3))
    if "exact_root" not in spec:
        return {
            "has_substitution": False,
            "answer": f"$\\approx {approx}$",
            "answer_key": f"$\\approx {approx}$",
            "answer_note": f"корень $\\approx {approx}$ (численно); массив $w[]$",
            "numerical_note": f"программа: $\\approx {approx}$",
        }
    exact = sp.simplify(spec["exact_root"])
    exact_tex = _exact_tex(exact)
    return {
        "has_substitution": True,
        "exact_root_tex": exact_tex,
        "exact_root_html": _exact_html(exact),
        "substitution_tex": spec["substitution_tex"],
        "substitution_plain": spec["substitution_plain"],
        "answer": f"${exact_tex}$",
        "answer_key": f"${exact_tex}$ (${spec['substitution_plain']}; программа $\\approx {approx}$)",
        "answer_note": (
            f"точный корень ${exact_tex}$; {spec['substitution_plain']}; "
            f"программа $\\approx {approx}$"
        ),
        "numerical_note": f"программа: $\\approx {approx}$",
    }


def build_task8(spec: dict) -> dict:
    expr = sp.expand(spec["expr"])
    eq_html = expr_to_html(expr)
    eq_tex = expr_to_tex(expr)
    method = spec["method"]
    common = {
        "eq_html": eq_html,
        "eq_tex": eq_tex,
        "f_html": f"f(x) = {eq_html}",
        "f_tex": f"f(x)={eq_tex}",
    }

    if method == "bisection":
        a, b, eps = spec["a"], spec["b"], spec["eps"]
        fa, fb = float(expr.subs(_X, a)), float(expr.subs(_X, b))
        if fa * fb >= 0:
            raise ValueError(f"bisection interval [{a}, {b}] has no sign change for {expr}")
        root = float(sp.nsolve(expr, _X, (a + b) / 2))
        meta = _task8_answer_meta(spec, root)
        return {
            **common,
            **meta,
            "method": method,
            "method_title": "методом половинного деления",
            "interval": (a, b),
            "interval_str": f"[{_fmt_num(a)}; {_fmt_num(b)}]",
            "eps": eps,
            "r1": a,
            "r2": b,
            "r3": eps,
            "r1_desc": f"левая граница отрезка ({_fmt_num(a)})",
            "r2_desc": f"правая граница отрезка ({_fmt_num(b)})",
            "r3_desc": f"требуемая точность ε ({_fmt_num(eps)})",
            "output_desc": "приближённое значение корня в регистре r5",
            "cells_html": (
                "<em>w</em>[0] — левая граница, <em>w</em>[1] — правая граница, "
                "<em>w</em>[2] — середина, <em>w</em>[3] — значение <em>f</em>(середина)"
            ),
            "cells_tex": (
                "$w[0]$ — левая граница, $w[1]$ — правая, $w[2]$ — середина, "
                "$w[3]$ — $f$(середина)"
            ),
            "requirements": [
                "Промежуточные значения (границы, середина, значения функции) храните в массиве памяти w[0], w[1], … — не в стеке.",
                "На каждой итерации обновляйте w[0], w[1], w[2], w[3].",
                "Итерации выполняйте, пока |w[1] − w[0]| > ε.",
            ],
            "requirements_html": [
                "Промежуточные значения (границы, середина, значения функции) храните в "
                "<strong>массиве памяти</strong> <em>w</em>[0], <em>w</em>[1], … — не в стеке.",
                "На каждой итерации обновляйте <em>w</em>[0], <em>w</em>[1], <em>w</em>[2], <em>w</em>[3].",
                "Итерации выполняйте, пока |<em>w</em>[1] − <em>w</em>[0]| &gt; ε.",
            ],
            "fragment": BISECTION_INIT_FRAGMENT,
            "fragment_note": "инициализация границ отрезка и вычисление середины",
            "f_fragment": gen_f_fragment(expr, x_cell=2, out_cell=3),
            "f_fragment_note": "вычисление f(x) в середине отрезка (x = w[2])",
        }

    x0, eps, max_iter = spec["x0"], spec["eps"], spec["max_iter"]
    root = float(sp.nsolve(expr, _X, x0))
    meta = _task8_answer_meta(spec, root)
    return {
        **common,
        **meta,
        "method": method,
        "method_title": "методом Ньютона",
        "x0": x0,
        "eps": eps,
        "max_iter": max_iter,
        "r1": x0,
        "r2": eps,
        "r3": max_iter,
        "r1_desc": f"начальное приближение ({_fmt_num(x0)})",
        "r2_desc": f"требуемая точность ε ({_fmt_num(eps)})",
        "r3_desc": f"максимальное число итераций ({max_iter})",
        "output_desc": "приближённое значение корня в регистре r5",
        "cells_html": (
            "<em>w</em>[0] — текущее <em>x</em>, <em>w</em>[1] — <em>f</em>(<em>x</em>), "
            "<em>w</em>[2] — <em>f</em>′(<em>x</em>), <em>w</em>[3] — новое приближение"
        ),
        "cells_tex": (
            "$w[0]$ — текущее $x$, $w[1]$ — $f(x)$, $w[2]$ — $f'(x)$, $w[3]$ — новое $x$"
        ),
        "requirements": [
            "На каждой итерации храните в массиве памяти w[] значения x, f(x), f′(x) и новое приближение — не в стеке.",
            "Обновляйте как минимум w[0]–w[3] на каждом шаге.",
            "Остановка: |f(x)| < ε или достигнут лимит итераций r3.",
        ],
        "requirements_html": [
            "На каждой итерации храните в <strong>массиве памяти</strong> <em>w</em>[] значения "
            "<em>x</em>, <em>f</em>(<em>x</em>), <em>f</em>′(<em>x</em>) и новое приближение — не в стеке.",
            "Обновляйте как минимум <em>w</em>[0]–<em>w</em>[3] на каждом шаге.",
            "Остановка: |<em>f</em>(<em>x</em>)| &lt; ε или достигнут лимит итераций <em>r</em>3.",
        ],
        "fragment": "mw 0 r1",
        "fragment_note": "запись начального приближения в w[0]",
        "f_fragment": gen_f_fragment(expr, x_cell=0, out_cell=1),
        "f_fragment_note": "вычисление f(x) при x = w[0]",
    }


EXCHANGE_FRAC = [
    ("одна пятая", "одна треть", sp.Rational(1, 5), sp.Rational(1, 3)),
    ("одна четвёртая", "одна треть", sp.Rational(1, 4), sp.Rational(1, 3)),
    ("одна четвёртая", "одна треть", sp.Rational(1, 4), sp.Rational(1, 3)),
    ("одна четвёртая", "одна треть", sp.Rational(1, 4), sp.Rational(1, 3)),
    ("одна четвёртая", "одна пятая", sp.Rational(1, 4), sp.Rational(1, 5)),
    ("одна шестая", "одна четвёртая", sp.Rational(1, 6), sp.Rational(1, 4)),
    ("одна четвёртая", "одна треть", sp.Rational(1, 4), sp.Rational(1, 3)),
    ("одна четвёртая", "одна треть", sp.Rational(1, 4), sp.Rational(1, 3)),
    ("одна пятая", "одна треть", sp.Rational(1, 5), sp.Rational(1, 3)),
    ("одна четвёртая", "одна треть", sp.Rational(1, 4), sp.Rational(1, 3)),
    ("одна четвёртая", "одна треть", sp.Rational(1, 4), sp.Rational(1, 3)),
    ("одна четвёртая", "одна треть", sp.Rational(1, 4), sp.Rational(1, 3)),
]

EXCHANGE_DATA = [
    (980, 490, 1310, 111),
    (720, 490, 924, 261),
    (800, 550, 1004, 321),
    (760, 520, 964, 291),
    (840, 560, 440, 939),
    (770, 560, 440, 939),
    (840, 580, 1044, 351),
    (880, 610, 1084, 381),
    (910, 455, 1310, 111),
    (920, 640, 1124, 411),
    (960, 620, 1368, 162),
    (720, 590, 516, 819),
]


def _variant_indices(num: int) -> dict[str, int]:
    """Pick task indices; variants 17+ are new mixes."""
    i = num - 5
    if i < 12:
        return {
            "t1": i, "t2": i, "t3": i, "t4": i,
            "t5": i, "t6": i, "t7": i, "t8": i,
        }
    base = i % 12
    return {
        "t1": base,
        "t2": (base + 4) % 12,
        "t3": (base + 6) % 12,
        "t4": (base + 8) % 12,
        "t5": (base + 3) % 12,
        "t6": (base + 5) % 12,
        "t7": (base + 7) % 12,
        "t8": (base + 9) % 12,
    }


def build_variant(num: int) -> dict:
    idx = _variant_indices(num)
    i4 = idx["t4"]
    t1_tex, t1_html, t1_ans = task1_answer(TASK1_SPECS[idx["t1"]])
    a2 = TASK2_A[idx["t2"]]
    t2_ans = task2_count(a2)
    t3_text, t3_ans = TASK3[idx["t3"]]
    fp, fk, p2t, k3t, p0, k0 = TASK4[i4]
    # fix degenerate task4 entries
    if p0 == p2t and k0 == k3t and fp == sp.Rational(1, 5) and fk == sp.Rational(2, 7):
        p2t, k3t, p0, k0 = 875, 525, 1310, 111
    if p0 == p2t and fp == sp.Rational(1, 6):
        p2t, k3t, p0, k0 = 770, 560, 440, 939
    t5 = build_task5(idx["t5"])
    t6 = TASK6[idx["t6"]]
    reg = REGION_CONFIGS[idx["t7"]]
    t8 = build_task8(TASK8_SPECS[idx["t8"]])
    n1, n2, item = NAMES[i4]
    ef1, ef2, _, _ = EXCHANGE_FRAC[i4]
    p2t, k3t, p0, k0 = EXCHANGE_DATA[i4]

  # verify region tests
    ty, tn = reg["test_yes"], reg["test_no"]
    assert in_region(*ty, reg)
    assert not in_region(*tn, reg)

    return {
        "num": num,
        "t1_tex": t1_tex,
        "t1_html": t1_html,
        "t1_ans": t1_ans,
        "t2_a": a2,
        "t2_ans": t2_ans,
        "t3_text": t3_text,
        "t3_ans": t3_ans,
        "t4": (n1, n2, item, ef1, ef2, p2t, k3t, p0, k0),
        "t5": t5,
        "t6": t6,
        "t7": reg,
        "t7_svg": make_svg(reg),
        "t8": t8,
    }


def task8_answer_row(t8: dict) -> str:
    if t8.get("has_substitution"):
        return f"{t8['answer']}; {t8['substitution_plain']}; {t8['numerical_note']}"
    return t8["answer"]


def task8_answer_key_cell(t8: dict) -> str:
    if t8.get("has_substitution"):
        return t8["exact_root_tex"]
    return t8["answer"].replace("$", "")


def task8_problem_html(t8: dict) -> str:
    if t8["method"] == "bisection":
        return (
            f"<p>Разработайте программу для исполнителя «Сириус», которая "
            f"<strong>{t8['method_title']}</strong> находит приближённый корень уравнения "
            f"<em>{t8['f_html']}</em> = 0 на отрезке {t8['interval_str']} "
            f"с точностью ε = {_fmt_num(t8['eps'])}.</p>"
        )
    return (
        f"<p>Разработайте программу для исполнителя «Сириус», которая "
        f"<strong>{t8['method_title']}</strong> находит приближённый корень уравнения "
        f"<em>{t8['f_html']}</em> = 0 с точностью ε = {_fmt_num(t8['eps'])}.</p>"
    )


def task8_io_html(t8: dict) -> str:
    return (
        f"<p><strong>Вход:</strong> <em>r</em>1 — {t8['r1_desc']}, "
        f"<em>r</em>2 — {t8['r2_desc']}, <em>r</em>3 — {t8['r3_desc']}.<br>"
        f"<strong>Выход:</strong> {t8['output_desc']}.</p>"
    )


def task8_requirements_html(t8: dict) -> str:
    items = "".join(f"<li>{req}</li>" for req in t8["requirements_html"])
    return (
        f'<p class="isa-note"><strong>Обязательно:</strong><ol style="margin:2mm 0 0 5mm;padding:0;">'
        f"{items}</ol></p>"
    )


def task8_md_body(t8: dict) -> str:
    if t8["method"] == "bisection":
        intro = (
            f"Разработайте программу для исполнителя «Сириус», которая **{t8['method_title']}** "
            f"находит приближённый корень уравнения\n\n"
            f"$${t8['f_tex']}=0$$\n\n"
            f"на отрезке ${t8['interval_str'].replace(';', ';\\,')}$ с точностью "
            f"$\\varepsilon={str(t8['eps']).replace('.', '{,}')}$."
        )
    else:
        intro = (
            f"Разработайте программу для исполнителя «Сириус», которая **{t8['method_title']}** "
            f"находит приближённый корень уравнения\n\n"
            f"$${t8['f_tex']}=0$$\n\n"
            f"с точностью $\\varepsilon={str(t8['eps']).replace('.', '{,}')}$."
        )
    reqs = "\n".join(f"{i}. {r}" for i, r in enumerate(t8["requirements"], 1))
    frag2 = ""
    if t8["f_fragment"] != t8["fragment"]:
        frag2 = f"\n*Вычисление $f(x)$ ({t8['f_fragment_note']}):*\n\n```\n{t8['f_fragment']}\n```\n"
    return f"""{intro}

**Вход:** $r1$ — {t8['r1_desc']}; $r2$ — {t8['r2_desc']}; $r3$ — {t8['r3_desc']}.

**Выход:** {t8['output_desc'].replace('r5', '$r5$')}.

**Требования:**

{reqs}

{t8['cells_tex']}

### Команды регистров ($r0$–$r7$)

| Символ | Действие | Пример | Результат |
|--------|----------|--------|-----------|
| $m$ | присвоение | `m r0 2.5` | $r0 = 2{{,}}5$ |
| $+$ | сложение | `+ r0 r1` | $r0 = r0 + r1$ |
| $-$ | вычитание | `- r1 r2` | $r1 = r1 - r2$ |
| $*$ | умножение | `* r2 r0` | $r2 = r2 \\cdot r0$ |
| $/$ | деление | `/ r3 r2` | $r3 = r3 / r2$ |
| $^$ | степень | `^ r4 r1` | $r4 = r4^{{r1}}$ |

### Команды массива памяти $w[0]$–$w[9]$

| Команда | Действие | Пример | Результат |
|---------|----------|--------|-----------|
| `mw` | запись | `mw 0 r1` | $w[0] = r1$ |
| `mr` | чтение | `mr r4 2` | $r4 = w[2]$ |
| `+w −w *w /w` | арифметика | `+w 0 r4` | $w[0] = w[0] + r4$ |

*Пример фрагмента ({t8['fragment_note']}):*

```
{t8['fragment']}
```
{frag2}"""


CSS = """
@page { size: A4; margin: 16mm 14mm 18mm 14mm; }
* { box-sizing: border-box; }
body {
  font-family: "Times New Roman", Times, serif;
  font-size: 12pt; line-height: 1.4; color: #111;
  max-width: 210mm; margin: 0 auto; padding: 10mm 12mm; background: #fff;
}
.doc-header { border-bottom: 2px solid #1a3a5c; padding-bottom: 5mm; margin-bottom: 6mm; }
h1 { font-size: 13pt; text-align: center; margin: 0 0 3mm; color: #1a3a5c; }
.subtitle { text-align: center; font-size: 11pt; margin: 0; }
.meta { width: 100%; border-collapse: collapse; margin: 5mm 0 6mm; font-size: 11pt; }
.meta td { border: 1px solid #333; padding: 3mm 4mm; }
.meta .label { width: 30%; font-weight: bold; background: #f0f4f8; }
.meta .field { min-height: 9mm; }
.info-box {
  border: 1px solid #bbb; background: #f8fafc; padding: 4mm 5mm;
  font-size: 10.5pt; margin-bottom: 6mm; border-radius: 2px;
}
.task { margin-bottom: 6mm; page-break-inside: avoid; }
.task-head {
  display: flex; align-items: baseline; gap: 3mm;
  border-left: 4px solid #1a5fb4; padding-left: 3mm; margin-bottom: 2mm;
}
.task-num { font-weight: bold; font-size: 12pt; }
.task-pts { font-size: 10pt; color: #555; }
.task-body p { margin: 2mm 0; }
.formula {
  margin: 3mm 0; padding: 3mm 4mm; text-align: center;
  background: #fafbfc; border: 1px solid #ddd; font-size: 12pt;
}
.answer-box {
  border: 1px solid #333; min-height: 13mm; margin-top: 3mm; padding: 2mm 3mm 2mm 12mm;
  position: relative; background: #fff;
}
.answer-box::before {
  content: "Ответ"; position: absolute; left: 0; top: 0; bottom: 0; width: 10mm;
  background: #eef2f6; border-right: 1px solid #333;
  display: flex; align-items: center; justify-content: center;
  font-size: 8.5pt; font-weight: bold; writing-mode: vertical-rl; transform: rotate(180deg);
}
.answer-box.tall { min-height: 26mm; }
.answer-box.xtall { min-height: 40mm; }
.solution-space {
  border: 1px dashed #999; min-height: 32mm; margin-top: 3mm;
  background: repeating-linear-gradient(0deg, transparent, transparent 7mm, #f5f5f5 7mm, #f5f5f5 7.4mm);
}
.solution-space.medium { min-height: 48mm; }
.solution-space.large { min-height: 64mm; }
.solution-label { font-size: 9pt; color: #666; margin-top: 2mm; }
pre.code {
  font-family: "Courier New", monospace; font-size: 9.5pt;
  border: 1px solid #ccc; background: #f7f7f7; padding: 3mm 4mm;
  margin: 3mm 0; line-height: 1.3; overflow-x: auto;
  text-align: left; white-space: pre; display: block; width: 100%;
}
table.examples { border-collapse: collapse; margin: 3mm auto; font-size: 11pt; }
table.examples th, table.examples td { border: 1px solid #333; padding: 2mm 6mm; }
table.examples th { background: #eef2f6; }
.figure { margin: 4mm 0; page-break-inside: avoid; }
.figure-graph { text-align: center; }
.figure-graph svg { max-width: 100%; height: auto; }
.figure-code { text-align: left; }
.figure-code pre.code { margin-left: 0; margin-right: 0; }
.figure-caption { font-size: 10pt; margin-top: 2mm; font-style: italic; text-align: center; }
.isa-note {
  border: 1px solid #bbb; background: #f8fafc; padding: 3mm 4mm;
  font-size: 10.5pt; margin: 3mm 0; border-radius: 2px; line-height: 1.4;
}
table.examples-left { text-align: left; }
table.examples-left th { text-align: center; }
.page-break { page-break-before: always; }
.footer { margin-top: 6mm; padding-top: 3mm; border-top: 1px solid #ccc; font-size: 9pt; text-align: center; color: #666; }
.no-print { text-align: center; font-family: sans-serif; font-size: 10pt; color: #666; margin-bottom: 4mm; }
@media print { body { padding: 0; } .no-print { display: none; } }
"""


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_blank(v: dict) -> str:
    n = v["num"]
    n1, n2, item, ef1, ef2, p2t, k3t, p0, k0 = v["t4"]
    t5 = v["t5"]
    reg = v["t7"]
    ty, tn = reg["test_yes"], reg["test_no"]
    t6 = v["t6"]
    t8 = v["t8"]

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Вариант {n} — бланк письменного экзамена</title>
  <style>{CSS}</style>
</head>
<body>
  <p class="no-print">Печать: <strong>Ctrl+P</strong> → A4, масштаб 100%, включить «Фоновая графика».</p>

  <div class="doc-header">
    <h1>АНОО ВО «Университет «Сириус»</h1>
    <p class="subtitle">Письменный экзамен — <strong>Вариант {n}</strong><br>
    Специальность: «Проектирование, разработка и управление сложными информационными системами»</p>
  </div>

  <table class="meta">
    <tr><td class="label">Фамилия, имя, отчество</td><td class="field" colspan="3"></td></tr>
    <tr>
      <td class="label">Класс / группа</td><td class="field" style="width:22%"></td>
      <td class="label" style="width:16%">Дата</td><td class="field" style="width:22%"></td>
    </tr>
  </table>

  <div class="info-box">
    <strong>Время:</strong> 180 минут. Задания 1–6 — на бумаге; 7–8 — на компьютере (Python).<br>
    Задания 1, 2, 5, 6 — по 10 баллов; 3, 4 — по 15; 7, 8 — по 15.
  </div>

  <div class="task">
    <div class="task-head"><span class="task-num">Задание 1</span><span class="task-pts">(10 баллов)</span></div>
    <div class="task-body">
      <p>Найдите значение выражения (запишите ход решения).</p>
      <div class="formula">{v['t1_html']}</div>
      <p class="solution-label">Решение:</p><div class="solution-space"></div>
      <div class="answer-box"><div></div></div>
    </div>
  </div>

  <div class="task">
    <div class="task-head"><span class="task-num">Задание 2</span><span class="task-pts">(10 баллов)</span></div>
    <div class="task-body">
      <p>Найдите <strong>количество целых</strong> значений <em>x</em>:</p>
      <div class="formula">√({v['t2_a']}(x + 1)² − 1) &gt; √({v['t2_a']} − (x − 1)²)</div>
      <p class="solution-label">Решение:</p><div class="solution-space medium"></div>
      <div class="answer-box"></div>
    </div>
  </div>

  <div class="task">
    <div class="task-head"><span class="task-num">Задание 3</span><span class="task-pts">(15 баллов)</span></div>
    <div class="task-body">
      <p>{v['t3_text'].replace('$', '')}</p>
      <p class="solution-label">Решение:</p><div class="solution-space large"></div>
      <div class="answer-box"></div>
    </div>
  </div>

  <div class="page-break"></div>

  <div class="task">
    <div class="task-head"><span class="task-num">Задание 4</span><span class="task-pts">(15 баллов)</span></div>
    <div class="task-body">
      <p>{n1} и {n2} три раза обменивались {item}. Каждый раз {ef1} часть {item} {n1}а
      менялась на {ef2} {item} {n2}ы. Сколько {item} было изначально, если после второго обмена
      у {n1}а осталось {p2t}, а после третьего у {n2}ы — {k3t}?</p>
      <p class="solution-label">Решение:</p><div class="solution-space large"></div>
      <div class="answer-box tall"></div>
    </div>
  </div>

  <div class="task">
    <div class="task-head"><span class="task-num">Задание 5</span><span class="task-pts">(10 баллов)</span></div>
    <div class="task-body">
      <p>В выражении {t5['html']} (<em>x</em> — цифра):</p>
      <p>а) наибольшее <em>x</em>, при котором значение кратно 99;<br>
      б) частное при этом <em>x</em>. <em>Ответ в десятичной системе.</em></p>
      <p class="solution-label">Решение:</p><div class="solution-space medium"></div>
      <div class="answer-box">а) &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; б)</div>
    </div>
  </div>

  <div class="task">
    <div class="task-head"><span class="task-num">Задание 6</span><span class="task-pts">(10 баллов)</span></div>
    <div class="task-body">
      <p>Программа должна выводить <strong>{t6['desc']}</strong>. Найдите ошибки (рис. а).</p>
      <p>а) Укажите ошибки. б) Исправленные строки.</p>
      <div class="figure figure-code"><pre class="code">{html_escape(t6['code'])}</pre><div class="figure-caption">Рис. а</div></div>
      <p class="solution-label">Решение:</p><div class="solution-space medium"></div>
      <div class="answer-box xtall"></div>
    </div>
  </div>

  <div class="page-break"></div>

  <div class="task">
    <div class="task-head"><span class="task-num">Задание 7</span><span class="task-pts">(15 баллов, компьютер)</span></div>
    <div class="task-body">
      <p>Графики: <em>{reg['labels'][0]}</em>, <em>{reg['labels'][1]}</em>, <em>{reg['labels'][2]}</em>.
      Закрашенные области — рис. б. Программа: точка (<em>x</em>, <em>y</em>) в одной из областей? → <code>YES</code>/<code>NO</code>.</p>
      <table class="examples">
        <tr><th>Ввод</th><th>Вывод</th></tr>
        <tr><td>{ty[0]} &nbsp; {ty[1]}</td><td>YES</td></tr>
        <tr><td>{tn[0]} &nbsp; {tn[1]}</td><td>NO</td></tr>
      </table>
      <div class="figure figure-graph">{v['t7_svg']}<div class="figure-caption">Рис. б — закрашенные области (A — YES, B — NO)</div></div>
    </div>
  </div>

  <div class="task">
    <div class="task-head"><span class="task-num">Задание 8</span><span class="task-pts">(15 баллов, компьютер)</span></div>
    <div class="task-body">
      {task8_problem_html(t8)}
      {task8_io_html(t8)}
      <p>Назначение ячеек массива: {t8['cells_html']}.</p>
      {task8_requirements_html(t8)}

      <table class="examples examples-left" style="width:100%;font-size:10pt">
        <tr><th colspan="4">Команды регистров (r0–r7)</th></tr>
        <tr><th>Символ</th><th>Действие</th><th>Пример</th><th>Результат</th></tr>
        <tr><td><em>m</em></td><td>присвоение</td><td><code>m r0 2.5</code></td><td>r0 = 2,5</td></tr>
        <tr><td><em>+ − * / ^</em></td><td>арифметика</td><td><code>+ r0 r1</code></td><td>r0 = r0 + r1</td></tr>
        <tr><th colspan="4">Команды массива памяти w[0]–w[9]</th></tr>
        <tr><td><code>mw</code></td><td>запись</td><td><code>mw 0 r1</code></td><td>w[0] = r1</td></tr>
        <tr><td><code>mr</code></td><td>чтение</td><td><code>mr r4 2</code></td><td>r4 = w[2]</td></tr>
        <tr><td><code>+w −w *w /w</code></td><td>арифметика</td><td><code>+w 0 r4</code></td><td>w[0] = w[0] + r4</td></tr>
      </table>

      <p><em>Пример фрагмента ({t8['fragment_note']}):</em></p>
      <pre class="code">{html_escape(t8['fragment'])}</pre>
      <p><em>Пример вычисления f(x) ({t8['f_fragment_note']}):</em></p>
      <pre class="code">{html_escape(t8['f_fragment'])}</pre>
      <p class="solution-label">Программа:</p><div class="solution-space large"></div>
    </div>
  </div>

  <div class="footer">Вариант {n} · АНОО ВО «Университет «Сириус» · Лист ___ из ___</div>
</body>
</html>"""


def render_md(v: dict) -> str:
    n = v["num"]
    n1, n2, item, ef1, ef2, p2t, k3t, p0, k0 = v["t4"]
    t5 = v["t5"]
    reg = v["t7"]
    ty, tn = reg["test_yes"], reg["test_no"]
    t6, t8 = v["t6"], v["t8"]

    return f"""# Вариант {n} — письменный экзамен

**Специальность:** «Проектирование, разработка и управление сложными информационными системами»  
**Время:** 180 минут  
**Задания 1–6** — на бумаге, **задания 7–8** — на компьютере (Python).

---

## Задание 1 (10 баллов)

$${v['t1_tex']}$$

---

## Задание 2 (10 баллов)

$$\\sqrt{{{v['t2_a']}(x+1)^2-1}}>\\sqrt{{{v['t2_a']}-(x-1)^2}}$$

---

## Задание 3 (15 баллов)

{v['t3_text']}

---

## Задание 4 (15 баллов)

{n1} и {n2} три раза обменивались {item}. Каждый раз {ef1} часть {item} {n1}а менялась на {ef2} {item} {n2}ы. Сколько {item} было изначально, если после второго обмена у {n1}а осталось {p2t}, а после третьего обмена у {n2}ы осталось {k3t}?

---

## Задание 5 (10 баллов)

В выражении ${t5['tex']}$:

а) наибольшее $x$ при кратности 99; б) частное. *Ответ в десятичной системе.*

---

## Задание 6 (10 баллов)

Программа должна выводить **{t6['desc']}**. Найдите ошибки:

```python
{t6['code']}
```

---

## Задание 7 (15 баллов)

Графики: {', '.join(reg['labels'])}. Закрашенные области (см. `variant-{n}-blank.html`, рис. б).

| Ввод | Вывод |
|------|-------|
| {ty[0]} {ty[1]} | YES |
| {tn[0]} {tn[1]} | NO |

---

## Задание 8 (15 баллов)

{task8_md_body(t8)}

---

## Ответы

| № | Ответ |
|---|-------|
| 1 | ${v['t1_ans']}$ |
| 2 | ${v['t2_ans']}$ |
| 3 | {v['t3_ans']} |
| 4 | {n1} — ${p0}$, {n2} — ${k0}$ |
| 5а | ${t5['x5']}$ |
| 5б | ${t5['q5']}$ |
| 6 | {t6['errors']} |
| 7 | см. условия выше |
| 8 | {task8_answer_row(t8)} |
"""


def main():
    variants = []
    for num in range(5, 19):
        try:
            v = build_variant(num)
            variants.append(v)
        except Exception as e:
            raise RuntimeError(f"variant {num}: {e}") from e

        (OUT / f"variant-{num}.md").write_text(render_md(v), encoding="utf-8")
        (OUT / f"variant-{num}-blank.html").write_text(render_blank(v), encoding="utf-8")
        print(f"variant-{num} OK  t1={v['t1_ans']} t2={v['t2_ans']}")

    # answers key
    lines = ["# Ключ ответов (варианты 5–18)\n", "| Вар. | 1 | 2 | 3 | 4 | 5а | 5б | 8 |", "|------|---|---|---|---|----|----|---|"]
    for v in variants:
        n1, n2, _, _, _, _, _, p0, k0 = v["t4"]
        x5, q5 = v["t5"]["x5"], v["t5"]["q5"]
        lines.append(
            f"| {v['num']} | {v['t1_ans']} | {v['t2_ans']} | {v['t3_ans'].replace('$','')} | {p0}/{k0} | {x5} | {q5} | {task8_answer_key_cell(v['t8'])} |"
        )
    lines += [
        "",
        "## Задание 8 — точные корни (метод замены)",
        "",
        "| Вар. | Искомый корень | Замена | Программа (r5) |",
        "|------|----------------|--------|----------------|",
    ]
    for v in variants:
        t8 = v["t8"]
        if t8.get("has_substitution"):
            lines.append(
                f"| {v['num']} | ${t8['exact_root_tex']}$ | {t8['substitution_plain']} | {t8['numerical_note'].replace('$', '')} |"
            )
        else:
            lines.append(f"| {v['num']} | — | численно | {t8['answer'].replace('$', '')} |")
    key_text = "\n".join(lines)
    (OUT / "answers-key-5-18.md").write_text(key_text, encoding="utf-8")
    (OUT / "answers-key-5-16.md").write_text(key_text, encoding="utf-8")
    print("done")


if __name__ == "__main__":
    main()

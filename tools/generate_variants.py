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

def in_region(x: float, y: float, cfg: dict) -> bool:
    lo = max(fn(x) for fn in cfg["lower_fns"])
    hi = min(fn(x) for fn in cfg["upper_fns"])
    return lo - 1e-9 <= y <= hi + 1e-9


def find_region_polygon(cfg: dict, n: int = 400) -> list[tuple[float, float]]:
    x_lo, x_hi = cfg["x_range"]
    xs = []
    x = x_lo
    step = (x_hi - x_lo) / n
    while x <= x_hi + 1e-9:
        lo = max(fn(x) for fn in cfg["lower_fns"])
        hi = min(fn(x) for fn in cfg["upper_fns"])
        if lo <= hi:
            xs.append(x)
        x += step
    if not xs:
        return []
    upper_pts = [(x, min(fn(x) for fn in cfg["upper_fns"])) for x in xs]
    lower_pts = [(x, max(fn(x) for fn in cfg["lower_fns"])) for x in reversed(xs)]
    return upper_pts + lower_pts


def make_svg(cfg: dict, width: int = 420, height: int = 360) -> str:
    x_min, x_max = cfg["plot_x"]
    y_min, y_max = cfg["plot_y"]
    margin_l, margin_r, margin_t, margin_b = 48, 24, 28, 44
    pw = width - margin_l - margin_r
    ph = height - margin_t - margin_b

    def tx(x):
        return margin_l + (x - x_min) / (x_max - x_min) * pw

    def ty(y):
        return margin_t + (y_max - y) / (y_max - y_min) * ph

    def curve_path(fn, x0, x1, steps=120):
        pts = []
        for i in range(steps + 1):
            x = x0 + (x1 - x0) * i / steps
            y = fn(x)
            if y_min - 1 <= y <= y_max + 1:
                pts.append((tx(x), ty(y)))
        if len(pts) < 2:
            return ""
        d = f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"
        for px, py in pts[1:]:
            d += f" L {px:.1f} {py:.1f}"
        return d

    poly = find_region_polygon(cfg)
    if poly:
        pd = " ".join(f"{'L' if i else 'M'} {tx(x):.1f} {ty(y):.1f}" for i, (x, y) in enumerate(poly))
        shade = f'<path d="{pd} Z" fill="#b8d4f0" fill-opacity="0.85" stroke="#2c5f8a" stroke-width="1.2"/>'
    else:
        shade = ""

    # grid
    grid = []
    for xi in range(math.ceil(x_min), math.floor(x_max) + 1):
        grid.append(
            f'<line x1="{tx(xi):.1f}" y1="{margin_t}" x2="{tx(xi):.1f}" y2="{margin_t+ph}" stroke="#e0e0e0" stroke-width="1"/>'
        )
        if xi != 0:
            grid.append(
                f'<text x="{tx(xi):.1f}" y="{margin_t+ph+16}" text-anchor="middle" font-size="11" fill="#333">{xi}</text>'
            )
    for yi in range(math.ceil(y_min), math.floor(y_max) + 1):
        grid.append(
            f'<line x1="{margin_l}" y1="{ty(yi):.1f}" x2="{margin_l+pw}" y2="{ty(yi):.1f}" stroke="#e0e0e0" stroke-width="1"/>'
        )
        if yi != 0:
            grid.append(
                f'<text x="{margin_l-8}" y="{ty(yi)+4:.1f}" text-anchor="end" font-size="11" fill="#333">{yi}</text>'
            )

    x0, x1 = cfg["x_range"]
    curves = [
        (cfg["lower_fns"][0], cfg["labels"][0], "#1a5fb4", 2.2),
        (cfg["upper_fns"][0], cfg["labels"][1], "#c01c28", 2.2),
        (cfg["line_fn"], cfg["labels"][2], "#26a269", 2.2),
    ]
    curve_svg = []
    for fn, label, color, sw in curves:
        d = curve_path(fn, x0, x1)
        if d:
            curve_svg.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"/>')

    # legend
    lx, ly = margin_l + 8, margin_t + 8
    legend_items = [
        ("#1a5fb4", cfg["labels"][0]),
        ("#c01c28", cfg["labels"][1]),
        ("#26a269", cfg["labels"][2]),
    ]
    legend = [f'<rect x="{margin_l}" y="{margin_t}" width="{pw}" height="58" fill="white" fill-opacity="0.92" stroke="#ccc"/>']
    for i, (col, lab) in enumerate(legend_items):
        yy = ly + i * 16
        legend.append(f'<line x1="{lx}" y1="{yy}" x2="{lx+22}" y2="{yy}" stroke="{col}" stroke-width="2.5"/>')
        legend.append(f'<text x="{lx+28}" y="{yy+4}" font-size="11" fill="#111">{lab}</text>')
    legend.append(f'<text x="{lx}" y="{ly+52}" font-size="10" fill="#555">Закрашенная область</text>')

    ox0, oy0 = tx(0), ty(0)
    axes = f'''
    <line x1="{margin_l}" y1="{margin_t+ph}" x2="{margin_l+pw}" y2="{margin_t+ph}" stroke="#000" stroke-width="1.5"/>
    <line x1="{margin_l}" y1="{margin_t}" x2="{margin_l}" y2="{margin_t+ph}" stroke="#000" stroke-width="1.5"/>
    <text x="{margin_l+pw+4}" y="{margin_t+ph+4}" font-size="12" font-style="italic">x</text>
    <text x="{margin_l-6}" y="{margin_t-8}" font-size="12" font-style="italic">y</text>
    <text x="{tx(0)+4}" y="{margin_t+ph+16}" font-size="11">0</text>
    <text x="{margin_l-8}" y="{ty(0)+4}" text-anchor="end" font-size="11">0</text>
    '''

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="График задания 7">
  <rect width="100%" height="100%" fill="#fff"/>
  {''.join(grid)}
  {shade}
  {''.join(curve_svg)}
  {axes}
  {''.join(legend)}
</svg>'''


REGION_CONFIGS = [
    {
        "lower_fns": [lambda x: x**2 - 4],
        "upper_fns": [lambda x: 5 - x**2, lambda x: 3 - 2 * x],
        "line_fn": lambda x: 3 - 2 * x,
        "labels": ["y = x² − 4", "y = 5 − x²", "y = 3 − 2x"],
        "x_range": (-2.2, 2.0), "plot_x": (-3, 3), "plot_y": (-4, 5),
        "test_yes": (-1, 2), "test_no": (1.5, 1.5),
        "desc": ["$y \\ge x^2 - 4$", "$y \\le 5 - x^2$", "$y \\le 3 - 2x$"],
    },
    {
        "lower_fns": [lambda x: x**2 - 3],
        "upper_fns": [lambda x: 4 - x**2, lambda x: 2 - x],
        "line_fn": lambda x: 2 - x,
        "labels": ["y = x² − 3", "y = 4 − x²", "y = 2 − x"],
        "x_range": (-1.9, 1.85), "plot_x": (-3, 3), "plot_y": (-4, 5),
        "test_yes": (-1.5, 1.5), "test_no": (1.5, 1.5),
        "desc": ["$y \\ge x^2 - 3$", "$y \\le 4 - x^2$", "$y \\le 2 - x$"],
    },
    {
        "lower_fns": [lambda x: -x**2 + 1, lambda x: x - 2],
        "upper_fns": [lambda x: 3 - x**2],
        "line_fn": lambda x: x - 2,
        "labels": ["y = −x² + 1", "y = 3 − x²", "y = x − 2"],
        "x_range": (-2.0, 1.85), "plot_x": (-3, 3), "plot_y": (-4, 4),
        "test_yes": (-1, 1), "test_no": (1.5, 1.5),
        "desc": ["$y \\ge -x^2 + 1$", "$y \\le 3 - x^2$", "$y \\ge x - 2$"],
    },
    {
        "lower_fns": [lambda x: x**2 - 5],
        "upper_fns": [lambda x: 2 - 2 * x**2, lambda x: 1 - x],
        "line_fn": lambda x: 1 - x,
        "labels": ["y = x² − 5", "y = 2 − 2x²", "y = 1 − x"],
        "x_range": (-1.75, 1.75), "plot_x": (-3, 3), "plot_y": (-6, 4),
        "test_yes": (-0.2, -0.3), "test_no": (-1.9, -5.5),
        "desc": ["$y \\ge x^2 - 5$", "$y \\le 2 - 2x^2$", "$y \\le 1 - x$"],
    },
    {
        "lower_fns": [lambda x: x**2 - 2],
        "upper_fns": [lambda x: 6 - x**2, lambda x: 4 - x],
        "line_fn": lambda x: 4 - x,
        "labels": ["y = x² − 2", "y = 6 − x²", "y = 4 − x"],
        "x_range": (-2.0, 2.0), "plot_x": (-3, 3), "plot_y": (-3, 7),
        "test_yes": (0, 1), "test_no": (2, 3),
        "desc": ["$y \\ge x^2 - 2$", "$y \\le 6 - x^2$", "$y \\le 4 - x$"],
    },
    {
        "lower_fns": [lambda x: -x**2 + 2, lambda x: 2 * x - 1],
        "upper_fns": [lambda x: 4 - x**2],
        "line_fn": lambda x: 2 * x - 1,
        "labels": ["y = −x² + 2", "y = 4 − x²", "y = 2x − 1"],
        "x_range": (-1.5, 1.65), "plot_x": (-3, 3), "plot_y": (-3, 5),
        "test_yes": (-0.7, 2.6), "test_no": (-2.0, 1.9),
        "desc": ["$y \\ge -x^2 + 2$", "$y \\le 4 - x^2$", "$y \\ge 2x - 1$"],
    },
    {
        "lower_fns": [lambda x: x**2 - 1],
        "upper_fns": [lambda x: 5 - x**2, lambda x: 3 - 1.5 * x],
        "line_fn": lambda x: 3 - 1.5 * x,
        "labels": ["y = x² − 1", "y = 5 − x²", "y = 3 − 1,5x"],
        "x_range": (-2.0, 1.9), "plot_x": (-3, 3), "plot_y": (-2, 6),
        "test_yes": (-1, 2), "test_no": (1.5, 0),
        "desc": ["$y \\ge x^2 - 1$", "$y \\le 5 - x^2$", "$y \\le 3 - 1{,}5x$"],
    },
    {
        "lower_fns": [lambda x: x**2 - 6],
        "upper_fns": [lambda x: 3 - x**2, lambda x: -x],
        "line_fn": lambda x: -x,
        "labels": ["y = x² − 6", "y = 3 − x²", "y = −x"],
        "x_range": (-2.1, 2.1), "plot_x": (-3, 3), "plot_y": (-7, 4),
        "test_yes": (0, 0), "test_no": (2, 2),
        "desc": ["$y \\ge x^2 - 6$", "$y \\le 3 - x^2$", "$y \\le -x$"],
    },
    {
        "lower_fns": [lambda x: -x**2, lambda x: x - 3],
        "upper_fns": [lambda x: 2 - x**2],
        "line_fn": lambda x: x - 3,
        "labels": ["y = −x²", "y = 2 − x²", "y = x − 3"],
        "x_range": (-1.8, 1.7), "plot_x": (-3, 3), "plot_y": (-4, 3),
        "test_yes": (-1, 0), "test_no": (1.5, 1),
        "desc": ["$y \\ge -x^2$", "$y \\le 2 - x^2$", "$y \\ge x - 3$"],
    },
    {
        "lower_fns": [lambda x: x**2 - 3],
        "upper_fns": [lambda x: 5 - 2 * x**2, lambda x: 2 - x],
        "line_fn": lambda x: 2 - x,
        "labels": ["y = x² − 3", "y = 5 − 2x²", "y = 2 − x"],
        "x_range": (-1.6, 1.6), "plot_x": (-3, 3), "plot_y": (-4, 5),
        "test_yes": (-1, 1), "test_no": (1.5, 1.5),
        "desc": ["$y \\ge x^2 - 3$", "$y \\le 5 - 2x^2$", "$y \\le 2 - x$"],
    },
    {
        "lower_fns": [lambda x: x**2 - 4],
        "upper_fns": [lambda x: 4 - x**2, lambda x: 1 - 2 * x],
        "line_fn": lambda x: 1 - 2 * x,
        "labels": ["y = x² − 4", "y = 4 − x²", "y = 1 − 2x"],
        "x_range": (-1.9, 1.5), "plot_x": (-3, 3), "plot_y": (-5, 5),
        "test_yes": (-1, 0), "test_no": (1.5, 1.5),
        "desc": ["$y \\ge x^2 - 4$", "$y \\le 4 - x^2$", "$y \\le 1 - 2x$"],
    },
    {
        "lower_fns": [lambda x: -x**2 + 3, lambda x: x + 1],
        "upper_fns": [lambda x: 5 - x**2],
        "line_fn": lambda x: x + 1,
        "labels": ["y = −x² + 3", "y = 5 − x²", "y = x + 1"],
        "x_range": (-1.7, 1.7), "plot_x": (-3, 3), "plot_y": (-2, 6),
        "test_yes": (-0.5, 4.0), "test_no": (-2.1, 4.7),
        "desc": ["$y \\ge -x^2 + 3$", "$y \\le 5 - x^2$", "$y \\ge x + 1$"],
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

TASK8 = [
    {
        "title": "методом половинного деления",
        "eq": "x^3-3x-1=0",
        "eq_tex": "f(x)=x^3-3x-1=0",
        "method": "bisection",
        "input": "$r1=1$, $r2=2$, $r3=0{,}001$",
        "output": "$r5$ — приближённый корень",
        "cells": "$w[0]$ граница слева, $w[1]$ справа, $w[2]$ середина, $w[3]$ значение $f$ в середине",
        "answer": "$\\approx 1{,}879$",
        "fragment": "mw 0 r1\nmw 1 r2\nmr r0 0\n+ r0 r1\nmr r4 1\n+ r0 r4\nm r7 2\n/ r0 r7\nmw 2 r0",
    },
    {
        "title": "методом Ньютона",
        "eq": "x^3-2x-5=0",
        "eq_tex": "f(x)=x^3-2x-5=0",
        "method": "newton",
        "input": "$r1=2{,}5$, $r2=0{,}001$, $r3=20$",
        "output": "$r5$ — приближённый корень",
        "cells": "$w[0]$ текущее $x$, $w[1]$ $f(x)$, $w[2]$ $f'(x)$, $w[3]$ новое приближение",
        "answer": "$\\approx 2{,}095$",
        "fragment": "mw 0 r1\nmr r4 0\nm r0 r4\nm r7 3\n^ r0 r7\nm r5 2\n* r5 r4\n- r0 r5\nm r7 5\n- r0 r7\nmw 1 r0",
    },
    {
        "title": "методом половинного деления",
        "eq": "x^3-x-1=0",
        "eq_tex": "f(x)=x^3-x-1=0",
        "method": "bisection",
        "input": "$r1=1$, $r2=2$, $r3=0{,}001$",
        "output": "$r5$",
        "cells": "$w[0]$–$w[3]$ как в задании с бисекцией",
        "answer": "$\\approx 1{,}325$",
        "fragment": "mw 0 r1\nmw 1 r2\nmr r0 0\n+ r0 r1\nmr r4 1\n+ r0 r4\nm r7 2\n/ r0 r7\nmw 2 r0",
    },
    {
        "title": "методом Ньютона",
        "eq": "x^3-x-3=0",
        "eq_tex": "f(x)=x^3-x-3=0",
        "method": "newton",
        "input": "$r1=2$, $r2=0{,}001$, $r3=20$",
        "output": "$r5$",
        "cells": "$w[0]$–$w[3]$ как в методе Ньютона",
        "answer": "$\\approx 1{,}671$",
        "fragment": "mw 0 r1\nmr r4 0\nm r0 r4\nm r7 3\n^ r0 r7\nm r5 1\n* r5 r4\n- r0 r5\nm r7 3\n- r0 r7\nmw 1 r0",
    },
    {
        "title": "методом половинного деления",
        "eq": "x^3+2x-5=0",
        "eq_tex": "f(x)=x^3+2x-5=0",
        "method": "bisection",
        "input": "$r1=1$, $r2=2$, $r3=0{,}001$",
        "output": "$r5$",
        "cells": "$w[0]$–$w[3]$",
        "answer": "$\\approx 1{,}432$",
        "fragment": "mw 0 r1\nmw 1 r2\nmr r0 0\n+ r0 r1\nmr r4 1\n+ r0 r4\nm r7 2\n/ r0 r7\nmw 2 r0",
    },
    {
        "title": "методом Ньютона",
        "eq": "x^3+3x-7=0",
        "eq_tex": "f(x)=x^3+3x-7=0",
        "method": "newton",
        "input": "$r1=2$, $r2=0{,}001$, $r3=20$",
        "output": "$r5$",
        "cells": "$w[0]$–$w[3]$",
        "answer": "$\\approx 1{,}568$",
        "fragment": "mw 0 r1\nmr r4 0\nm r0 r4\nm r7 3\n^ r0 r7\nm r5 3\n* r5 r4\n+ r0 r5\nm r7 7\n- r0 r7\nmw 1 r0",
    },
    {
        "title": "методом половинного деления",
        "eq": "x^3-4x+1=0",
        "eq_tex": "f(x)=x^3-4x+1=0",
        "method": "bisection",
        "input": "$r1=0$, $r2=1$, $r3=0{,}001$",
        "output": "$r5$",
        "cells": "$w[0]$–$w[3]$",
        "answer": "$\\approx 0{,}257$",
        "fragment": "mw 0 r1\nmw 1 r2\nmr r0 0\n+ r0 r1\nmr r4 1\n+ r0 r4\nm r7 2\n/ r0 r7\nmw 2 r0",
    },
    {
        "title": "методом Ньютона",
        "eq": "x^3-4x+2=0",
        "eq_tex": "f(x)=x^3-4x+2=0",
        "method": "newton",
        "input": "$r1=2$, $r2=0{,}001$, $r3=20$",
        "output": "$r5$",
        "cells": "$w[0]$–$w[3]$",
        "answer": "$\\approx 1{,}769$",
        "fragment": "mw 0 r1\nmr r4 0\nm r0 r4\nm r7 3\n^ r0 r7\nm r5 4\n* r5 r4\n- r0 r5\nm r7 2\n+ r0 r7\nmw 1 r0",
    },
    {
        "title": "методом половинного деления",
        "eq": "x^3+ x-1=0",
        "eq_tex": "f(x)=x^3+x-1=0",
        "method": "bisection",
        "input": "$r1=0$, $r2=1$, $r3=0{,}001$",
        "output": "$r5$",
        "cells": "$w[0]$–$w[3]$",
        "answer": "$\\approx 0{,}682$",
        "fragment": "mw 0 r1\nmw 1 r2\nmr r0 0\n+ r0 r1\nmr r4 1\n+ r0 r4\nm r7 2\n/ r0 r7\nmw 2 r0",
    },
    {
        "title": "методом Ньютона",
        "eq": "x^3-5x+1=0",
        "eq_tex": "f(x)=x^3-5x+1=0",
        "method": "newton",
        "input": "$r1=2{,}5$, $r2=0{,}001$, $r3=20$",
        "output": "$r5$",
        "cells": "$w[0]$–$w[3]$",
        "answer": "$\\approx 2{,}257$",
        "fragment": "mw 0 r1\nmr r4 0\nm r0 r4\nm r7 3\n^ r0 r7\nm r5 5\n* r5 r4\n- r0 r5\nm r7 1\n+ r0 r7\nmw 1 r0",
    },
    {
        "title": "методом половинного деления",
        "eq": "x^3-2x^2-1=0",
        "eq_tex": "f(x)=x^3-2x^2-1=0",
        "method": "bisection",
        "input": "$r1=2$, $r2=3$, $r3=0{,}001$",
        "output": "$r5$",
        "cells": "$w[0]$–$w[3]$",
        "answer": "$\\approx 2{,}532$",
        "fragment": "mw 0 r1\nmw 1 r2\nmr r0 0\n+ r0 r1\nmr r4 1\n+ r0 r4\nm r7 2\n/ r0 r7\nmw 2 r0",
    },
    {
        "title": "методом Ньютона",
        "eq": "x^3-x^2-4=0",
        "eq_tex": "f(x)=x^3-x^2-4=0",
        "method": "newton",
        "input": "$r1=2$, $r2=0{,}001$, $r3=20$",
        "output": "$r5$",
        "cells": "$w[0]$–$w[3]$",
        "answer": "$\\approx 2{,}058$",
        "fragment": "mw 0 r1\nmr r4 0\nm r0 r4\nm r7 3\n^ r0 r7\nmr r5 0\n^ r5 r4\n- r0 r5\nm r7 4\n- r0 r7\nmw 1 r0",
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


def build_variant(num: int) -> dict:
    i = num - 5
    t1_tex, t1_html, t1_ans = task1_answer(TASK1_SPECS[i])
    a2 = TASK2_A[i]
    t2_ans = task2_count(a2)
    t3_text, t3_ans = TASK3[i]
    fp, fk, p2t, k3t, p0, k0 = TASK4[i]
    # fix degenerate task4 entries
    if p0 == p2t and k0 == k3t and fp == sp.Rational(1, 5) and fk == sp.Rational(2, 7):
        p2t, k3t, p0, k0 = 875, 525, 1310, 111
    if p0 == p2t and fp == sp.Rational(1, 6):
        p2t, k3t, p0, k0 = 770, 560, 440, 939
    d5, suf, last, x5, q5 = TASK5[i]
    t6 = TASK6[i]
    reg = REGION_CONFIGS[i]
    t8 = TASK8[i]
    n1, n2, item = NAMES[i]
    ef1, ef2, _, _ = EXCHANGE_FRAC[i]
    p2t, k3t, p0, k0 = EXCHANGE_DATA[i]

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
        "t5": (d5, suf, last, x5, q5),
        "t6": t6,
        "t7": reg,
        "t7_svg": make_svg(reg),
        "t8": t8,
    }


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
}
table.examples { border-collapse: collapse; margin: 3mm auto; font-size: 11pt; }
table.examples th, table.examples td { border: 1px solid #333; padding: 2mm 6mm; }
table.examples th { background: #eef2f6; }
.figure { text-align: center; margin: 4mm 0; page-break-inside: avoid; }
.figure svg { max-width: 100%; height: auto; border: 1px solid #333; }
.figure-caption { font-size: 10pt; margin-top: 2mm; font-style: italic; }
.region-list { font-size: 10.5pt; margin: 2mm 0 2mm 6mm; }
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
    d5, suf, last, x5, q5 = v["t5"]
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
      <p>В выражении {d5}<sub>x{suf}</sub> + 1x{last}<sub>100</sub> (<em>x</em> — цифра):</p>
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
      <div class="figure"><pre class="code">{html_escape(t6['code'])}</pre><div class="figure-caption">Рис. а</div></div>
      <p class="solution-label">Решение:</p><div class="solution-space medium"></div>
      <div class="answer-box xtall"></div>
    </div>
  </div>

  <div class="page-break"></div>

  <div class="task">
    <div class="task-head"><span class="task-num">Задание 7</span><span class="task-pts">(15 баллов, компьютер)</span></div>
    <div class="task-body">
      <p>Графики: <em>{reg['labels'][0]}</em>, <em>{reg['labels'][1]}</em>, <em>{reg['labels'][2]}</em>.
      Закрашенная область — рис. б. Программа: точка (<em>x</em>, <em>y</em>) в области? → <code>YES</code>/<code>NO</code>.</p>
      <table class="examples">
        <tr><th>Ввод</th><th>Вывод</th></tr>
        <tr><td>{ty[0]} &nbsp; {ty[1]}</td><td>YES</td></tr>
        <tr><td>{tn[0]} &nbsp; {tn[1]}</td><td>NO</td></tr>
      </table>
      <div class="figure">{v['t7_svg']}<div class="figure-caption">Рис. б — закрашенная область</div></div>
    </div>
  </div>

  <div class="task">
    <div class="task-head"><span class="task-num">Задание 8</span><span class="task-pts">(15 баллов, компьютер)</span></div>
    <div class="task-body">
      <p>Исполнитель «Сириус»: <strong>{t8['title']}</strong> найти корень {t8['eq_tex'].replace('$','')}.
      Промежуточные значения — в <strong>массиве памяти</strong> <em>w</em>[] (стек не использовать).</p>
      <p>Вход: {t8['input'].replace('$','')}. Выход: {t8['output'].replace('$','')}.</p>
      <p>Ячейки: {t8['cells'].replace('$','')}.</p>
      <table class="examples" style="width:100%;font-size:10pt">
        <tr><th>mw / mr / +w …</th><th>Команды массива w[0]–w[9]</th></tr>
        <tr><td colspan="2">Регистры r0–r7: m, +, −, *, /, ^</td></tr>
      </table>
      <pre class="code">{html_escape(t8['fragment'])}</pre>
      <p class="solution-label">Программа:</p><div class="solution-space large"></div>
    </div>
  </div>

  <div class="footer">Вариант {n} · АНОО ВО «Университет «Сириус» · Лист ___ из ___</div>
</body>
</html>"""


def render_md(v: dict) -> str:
    n = v["num"]
    n1, n2, item, ef1, ef2, p2t, k3t, p0, k0 = v["t4"]
    d5, suf, last, x5, q5 = v["t5"]
    reg = v["t7"]
    ty, tn = reg["test_yes"], reg["test_no"]
    t6, t8 = v["t6"], v["t8"]
    desc7 = "\n".join(f"- {d}" for d in reg["desc"])

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

В выражении ${d5}_{{x{suf}}}+1x{last}_{{100}}$:

а) наибольшее $x$ при кратности 99; б) частное. *Ответ в десятичной системе.*

---

## Задание 6 (10 баллов)

Программа должна выводить **{t6['desc']}**. Найдите ошибки:

```python
{t6['code']}
```

---

## Задание 7 (15 баллов)

Графики: {', '.join(reg['labels'])}. Закрашенная область (см. `variant-{n}-blank.html`, рис. б).

| Ввод | Вывод |
|------|-------|
| {ty[0]} {ty[1]} | YES |
| {tn[0]} {tn[1]} | NO |

{desc7}

---

## Задание 8 (15 баллов)

{t8['title'].capitalize()} найти корень ${t8['eq_tex'].replace('$','')}$. Массив $w[]$, не стек.  
Вход: {t8['input']}. Выход: {t8['output']}.

---

## Ответы

| № | Ответ |
|---|-------|
| 1 | ${v['t1_ans']}$ |
| 2 | ${v['t2_ans']}$ |
| 3 | {v['t3_ans']} |
| 4 | {n1} — ${p0}$, {n2} — ${k0}$ |
| 5а | ${x5}$ |
| 5б | ${q5}$ |
| 6 | {t6['errors']} |
| 7 | см. условия выше |
| 8 | {t8['answer']} |
"""


def main():
    variants = []
    for num in range(5, 17):
        try:
            v = build_variant(num)
            variants.append(v)
        except Exception as e:
            raise RuntimeError(f"variant {num}: {e}") from e

        (OUT / f"variant-{num}.md").write_text(render_md(v), encoding="utf-8")
        (OUT / f"variant-{num}-blank.html").write_text(render_blank(v), encoding="utf-8")
        print(f"variant-{num} OK  t1={v['t1_ans']} t2={v['t2_ans']}")

    # answers key
    lines = ["# Ключ ответов (варианты 5–16)\n", "| Вар. | 1 | 2 | 3 | 4 | 5а | 5б | 8 |", "|------|---|---|---|---|----|----|---|"]
    for v in variants:
        n1, n2, _, _, _, _, _, p0, k0 = v["t4"]
        x5, q5 = v["t5"][3], v["t5"][4]
        lines.append(
            f"| {v['num']} | {v['t1_ans']} | {v['t2_ans']} | {v['t3_ans'].replace('$','')} | {p0}/{k0} | {x5} | {q5} | {v['t8']['answer'].replace('$','')} |"
        )
    (OUT / "answers-key-5-16.md").write_text("\n".join(lines), encoding="utf-8")
    print("done")


if __name__ == "__main__":
    main()

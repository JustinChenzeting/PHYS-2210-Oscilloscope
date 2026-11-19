"""Reusable Seshadri-first Matplotlib helpers. Local implementation, 2026-10-13.

See ../nature-figure/references/seshadri.md for source pages and which numeric
settings are local defaults. Does not calculate statistics or invent data.
"""
from __future__ import annotations

import itertools
import json
import math
import re
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from cycler import cycler
from matplotlib import colors, font_manager
from matplotlib.text import Text
from matplotlib.ticker import LogFormatter, LogLocator, MaxNLocator, NullLocator

PALETTE = ("#4477AA", "#CC8844", "#444444", "#8877AA")
MARKERS = ("o", "s", "^", "D")
LINESTYLES = ("-", "--", "-.", ":")
FONT_PREFERENCES = ("Helvetica", "Calibri", "Gill Sans", "Arial", "DejaVu Sans")


class _ReadableLogLocator(LogLocator):
    """Include 2/5 ticks in a short log range instead of one lonely decade tick."""

    def tick_values(self, vmin, vmax):
        lo, hi = sorted((vmin, vmax))
        if lo > 0 and math.log10(hi/lo) <= 1.6:
            return LogLocator(base=10, subs=(1, 2, 5), numticks=12).tick_values(lo, hi)
        return super().tick_values(lo, hi)


def _positive(value, name):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def apply_seshadri_style(*, fontsize=8, font=None, frame="boxed", dpi=600):
    """Apply one regular text size, redundant styles, and editable vector text.

    Returns the selected font and numeric settings for provenance. Frame choice
    is a local default; Seshadri does not mandate tick direction or a frame.
    """
    fontsize = _positive(fontsize, "fontsize")
    dpi = _positive(dpi, "dpi")
    if frame not in {"boxed", "open", "none"}:
        raise ValueError("frame must be boxed, open, or none")
    candidates = (font,) if font else FONT_PREFERENCES
    chosen = None
    for candidate in candidates:
        try:
            path = font_manager.findfont(
                font_manager.FontProperties(family=candidate), fallback_to_default=False
            )
            chosen = font_manager.FontProperties(fname=path).get_name()
            break
        except ValueError:
            continue
    if chosen is None:
        raise ValueError(f"Requested font is unavailable: {font!r}")
    mpl.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": [chosen],
        "font.size": fontsize, "font.weight": "normal",
        "axes.labelsize": fontsize, "axes.titlesize": fontsize,
        "axes.labelweight": "normal", "axes.titleweight": "normal",
        "figure.titlesize": fontsize, "figure.titleweight": "normal",
        "figure.labelsize": fontsize, "figure.labelweight": "normal",
        "legend.fontsize": fontsize, "legend.title_fontsize": fontsize,
        "xtick.labelsize": fontsize, "ytick.labelsize": fontsize,
        "text.color": "black", "axes.labelcolor": "black",
        "axes.titlecolor": "black", "xtick.color": "black", "ytick.color": "black",
        "axes.edgecolor": "black", "axes.linewidth": 0.8,
        "axes.spines.top": frame == "boxed", "axes.spines.right": frame == "boxed",
        "axes.spines.left": frame != "none", "axes.spines.bottom": frame != "none",
        "axes.grid": False, "axes.facecolor": "white", "figure.facecolor": "white",
        "xtick.direction": "in", "ytick.direction": "in",
        "xtick.major.size": 3, "ytick.major.size": 3,
        "xtick.major.width": 0.8, "ytick.major.width": 0.8,
        "xtick.minor.visible": False, "ytick.minor.visible": False,
        "xtick.top": frame == "boxed", "ytick.right": frame == "boxed",
        "lines.linewidth": 1.2, "lines.markersize": 3.5,
        "lines.markeredgewidth": 0.8,
        "axes.prop_cycle": cycler(color=PALETTE) + cycler(marker=MARKERS)
            + cycler(linestyle=LINESTYLES) + cycler(fillstyle=("full", "none", "full", "none")),
        "legend.frameon": False, "legend.labelcolor": "black",
        "legend.loc": "best", "legend.handlelength": 2.8,
        "mathtext.fontset": "dejavusans", "text.usetex": False,
        "svg.fonttype": "none", "pdf.fonttype": 42, "ps.fonttype": 42,
        "figure.dpi": 150, "savefig.dpi": dpi, "savefig.bbox": None,
        "savefig.facecolor": "white", "savefig.transparent": False,
    })
    return {"font": chosen, "font_size_pt": fontsize, "dpi": dpi, "frame": frame}


def series_styles(labels):
    """Stable label->style map in caller-supplied order (up to four groups).

    Build once from the full paper's group order and reuse subsets across panels.
    No scientific role (control/treatment) is inferred from a label.
    """
    labels = list(labels)
    if not labels or len(set(labels)) != len(labels):
        raise ValueError("Supply nonempty, unique series labels")
    if len(labels) > len(PALETTE):
        raise ValueError("More than four series: facet or design an explicit additional encoding")
    return {label: {
        "color": PALETTE[i], "marker": MARKERS[i], "linestyle": LINESTYLES[i],
        "markerfacecolor": PALETTE[i] if i % 2 == 0 else "white",
        "markeredgecolor": PALETTE[i], "markersize": 3.5, "linewidth": 1.2,
    } for i, label in enumerate(labels)}


def style_axes(ax, *, square=True, max_ticks=5):
    """Square the physical axes box without forcing equal data-unit scales."""
    if not isinstance(max_ticks, int) or max_ticks < 2:
        raise ValueError("max_ticks must be an integer >= 2")
    if square:
        ax.set_box_aspect(1)
    ax._seshadri_square = square
    for axis, scale in ((ax.xaxis, ax.get_xscale()), (ax.yaxis, ax.get_yscale())):
        if scale == "linear":
            axis.set_major_locator(MaxNLocator(nbins=max_ticks - 1))
        elif scale == "log":
            axis.set_major_locator(_ReadableLogLocator(numticks=max_ticks))
            axis.set_major_formatter(LogFormatter(labelOnlyBase=False,
                                                  minor_thresholds=(float("inf"), float("inf"))))
        axis.set_minor_locator(NullLocator())
    ax.margins(0.06)
    return ax


def subplots(nrows=1, ncols=1, *, width_mm=89, height_mm=None,
             sharex=False, sharey=False, square=True):
    """Return (figure, 2-D axes array), with equal square plotting boxes by default."""
    width_mm = _positive(width_mm, "width_mm")
    if not all(isinstance(n, int) and n > 0 for n in (nrows, ncols)):
        raise ValueError("nrows and ncols must be positive integers")
    height_mm = _positive(height_mm if height_mm is not None else width_mm*nrows/ncols,
                          "height_mm")
    fig, axes = plt.subplots(nrows, ncols, figsize=(width_mm/25.4, height_mm/25.4),
                             squeeze=False, layout="constrained", sharex=sharex, sharey=sharey)
    for ax in axes.flat:
        style_axes(ax, square=square)
    return fig, axes


def panel_label(ax, letter, *, x=0.04, y=0.96, fontsize=None):
    """Place regular '(a)' inside a panel at a consistent axes-relative location."""
    value = str(letter).strip().strip("()")
    if len(value) != 1 or value not in "abcdefghijklmnopqrstuvwxyz":
        raise ValueError("Panel labels must be a single lowercase letter, e.g. 'a'")
    return ax.text(x, y, f"({value})", transform=ax.transAxes, va="top", ha="left",
                   fontsize=fontsize or mpl.rcParams["font.size"],
                   fontweight="normal", color="black", gid=f"seshadri-panel-{value}")


def inplot_legend(ax, *, loc="best", **kwargs):
    """Dataset legend inside the axes; caller must verify it does not cover data."""
    if "bbox_to_anchor" in kwargs:
        raise ValueError("Use an in-plot loc; outside legend anchors need deliberate custom layout")
    return ax.legend(loc=loc, frameon=False, labelcolor="black", **kwargs)


def _drawn_texts(fig):
    # Matplotlib creates labels for ticks outside the view limits; they are not
    # actually drawn and must not produce false clipping/overlap failures.
    tick_ids, drawn_ids = set(), set()
    for ax in fig.axes:
        for axis, limits in ((ax.xaxis, ax.get_xlim()), (ax.yaxis, ax.get_ylim())):
            lo, hi = sorted(limits)
            for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                labels = (tick.label1, tick.label2)
                tick_ids.update(id(t) for t in labels)
                if axis.get_visible() and lo-1e-10 <= tick.get_loc() <= hi+1e-10:
                    drawn_ids.update(id(t) for t in labels if t.get_visible())
    return [t for t in fig.findobj(Text) if t.get_visible() and t.get_text().strip()
            and (id(t) not in tick_ids or id(t) in drawn_ids)
            and (t.axes is None or t.axes.get_visible())]


def audit_figure(fig, *, fontsize=None):
    """Check measurable styling/layout issues; does not certify scientific validity.

    Text overlaps and colored text are review findings. Clipping, size hierarchy,
    bold text, wrong panel labels, and unintended nonsquare boxes are errors.
    """
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    base = float(fontsize or mpl.rcParams["font.size"])
    findings = []
    def add(code, detail, level="error"):
        findings.append({"code": code, "level": level, "detail": detail})
    texts = _drawn_texts(fig)
    boxes = []
    for t in texts:
        value = t.get_text()
        box = t.get_window_extent(renderer)
        if abs(t.get_fontsize()-base) > 0.05:
            add("TEXT_SIZE", f"{value!r}: {t.get_fontsize():g} pt; expected {base:g}")
        if t.get_fontweight() not in ("normal", "regular", "book", 400):
            add("TEXT_WEIGHT", f"{value!r}: {t.get_fontweight()}")
        if colors.to_hex(t.get_color()).lower() != "#000000":
            add("TEXT_COLOR", f"{value!r}: justify non-black text", "review")
        if box.x0 < -1 or box.y0 < -1 or box.x1 > fig.bbox.x1+1 or box.y1 > fig.bbox.y1+1:
            add("CLIPPED_TEXT", value)
        if t.get_gid() and t.get_gid().startswith("seshadri-panel-"):
            if not re.fullmatch(r"\([a-z]\)", value):
                add("PANEL_LABEL", value)
        boxes.append((value, box))
    for (a, ba), (b, bb) in itertools.combinations(boxes, 2):
        if ba.overlaps(bb):
            add("TEXT_OVERLAP", f"{a!r} overlaps {b!r}", "review")
    for i, ax in enumerate(fig.axes):
        if not ax.get_visible():
            continue
        if getattr(ax, "_seshadri_square", False) and abs(ax.bbox.width/ax.bbox.height-1) > 0.01:
            add("PANEL_ASPECT", f"Panel {i}: expected square physical box")
        legend = ax.get_legend()
        if legend is not None:
            box = legend.get_window_extent(renderer)
            if not (box.x0 >= ax.bbox.x0-1 and box.x1 <= ax.bbox.x1+1
                    and box.y0 >= ax.bbox.y0-1 and box.y1 <= ax.bbox.y1+1):
                add("LEGEND_OUTSIDE", f"Panel {i}: legend must fit inside plot")
        for scale, label in ((ax.get_xscale(), ax.get_xlabel()), (ax.get_yscale(), ax.get_ylabel())):
            if scale == "log" and re.search(r"\b(?:log|ln)\s*\(", label, re.I):
                add("LOG_LABEL", f"{label!r}: label the untransformed quantity on a log axis")
    return {"automated_status": "fail" if any(f["level"] == "error" for f in findings)
            else "review" if findings else "pass",
            "findings": findings,
            "visual_review": "pending", "quarter_size_review": "pending",
            "scientific_review": "pending",
            "width_mm": float(fig.get_figwidth()*25.4),
            "height_mm": float(fig.get_figheight()*25.4), "font_size_pt": base}


def save_figure(fig, stem, *, dpi=600, tiff=False, overwrite=False, strict=True):
    """Save fixed-size PDF/SVG, PNG, grayscale/quarter previews, and audit JSON.

    Never use bbox_inches='tight': it changes the intended printed dimensions.
    Review findings stay visible in the report; no automatic visual-pass claim.
    """
    from PIL import Image, ImageOps
    dpi = _positive(dpi, "dpi")
    stem = Path(stem)
    extensions = ["pdf", "svg", "png", "gray.png", "quarter.png", "audit.json"]
    if tiff:
        extensions.append("tiff")
    paths = {ext: Path(f"{stem}.{ext}") for ext in extensions}
    existing = [str(p) for p in paths.values() if p.exists()]
    if existing and not overwrite:
        raise FileExistsError("Output exists; choose a new stem or overwrite=True: " + ", ".join(existing))
    report = audit_figure(fig)
    if strict and report["automated_status"] == "fail":
        raise ValueError("Figure audit failed: " + json.dumps(report["findings"]))
    stem.parent.mkdir(parents=True, exist_ok=True)
    # An rc_context also protects the physical canvas if another library set
    # savefig.bbox='tight' after the style was applied.
    with mpl.rc_context({"savefig.bbox": None}):
        for ext in ("pdf", "svg", "png") + (("tiff",) if tiff else ()):
            fig.savefig(paths[ext], dpi=dpi, facecolor="white", bbox_inches=None)
    with Image.open(paths["png"]) as source:
        rgb = source.convert("RGB")
        ImageOps.grayscale(rgb).save(paths["gray.png"], dpi=(dpi, dpi))
        small = rgb.resize((max(1, rgb.width//4), max(1, rgb.height//4)), Image.Resampling.LANCZOS)
        small.save(paths["quarter.png"], dpi=(dpi, dpi))
    report["outputs"] = {ext: p.name for ext, p in paths.items()}
    report["preview_note"] = "Quarter preview is 1/4 in each pixel dimension; inspect at native size."
    paths["audit.json"].write_text(json.dumps(report, indent=2) + "\n")
    return paths, report

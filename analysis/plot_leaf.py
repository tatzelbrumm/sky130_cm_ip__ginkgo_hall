# SPDX-License-Identifier: Apache-2.0
"""Plot the ginkgo-leaf Hall plate pair from the geometry model (not a GDS rendering).

Run: python3 analysis/plot_leaf.py   -> doc/ginkgo_leaf_pair.png
"""
import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "layout"))
import ginkgo_geom as g  # noqa: E402

p = g.LeafParams()
outline = g.leaf_outline(p)
cts = g.contacts(p)
veins = g.vein_tree(p)
gap = 4.0                                   # um between the two petiole tips
dy = -(2 * p.petiole_len + gap)             # leaf B: rotated 180 deg, shifted down


def tf(xy, leaf):
    xy = np.asarray(xy, float)
    return xy if leaf == "A" else np.c_[-xy[..., 0], -xy[..., 1] + dy] if xy.ndim == 2 else np.array([-xy[0], -xy[1] + dy])


fig, ax = plt.subplots(figsize=(7.5, 9))
for leaf in ("A", "B"):
    o = tf(outline, leaf)
    ax.fill(o[:, 0], o[:, 1], color="#9ecae1", ec="#3182bd", lw=1.0, zorder=1)
    for a, b, lvl in veins:
        pa, pb = tf(a, leaf), tf(b, leaf)
        ax.plot([pa[0], pb[0]], [pa[1], pb[1]], color="#31a354", lw=max(0.5, 2.0 - 0.3 * lvl),
                alpha=0.8, zorder=2)
    for k, (x0, y0, x1, y1) in cts.items():
        c = tf(np.array([[x0, y0], [x1, y1]]), leaf)
        lo, hi = c.min(0), c.max(0)
        ax.add_patch(plt.Rectangle(lo, *(hi - lo), color="#de2d26", zorder=3))
        cx, cy = (lo + hi) / 2
        off = {"P": (1.6, 0), "N": (0, 1), "L": (-1, 0), "R": (1, 0)}[k]
        s = 1 if leaf == "A" else -1
        ax.annotate(f"{k}{leaf}", (cx, cy), xytext=(cx + 5 * s * off[0], cy + 5 * s * off[1]),
                    ha="center", va="center", fontsize=10, weight="bold", zorder=4)
    ctr = tf(np.array([0.0, 35.0]), leaf)
    ax.text(ctr[0], ctr[1] - (10 if leaf == "A" else -10), f"leaf {leaf}", ha="center",
            fontsize=11, style="italic", color="#08519c")
ax.set_aspect("equal")
ax.set_xlabel("x [µm]")
ax.set_ylabel("y [µm]")
ax.set_title("sky130_cm_ip__ginkgo_hall: orthogonally coupled leaf pair\n"
             "n-well plate (blue), n+ contacts (red), met4 vein art (green)", fontsize=10)
ax.grid(alpha=0.25)
out = os.path.join(here, "..", "doc", "ginkgo_leaf_pair.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
fig.tight_layout()
fig.savefig(out, dpi=150)
print(out)

# SPDX-License-Identifier: Apache-2.0
"""Parametric ginkgo-leaf geometry for the sky130_cm_ip__ginkgo_hall Hall plate.

Pure Python/NumPy, no EDA dependencies, so that the GDS generator
(gen_ginkgo_hall.py) and the finite-difference model (analysis/fd_hall.py)
use the identical outline.

Coordinates in micrometres.  Origin at the junction of petiole and blade,
leaf axis along +y (petiole points to -y, notch at +y).

The outline is generated from closed-form math (fan + wavy margin +
trapezoidal notch + rectangular petiole); it is not traced from any
photograph or existing artwork.
"""
from dataclasses import dataclass, field
import math
import numpy as np


@dataclass
class LeafParams:
    blade_radius: float = 60.0      # um, distance base point -> margin (lobe crest)
    opening_deg: float = 150.0      # total fan opening angle
    notch_depth: float = 20.0       # um, radial depth of the central notch
    notch_halfangle_deg: float = 9.0  # angular half-width of the notch at the margin
    notch_bottom: float = 2.0       # um, flat notch bottom (>= nwell.2a 1.27 um)
    wave_amp: float = 1.2           # um, lobule waviness amplitude of the margin
    wave_n: int = 7                 # lobules per half blade
    petiole_len: float = 13.0       # um, n-well part of the petiole
    petiole_w: float = 8.0          # um
    base_round: float = 6.0         # um, half-width of blade base where it meets petiole
    contact_angle_deg: float = 51.0 # lobe-flank contact position, angle from axis
    contact_size: float = 3.0       # um, n+ contact edge (tap) for N, L, R
    enclosure: float = 0.5          # um, nwell enclosure of n+ tap (rule difftap.10: 0.18)
    n_margin: int = 241             # points along the margin
    grid: float = 0.005             # um, manufacturing grid


def margin_radius(p: LeafParams, phi):
    """Margin radius r(phi), phi in rad from +y axis (positive = right lobe)."""
    phi = np.asarray(phi, dtype=float)
    half = math.radians(p.opening_deg) / 2
    # lobules: cosine waviness, zero phase at the lobe ends
    r = p.blade_radius + p.wave_amp * np.cos(p.wave_n * math.pi * np.abs(phi) / half)
    # trapezoidal notch: linear flanks, flat bottom of width notch_bottom
    na = math.radians(p.notch_halfangle_deg)
    rb = p.blade_radius - p.notch_depth
    flat = (p.notch_bottom / 2) / rb  # half-angle of flat bottom
    a = np.abs(phi)
    depth = np.where(a <= flat, p.notch_depth,
                     np.where(a < na, p.notch_depth * (na - a) / (na - flat), 0.0))
    return r - depth


def _pol(r, phi):
    return np.stack([r * np.sin(phi), r * np.cos(phi)], axis=-1)


def leaf_outline(p: LeafParams):
    """Closed polygon (N x 2 array, counter-clockwise) of the n-well blade+petiole."""
    half = math.radians(p.opening_deg) / 2
    phis = np.linspace(half, -half, p.n_margin)        # right lobe -> left lobe (CCW)
    margin = _pol(margin_radius(p, phis), phis)
    # notch bottom must be a flat segment: replace near-axis points by exact corners
    pts = [(p.petiole_w / 2, -p.petiole_len),           # petiole tip, right
           (p.petiole_w / 2, 0.0),
           (p.base_round, 0.0)]
    pts += [tuple(x) for x in margin]
    pts += [(-p.base_round, 0.0), (-p.petiole_w / 2, 0.0),
            (-p.petiole_w / 2, -p.petiole_len)]
    a = np.array(pts)
    # drop consecutive duplicates
    keep = np.r_[True, np.any(np.abs(np.diff(a, axis=0)) > 1e-9, axis=1)]
    return a[keep]


def notch_apex(p: LeafParams):
    return np.array([0.0, p.blade_radius - p.notch_depth])


def contacts(p: LeafParams):
    """n+ contact rectangles (x0, y0, x1, y1), axis-aligned, keyed P, N, L, R.

    P: petiole tip, N: notch bottom, L/R: lobe flanks at +-contact_angle.
    Each rectangle is placed with at least `enclosure` of n-well around it.
    """
    e, c = p.enclosure, p.contact_size
    out = {}
    out["P"] = (-p.petiole_w / 2 + e, -p.petiole_len + e,
                p.petiole_w / 2 - e, -p.petiole_len + e + c)
    ya = p.blade_radius - p.notch_depth
    out["N"] = (-min(c, p.notch_bottom - 2 * e + 2 * c) / 2, ya - e - c,
                min(c, p.notch_bottom - 2 * e + 2 * c) / 2, ya - e)
    for key, sgn in (("R", 1), ("L", -1)):
        phi = sgn * math.radians(p.contact_angle_deg)
        r = float(margin_radius(p, phi))
        # inset the square along the inward normal (radial direction) so that
        # all four corners keep >= e from the (locally straight) margin
        d = e + c * (abs(math.sin(phi)) + abs(math.cos(phi))) / 2 + 0.3
        cx, cy = (r - d) * math.sin(phi), (r - d) * math.cos(phi)
        out[key] = (cx - c / 2, cy - c / 2, cx + c / 2, cy + c / 2)
    return out


def vein_tree(p: LeafParams, levels: int = 5, margin_gap: float = 3.0):
    """Dichotomous venation as list of line segments ((x0,y0),(x1,y1),level).

    Two primary veins leave the petiole, one per lobe, then fork
    dichotomously `levels` times; terminal veins end `margin_gap` inside
    the margin, evenly spaced in angle.  The notch is never crossed.
    """
    half = math.radians(p.opening_deg) / 2
    na = math.radians(p.notch_halfangle_deg)
    segs = []
    nleaf = 2 ** levels
    for sgn in (-1, 1):
        lo, hi = na + 0.03, half - 0.05
        ends = np.linspace(lo, hi, nleaf) * sgn
        # root at the petiole/blade junction
        root = np.array([0.0 * sgn, -p.petiole_len * 0.5])

        def build(idx, lvl, parent):
            angs = ends[idx]
            am = float(np.mean(angs))
            if len(idx) == 1:
                r = float(margin_radius(p, am)) - margin_gap
                node = _pol(r, am)
                segs.append((tuple(parent), tuple(node), lvl))
                return
            frac = (lvl + 1) / (levels + 1.4)
            r = float(margin_radius(p, am)) * frac
            node = _pol(r, am)
            # first segment hugs the base: start from the petiole
            segs.append((tuple(parent), tuple(node), lvl))
            h = len(idx) // 2
            build(idx[:h], lvl + 1, node)
            build(idx[h:], lvl + 1, node)

        build(np.arange(nleaf), 0, root)
    return segs


def snap(a, grid):
    return np.round(np.asarray(a) / grid) * grid

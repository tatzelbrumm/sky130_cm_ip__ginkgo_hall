# SPDX-License-Identifier: Apache-2.0
"""2-D finite-element model of a thin Hall plate of arbitrary outline.

Solves div(sigma(B) grad V) = 0 on the plate, with
  sigma = (1/Rsq) / (1+beta^2) * [[1, beta], [-beta, 1]],  beta = mu_H * B,
insulating outline (natural boundary condition) and n+ contacts modelled as
ideal equipotential "super-nodes".  P1 triangles on a structured grid
(each square cell inside the outline -> 2 triangles).

Units: Rsq = 1 (results in units of the sheet resistance), current I = 1.

Outputs (per spinning phase, small-Hall-angle limit):
  R_in   input resistance between the two current contacts     [x Rsq]
  R_out  output resistance between the two sense contacts      [x Rsq]
  G_H    geometric correction factor, V_H = G_H * mu_H * B * Rsq * I
  V_off  geometric offset at B = 0 (should be ~0 by symmetry)  [x Rsq*I]

Results are [estimate, FD model]: uniform sheet, no junction field effect,
no velocity saturation, contacts ideal.
"""
import sys
import os
import math
import json
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from matplotlib.path import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "layout"))


def build_mesh(outline, h):
    xmin, ymin = outline.min(0) - h
    xmax, ymax = outline.max(0) + h
    nx = int(math.ceil((xmax - xmin) / h)) + 1
    ny = int(math.ceil((ymax - ymin) / h)) + 1
    xs = xmin + h * np.arange(nx)
    ys = ymin + h * np.arange(ny)
    cx = xs[:-1] + h / 2
    cy = ys[:-1] + h / 2
    CX, CY = np.meshgrid(cx, cy, indexing="ij")
    inside = Path(outline).contains_points(np.c_[CX.ravel(), CY.ravel()]).reshape(CX.shape)
    nid = lambda i, j: i * ny + j
    tris = []
    for i, j in zip(*np.nonzero(inside)):
        a, b, c, d = nid(i, j), nid(i + 1, j), nid(i + 1, j + 1), nid(i, j + 1)
        tris.append((a, b, c))
        tris.append((a, c, d))
    tris = np.array(tris)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    pts = np.c_[X.ravel(), Y.ravel()]
    used = np.unique(tris)
    remap = -np.ones(len(pts), int)
    remap[used] = np.arange(len(used))
    return pts[used], remap[tris]


def assemble(pts, tris, beta):
    s = 1.0 / (1.0 + beta ** 2)
    sig = s * np.array([[1.0, beta], [-beta, 1.0]])
    rows, cols, vals = [], [], []
    for t in tris:
        P = pts[t]
        M = np.c_[np.ones(3), P]
        area = 0.5 * abs(np.linalg.det(M))
        G = np.linalg.inv(M)[1:, :].T          # 3x2 basis gradients
        K = area * G @ sig @ G.T                # row i: test fn i, col j: trial fn j
        for a in range(3):
            for b in range(3):
                rows.append(t[a]); cols.append(t[b]); vals.append(K[a, b])
    n = len(pts)
    return sp.csr_matrix((vals, (rows, cols)), shape=(n, n))


class Plate:
    def __init__(self, outline, contacts, h=0.5):
        self.pts, self.tris = build_mesh(np.asarray(outline), h)
        self.cnodes = {}
        for k, (x0, y0, x1, y1) in contacts.items():
            m = ((self.pts[:, 0] >= x0 - 1e-9) & (self.pts[:, 0] <= x1 + 1e-9) &
                 (self.pts[:, 1] >= y0 - 1e-9) & (self.pts[:, 1] <= y1 + 1e-9))
            idx = np.nonzero(m)[0]
            if len(idx) == 0:  # contact smaller than grid: nearest node
                c = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
                idx = np.array([np.argmin(((self.pts - c) ** 2).sum(1))])
            self.cnodes[k] = idx
        self._K = {}

    def K(self, beta):
        if beta not in self._K:
            self._K[beta] = assemble(self.pts, self.tris, beta)
        return self._K[beta]

    def solve(self, beta, i_in, i_out):
        """Current 1 into contact i_in, contact i_out grounded. Returns contact potentials."""
        n = len(self.pts)
        # super-node reduction: P maps every node to an unknown
        owner = np.arange(n)
        for k, idx in self.cnodes.items():
            owner[idx] = idx[0]
        uniq, inv = np.unique(owner, return_inverse=True)
        Pm = sp.csr_matrix((np.ones(n), (np.arange(n), inv)), shape=(n, len(uniq)))
        Kr = (Pm.T @ self.K(beta) @ Pm).tolil()
        rhs = np.zeros(len(uniq))
        gnd = inv[self.cnodes[i_out][0]]
        src = inv[self.cnodes[i_in][0]]
        rhs[src] = 1.0
        Kr[gnd, :] = 0
        Kr[gnd, gnd] = 1.0
        rhs[gnd] = 0.0
        u = spla.spsolve(Kr.tocsr(), rhs)
        return {k: float(u[inv[idx[0]]]) for k, idx in self.cnodes.items()}

    def phase(self, i_in, i_out, s_p, s_n, beta=1e-3):
        v0 = self.solve(0.0, i_in, i_out)
        vp = self.solve(beta, i_in, i_out)
        vm = self.solve(-beta, i_in, i_out)
        vh = ((vp[s_p] - vp[s_n]) - (vm[s_p] - vm[s_n])) / 2
        r_out = self.solve(0.0, s_p, s_n)[s_p]
        return dict(R_in=v0[i_in], R_out=r_out, G_H=vh / beta,
                    V_off=v0[s_p] - v0[s_n])


def validate(h=0.25):
    """Long rectangle L/W = 6, full-width current contacts, point sense contacts: G_H -> ~1."""
    L, W = 30.0, 5.0
    outline = np.array([[0, 0], [L, 0], [L, W], [0, W]])
    c = {"A": (0, 0, 0.0, W), "B": (L, 0, L, W),
         "S": (L / 2, 0, L / 2, 0), "T": (L / 2, W, L / 2, W)}  # point sense contacts
    pl = Plate(outline, c, h)
    r = pl.phase("A", "B", "S", "T")
    return r, L / W


def leaf_report(h=0.5, **kw):
    import ginkgo_geom as g
    p = g.LeafParams(**kw)
    pl = Plate(g.leaf_outline(p), g.contacts(p), h)
    # 4 phases of the spinning-current sequence (contacts in perimeter order P, R, N, L)
    ph = {
        "phi1 I:P->N  V:R-L": pl.phase("P", "N", "R", "L"),
        "phi2 I:R->L  V:N-P": pl.phase("R", "L", "N", "P"),
        "phi3 I:N->P  V:L-R": pl.phase("N", "P", "L", "R"),
        "phi4 I:L->R  V:P-N": pl.phase("L", "R", "P", "N"),
    }
    return p, ph


if __name__ == "__main__":
    r, lw = validate()
    print(f"validation rectangle L/W={lw:.0f}: R_in={r['R_in']:.3f} (expect ~{lw:.1f}), "
          f"G_H={r['G_H']:.3f} (theory 1.00 for point sense contacts, L/W >= 3)")
    out = {}
    sweep = [float(a) for a in sys.argv[1:]] or [None]
    for ang in sweep:
        kw = {} if ang is None else {"contact_angle_deg": ang}
        p, ph = leaf_report(**kw)
        print(f"\nleaf contact_angle_deg={p.contact_angle_deg}")
        for k, v in ph.items():
            print(f"  {k}: R_in={v['R_in']:.3f} Rsq  R_out={v['R_out']:.3f} Rsq  "
                  f"G_H={v['G_H']:+.4f}  V_off={v['V_off']:+.2e} Rsq*I")
        out[str(p.contact_angle_deg)] = ph
    with open(os.path.join(os.path.dirname(__file__), "fd_results.json"), "w") as f:
        json.dump(out, f, indent=1)

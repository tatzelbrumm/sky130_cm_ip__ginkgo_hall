# SPDX-License-Identifier: Apache-2.0
"""Every [estimate] number in Proposal.md, computed in one place.

Run:  python3 analysis/estimates.py
Inputs are tagged S (sourced, see Proposal.md references) or A (assumption).
FD-model results come from analysis/fd_hall.py (analysis/fd_results.json).
"""
import json
import math
import os

q = 1.602176634e-19
kB = 1.380649e-23
here = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- inputs
Rsq = {"min": 1240.0, "typ": 1700.0, "max": 2160.0}   # S: sky130 SPICE r+c corners, rnw [Ohm/sq]
Rsq_doc = {"min": 550.0, "typ": 950.0, "max": 1350.0}  # S: PDK device-details RSNW (discrepancy!)
tc1, tc2, tnom = 1.483e-3, 7.824e-6, 30.0              # S: sky130_fd_pr__res_generic_nw model
rH = 1.15                                              # S: Hall scattering factor, electrons in Si
xj_nw = 1.1e-4                                         # S: n-well vertical dimension 1.1 um [cm]
sti = 0.3e-4                                           # A: STI depth (KLayout xsect script value) [cm]
depl = {"min": 0.1e-4, "typ": 0.2e-4, "max": 0.3e-4}   # A: total depletion (top+bottom) [cm]

fd = json.load(open(os.path.join(here, "fd_results.json")))
ph = list(fd[sorted(fd)[0]].values())
G_H = ph[0]["G_H"]                                     # FD model (h = 0.5 um)
r_in = max(p["R_in"] for p in ph)                      # in units of Rsq
r_out = max(p["R_out"] for p in ph)

I_typ, I_min, I_max = 200e-6, 50e-6, 300e-6            # A: per-leaf bias current [A]


def mu_n_ct(N):
    """Caughey-Thomas electron mobility in Si, 300 K [cm^2/Vs].
    A: textbook parameters (mu_min 65, mu_max 1330, Nref 8.5e16, alpha 0.72),
    not verified against the PDK; replace with measured data."""
    return 65.0 + 1265.0 / (1.0 + (N / 8.5e16) ** 0.72)


def solve_N(Rs, t):
    """Effective donor density N such that Rs = 1 / (q N mu(N) t)."""
    lo, hi = 1e14, 1e19
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        if q * mid * mu_n_ct(mid) * t * Rs > 1.0:
            hi = mid
        else:
            lo = mid
    return mid


def line(name, val, unit, how):
    print(f"{name:<34s} {val:>12s} {unit:<10s} {how}")


print("=== material / sheet ===")
mus = {}
for c, (Rs, d) in {"typ": (Rsq["typ"], depl["typ"]),
                   "lo_mu": (Rsq["min"], depl["min"]),
                   "hi_mu": (Rsq["max"], depl["max"])}.items():
    t = xj_nw - sti - d
    N = solve_N(Rs, t)
    mu = mu_n_ct(N) * 1e-4
    mus[c] = rH * mu
    line(f"t_eff, N_eff, mu_n ({c})", f"{t*1e4:.2f}um {N:.2e}", f"{mu:.3f}m2/Vs",
         "t = xj - STI - depletion; N from Rsq = 1/(q N mu(N) t)")
muH = {"min": min(mus.values()), "typ": mus["typ"], "max": max(mus.values())}
line("mu_H", f"{muH['min']:.3f}/{muH['typ']:.3f}/{muH['max']:.3f}", "m2/Vs", "mu_H = r_H * mu_n")

print("\n=== plate (one leaf) ===")
line("G_H (FD)", f"{G_H:.3f}", "-", "fd_hall.py, all 4 phases equal (reciprocity)")
line("R_in/Rsq, R_out/Rsq (FD)", f"{r_in:.3f} {r_out:.3f}", "-", "fd_hall.py")
Rin = {k: r_in * v for k, v in Rsq.items()}
line("R_in 30C", f"{Rin['min']:.0f}/{Rin['typ']:.0f}/{Rin['max']:.0f}", "Ohm", "R_in = (R_in/Rsq) * Rsq corners")
fT = lambda T: 1 + tc1 * (T - tnom) + tc2 * (T - tnom) ** 2
line("R(T)/R(30C) at 0, 110 C", f"{fT(0):.3f} {fT(110):.3f}", "-", "1 + tc1 dT + tc2 dT^2")
line("R(T)/R(30C) at -40 C", f"{fT(-40):.3f}", "-", "same, extrapolated below model range?")
line("R_in worst (max corner, 110C)", f"{Rin['max']*fT(110):.0f}", "Ohm", "")
line("R_in best (min corner, 0C)", f"{Rin['min']*fT(0):.0f}", "Ohm", "")

# S_I = G_H * mu_H * Rsq  (equivalent to G_H r_H / (q n t))
SI = {"min": G_H * muH["min"] * Rsq["min"], "typ": G_H * muH["typ"] * Rsq["typ"],
      "max": G_H * muH["max"] * Rsq["max"]}
line("S_I", f"{SI['min']:.0f}/{SI['typ']:.0f}/{SI['max']:.0f}", "V/(A T)", "S_I = G_H * mu_H * Rsq")
SV = {k: G_H * muH[k] / r_in for k in muH}
line("S_V", f"{SV['min']*1e3:.1f}/{SV['typ']*1e3:.1f}/{SV['max']*1e3:.1f}", "mV/(V T)",
     "S_V = S_I / R_in = G_H mu_H / (R_in/Rsq)")
u = 0.25                                               # A: +-25 % uncertainty of mu_H model (unverified CT params)
line("S_I spec (incl. +-25% mu_H)", f"{SI['min']*(1-u):.0f}/{SI['typ']:.0f}/{SI['max']*(1+u):.0f}", "V/(A T)", "")
line("S_V spec (incl. +-25% mu_H)", f"{SV['min']*(1-u)*1e3:.1f}/{SV['typ']*1e3:.1f}/{SV['max']*(1+u)*1e3:.1f}", "mV/(V T)", "")
line("S_A spec at 200 uA (incl.)", f"{SI['min']*(1-u)*I_typ*1e3:.1f}/{SI['typ']*I_typ*1e3:.1f}/{SI['max']*(1+u)*I_typ*1e3:.1f}", "mV/T", "")
SA = SI["typ"] * I_typ
line("S_A at 200 uA", f"{SA*1e3:.1f}", "mV/T", "S_I * I_bias   (= uV/mT)")
line("S_A range at 200 uA", f"{SI['min']*I_typ*1e3:.1f}..{SI['max']*I_typ*1e3:.1f}", "mV/T", "")
Vp = {k: v * I_typ for k, v in Rin.items()}
line("V_plate at 200 uA, 30C", f"{Vp['min']:.2f}/{Vp['typ']:.2f}/{Vp['max']:.2f}", "V", "I * R_in")
line("V_plate at 300 uA, max, 110C", f"{I_max*Rin['max']*fT(110):.2f}", "V", "compliance check vs 3.3 V")
P = I_typ ** 2 * Rin["typ"]
line("P_plate at 200 uA", f"{P*1e3:.3f}", "mW", "I^2 R_in")
line("P from avdd if biased on-chip", f"{3.3*I_typ*1e3:.2f}", "mW", "3.3 V * I")

print("\n=== noise ===")
T = 300.0
Rout = r_out * Rsq["typ"]
vn = math.sqrt(4 * kB * T * Rout)
line("thermal v_n (one leaf)", f"{vn*1e9:.1f}", "nV/rtHz", "sqrt(4kT R_out), 300 K")
Bn = vn / SA
line("B_n thermal, one leaf 200 uA", f"{Bn*1e6:.2f}", "uT/rtHz", "v_n / S_A")
Bn2 = math.sqrt(4 * kB * T * Rout / 2) / SA
line("B_n thermal, pair (each 200 uA)", f"{Bn2*1e6:.2f}", "uT/rtHz", "R_out/2, same S_A")
Bn_hot = math.sqrt(4 * kB * 383 * Rsq["max"] * r_out * fT(110)) / (SI["min"] * I_typ)
Bn_hot = Bn_hot / (1 - u)
line("B_n worst (383 K, max R, min S_I incl. -25%)", f"{Bn_hot*1e6:.2f}", "uT/rtHz", "")
for bw in (10.0, 1e3):
    line(f"B_n rms in {bw:g} Hz (thermal only)", f"{Bn*math.sqrt(bw)*1e6:.3f}", "uT", "")

print("\n=== offset / linearity / bandwidth ===")
# geometric offset is zero by mirror symmetry; random raw offset from literature range
line("raw offset 5..50 mT -> V at 200uA", f"{5e-3*SA*1e6:.0f}..{50e-3*SA*1e6:.0f}", "uV", "B_off * S_A")
for B in (0.1, 0.5, 1.0):
    line(f"(mu_H B)^2 at B={B} T", f"{(muH['max']*B)**2*100:.3f}", "%", "magnetoresistance scale, max mu_H")
Rsw = 200.0   # A: 3.3 V transmission-gate on-resistance target
for C in (15e-12, 50e-12, 115e-12):
    tau = (Rout + Rsw) * C
    line(f"tau, f3dB with C_load={C*1e12:.0f} pF", f"{tau*1e9:.0f}ns {1/(2*math.pi*tau)/1e3:.0f}kHz", "",
         "(R_out + R_sw) C")
tau = (Rsq["max"] * r_out * fT(110) + Rsw) * 115e-12
line("phase settling 0.01% (9.2 tau), worst", f"{9.2*tau*1e6:.2f}", "us", "R max/110C, 115 pF")
line("-> max phase rate (settle <= 25%)", f"{0.25/(9.2*tau)/1e3:.0f}", "kHz", "")
# stray field of bias current in vein routing
for d in (2e-6, 5e-6):
    line(f"stray B of 300 uA wire at {d*1e6:.0f} um", f"{4e-7*math.pi*I_max/(2*math.pi*d)*1e6:.1f}", "uT", "mu0 I / (2 pi d)")
# skin depth in Al
rhoAl, f = 2.8e-8, 100e3
line("skin depth Al at 100 kHz", f"{math.sqrt(rhoAl/(math.pi*f*4e-7*math.pi))*1e6:.0f}", "um", "sqrt(rho/(pi f mu0))")

print("\n=== area ===")
import sys
sys.path.insert(0, os.path.join(here, "..", "layout"))
import ginkgo_geom as g
import numpy as np
p = g.LeafParams()
o = g.leaf_outline(p)
A = 0.5 * abs(sum(o[i, 0] * o[i - 1, 1] - o[i - 1, 0] * o[i, 1] for i in range(len(o))))
line("leaf n-well area", f"{A:.0f}", "um^2", "shoelace on generated outline")
w, h = float(np.ptp(o[:, 0])), float(np.ptp(o[:, 1]))
line("leaf bounding box", f"{w:.1f}x{h:.1f}", "um", "")

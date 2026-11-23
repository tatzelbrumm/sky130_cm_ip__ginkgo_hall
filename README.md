# sky130_cm_ip__ginkgo_hall

A Hall-effect magnetic field sensor IP block for the SkyWater Sky130 process (Chipalooza
Challenge #4). The Hall plate is an n-well region drawn as a ginkgo leaf (fan-shaped bilobed
blade plus petiole), so the layout art is the sensor. Two leaves are orthogonally coupled and
operated with a 4-phase spinning-current switch matrix; a Greek-cross plate on the same die
serves as reference. See **[Proposal.md](Proposal.md)** for I/O, functional description,
target specification and test plan.

## Regenerating the views

Requirements: Python 3 with `numpy`, `scipy`, `matplotlib`, and the `klayout` Python module
(`pip install klayout`), or a KLayout installation.

```
python3 layout/gen_ginkgo_hall.py            # -> layout/ginkgo_hall.gds, layout/ginkgo_hall.png
python3 analysis/fd_hall.py                  # FD plate model -> analysis/fd_results.json
python3 analysis/estimates.py > analysis/estimates.txt   # all [estimate] numbers of Proposal.md
```

DRC (KLayout, open_pdks sky130A deck): see the header of `layout/gen_ginkgo_hall.py`.

## License

Apache License 2.0, see [LICENSE](LICENSE).

# PCB-009D: experimental feed-edge mesh

`aligned` remains the default. `thirds` is an explicit experiment limited to
exactly two rectangular synthetic pads, their facing X edges and common Y
edges. Copper coordinates and the physical native port box are unchanged.
Z remains exactly zero. Unsupported contacts, conflicting anchors, reinserted
physical edge lines, or grading which splits an edge-hint cell are rejected.
This is not general polygon edge correction or Gerber support.

The requested edge scales are the smaller of the port and substrate XY steps.
Each edge cell has one third on the metal side and two thirds on the gap/air
side. Hints are preserved exactly. The discrete contact/gap audit uses actual
mesh coordinates; its active-edge count is a Python audit, not a verification
of undocumented native resistor implementation. Native grid readback remains
exact and no edges2grid request is made.

## Local experiment

```bat
set "CSXCAD_INSTALL_PATH=C:\dev\openems\openEMS"
.\.venv\Scripts\python.exe -m antenna_lab.pcb.edge_convergence
```

Four sequential runs: aligned_L2, aligned_L3, thirds_L2, thirds_L3.
They use the PCB-009C L2/L3 settings with no increase in domain or timestep
limits. Shared frequency CLI options remain available (`--help`). Results go
to a new directory under outcomes/pcb_edge_convergence; existing results are
never resumed or overwritten. JSON/CSV retain completed runs after a failure.

Both native Run flags exact_endcriteria and dump_statistics are enabled only
for this experiment. openEMS_stats.txt must contain finite timestep and elapsed
numerical time, consistent with a positive iteration count strictly below the
configured maximum. Missing/invalid statistics or reaching the cap prevents
comparison. Default control-run kwargs are unchanged.

The report compares L3/L2 in both modes and thirds/aligned at each level.
The engineering gate requires all-frequency relative Z/X <=1% and R <=5%,
finite passive data and termination checks. It is a diagnostic candidate,
not physical validation. Historical aligned drift around 2.3% is a broad
factor-of-two diagnostic only at the original band/frequencies, never an
exact pass criterion. No automatic default change follows from the report.

## API/source basis

- [openEMS mesh concepts, documentation labelled 0.37.0-rc3](https://docs.openems.de/en/latest/concepts/mesh.html): metal-edge thirds and risk of subsequent smoothing splitting that cell.
- Source examined at [6761a36e28567129d833de2ae7df4fb102dc5ceb](https://github.com/thliebig/openEMS/tree/6761a36e28567129d833de2ae7df4fb102dc5ceb):
  `python/openEMS/automesh.py` (edge-hint formula),
  `python/openEMS/ports.py` (physical LumpedPort bounds),
  `python/openEMS/openEMS.pyx` (Run keyword options and working directory),
  `openems.cpp` (exact-endcriteria and DumpStatistics value/%label format).
  This source inspection does not assert that the installed Windows binary
  was built from that exact commit.

Implementation tests use native fakes. The native A/B experiment remains to
be run with the supported Windows openEMS 0.37.0rc3/CSXCAD 0.7.0rc3 installation.
No real FDTD was executed during implementation.

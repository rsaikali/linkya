# nilm-lab — heater detector research (2026-10-29)

Offline lab for a new water-heater detector on the Linky curve (no HA switch data, no radiator hints).
Data (not committed): `linky.csv.gz` = `\copy (select extract(epoch from time), papp from linky_realtime order by time) to stdout with csv`,
`sigs.csv` = nilm_signatures (id, is_negative, start epoch, end epoch, created_at).

Pipeline: `anchors.py` (14:24 / 23:54 contactor cycles = certain positives) -> `stab.py` (heater level reference)
-> `lab.py` (semi-synthetic data engine: real quiet curve + real heater templates + radiators/negatives/synthetic loads)
-> `model.py` (dilated gated TCN, 3 input channels: curve/ref, HC-window flag, derivative) -> `infer.py` + `refine2.py`
(sliding inference, segments, edge snapping) -> `evalreal.py`, `synthtest.py`, `episodes.py` (evaluation).
Paths in the scripts point at the session scratchpad: adjust `load.py` / `lab.py` before reuse.

## Status 2026-10-29 (end of session)
- Production code: `nilm-service/src/nilm/detectors/matched_filter.py` + `src/matched_engine.py` (+ tests). This lab only holds research:
  `bench.py` (same code, 4 appliances, signatures from the first 60 % of the timeline), `bench35b.py` (profile from the 35 DB signatures,
  rolling 2 h replay), `truth.py` / `truth2.py` (smart-plug ground truth vs detections), `prod_check.py` (read-only check of the DB glue inside the
  running nilm container), `lattice.py` / `trans.py` (edge-height clusters, switch-on transient: shared by all resistive heating elements).
- `models/tcn_v1.keras` + `lab.py` / `model.py` / `infer.py`: dilated gated TCN trained on semi-synthetic mixtures (real quiet curve + real
  templates). Prototype for appliances WITHOUT plateaus; it still contains heater-specific bits (tariff-window input channel) to remove first.
- Smart-plug power history (not committed) lives in the session scratchpad: `plugs/*.csv` (epoch, W), pulled read-only from HA.

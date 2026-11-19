# PHYS 2210 Oscilloscope

## Diode plots

Saved experimental figures are in [`analysis/`](analysis/). Each figure is available as PNG, SVG, and PDF, with CSV source tables and Python plotting scripts beside it.

| Figure | Preview | PDF |
| --- | --- | --- |
| Schottky vs. Vishay: relative voltage difference vs. nominal input | [PNG](analysis/2026-11-12_schottky_vishay/relative_difference.png) | [PDF](analysis/2026-11-12_schottky_vishay/relative_difference.pdf) |
| Schottky vs. Vishay: measured output vs. nominal input | [PNG](analysis/2026-11-12_schottky_vishay/output_vs_input.png) | [PDF](analysis/2026-11-12_schottky_vishay/output_vs_input.pdf) |
| 120 Ω load current vs. load voltage | [PNG](analysis/2026-11-12_120ohm/load_iv_120ohm.png) | [PDF](analysis/2026-11-12_120ohm/load_iv_120ohm.pdf) |
| Three-diode measured output vs. nominal input | [PNG](analysis/2026-11-12_120ohm/output_vs_input.png) | [PDF](analysis/2026-11-12_120ohm/output_vs_input.pdf) |
| Output voltage vs. frequency | [PNG](analysis/2026-11-12_120ohm/voltage_vs_frequency.png) | [PDF](analysis/2026-11-12_120ohm/voltage_vs_frequency.pdf) |
| Combined three-panel figure | [PNG](analysis/2026-11-12_120ohm/today_diagrams.png) | [PDF](analysis/2026-11-12_120ohm/today_diagrams.pdf) |

The normalized two-diode figure uses **100 × (measured output − nominal input) / nominal input (%)**. Both voltages are peak-to-peak; nominal input comes from the generator setting recorded in each capture folder name. The two-diode comparison includes 11 Schottky and 11 Vishay captures at nominal 5 kHz.

![Schottky and Vishay relative voltage difference](analysis/2026-11-12_schottky_vishay/relative_difference.png)

The 120 Ω figures preserve an earlier 31-capture snapshot, including 13 `in4007` captures whose raw files are unavailable in this checkout. Reproduce that snapshot from its included summary CSV. The [two-diode notes](analysis/2026-11-12_schottky_vishay/README.md) and [120 Ω notes](analysis/2026-11-12_120ohm/README.md) describe the measurements and selection rules. Saved CSV paths, provenance, and audit records retain their original local source locations.

### Reproduce the figures

From the repository root, install the plotting dependencies and run:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-analysis.txt
.venv/bin/python analysis/2026-11-12_schottky_vishay/plot_output_vs_input.py
.venv/bin/python analysis/2026-11-12_schottky_vishay/plot_relative_difference.py
.venv/bin/python analysis/2026-11-12_120ohm/plot_diagrams.py --resistance-ohm 120 --from-summary
```

These commands overwrite the corresponding generated figures and tables. Font choice follows locally available fonts; the committed figures use Helvetica.

## Capture waveforms

Standalone **Python 3.12** script for fetching Tektronix **TBS2074B** waveforms and measurements over Ethernet. Requires only `python-vxi11` plus Python's standard library.

Connect your computer to the scope's network, enable the desired channels, and set the correct probe factors. Replace `SCOPE_IP` with the address shown on the scope:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install python-vxi11==0.9
.venv/bin/python capture.py --host SCOPE_IP
```

Add `--channels CH1 CH2` to select channels or `--output ./my_capture` to choose a new output folder. By default, CSVs, raw responses, and metadata go to `data/<timestamp>/` beside the script.

Press **Stop** on the scope first if channels must share a stopped acquisition; running acquisitions are read sequentially. The script preserves acquisition settings and restores its temporary transfer/measurement settings.

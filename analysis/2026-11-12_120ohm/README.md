# Diode capture diagrams — 12 November 2026

These plots use a snapshot of 31 saved captures from 12 November 2026: 7 Schottky, 11 Vishay, and 13 from the `in4007` folder. The analysis uses the user-supplied **120 Ω** resistor value and the stated CH1 connection across the resistor for all selected captures.

All plotted voltage amplitudes are **peak-to-peak**. Output voltage is the native CH1 peak-to-peak measurement in `measurements.csv`. Input voltage is the **nominal setting in the folder name**, not an independently recorded input waveform. Frequency is the oscilloscope's native measured frequency.

## Figures

**(a) Load current versus load voltage.** The 26 captures at nominal 5 kHz are plotted using `I_pp (mA) = 1000 × V_pp (V) / 120 Ω`. The dashed line shows this conversion. Current is inferred from voltage, so the straight line is the resistor load relation, not a measured diode-junction I–V characteristic. A diode I–V curve requires the voltage across the diode as well as its current.

**(b) Output voltage versus nominal input voltage.** The same 26 captures at nominal 5 kHz show the measured CH1 peak-to-peak voltage against the input setting. The later `in4007` repeat at 3 Vpp is retained as an open diamond. Some coincident points overlap; no observations are averaged or offset.

**(c) Output voltage versus frequency.** Only the 9 captures labeled nominal 3 Vpp are used, so input-amplitude changes do not become frequency effects. `in4007` has six frequency settings from 1 to 25 kHz plus a later 5 kHz repeat. Schottky and Vishay each have one point near 5 kHz in the current saved folders; these single points do not establish frequency-response curves for those devices.

The three panels are combined in `today_diagrams.png`, `.svg`, and `.pdf`. Individual figures use the stems `load_iv_120ohm`, `output_vs_input`, and `voltage_vs_frequency` and are also available in PNG, SVG, and PDF. Each individual figure is 150 × 150 mm; the combined figure is 360 × 140 mm.

## Source and reproduction

`source_data.csv` contains every included capture, its folder and retrieval time, nominal settings, native measurements, waveform-derived statistics, inferred currents, and hashes of the source files. `amplitude_sweep_data.csv` and `frequency_sweep_data.csv` give the exact plotted subsets. Mean and RMS quantities remain separate from peak-to-peak values. The scope was running during sequential retrieval, so native measurements can differ slightly from statistics of the saved waveform.

No fitted curves, fabricated uncertainty bars, smoothing, or averaging were added. Resistance tolerance and measurement uncertainty were not provided. Plotting symbols are observations, not estimated uncertainty intervals.

From the repository root, after installing `requirements-analysis.txt` into `.venv`, redraw the saved snapshot with:

```bash
.venv/bin/python analysis/2026-11-12_120ohm/plot_diagrams.py --resistance-ohm 120 --from-summary
```

The saved summary includes 13 historical `in4007` captures whose raw files were absent from the data directory on November 19. Use `--from-summary` to reproduce all 31 observations. To analyze the raw files currently present, omit `--from-summary` and pass a separate `--output` directory to preserve the historical summary. `figure_style.py` is the local Seshadri plotting helper copied from the figure-style skill; its hash and the plotting-library versions are recorded in `provenance.json`.

All current conversions were independently checked at 120 Ω. The selection rules, source counts, and vector exports were checked. The combined PDF render, grayscale overview, and native-size quarter previews of the combined and individual figures were visually inspected for legibility and overlap.

The committed CSV paths, provenance, and figure audits record the original local analysis locations. Regenerating updates paths recorded by the scripts to the current checkout.

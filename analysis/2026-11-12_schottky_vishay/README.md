# Schottky and Vishay input–output voltage

Output voltage versus nominal input voltage for the 5 kHz amplitude sweeps in `data/half wave Schottky data` and `data/half wave vishay data`.

Both axes use peak-to-peak volts. Input values are the settings in the capture folder names; output values are the oscilloscope's native CH1 peak-to-peak measurements in `measurements.csv`. Each marker represents a capture. No averaging, fitting, smoothing, or uncertainty bars are applied.

The plot is saved as `output_vs_input.png`, `.svg`, and `.pdf`. `source_data.csv` preserves the plotted values, capture paths, timestamps, measured frequencies, and hashes of the source files. The plotting code and local style helper are included.

From the repository root, after installing `requirements-analysis.txt` into `.venv`, regenerate with:

```bash
.venv/bin/python analysis/2026-11-12_schottky_vishay/plot_output_vs_input.py
```

## Relative voltage difference

`relative_difference.pdf` shows the signed difference between the measured load voltage and the nominal generator setting as a percentage of that setting. Each marker represents one capture. Negative values indicate a load voltage below the generator setting. `relative_difference.csv` lists both voltages, their difference in volts peak-to-peak, the signed fraction, and the percentage for each capture.

Regenerate the comparison from the saved `source_data.csv` with

```bash
.venv/bin/python analysis/2026-11-12_schottky_vishay/plot_relative_difference.py
```

The committed CSV paths, provenance, and figure audits record the original local analysis locations. Regenerating updates paths recorded by the scripts to the current checkout.

#!/usr/bin/env python3
"""Plot native CH1 output Vpp against nominal input Vpp from two capture folders."""
import csv
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / 'data'
os.environ.setdefault('MPLCONFIGDIR', str(HERE.parent / '2026-11-12_120ohm/.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import figure_style as sf

SOURCES = {
    'Schottky': DATA / 'half wave Schottky data',
    'Vishay': DATA / 'half wave vishay data',
}
PATTERN = re.compile(r'^(\d+(?:\.\d+)?)\s*khz\s+(\d+(?:\.\d+)?)\s*vpp$', re.I)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows = []
    for dataset, source in SOURCES.items():
        assert source.is_dir(), source
        for path in sorted(source.rglob('metadata.json')):
            metadata = json.loads(path.read_text())
            capture = path.parent
            condition = PATTERN.fullmatch(capture.relative_to(source).parts[0])
            assert condition, f'Unrecognized condition: {capture}'
            assert float(condition[1]) == 5, f'Expected a 5 kHz capture: {capture}'
            assert metadata['complete'], f'Incomplete capture: {capture}'
            measurement_path = capture / 'measurements.csv'
            with measurement_path.open(newline='') as handle:
                values = {r['measurement']: r for r in csv.DictReader(handle) if r['channel'] == 'CH1'}
            for key, unit in [('peak_to_peak', 'V'), ('frequency', 'Hz')]:
                assert values[key]['status'] == 'valid' and values[key]['unit'] == unit
                assert math.isfinite(float(values[key]['value']))
            rows.append({
                'dataset': dataset,
                'nominal_input_vpp_v': float(condition[2]),
                'output_vpp_v': float(values['peak_to_peak']['value']),
                'measured_frequency_hz': float(values['frequency']['value']),
                'nominal_frequency_hz': 5000,
                'retrieved_at': metadata['retrieved_at'],
                'capture_path': str(capture.resolve()),
                'measurements_sha256': file_hash(measurement_path),
                'metadata_sha256': file_hash(path),
            })
    rows.sort(key=lambda r: (r['dataset'], r['nominal_input_vpp_v'], r['retrieved_at']))
    assert rows and {r['dataset'] for r in rows} == set(SOURCES)
    with (HERE / 'source_data.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    style = sf.apply_seshadri_style(fontsize=10, frame='open', dpi=300)
    styles = sf.series_styles(list(SOURCES))
    fig, axes = sf.subplots(width_mm=150, height_mm=150)
    ax = axes[0, 0]
    counts = {}
    for dataset in SOURCES:
        points = [r for r in rows if r['dataset'] == dataset]
        counts[dataset] = len(points)
        ax.plot([r['nominal_input_vpp_v'] for r in points],
                [r['output_vpp_v'] for r in points],
                label=dataset, **dict(styles[dataset], linestyle='none', markersize=5.5))
    ax.set(xlim=(0, 16), ylim=(0, 5.6),
           xlabel='Nominal input voltage (V peak-to-peak)',
           ylabel='Measured output voltage (V peak-to-peak)',
           title='Input–output voltage at 5 kHz')
    ax.set_xticks([0, 5, 10, 15])
    ax.set_yticks([0, 1, 2, 3, 4, 5])
    sf.inplot_legend(ax, loc='upper left')
    for line, dataset in zip(ax.lines, SOURCES):
        points = [r for r in rows if r['dataset'] == dataset]
        assert list(line.get_xdata()) == [r['nominal_input_vpp_v'] for r in points]
        assert list(line.get_ydata()) == [r['output_vpp_v'] for r in points]
    _, audit = sf.save_figure(fig, HERE / 'output_vs_input', dpi=300, overwrite=True)
    plt.close(fig)
    provenance = {
        'generated_at': datetime.now().astimezone().isoformat(),
        'sources': {name: str(path.resolve()) for name, path in SOURCES.items()},
        'capture_counts': counts,
        'x_definition': 'Nominal input Vpp from the user-assigned condition folder.',
        'y_definition': 'Native CH1 peak-to-peak voltage in measurements.csv.',
        'frequency_selection': 'All included folders are labeled 5 kHz.',
        'point_handling': 'Every capture is shown; no averaging, fitting, or smoothing.',
        'source_data_sha256': file_hash(HERE / 'source_data.csv'),
        'style': style,
        'automated_audit': audit['automated_status'],
    }
    (HERE / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps({'capture_counts': counts, 'total': len(rows), 'audit': audit['automated_status'], 'output': str(HERE / 'output_vs_input.png')}, indent=2))


if __name__ == '__main__':
    main()

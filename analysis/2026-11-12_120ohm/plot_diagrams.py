#!/usr/bin/env python3
"""Extract today's captures and plot load I-V, input/output, and frequency data.

Run with Python and the dependencies in requirements-analysis.txt. Use --from-summary to redraw
from the saved source_data.csv without reading the original capture folders.
"""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR', str(HERE / '.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import figure_style as sf

GROUPS = {
    'Voltage sweeps/half wave Schottky data': 'Schottky',
    'Voltage sweeps/half wave vishay data': 'Vishay',
    'Other captures/in4007': 'in4007',
}
CONDITION = re.compile(r'^(\d+(?:\.\d+)?)\s*khz\s+(\d+(?:\.\d+)?)\s*vpp$', re.I)
FIELDS = [
    'capture_id', 'dataset', 'retrieved_at', 'nominal_frequency_hz',
    'nominal_input_vpp_v', 'measured_frequency_hz', 'output_vpp_v',
    'output_mean_v', 'output_rms_v', 'waveform_vpp_v', 'waveform_mean_v',
    'waveform_rms_v', 'resistance_ohm', 'derived_current_pp_ma',
    'derived_current_mean_ma', 'derived_current_rms_ma', 'sample_count',
    'adc_endpoint_samples', 'metadata_sha256', 'measurements_sha256',
    'waveform_sha256',
]
NUMERIC = set(FIELDS) - {
    'capture_id', 'dataset', 'retrieved_at', 'metadata_sha256',
    'measurements_sha256', 'waveform_sha256',
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(data_root, date, resistance):
    rows = []
    for folder, label in GROUPS.items():
        group_root = data_root / folder
        if not group_root.is_dir():
            group_root = data_root / Path(folder).name  # Also accept the original layout.
        for meta_path in sorted(group_root.rglob('metadata.json')):
            metadata = json.loads(meta_path.read_text())
            if datetime.fromisoformat(metadata['retrieved_at']).date().isoformat() != date:
                continue
            capture = meta_path.parent
            parts = capture.relative_to(group_root).parts
            condition = CONDITION.fullmatch(parts[0])
            if not condition:
                raise ValueError(f'Unrecognized condition folder: {capture}')
            assert metadata['complete'], f'Incomplete capture: {capture}'
            assert list(metadata['channels']) == ['CH1'], f'Unexpected channels: {capture}'
            assert all(x['ok'] for x in metadata['restoration'].values())
            measurement_path = capture / 'measurements.csv'
            with measurement_path.open(newline='') as handle:
                measurements = {r['measurement']: r for r in csv.DictReader(handle) if r['channel'] == 'CH1'}
            values = {}
            for name in ['frequency', 'peak_to_peak', 'mean', 'rms']:
                entry = measurements[name]
                assert entry['status'] == 'valid', f'Unavailable {name}: {capture}'
                assert entry['unit'] == ('Hz' if name == 'frequency' else 'V')
                values[name] = float(entry['value'])
                assert math.isfinite(values[name])
            waveform_path = capture / 'CH1_waveform.csv'
            with waveform_path.open(newline='') as handle:
                samples = list(csv.DictReader(handle))
            times = np.array([float(r['time_s']) for r in samples])
            volts = np.array([float(r['voltage_v']) for r in samples])
            codes = np.array([int(r['adc_code']) for r in samples])
            assert len(samples) == metadata['channels']['CH1']['preamble']['point_count']
            assert np.isfinite(times).all() and np.isfinite(volts).all()
            assert (np.diff(times) > 0).all()
            rows.append({
                'capture_id': str(capture.relative_to(data_root)),
                'dataset': label,
                'retrieved_at': metadata['retrieved_at'],
                'nominal_frequency_hz': float(condition[1]) * 1000,
                'nominal_input_vpp_v': float(condition[2]),
                'measured_frequency_hz': values['frequency'],
                'output_vpp_v': values['peak_to_peak'],
                'output_mean_v': values['mean'],
                'output_rms_v': values['rms'],
                'waveform_vpp_v': float(np.ptp(volts)),
                'waveform_mean_v': float(np.mean(volts)),
                'waveform_rms_v': float(np.sqrt(np.mean(volts ** 2))),
                'resistance_ohm': resistance,
                'derived_current_pp_ma': 1000 * values['peak_to_peak'] / resistance,
                'derived_current_mean_ma': 1000 * values['mean'] / resistance,
                'derived_current_rms_ma': 1000 * values['rms'] / resistance,
                'sample_count': len(samples),
                'adc_endpoint_samples': int(np.isin(codes, [-128, 127]).sum()),
                'metadata_sha256': sha256(meta_path),
                'measurements_sha256': sha256(measurement_path),
                'waveform_sha256': sha256(waveform_path),
            })
    return sorted(rows, key=lambda r: r['retrieved_at'])


def write_csv(path, rows):
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def split_repeats(rows, xkey):
    primary, repeats, seen = [], [], set()
    for row in sorted(rows, key=lambda r: r['retrieved_at']):
        key = row[xkey]
        (repeats if key in seen else primary).append(row)
        seen.add(key)
    return sorted(primary, key=lambda r: r[xkey]), repeats


def draw(ax, rows, kind, styles, resistance):
    for dataset in GROUPS.values():
        group = [r for r in rows if r['dataset'] == dataset]
        if not group:
            continue
        key = 'nominal_frequency_hz' if kind == 'frequency' else 'nominal_input_vpp_v'
        primary, repeats = split_repeats(group, key)
        style = dict(styles[dataset], linestyle='none', markersize=5.5)
        label = dataset
        if kind == 'frequency' and len(primary) == 1:
            label += ' (one frequency)'
        for points, repeated in [(primary, False), (repeats, True)]:
            if not points:
                continue
            if kind == 'iv':
                x = [r['output_vpp_v'] for r in points]
                y = [r['derived_current_pp_ma'] for r in points]
            elif kind == 'input':
                x = [r['nominal_input_vpp_v'] for r in points]
                y = [r['output_vpp_v'] for r in points]
            else:
                x = [r['measured_frequency_hz'] / 1000 for r in points]
                y = [r['output_vpp_v'] for r in points]
            current_style = dict(style)
            if repeated:
                current_style.update(marker='D', markerfacecolor='white', markersize=7)
            ax.plot(x, y, label=label + (' repeat' if repeated else ''), **current_style, zorder=3)
    if kind == 'iv':
        x = np.array([0, 5.6])
        ax.plot(x, 1000 * x / resistance, color='#888888', linestyle='--', marker='', linewidth=0.9, zorder=1)
        ax.set(xlim=(0, 5.6), ylim=(0, 48),
               xlabel='Load voltage (V peak-to-peak)',
               ylabel='Derived load current (mA peak-to-peak)',
               title=f'Load I–V at 5 kHz, R = {resistance:g} Ω')
        ax.set_xticks([0, 1, 2, 3, 4, 5])
        ax.set_yticks([0, 10, 20, 30, 40])
        sf.inplot_legend(ax, loc='upper left')
    elif kind == 'input':
        ax.set(xlim=(0, 16), ylim=(0, 5.6),
               xlabel='Nominal input voltage (V peak-to-peak)',
               ylabel='Measured output voltage (V peak-to-peak)',
               title='Input–output voltage at 5 kHz')
        ax.set_xticks([0, 5, 10, 15])
        ax.set_yticks([0, 1, 2, 3, 4, 5])
        sf.inplot_legend(ax, loc='upper left')
    else:
        ax.set(xlim=(0, 27), ylim=(0, 2.6),
               xlabel='Measured frequency (kHz)',
               ylabel='Measured output voltage (V peak-to-peak)',
               title='Frequency response at nominal 3 Vpp')
        ax.set_xticks([0, 5, 10, 15, 20, 25])
        ax.set_yticks([0, 0.5, 1.0, 1.5, 2.0, 2.5])
        sf.inplot_legend(ax, loc='center right')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', default='2026-11-12')
    parser.add_argument('--resistance-ohm', type=float, default=120)
    parser.add_argument('--data-root', type=Path, default=HERE.parents[1] / 'data')
    parser.add_argument('--output', type=Path, default=HERE)
    parser.add_argument('--from-summary', action='store_true')
    args = parser.parse_args()
    assert args.resistance_ohm > 0 and math.isfinite(args.resistance_ohm)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.from_summary:
        with (args.output / 'source_data.csv').open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            for key in NUMERIC:
                row[key] = float(row[key])
        assert all(r['resistance_ohm'] == args.resistance_ohm for r in rows)
    else:
        rows = extract(args.data_root, args.date, args.resistance_ohm)
        write_csv(args.output / 'source_data.csv', rows)
    assert rows, 'No matching captures.'
    amplitude = [r for r in rows if r['nominal_frequency_hz'] == 5000]
    frequency = [r for r in rows if r['nominal_input_vpp_v'] == 3]
    write_csv(args.output / 'amplitude_sweep_data.csv', amplitude)
    write_csv(args.output / 'frequency_sweep_data.csv', frequency)
    for row in rows:
        assert math.isclose(row['derived_current_pp_ma'], row['output_vpp_v'] * 1000 / args.resistance_ohm)
    style_settings = sf.apply_seshadri_style(fontsize=10, frame='open', dpi=300)
    styles = sf.series_styles(list(GROUPS.values()))
    plots = [('load_iv_120ohm', 'iv', amplitude),
             ('output_vs_input', 'input', amplitude),
             ('voltage_vs_frequency', 'frequency', frequency)]
    audits = {}
    for stem, kind, selected in plots:
        fig, axes = sf.subplots(width_mm=150, height_mm=150)
        draw(axes[0, 0], selected, kind, styles, args.resistance_ohm)
        _, report = sf.save_figure(fig, args.output / stem, dpi=300, overwrite=True)
        audits[stem] = report['automated_status']
        plt.close(fig)
    fig, axes = sf.subplots(1, 3, width_mm=360, height_mm=140)
    for ax, (stem, kind, selected), letter in zip(axes.flat, plots, 'abc'):
        draw(ax, selected, kind, styles, args.resistance_ohm)
        if kind in {'iv', 'input'}:
            sf.inplot_legend(ax, loc=(0.02, 0.66))
        sf.panel_label(ax, letter)
    _, report = sf.save_figure(fig, args.output / 'today_diagrams', dpi=300, overwrite=True)
    audits['today_diagrams'] = report['automated_status']
    plt.close(fig)
    provenance = {
        'date': args.date,
        'resistance_ohm': args.resistance_ohm,
        'resistance_source': 'User-supplied value; CH1 across the resistor. Applied to all selected captures.',
        'source_root': str(args.data_root.resolve()),
        'capture_count': len(rows),
        'amplitude_plot_capture_count': len(amplitude),
        'frequency_plot_capture_count': len(frequency),
        'voltage_definition': 'Native oscilloscope CH1 peak-to-peak measurements, in volts.',
        'current_definition': 'Derived peak-to-peak resistor current = 1000 * CH1 Vpp / R, in mA.',
        'input_definition': 'Nominal source Vpp taken from the user-assigned capture folder name, not independently measured input.',
        'repeat_handling': 'Every capture retained. Later repeated setpoints shown as open diamonds. No averaging, fitting, jitter, or fabricated error bars.',
        'iv_interpretation': 'Load relation across the resistor, not a diode junction I-V measurement.',
        'frequency_coverage_nominal_khz': {
            group: sorted({r['nominal_frequency_hz'] / 1000 for r in frequency if r['dataset'] == group})
            for group in GROUPS.values()
        },
        'source_summary_sha256': sha256(args.output / 'source_data.csv'),
        'analysis_generated_at': datetime.now().astimezone().isoformat(),
        'capture_timing': 'Native measurements and waveform records were retrieved sequentially while acquisition was running.',
        'style': style_settings,
        'style_helper_sha256': sha256(HERE / 'figure_style.py'),
        'matplotlib_version': matplotlib.__version__,
        'numpy_version': np.__version__,
        'automated_figure_audits': audits,
    }
    (args.output / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps({k: provenance[k] for k in ['capture_count', 'amplitude_plot_capture_count', 'frequency_plot_capture_count', 'automated_figure_audits']}, indent=2))


if __name__ == '__main__':
    main()

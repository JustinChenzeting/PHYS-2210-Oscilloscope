"""Compare measured load Vpp with nominal generator Vpp in the 5 kHz sweeps."""

import csv
from decimal import Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import figure_style as sf


HERE = Path(__file__).resolve().parent


def main():
    with (HERE / "source_data.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        nominal = Decimal(row["nominal_input_vpp_v"])
        measured = Decimal(row["output_vpp_v"])
        if nominal <= 0 or Decimal(row["nominal_frequency_hz"]) != 5000:
            raise ValueError(f"Expected positive nominal Vpp at 5 kHz in {row['capture_path']}")
        difference = measured - nominal
        row["difference_vpp_v"] = difference
        row["relative_difference"] = difference / nominal
        row["relative_difference_pct"] = 100 * difference / nominal

    columns = ["dataset", "nominal_input_vpp_v", "output_vpp_v", "difference_vpp_v",
               "relative_difference", "relative_difference_pct", "capture_path"]
    with (HERE / "relative_difference.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    sf.apply_seshadri_style(fontsize=10, frame="open", dpi=300)
    fig, axes = sf.subplots(width_mm=150)
    ax = axes[0, 0]
    datasets = sorted({row["dataset"] for row in rows})
    for dataset, style in sf.series_styles(datasets).items():
        points = [row for row in rows if row["dataset"] == dataset]
        ax.plot([float(row["nominal_input_vpp_v"]) for row in points],
                [float(row["relative_difference_pct"]) for row in points],
                label=dataset, **dict(style, linestyle="none", markersize=5.5))
    ax.set(title="Half-wave rectification at 5 kHz",
           xlabel="Nominal input voltage (V peak-to-peak)",
           ylabel="(Measured output − nominal input) / nominal input (%)",
           xticks=[1, 3, 5, 10, 15], yticks=[-100, -90, -80, -70, -60])
    sf.inplot_legend(ax, loc="lower right")
    sf.save_figure(fig, HERE / "relative_difference", dpi=300, overwrite=True)
    plt.close(fig)


if __name__ == "__main__":
    main()

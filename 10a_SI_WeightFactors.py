"""Generate empirical suitability weights as a numbered workflow step.

Run this after all individual suitability criteria are available and before
`11_SI_Farmarea.py`, which consumes `weightfactors/empirical_weights.json` by
default.
"""

from pathlib import Path

from weightfactors.evaluate_weight_factors import generate_empirical_weights


def build_empirical_weight_factors(
    output_dir=Path("Output"),
    data_dir=Path("Data"),
    weights_dir=Path("weightfactors"),
    output_file=None,
):
    weights_dir = Path(weights_dir)
    output_file = Path(output_file) if output_file else weights_dir / "empirical_weights.json"

    generate_empirical_weights(
        output_dir=Path(output_dir),
        data_dir=Path(data_dir),
        out_weights_file=output_file,
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate empirical SI weight factors for the vertical 1-12 workflow."
    )
    parser.add_argument(
        "--output-dir",
        default="Output",
        help="Directory containing xr_SI_*.nc criterion outputs.",
    )
    parser.add_argument(
        "--data-dir",
        default="Data",
        help="Directory containing plant and feedstock input data.",
    )
    parser.add_argument(
        "--weights-dir",
        default="weightfactors",
        help="Directory where the default empirical weight file is written.",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="Optional explicit JSON output path. Defaults to weightfactors/empirical_weights.json.",
    )
    args = parser.parse_args()

    build_empirical_weight_factors(
        output_dir=Path(args.output_dir),
        data_dir=Path(args.data_dir),
        weights_dir=Path(args.weights_dir),
        output_file=args.output_file,
    )


if __name__ == "__main__":
    main()

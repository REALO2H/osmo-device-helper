import csv
import re
import getpass
import argparse
from pathlib import Path


def get_current_user() -> str:
    """Return the current OS username."""
    try:
        return getpass.getuser()
    except Exception:
        return ""


def split_sample_id(sample_id: str):
    """
    Split SampleID like:
      'jMDA.^01' -> ('jMDA.', '01')
      '0.^02'    -> ('0.', '02')
      'ABC'      -> ('ABC', '')
    """
    if sample_id is None:
        return "", ""

    sample_id = sample_id.strip()

    if "^" in sample_id:
        lot, port = sample_id.split("^", 1)
    else:
        lot, port = sample_id, ""

    return lot.strip(), port.strip()


def is_viable_lot(lot: str) -> bool:
    """
    Decide whether the lot number is 'real' or just a placeholder.
    We treat these as NOT viable:
      - empty
      - only zeros / dots / dashes / spaces
      Examples:
        '', '0', '0.', '000', '------------------', '.'
    Valid examples:
        'jMDA.', 'OMAR1', '55', 'S-20260413-00201'
    """
    if not lot:
        return False

    compact = re.sub(r"\s+", "", lot)

    # Only placeholder characters? -> not viable
    if re.fullmatch(r"[0.\-]+", compact):
        return False

    return True


def transform_csv(input_path: Path, output_path: Path, operator_override: str = ""):
    operator = operator_override.strip() if operator_override else get_current_user()

    last_valid_lot = ""
    output_rows = []

    with input_path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            result_type = (row.get("ResultType") or "").strip()

            # Only keep the OSM rows
            if result_type != "^^^Osm":
                continue

            measurement_timestamp = (row.get("MeasurementTimestamp") or "").strip()
            sample_id = (row.get("SampleID") or "").strip()
            result_value = (row.get("ResultValue") or "").strip()
            flags = (row.get("Flags") or "").strip()
            error_or_comment = (row.get("ErrorOrComment") or "").strip()

            lot, port = split_sample_id(sample_id)

            # If lot is not usable, inherit from previous valid lot
            if is_viable_lot(lot):
                last_valid_lot = lot
            else:
                lot = last_valid_lot

            output_rows.append({
                "Port": port,
                "Lot-Number": lot,
                "Value": result_value,
                "Unit": "mOsm/kg",
                "Timestamp": measurement_timestamp,
                "Operator": operator,
                "Flags": flags,
                "ErrorOrComment": error_or_comment
            })

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "Port",
                "Lot-Number",
                "Value",
                "Unit",
                "Timestamp",
                "Operator",
                "Flags",
                "ErrorOrComment"
            ]
        )
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Done. Output written to:\n{output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Transform OM6070 parsed CSV into simplified CSV"
    )
    parser.add_argument("input_csv", help="Path to the input CSV file")
    parser.add_argument(
        "-o", "--output",
        help="Path to the output CSV file (default: inputname_transformed.csv)"
    )
    parser.add_argument(
        "--operator",
        help="Optional operator name override (default: current computer user)",
        default=""
    )

    args = parser.parse_args()

    input_path = Path(args.input_csv)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_name(input_path.stem + "_transformed.csv")

    transform_csv(input_path, output_path, args.operator)


if __name__ == "__main__":
    main()

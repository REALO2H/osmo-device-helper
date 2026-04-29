import csv
import re
import getpass
import argparse
import time
import json
import traceback
from pathlib import Path
from tempfile import NamedTemporaryFile


def get_current_user() -> str:
    """Return the current OS username."""
    try:
        return getpass.getuser()
    except Exception:
        return ""


def ensure_parent_folder(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


def write_log(log_file: Path | None, message: str):
    if not log_file:
        return
    try:
        ensure_parent_folder(log_file)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except Exception:
        pass


def update_heartbeat(
    heartbeat_file: Path | None,
    state: str,
    details: str,
    input_csv: Path,
    output_csv: Path
):
    if not heartbeat_file:
        return

    try:
        ensure_parent_folder(heartbeat_file)
        payload = {
            "pid": __import__("os").getpid(),
            "state": state,
            "details": details,
            "last_seen": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "input_csv": str(input_csv),
            "output_csv": str(output_csv),
        }
        heartbeat_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


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


def resolve_operator(operator_override: str) -> str:
    """
    For now:
      - use --operator if provided
      - otherwise use current OS user
    Later, this can be extended to read from an owner/supervisor file.
    """
    if operator_override and operator_override.strip():
        return operator_override.strip()
    return get_current_user()


def transform_csv(input_path: Path, output_path: Path, operator_override: str = "", log_file: Path | None = None):
    operator = resolve_operator(operator_override)

    last_valid_lot = ""
    output_rows = []

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    write_log(log_file, f"Transforming input: {input_path}")

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

    # Atomic write: write to temp file first, then replace
    ensure_parent_folder(output_path)
    with NamedTemporaryFile("w", newline="", encoding="utf-8", delete=False, dir=str(output_path.parent)) as tmp:
        writer = csv.DictWriter(
            tmp,
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
        temp_name = tmp.name

    Path(temp_name).replace(output_path)

    write_log(log_file, f"Output updated: {output_path} ({len(output_rows)} rows)")
    print(f"Updated: {output_path}")


def watch_csv(
    input_path: Path,
    output_path: Path,
    operator_override: str = "",
    stop_file: Path | None = None,
    heartbeat_file: Path | None = None,
    log_file: Path | None = None,
    interval: float = 1.0
):
    last_mtime = None
    last_size = None

    write_log(log_file, f"Watcher started. Input={input_path} Output={output_path}")
    update_heartbeat(heartbeat_file, "starting", "Watcher initializing", input_path, output_path)

    print(f"Watching: {input_path}")
    print(f"Output  : {output_path}")

    while True:
        try:
            if stop_file and stop_file.exists():
                write_log(log_file, f"Stop file detected: {stop_file}")
                update_heartbeat(heartbeat_file, "stopping", "Stop file detected", input_path, output_path)
                print("Stop file detected. Exiting watcher.")
                break

            if input_path.exists():
                stat = input_path.stat()
                mtime = stat.st_mtime
                size = stat.st_size

                if mtime != last_mtime or size != last_size:
                    try:
                        transform_csv(input_path, output_path, operator_override, log_file=log_file)
                        last_mtime = mtime
                        last_size = size
                        update_heartbeat(heartbeat_file, "running", "Transformed latest input", input_path, output_path)
                    except Exception as e:
                        write_log(log_file, f"Transform error: {e}")
                        write_log(log_file, traceback.format_exc())
                        update_heartbeat(heartbeat_file, "error", str(e), input_path, output_path)

            else:
                update_heartbeat(heartbeat_file, "waiting", "Input CSV not found yet", input_path, output_path)

            time.sleep(interval)

        except KeyboardInterrupt:
            write_log(log_file, "Watcher interrupted by user")
            update_heartbeat(heartbeat_file, "stopped", "Interrupted by user", input_path, output_path)
            print("Stopping watcher.")
            break
        except Exception as e:
            write_log(log_file, f"Watcher loop error: {e}")
            write_log(log_file, traceback.format_exc())
            update_heartbeat(heartbeat_file, "error", str(e), input_path, output_path)
            time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(
        description="Transform OM6070 parsed CSV into simplified CSV"
    )

    parser.add_argument(
        "input_csv",
        nargs="?",
        default=r"C:\OSMO\Osmo6070\OM6070_Parsed_Live.csv",
        help="Path to the input CSV file"
    )

    parser.add_argument(
        "-o", "--output",
        default=r"C:\OSMO\Osmo6070\OM6070_Transformed_Live.csv",
        help="Path to the output CSV file"
    )

    parser.add_argument(
        "--operator",
        help="Optional operator name override (default: current computer user)",
        default=""
    )

    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch the input CSV continuously and update output whenever it changes"
    )

    parser.add_argument(
        "--stop-file",
        default=r"C:\OSMO\Osmo6070\stop_transform.flag",
        help="Path to a stop flag file"
    )

    parser.add_argument(
        "--heartbeat-file",
        default=r"C:\OSMO\Osmo6070\transform_heartbeat.json",
        help="Path to heartbeat JSON file"
    )

    parser.add_argument(
        "--log-file",
        default=r"C:\OSMO\Osmo6070\transform.log",
        help="Path to transformer log file"
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds when using --watch"
    )

    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_path = Path(args.output)
    stop_file = Path(args.stop_file) if args.stop_file else None
    heartbeat_file = Path(args.heartbeat_file) if args.heartbeat_file else None
    log_file = Path(args.log_file) if args.log_file else None

    ensure_parent_folder(output_path)
    if stop_file:
        ensure_parent_folder(stop_file)
    if heartbeat_file:
        ensure_parent_folder(heartbeat_file)
    if log_file:
        ensure_parent_folder(log_file)

    # Optional: remove stale stop file at startup
    if stop_file and stop_file.exists():
        try:
            stop_file.unlink()
        except Exception:
            pass

    if args.watch:
        watch_csv(
            input_path=input_path,
            output_path=output_path,
            operator_override=args.operator,
            stop_file=stop_file,
            heartbeat_file=heartbeat_file,
            log_file=log_file,
            interval=args.interval
        )
    else:
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        transform_csv(input_path, output_path, args.operator, log_file=log_file)
        update_heartbeat(heartbeat_file, "finished", "One-shot transformation completed", input_path, output_path)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


def run_step(command: list[str], step_name: str) -> None:
    print(f"\n==> {step_name}")
    print("$ " + " ".join(shlex.quote(part) for part in command), flush=True)
    subprocess.run(command, check=True)


def add_optional_float_arg(command: list[str], flag: str, value: float | None) -> None:
    if value is not None:
        command.extend([flag, str(value)])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automatisiert den gesamten Workflow: Datenabruf und Orbit-Aehnlichkeitsanalyse."
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python-Interpreter fuer die Teilskripte (Standard: aktueller Interpreter).",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Ueberspringt den API-Abruf und nutzt vorhandene CSV-Dateien.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=20,
        help="Anzahl paralleler Verbindungen fuer den Orbit-Abruf (nur wenn Fetch aktiv).",
    )
    parser.add_argument(
        "--mode",
        choices=("very-strict", "strict", "normal"),
        default="strict",
        help="Modus fuer die Orbit-Aehnlichkeitsanalyse (Standard: strict).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Anzahl Treffer, die die Analyse in der Konsole ausgibt.",
    )

    parser.add_argument("--score-threshold", type=float, default=None)
    parser.add_argument("--e-tol", type=float, default=None)
    parser.add_argument("--q-tol", type=float, default=None)
    parser.add_argument("--i-tol", type=float, default=None)
    parser.add_argument("--om-tol", type=float, default=None)
    parser.add_argument("--w-tol", type=float, default=None)
    parser.add_argument("--a-rel-tol", type=float, default=None)

    parser.add_argument(
        "--comets-output",
        type=Path,
        default=Path("data/comets.csv"),
        help="Zieldatei fuer Kometenliste.",
    )
    parser.add_argument(
        "--orbits-output",
        type=Path,
        default=Path("data/comets_orbits.csv"),
        help="Zieldatei fuer Orbitdaten.",
    )
    parser.add_argument(
        "--similar-output",
        type=Path,
        default=Path("data/similar_orbits.csv"),
        help="Zieldatei fuer aehnliche Orbit-Paare.",
    )
    parser.add_argument(
        "--exact-output",
        type=Path,
        default=Path("data/exact_orbit_groups.csv"),
        help="Zieldatei fuer exakte Orbit-Gruppen.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    root = Path(__file__).resolve().parent
    fetch_script = root / "fetch_comets.py"
    find_script = root / "find_similar_orbits.py"

    if not fetch_script.exists() or not find_script.exists():
        raise SystemExit("Benoetigte Skripte nicht gefunden (fetch_comets.py/find_similar_orbits.py).")

    if not args.skip_fetch:
        fetch_command = [
            args.python,
            str(fetch_script),
            "--output",
            str(args.comets_output),
            "--orbit-output",
            str(args.orbits_output),
            "--workers",
            str(args.workers),
        ]
        run_step(fetch_command, "Schritt 1/2: Kometen- und Orbitdaten abrufen")
    else:
        if not args.orbits_output.exists():
            raise SystemExit(
                f"--skip-fetch gesetzt, aber Orbit-Datei fehlt: {args.orbits_output}. "
                "Bitte zuerst Daten abrufen oder --skip-fetch entfernen."
            )
        if not args.comets_output.exists():
            print(
                f"Hinweis: Kometen-Datei nicht gefunden ({args.comets_output}). "
                "Namen koennen dann teilweise generisch sein.",
                flush=True,
            )

    find_command = [
        args.python,
        str(find_script),
        "--orbits",
        str(args.orbits_output),
        "--comets",
        str(args.comets_output),
        "--output",
        str(args.similar_output),
        "--exact-output",
        str(args.exact_output),
        "--mode",
        args.mode,
        "--top",
        str(args.top),
    ]
    add_optional_float_arg(find_command, "--score-threshold", args.score_threshold)
    add_optional_float_arg(find_command, "--e-tol", args.e_tol)
    add_optional_float_arg(find_command, "--q-tol", args.q_tol)
    add_optional_float_arg(find_command, "--i-tol", args.i_tol)
    add_optional_float_arg(find_command, "--om-tol", args.om_tol)
    add_optional_float_arg(find_command, "--w-tol", args.w_tol)
    add_optional_float_arg(find_command, "--a-rel-tol", args.a_rel_tol)

    run_step(find_command, "Schritt 2/2: Orbit-Aehnlichkeiten berechnen")

    print("\nPipeline abgeschlossen.")
    print(f"Aehnliche Paare: {args.similar_output}")
    print(f"Exakte Gruppen: {args.exact_output}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"Pipeline fehlgeschlagen (Exit-Code {error.returncode}).") from error
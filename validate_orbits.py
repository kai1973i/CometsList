#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ORBITS_PATH = Path("data/comets_orbits.csv")
DEFAULT_ISSUES_OUTPUT = Path("data/orbit_plausibility_issues.csv")
DEFAULT_SUMMARY_OUTPUT = Path("data/orbit_plausibility_summary.csv")

CORE_FIELDS = ("e", "a", "q", "i", "om", "w")


@dataclass(frozen=True)
class Issue:
    comet_id: str
    severity: str
    rule: str
    message: str
    details: str


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def is_angle_in_range(value: float) -> bool:
    return 0.0 <= value < 360.0


def add_issue(
    issues: list[Issue],
    comet_id: str,
    severity: str,
    rule: str,
    message: str,
    details: str,
) -> None:
    issues.append(
        Issue(
            comet_id=comet_id,
            severity=severity,
            rule=rule,
            message=message,
            details=details,
        )
    )


def write_issues_csv(issues: list[Issue], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=["comet_id", "severity", "rule", "message", "details"],
        )
        writer.writeheader()
        for issue in issues:
            writer.writerow(
                {
                    "comet_id": issue.comet_id,
                    "severity": issue.severity,
                    "rule": issue.rule,
                    "message": issue.message,
                    "details": issue.details,
                }
            )


def write_summary_csv(summary: dict[str, str | int], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["metric", "value"])
        writer.writeheader()
        for key, value in summary.items():
            writer.writerow({"metric": key, "value": value})


def validate_row(
    row: dict[str, str],
    abs_tolerance: float,
    rel_tolerance: float,
    parabolic_eps: float,
) -> list[Issue]:
    comet_id = (row.get("comet_id") or "").strip() or "unknown"
    issues: list[Issue] = []

    values = {key: parse_float(row.get(key)) for key in ("e", "a", "q", "ad", "i", "om", "w", "ma", "per")}

    missing_core = [field for field in CORE_FIELDS if values[field] is None]
    if missing_core:
        add_issue(
            issues,
            comet_id,
            "WARN",
            "incomplete_core_fields",
            "Orbitdatensatz hat fehlende Kernfelder.",
            f"missing={','.join(missing_core)}",
        )

    e = values["e"]
    a = values["a"]
    q = values["q"]
    ad = values["ad"]
    i = values["i"]
    om = values["om"]
    w = values["w"]
    ma = values["ma"]
    per = values["per"]

    if e is not None:
        if e < 0:
            add_issue(issues, comet_id, "ERROR", "eccentricity_negative", "Exzentrizitaet e ist negativ.", f"e={e}")
        if e > 2:
            add_issue(issues, comet_id, "WARN", "eccentricity_extreme", "Exzentrizitaet e ist sehr hoch.", f"e={e}")

    if q is not None and q <= 0:
        add_issue(issues, comet_id, "ERROR", "perihelion_non_positive", "Perihel-Distanz q ist nicht positiv.", f"q={q}")

    if i is not None and not (0 <= i <= 180):
        add_issue(issues, comet_id, "ERROR", "inclination_out_of_range", "Inklination i liegt ausserhalb [0,180].", f"i={i}")

    if om is not None and not is_angle_in_range(om):
        add_issue(issues, comet_id, "WARN", "node_longitude_out_of_range", "Knotenlaenge om liegt ausserhalb [0,360).", f"om={om}")

    if w is not None and not is_angle_in_range(w):
        add_issue(issues, comet_id, "WARN", "perihelion_argument_out_of_range", "Perihelargument w liegt ausserhalb [0,360).", f"w={w}")

    if ma is not None and not (-1 <= ma < 361):
        add_issue(issues, comet_id, "WARN", "mean_anomaly_out_of_range", "Mittlere Anomalie ma ist ungewoehnlich.", f"ma={ma}")

    if per is not None and per <= 0:
        add_issue(issues, comet_id, "ERROR", "period_non_positive", "Umlaufperiode per ist nicht positiv.", f"per={per}")

    if e is not None and a is not None:
        if e < 1 - parabolic_eps and a <= 0:
            add_issue(
                issues,
                comet_id,
                "ERROR",
                "elliptic_semimajor_non_positive",
                "Gebundene Bahn (e<1) mit nicht-positiver grosser Halbachse a.",
                f"e={e};a={a}",
            )
        if e > 1 + parabolic_eps and a >= 0:
            add_issue(
                issues,
                comet_id,
                "WARN",
                "hyperbolic_semimajor_non_negative",
                "Hyperbolische Bahn (e>1) mit nicht-negativer grosser Halbachse a.",
                f"e={e};a={a}",
            )

    # In der Naehe von e=1 sind a-basierte Formeln numerisch instabil und oft stark gerundet.
    if e is not None and abs(1 - e) > parabolic_eps and a is not None and q is not None:
        expected_q = a * (1 - e)
        diff = abs(q - expected_q)
        allowed = max(abs_tolerance, rel_tolerance * max(abs(q), abs(expected_q), 1.0))
        if diff > allowed:
            severity = "ERROR" if diff > 5 * allowed else "WARN"
            add_issue(
                issues,
                comet_id,
                severity,
                "q_inconsistent_with_a_e",
                "q passt nicht zur Beziehung q = a * (1 - e).",
                f"q={q};expected_q={expected_q};diff={diff};allowed={allowed}",
            )

    if e is not None and abs(1 - e) > parabolic_eps and a is not None and ad is not None:
        expected_ad = a * (1 + e)
        diff = abs(ad - expected_ad)
        allowed = max(abs_tolerance, rel_tolerance * max(abs(ad), abs(expected_ad), 1.0))
        if diff > allowed:
            severity = "ERROR" if diff > 5 * allowed else "WARN"
            add_issue(
                issues,
                comet_id,
                severity,
                "ad_inconsistent_with_a_e",
                "ad passt nicht zur Beziehung ad = a * (1 + e).",
                f"ad={ad};expected_ad={expected_ad};diff={diff};allowed={allowed}",
            )

    if q is not None and ad is not None and q > ad:
        add_issue(
            issues,
            comet_id,
            "WARN",
            "perihelion_greater_than_aphelion",
            "q ist groesser als ad.",
            f"q={q};ad={ad}",
        )

    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prueft Orbitdaten auf Plausibilitaet und mathematische Konsistenz."
    )
    parser.add_argument(
        "--orbits",
        type=Path,
        default=DEFAULT_ORBITS_PATH,
        help=f"Pfad zur Orbit-CSV (Standard: {DEFAULT_ORBITS_PATH})",
    )
    parser.add_argument(
        "--issues-output",
        type=Path,
        default=DEFAULT_ISSUES_OUTPUT,
        help=f"Pfad zur Issues-CSV (Standard: {DEFAULT_ISSUES_OUTPUT})",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=DEFAULT_SUMMARY_OUTPUT,
        help=f"Pfad zur Summary-CSV (Standard: {DEFAULT_SUMMARY_OUTPUT})",
    )
    parser.add_argument(
        "--abs-tolerance",
        type=float,
        default=0.03,
        help="Absolute Toleranz fuer Formelchecks (q/ad).",
    )
    parser.add_argument(
        "--rel-tolerance",
        type=float,
        default=0.02,
        help="Relative Toleranz fuer Formelchecks (q/ad).",
    )
    parser.add_argument(
        "--parabolic-eps",
        type=float,
        default=0.001,
        help="Toleranz um e=1 fuer Klassifikation elliptisch/hyperbolisch.",
    )
    parser.add_argument(
        "--fail-on-errors",
        action="store_true",
        help="Beendet mit Exit-Code 1, wenn mindestens ein ERROR gefunden wurde.",
    )
    parser.add_argument(
        "--show",
        type=int,
        default=20,
        help="Anzahl Issues fuer die Konsolenausgabe.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.orbits.exists():
        raise SystemExit(f"Orbit-Datei nicht gefunden: {args.orbits}")

    with args.orbits.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        required_columns = {"comet_id", "e", "a", "q", "i", "om", "w"}
        missing = sorted(col for col in required_columns if col not in (reader.fieldnames or []))
        if missing:
            raise SystemExit("Orbit-CSV hat nicht alle erwarteten Spalten: " + ", ".join(missing))

        all_rows = list(reader)

    all_issues: list[Issue] = []
    checked_rows = 0
    for row in all_rows:
        comet_id = (row.get("comet_id") or "").strip()
        if not comet_id:
            continue
        checked_rows += 1
        all_issues.extend(
            validate_row(
                row,
                abs_tolerance=args.abs_tolerance,
                rel_tolerance=args.rel_tolerance,
                parabolic_eps=args.parabolic_eps,
            )
        )

    error_count = sum(1 for issue in all_issues if issue.severity == "ERROR")
    warn_count = sum(1 for issue in all_issues if issue.severity == "WARN")
    affected_comets = len({issue.comet_id for issue in all_issues})

    summary = {
        "checked_rows": checked_rows,
        "issue_count": len(all_issues),
        "error_count": error_count,
        "warn_count": warn_count,
        "affected_comets": affected_comets,
    }

    write_issues_csv(all_issues, args.issues_output)
    write_summary_csv(summary, args.summary_output)

    print(f"Gepruefte Datensaetze: {checked_rows}")
    print(f"Gefundene Issues: {len(all_issues)} (ERROR={error_count}, WARN={warn_count})")
    print(f"Betroffene Kometen: {affected_comets}")
    print(f"Issues-CSV: {args.issues_output}")
    print(f"Summary-CSV: {args.summary_output}")

    show_n = max(args.show, 0)
    if show_n > 0 and all_issues:
        print(f"Top {min(show_n, len(all_issues))} Issues:")
        for issue in all_issues[:show_n]:
            print(
                "  - "
                f"{issue.comet_id} [{issue.severity}] {issue.rule}: {issue.message} "
                f"({issue.details})"
            )

    if args.fail_on_errors and error_count > 0:
        raise SystemExit("Plausibilitaetspruefung fehlgeschlagen: ERROR-Issues gefunden.")


if __name__ == "__main__":
    main()
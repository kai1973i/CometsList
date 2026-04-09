#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ORBITS_PATH = Path("data/comets_orbits.csv")
DEFAULT_COMETS_PATH = Path("data/comets.csv")
DEFAULT_OUTPUT_PATH = Path("data/similar_orbits.csv")
DEFAULT_EXACT_OUTPUT_PATH = Path("data/exact_orbit_groups.csv")

MODE_PROFILES = {
    "very-strict": {
        "score_threshold": 0.45,
        "e_tol": 0.006,
        "q_tol": 0.1,
        "i_tol": 1.0,
        "om_tol": 2.5,
        "w_tol": 2.5,
        "a_rel_tol": 0.07,
    },
    "strict": {
        "score_threshold": 0.6,
        "e_tol": 0.01,
        "q_tol": 0.15,
        "i_tol": 1.5,
        "om_tol": 4.0,
        "w_tol": 4.0,
        "a_rel_tol": 0.1,
    },
    "normal": {
        "score_threshold": 1.0,
        "e_tol": 0.02,
        "q_tol": 0.3,
        "i_tol": 3.0,
        "om_tol": 8.0,
        "w_tol": 8.0,
        "a_rel_tol": 0.2,
    },
}

NUMERIC_COLUMNS = ("e", "q", "i", "om", "w", "a")


@dataclass(frozen=True)
class OrbitRecord:
    comet_id: int
    name: str
    e: float
    q: float
    i: float
    om: float
    w: float
    a: float


@dataclass(frozen=True)
class SimilarPair:
    record_a: OrbitRecord
    record_b: OrbitRecord
    score: float
    de: float
    dq: float
    di: float
    dom: float
    dw: float
    da_rel: float


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


def angular_difference(a: float, b: float) -> float:
    delta = abs((a - b) % 360.0)
    return min(delta, 360.0 - delta)


def relative_difference(a: float, b: float) -> float:
    scale = max(abs(a), abs(b), 1.0)
    return abs(a - b) / scale


def load_comet_names(comets_path: Path) -> dict[int, str]:
    if not comets_path.exists():
        return {}

    names: dict[int, str] = {}
    with comets_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            raw_id = row.get("id", "").strip()
            if not raw_id:
                continue
            try:
                comet_id = int(raw_id)
            except ValueError:
                continue

            label = (row.get("fullname") or "").strip() or (row.get("name") or "").strip()
            if label:
                names[comet_id] = label

    return names


def load_orbits(orbits_path: Path, comet_names: dict[int, str]) -> list[OrbitRecord]:
    records: list[OrbitRecord] = []

    with orbits_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)

        missing_columns = [col for col in ("comet_id",) + NUMERIC_COLUMNS if col not in reader.fieldnames]
        if missing_columns:
            raise SystemExit(
                "Orbit-CSV hat nicht alle erwarteten Spalten: " + ", ".join(sorted(missing_columns))
            )

        for row in reader:
            raw_id = (row.get("comet_id") or "").strip()
            if not raw_id:
                continue

            try:
                comet_id = int(raw_id)
            except ValueError:
                continue

            values: dict[str, float] = {}
            skip = False
            for column in NUMERIC_COLUMNS:
                parsed = parse_float(row.get(column))
                if parsed is None:
                    skip = True
                    break
                values[column] = parsed

            if skip:
                continue

            records.append(
                OrbitRecord(
                    comet_id=comet_id,
                    name=comet_names.get(comet_id, f"Comet {comet_id}"),
                    e=values["e"],
                    q=values["q"],
                    i=values["i"],
                    om=values["om"],
                    w=values["w"],
                    a=values["a"],
                )
            )

    return records


def group_exact_matches(records: list[OrbitRecord], decimals: int) -> list[list[OrbitRecord]]:
    buckets: dict[tuple[float, ...], list[OrbitRecord]] = {}

    for record in records:
        key = (
            round(record.e, decimals),
            round(record.q, decimals),
            round(record.i, decimals),
            round(record.om % 360.0, decimals),
            round(record.w % 360.0, decimals),
            round(record.a, decimals),
        )
        buckets.setdefault(key, []).append(record)

    return [group for group in buckets.values() if len(group) > 1]


def similarity_score(
    a: OrbitRecord,
    b: OrbitRecord,
    e_tol: float,
    q_tol: float,
    i_tol: float,
    om_tol: float,
    w_tol: float,
    a_rel_tol: float,
) -> tuple[float, float, float, float, float, float, float]:
    de = abs(a.e - b.e)
    dq = abs(a.q - b.q)
    di = abs(a.i - b.i)
    dom = angular_difference(a.om, b.om)
    dw = angular_difference(a.w, b.w)
    da_rel = relative_difference(a.a, b.a)

    components = (
        de / e_tol,
        dq / q_tol,
        di / i_tol,
        dom / om_tol,
        dw / w_tol,
        da_rel / a_rel_tol,
    )
    score = math.sqrt(sum(value * value for value in components) / len(components))
    return score, de, dq, di, dom, dw, da_rel


def find_similar_pairs(
    records: list[OrbitRecord],
    e_tol: float,
    q_tol: float,
    i_tol: float,
    om_tol: float,
    w_tol: float,
    a_rel_tol: float,
    score_threshold: float,
) -> list[SimilarPair]:
    pairs: list[SimilarPair] = []
    total = len(records)

    for idx in range(total):
        rec_a = records[idx]
        for jdx in range(idx + 1, total):
            rec_b = records[jdx]
            score, de, dq, di, dom, dw, da_rel = similarity_score(
                rec_a, rec_b, e_tol, q_tol, i_tol, om_tol, w_tol, a_rel_tol
            )
            if score <= score_threshold:
                pairs.append(
                    SimilarPair(
                        record_a=rec_a,
                        record_b=rec_b,
                        score=score,
                        de=de,
                        dq=dq,
                        di=di,
                        dom=dom,
                        dw=dw,
                        da_rel=da_rel,
                    )
                )

    pairs.sort(key=lambda item: item.score)
    return pairs


def write_pairs_csv(pairs: list[SimilarPair], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "comet_id_1",
                "name_1",
                "comet_id_2",
                "name_2",
                "score",
                "de",
                "dq",
                "di",
                "dom",
                "dw",
                "da_rel",
            ],
        )
        writer.writeheader()
        for pair in pairs:
            writer.writerow(
                {
                    "comet_id_1": pair.record_a.comet_id,
                    "name_1": pair.record_a.name,
                    "comet_id_2": pair.record_b.comet_id,
                    "name_2": pair.record_b.name,
                    "score": f"{pair.score:.6f}",
                    "de": f"{pair.de:.6f}",
                    "dq": f"{pair.dq:.6f}",
                    "di": f"{pair.di:.6f}",
                    "dom": f"{pair.dom:.6f}",
                    "dw": f"{pair.dw:.6f}",
                    "da_rel": f"{pair.da_rel:.6f}",
                }
            )


def write_exact_groups_csv(exact_groups: list[list[OrbitRecord]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "group_id",
                "group_size",
                "comet_id",
                "name",
                "e",
                "q",
                "i",
                "om",
                "w",
                "a",
            ],
        )
        writer.writeheader()

        for group_id, group in enumerate(exact_groups, start=1):
            for record in sorted(group, key=lambda item: item.comet_id):
                writer.writerow(
                    {
                        "group_id": group_id,
                        "group_size": len(group),
                        "comet_id": record.comet_id,
                        "name": record.name,
                        "e": f"{record.e:.6f}",
                        "q": f"{record.q:.6f}",
                        "i": f"{record.i:.6f}",
                        "om": f"{record.om:.6f}",
                        "w": f"{record.w:.6f}",
                        "a": f"{record.a:.6f}",
                    }
                )


def resolve_similarity_settings(args: argparse.Namespace) -> dict[str, float]:
    settings = MODE_PROFILES[args.mode].copy()

    for key in ("score_threshold", "e_tol", "q_tol", "i_tol", "om_tol", "w_tol", "a_rel_tol"):
        value = getattr(args, key)
        if value is not None:
            settings[key] = value

    return settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Liest Orbitdaten von Kometen und findet identische oder sehr aehnliche Bahnen."
        )
    )
    parser.add_argument(
        "--orbits",
        type=Path,
        default=DEFAULT_ORBITS_PATH,
        help=f"Pfad zur Orbit-CSV (Standard: {DEFAULT_ORBITS_PATH})",
    )
    parser.add_argument(
        "--comets",
        type=Path,
        default=DEFAULT_COMETS_PATH,
        help=f"Pfad zur Kometen-CSV fuer Namen (Standard: {DEFAULT_COMETS_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Pfad zur Ergebnis-CSV (Standard: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--exact-output",
        type=Path,
        default=DEFAULT_EXACT_OUTPUT_PATH,
        help=f"Pfad zur CSV mit exakten Orbit-Gruppen (Standard: {DEFAULT_EXACT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--mode",
        choices=("very-strict", "strict", "normal"),
        default="strict",
        help="Profil fuer Aehnlichkeitsgrenzen (Standard: strict).",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=None,
        help="Maximaler Aehnlichkeits-Score (ueberschreibt den Profilwert).",
    )
    parser.add_argument("--e-tol", type=float, default=None, help="Toleranz fuer Exzentrizitaet e (Override).")
    parser.add_argument("--q-tol", type=float, default=None, help="Toleranz fuer Perihel q in AU (Override).")
    parser.add_argument("--i-tol", type=float, default=None, help="Toleranz fuer Inklination i in Grad (Override).")
    parser.add_argument("--om-tol", type=float, default=None, help="Toleranz fuer Knotenlaenge om (Override).")
    parser.add_argument("--w-tol", type=float, default=None, help="Toleranz fuer Argument des Perihels w (Override).")
    parser.add_argument(
        "--a-rel-tol",
        type=float,
        default=None,
        help="Relative Toleranz fuer grosse Halbachse a (Override).",
    )
    parser.add_argument(
        "--exact-decimals",
        type=int,
        default=6,
        help="Rundungsstellen fuer den Vergleich auf exakt gleiche Orbits.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Anzahl Top-Treffer, die in der Konsole angezeigt werden.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = resolve_similarity_settings(args)

    if not args.orbits.exists():
        raise SystemExit(f"Orbit-Datei nicht gefunden: {args.orbits}")

    comet_names = load_comet_names(args.comets)
    records = load_orbits(args.orbits, comet_names)
    if not records:
        raise SystemExit("Keine gueltigen Orbit-Datensaetze gefunden.")

    exact_groups = group_exact_matches(records, decimals=args.exact_decimals)
    similar_pairs = find_similar_pairs(
        records,
        e_tol=settings["e_tol"],
        q_tol=settings["q_tol"],
        i_tol=settings["i_tol"],
        om_tol=settings["om_tol"],
        w_tol=settings["w_tol"],
        a_rel_tol=settings["a_rel_tol"],
        score_threshold=settings["score_threshold"],
    )

    write_pairs_csv(similar_pairs, args.output)
    write_exact_groups_csv(exact_groups, args.exact_output)

    print(f"Gueltige Orbit-Datensaetze: {len(records)}")
    print(
        "Modus: "
        f"{args.mode} "
        f"(score={settings['score_threshold']}, e={settings['e_tol']}, q={settings['q_tol']}, "
        f"i={settings['i_tol']}, om={settings['om_tol']}, w={settings['w_tol']}, a_rel={settings['a_rel_tol']})"
    )
    print(f"Exakt gleiche Orbits (Gruppen): {len(exact_groups)}")
    if exact_groups:
        print("Beispiele fuer exakte Gruppen:")
        for group in exact_groups[:5]:
            members = ", ".join(f"{item.comet_id}:{item.name}" for item in group)
            print(f"  - {members}")

    print(f"Aehnliche Orbit-Paare (Score <= {settings['score_threshold']}): {len(similar_pairs)}")
    print(f"Ergebnis-CSV geschrieben: {args.output}")
    print(f"Exakte Gruppen-CSV geschrieben: {args.exact_output}")

    top_n = max(args.top, 0)
    if top_n > 0 and similar_pairs:
        print(f"Top {min(top_n, len(similar_pairs))} aehnliche Paare:")
        for pair in similar_pairs[:top_n]:
            print(
                "  - "
                f"{pair.record_a.comet_id}:{pair.record_a.name} <-> "
                f"{pair.record_b.comet_id}:{pair.record_b.name} "
                f"(Score={pair.score:.3f}, de={pair.de:.3f}, dq={pair.dq:.3f}, "
                f"di={pair.di:.3f}, dom={pair.dom:.3f}, dw={pair.dw:.3f}, da_rel={pair.da_rel:.3f})"
            )


if __name__ == "__main__":
    main()
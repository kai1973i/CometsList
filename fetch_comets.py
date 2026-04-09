#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


API_URL = "https://cobs.si/api/comet_list.api"
ORBIT_API_URL = "https://www.cobs.si/api/comet.api"
DEFAULT_OUTPUT = Path("data/comets.csv")
DEFAULT_ORBIT_OUTPUT = Path("data/comets_orbits.csv")
ORBIT_FIELD_ORDER = [
    "comet_id",
    "e",
    "a",
    "q",
    "ad",
    "i",
    "om",
    "w",
    "ma",
    "tp",
    "tp_cd",
    "per",
    "epoch",
    "reference",
]
DEFAULT_FIELD_ORDER = [
    "id",
    "type",
    "name",
    "fullname",
    "mpc_name",
    "icq_name",
    "component",
    "current_mag",
    "perihelion_date",
    "perihelion_mag",
    "peak_mag",
    "peak_mag_date",
    "is_observed",
    "is_active",
]


def fetch_comets(api_url: str) -> list[dict[str, Any]]:
    try:
        with urlopen(api_url, timeout=30) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise SystemExit(f"HTTP-Fehler beim Abruf der API: {error.code} {error.reason}") from error
    except URLError as error:
        raise SystemExit(f"Netzwerkfehler beim Abruf der API: {error.reason}") from error

    objects = payload.get("objects")
    if not isinstance(objects, list):
        raise SystemExit("Unerwartetes API-Format: 'objects' ist keine Liste.")

    normalized_objects: list[dict[str, Any]] = []
    for entry in objects:
        if isinstance(entry, dict):
            normalized_objects.append(entry)

    return normalized_objects


def fetch_orbit(comet_id: int, orbit_api_url: str) -> dict[str, Any] | None:
    url = f"{orbit_api_url}?id={comet_id}&orbit=true"
    try:
        with urlopen(url, timeout=30) as response:
            payload = json.load(response)
    except (HTTPError, URLError):
        return None

    orbit = payload.get("orbit")
    if not isinstance(orbit, dict):
        return None

    orbit["comet_id"] = comet_id
    return orbit


def fetch_all_orbits(
    comet_ids: list[int],
    orbit_api_url: str,
    workers: int = 20,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    total = len(comet_ids)
    done = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_orbit, cid, orbit_api_url): cid for cid in comet_ids}
        for future in as_completed(futures):
            done += 1
            if done % 100 == 0 or done == total:
                print(f"  Orbit-Abruf: {done}/{total} ...", flush=True)
            result = future.result()
            if result is not None:
                results.append(result)

    results.sort(key=lambda r: r["comet_id"])
    return results


def build_fieldnames(
    objects: list[dict[str, Any]], preferred_order: list[str] = DEFAULT_FIELD_ORDER
) -> list[str]:
    discovered_fields = {key for entry in objects for key in entry.keys()}
    ordered_fields = [field for field in preferred_order if field in discovered_fields]
    extra_fields = sorted(discovered_fields - set(ordered_fields))
    return ordered_fields + extra_fields


def write_csv(
    objects: list[dict[str, Any]],
    output_path: Path,
    preferred_order: list[str] = DEFAULT_FIELD_ORDER,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = build_fieldnames(objects, preferred_order)

    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(objects)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Liest Kometen von der COBS-API und speichert sie als CSV."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Pfad zur Ausgabedatei (Standard: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--api-url",
        default=API_URL,
        help=f"API-URL fuer die Kometenliste (Standard: {API_URL})",
    )
    parser.add_argument(
        "--orbit-output",
        type=Path,
        default=DEFAULT_ORBIT_OUTPUT,
        help=f"Pfad zur Orbit-CSV (Standard: {DEFAULT_ORBIT_OUTPUT})",
    )
    parser.add_argument(
        "--orbit-api-url",
        default=ORBIT_API_URL,
        help=f"Basis-URL fuer die Orbit-API (Standard: {ORBIT_API_URL})",
    )
    parser.add_argument(
        "--no-orbits",
        action="store_true",
        help="Orbit-Daten nicht abrufen.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=20,
        help="Anzahl paralleler HTTP-Verbindungen fuer den Orbit-Abruf (Standard: 20).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    objects = fetch_comets(args.api_url)

    if not objects:
        raise SystemExit("Die API hat keine Kometendaten geliefert.")

    write_csv(objects, args.output)
    print(f"{len(objects)} Kometen nach {args.output} geschrieben.")

    if not args.no_orbits:
        comet_ids = [int(obj["id"]) for obj in objects if "id" in obj]
        print(f"Lade Orbit-Daten fuer {len(comet_ids)} Kometen ...")
        orbits = fetch_all_orbits(comet_ids, args.orbit_api_url, workers=args.workers)
        write_csv(orbits, args.orbit_output, preferred_order=ORBIT_FIELD_ORDER)
        print(f"{len(orbits)} Orbit-Datensaetze nach {args.orbit_output} geschrieben.")


if __name__ == "__main__":
    main()
# CometsList

CometsList ist ein kleines Python-Projekt zum Abrufen und Auswerten von Kometendaten.
Es nutzt die COBS-API, speichert Kometen- und Orbitdaten als CSV und findet Kometen mit gleichen oder sehr aehnlichen Bahndaten.

## Projektziele

- Kometenliste von COBS abrufen und lokal speichern.
- Orbitdaten fuer Kometen abrufen und als Tabelle speichern.
- Exakt gleiche Orbits gruppieren.
- Sehr aehnliche Orbits mit konfigurierbaren Toleranzen erkennen.

## Projektstruktur

- `fetch_comets.py`: Laedt Kometenliste und (optional) Orbitdaten von der API.
- `find_similar_orbits.py`: Analysiert Orbitdaten und sucht gleiche/aehnliche Bahnen.
- `validate_orbits.py`: Prueft Orbitdaten auf Plausibilitaet und Konsistenz.
- `run_pipeline.py`: Fuehrt Abruf, Analyse und Plausibilitaetspruefung automatisiert aus.
- `data/comets.csv`: Gespeicherte Kometen-Stammdaten.
- `data/comets_orbits.csv`: Gespeicherte Orbitdaten.
- `data/similar_orbits.csv`: Ergebnisdatei fuer aehnliche Orbit-Paare.
- `data/exact_orbit_groups.csv`: Ergebnisdatei fuer exakt gleiche Orbit-Gruppen.
- `data/orbit_plausibility_issues.csv`: Gefundene Plausibilitaets-Issues.
- `data/orbit_plausibility_summary.csv`: Kompakte Kennzahlen der Plausibilitaetspruefung.

## Voraussetzungen

- Python 3.10+
- Abhaengigkeiten aus `requirements.txt`

Installation:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Daten abrufen

Mit folgendem Befehl werden Kometen- und Orbitdaten aus der API in `data/` geschrieben:

```bash
python3 fetch_comets.py
```

Nuetzliche Optionen:

- `--no-orbits`: Nur Kometenliste laden, keine Orbitdaten.
- `--workers 20`: Anzahl paralleler Requests fuer Orbitdaten.
- `--output` und `--orbit-output`: Eigene Zielpfade setzen.

## Orbit-Aehnlichkeit analysieren

Das Skript `find_similar_orbits.py` liest `data/comets_orbits.csv`, vergleicht alle gueltigen Orbitdatensaetze paarweise und erstellt zwei Ergebnisdateien:

- `data/similar_orbits.csv` mit aehnlichen Paaren
- `data/exact_orbit_groups.csv` mit exakten Gruppen

Standardaufruf:

```bash
python3 find_similar_orbits.py --top 20
```

## Workflow automatisieren

Mit dem Pipeline-Skript kannst du den gesamten Ablauf (Abruf + Analyse + Plausibilitaetspruefung) in einem Schritt ausfuehren:

```bash
python3 run_pipeline.py --mode strict --top 20
```

Nuetzliche Varianten:

```bash
# Nur Analyse mit vorhandenen Daten
python3 run_pipeline.py --skip-fetch --mode very-strict --top 20

# Mit manuellen Grenzwerten
python3 run_pipeline.py --mode normal --score-threshold 0.7 --i-tol 2.0 --top 20

# Validierung streng behandeln (CI faellt bei ERROR-Issues)
python3 run_pipeline.py --mode strict --fail-on-validation-errors
```

## Plausibilitaetspruefung

Das Skript `validate_orbits.py` prueft, ob Orbitdaten intern konsistent und physikalisch plausibel sind.

Geprueft werden unter anderem:

- Wertebereiche (`e`, `i`, `om`, `w`, `ma`, `q`, `per`)
- Konsistenz von `q = a * (1 - e)`
- Konsistenz von `ad = a * (1 + e)`
- Typische Bahn-Klassifikation (`e < 1` mit `a > 0`, `e > 1` mit `a < 0`)
- Fehlende Kernfelder in Datensaetzen

Direkter Aufruf:

```bash
python3 validate_orbits.py --show 25
```

Optional streng (Exit-Code 1 bei gefundenen ERROR-Issues):

```bash
python3 validate_orbits.py --fail-on-errors
```

## GitHub Action (manuell)

Es gibt einen manuellen Workflow unter [`.github/workflows/update-comets-data.yml`](.github/workflows/update-comets-data.yml).

So startest du ihn:

1. GitHub Repository oeffnen.
2. Reiter **Actions** waehlen.
3. Workflow **Update Comets Data** auswaehlen.
4. **Run workflow** klicken und optional `mode`/`top` setzen.

Der Workflow fuehrt `run_pipeline.py` aus und committed geaenderte Dateien automatisch:

- `data/comets.csv`
- `data/comets_orbits.csv`
- `data/similar_orbits.csv`
- `data/exact_orbit_groups.csv`
- `data/orbit_plausibility_issues.csv`
- `data/orbit_plausibility_summary.csv`

### Modi

`--mode` steuert die Standardgrenzen fuer die Aehnlichkeit:

- `very-strict`: sehr enge Toleranzen, wenige Treffer
- `strict` (Standard): enge Toleranzen
- `normal`: lockere Toleranzen, mehr Treffer

Beispiele:

```bash
python3 find_similar_orbits.py --mode very-strict --top 20
python3 find_similar_orbits.py --mode strict --top 20
python3 find_similar_orbits.py --mode normal --top 20
```

### Eigene Grenzwerte setzen

Alle Profilwerte koennen einzeln ueberschrieben werden:

- `--score-threshold`
- `--e-tol`
- `--q-tol`
- `--i-tol`
- `--om-tol`
- `--w-tol`
- `--a-rel-tol`

Beispiel mit manuellen Overrides:

```bash
python3 find_similar_orbits.py --mode normal --i-tol 2.0 --score-threshold 0.7 --top 20
```

## Ergebnisdateien

### `similar_orbits.csv`

Enthaelt paarweise Aehnlichkeit inklusive Metriken:

- `comet_id_1`, `name_1`
- `comet_id_2`, `name_2`
- `score` (je kleiner, desto aehnlicher)
- `de`, `dq`, `di`, `dom`, `dw`, `da_rel`

### `exact_orbit_groups.csv`

Enthaelt Gruppen mit identischen (gerundeten) Orbitwerten:

- `group_id`, `group_size`
- `comet_id`, `name`
- Orbitspalten `e`, `q`, `i`, `om`, `w`, `a`

### `orbit_plausibility_issues.csv`

Enthaelt pro Datensatz erkannte Auffaelligkeiten:

- `comet_id`
- `severity` (`ERROR` oder `WARN`)
- `rule`
- `message`
- `details`

### `orbit_plausibility_summary.csv`

Enthaelt kompakte Kennzahlen:

- `checked_rows`
- `issue_count`
- `error_count`
- `warn_count`
- `affected_comets`

## Score-Interpretation

Der Aehnlichkeits-Score ist dimensionslos und kombiniert die normalisierten Abstaende der Orbitparameter.
Je kleiner der Wert, desto aehnlicher sind zwei Orbits.

Praktische Daumenregeln:

- `score <= 0.45`: sehr hohe Aehnlichkeit (nahezu deckungsgleich)
- `score <= 0.60`: hohe Aehnlichkeit (strenger Standard)
- `score <= 1.00`: moderate Aehnlichkeit (mehr Kandidaten)
- `score > 1.00`: eher schwache Aehnlichkeit

Empfohlene Nutzung:

- Fuer konservative Kandidatenlisten `--mode very-strict` verwenden.
- Fuer ausgewogene Trefferlisten `--mode strict` verwenden.
- Fuer explorative Suche mit mehr Kandidaten `--mode normal` verwenden.
- Fuer Fachanalysen einzelne Toleranzen mit `--i-tol`, `--om-tol`, `--w-tol` gezielt nachschaerfen.

## Entscheidungshilfe Moduswahl

Schnelle Auswahl je nach Ziel:

1. Du willst nur sehr belastbare Kandidaten mit minimalen Fehltreffern:
	- Nutze `--mode very-strict`.
2. Du willst ein gutes Gleichgewicht aus Praezision und Treffermenge:
	- Nutze `--mode strict`.
3. Du willst moeglichst viele Kandidaten zur weiteren Sichtung:
	- Nutze `--mode normal`.
4. Du hast ein Spezialkriterium (z. B. Inklination besonders wichtig):
	- Starte mit einem Modus und ueberschreibe einzelne Toleranzen gezielt.

Beispiele:

```bash
python3 find_similar_orbits.py --mode very-strict --top 20
python3 find_similar_orbits.py --mode strict --top 20
python3 find_similar_orbits.py --mode normal --top 20
python3 find_similar_orbits.py --mode strict --i-tol 1.0 --om-tol 3.0 --w-tol 3.0 --top 20
```

## Hinweis zur Laufzeit

Der Paarvergleich ist quadratisch in der Anzahl gueltiger Datensaetze. Bei grossen Datenmengen kann die Analyse laenger dauern.


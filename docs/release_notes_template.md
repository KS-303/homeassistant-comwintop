# ComWinTop v<Version> – Freigabeentwurf

**Status:** Entwurf, nicht veröffentlicht. **HA Core:** <geprüfte Version>.
**Installationspaket:** <ZIP und SHA-256 erst nach CI eintragen>.

## Änderungen

- <jede freigegebene Funktion und ihr genauer Umfang>

## Nachweis je Funktion

| Funktion | Automatisiert | Simulator | Reale Hardware | Offen / gesperrt |
|---|---|---|---|---|
| <Name> | <Test> | <Test> | <Test> | <Grenze> |

## Installation, Update und Rückbau

Siehe [README](../README.md); Backup, Paketinhalt, Identitäten und HA-Neustart
in einer Testinstanz nachweisen. Keine Daten aus Diagnose-Dateien übernehmen.

## Freigabeprüfung

- [ ] `manifest.json`, `pyproject.toml`, Tag und ZIP sind konsistent.
- [ ] CI für Produkt und gegebenenfalls isolierten Upstream-Prototyp erfolgreich.
- [ ] Hardwaretests, 72-h-Betrieb und MB308N-Status wahrheitsgemäß beschrieben.
- [ ] Schreibsperre und Sicherheitsgrenzen erneut geprüft.
- [ ] Historie, Assets und Metadaten datenschutzgeprüft.
- [ ] Lizenz und Sichtbarkeit ausdrücklich entschieden.
- [ ] Maintainer hat Release und Tag ausdrücklich freigegeben.

# Prüfbericht 0.1.0b1

**Datum:** 15.11.2026. **Ergebnis:** verfügbare Softwareprüfungen der lesenden Beta bestanden.
Keine vollständige P0-Freigabe, keine Hardware- oder Schreibfreigabe.

## Umgebung und Nachweise

Linux, Python 3.14.10, echter Home Assistant Core 2026.11.0;
modbus-connection 4.12.7, tmodbus 1.1.0, pymodbus 3.13.1.
Direkte Testabhängigkeiten stehen in `requirements-test.txt`.
Die transitive Umgebung ist nicht vollständig per Lockfile eingefroren.

| Methode | Ergebnis | Aussagegrenze |
|---|---|---|
| Gesamte Pytest-Suite | **91 bestanden**, 0 fehlgeschlagen, 5,63 s | Kontrollierte Softwareumgebung |
| Coverage | **91 %** Statements; WriteManager 95 %, Coordinator 96 % | Keine vollständige Pfad-/Branch-Abdeckung |
| Grenzwerte und Hypothesis | bestanden | Prüft implementierte Skalierungsregeln, nicht elektrische Gerätewerte |
| Queue-/Konkurrenz-/TTL-/Recovery-Regeln | bestanden | Test-Executor; kein freigegebener realer Write-Executor |
| Unabhängiger TCP-/RTU-Frame-Simulator | bestanden | Echte HA-Modbus-Bibliotheken; keine echte RS485-Hardware |
| Serial über Linux-PTY | bestanden | Kein USB-Adapter-/HA-OS-Nachweis |
| Echter HA-Core | 13 Tests bestanden | Setup, Subentries, Reload, stabile IDs, Konfiguration, Sensorzustände, Diagnose |
| 1.000 Blocklesungen / 20 Verbindungsläufe | bestanden, Serververbindungen/-Tasks nach jedem Lauf geschlossen | Begrenzter Lasttest, kein 72-h-Lauf und keine umfassende Speicherprofilierung |
| Ruff Lint und Format | bestanden | Statische Regeln |
| Python Compileall | bestanden | Syntax/Bytecode; kein eigenständiger Funktionstest |
| HA Hassfest 2026.11.0 | **1 Integration, 0 ungültig** | Ausführungsanpassung unten beachten |
| Paketprüfung | Metadaten, Übersetzungsschlüssel, lokale Links, lesende Grenze bestanden | Zusätzlich AST-Kontrolle direkter write_-Aufrufe und fehlender Switch/Number-Klassen |
| ZIP-Prüfung | 18 Dateien, CRC und alle archivierten Bytes mit Quellen verglichen | Installationsablauf auf echter HA-OS-Instanz folgt |

Hassfest stammt aus offiziellem HA-Core-Commit
`74cf5a49c63ed8d4d87717844bf14f79c28c9cea` (Tag 2026.11.0).
Der unveränderte Standardaufruf scheiterte hier am vom Runtime-System gesperrten
Multiprocessing-Forkserver-Socket. Danach liefen **alle** Validatoren mit einem
ThreadPool anstelle des Prozesspools; keine Validatoren ausgelassen, keine
Prüfregeln abgeschwächt, keine HA-Produktionsbibliothek verändert. Dieser
Ausführungsunterschied ist kein Nachweis eines unveränderten CI-Hassfest-Laufs.

Die fünf Warnungen stammen von aiohttp-/backoff-Abhängigkeiten (Deprecations).
Sie wurden nicht ausgeblendet. GitHub Actions ist vorbereitet, aber wurde hier
noch nicht auf GitHub ausgeführt.

## Gefundene und behandelte Punkte

- Unvollständige HA-Subentry-Übersetzungsmetadaten und Manifest-Sortierung korrigiert;
  vollständiger Hassfest-Lauf danach bestanden.
- Simulator-Cleanup an Python 3.14 angepasst: Clients schließen, bevor auf den
  Serverabschluss gewartet wird; durch wiederholte Verbindungen geprüft.
- HA-Testinitialisierung lädt echte Basisregistries; keine nachgebauten Entity-Registries.
- Reaktivierte Kanäle bleiben über dieselbe Unique-ID nutzbar.
- **Nicht behobener Schreibblocker:** Exception 06 „Device busy“ führt im
  tatsächlichen Unterbau zu wiederholtem FC05. Der Test weist diesen Fehler nach
  und prüft die geschlossene Beta-Freigabe; er darf nicht als erfolgreicher
  Write-Retry-Sicherheitstest gelesen werden. Produktive Schreibpfade fehlen.
- **Weiterer Schreibblocker:** Die öffentliche HA-Unit-API garantiert den
  2-s-Sendeguard nicht am tatsächlichen Sendezeitpunkt bei geteiltem Bus.

## Freigabe

Geeignet für den nächsten **lesenden** HA-/Gerätetest nach
[Testplan](ha_test_plan.md). Nicht als Anlagensteuerung freigegeben.
Echte Gateway-/USB-Kompatibilität, Registerskalierung, Sensorkennungen,
negative Temperaturen und 72-h-Stabilität bleiben offen. Die vollständige
Abweichungsmatrix steht in [Implementierungsstatus](implementation_status.md).

Installationsarchiv SHA-256:
`dc3f4087e7aa6c60dc1e6568b61af4de33e03b1a5f91d32af9c7b3c508d955ab`.

Rohprotokolle und JUnit-Ergebnis liegen unter `docs/evidence/`.

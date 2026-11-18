# b18-Validierung (18. November 2026)

Ausgeführt in einer isolierten Testumgebung mit Python 3.14.10 und Home
Assistant Core 2026.11.0. Direkte Testabhängigkeiten stehen in
`requirements-test.txt`. Keine privaten Gateway-Adressen oder HA-Diagnosedaten
wurden für diesen Nachweis übernommen.

| Prüfung | Ergebnis |
|---|---|
| `ruff check .` und `ruff format --check .` | bestanden, 70 Dateien formatiert |
| Gesamter HA-/Simulator-Testlauf mit Coverage und JUnit außerhalb des Repositorys | 213 bestanden, 0 fehlgeschlagen, 92,84 % Statement-Abdeckung, 108,44 s |
| Paketprüfung | Versionen/Übersetzungen/Links und null aktive Modbus-Schreibaufrufe bestanden |
| Installationsarchiv | 20 erlaubte Dateien, bytegenau gegengeprüft; keine Schreibmanager-Datei |
| SHA-256 des ZIP | `16c7b49f1ce17a3ba80a9b31d47e17257adc55be426137b6ea6f1e48d59610c6` |
| Isolierte Upstream-Prototypen | 30 Netzwerk- und 34 serielle PTY-Wire-Szenarien bestanden; nicht im Produkt aktiviert |

Der Gesamtlauf meldete sieben Warnungen: fünf Deprecation-Hinweise aus HA/
Abhängigkeiten und zwei nicht deterministische `PytestUnraisableExceptionWarning`
aus dem Python-3.14-Selector-Transport beim Aufräumen von Test-Sockets.
Ein zusätzlicher Lauf, der diese Warnung zum Fehler erhob, meldete deshalb
210 bestandene Tests und drei Fehler beim *Setup nachfolgender Tests*;
ein Simulator-Aufräumversuch blockierte einen solchen Lauf und wurde
zurückgenommen. Die reguläre CI-Prüfung ist grün; diese Laufzeitwarnung ist
offen und wird nicht als bestandener verschärfter Gate dargestellt.

Der MB-308N-Simulator sah vier getrennte Lesefunktionscodes und mindestens
0,97 s Abstand zwischen gesendeten Telegrammen; die zweite DI-Abfrage lag
mindestens 8 s nach der ersten. Das belegt keine reale MB-308N-Hardware,
keine busweite Kapazität bei mehreren Geräten und keine 24-/72-Stunden-Stabilität.
Der RTU-Link-Reset nach Timeout bleibt bis zu einem gesonderten Wire-Nachweis
unverändert. Die produktive Schreibsperre bleibt bestehen.

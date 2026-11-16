# ComWinTop b13 – Sicherheitsprüfung vom 16.11.2026

Status: **Entwicklungsbranch, kein Release**. Grundlage b12, 166 bestandene Tests vor Änderungen.

| Befund | Reaktion in b13 |
|---|---|
| „Original b8“ im privaten ZIP ist tatsächlich b12 | **Bestätigt.** Alter Backup-Hinweis ungültig. Echte Rückfallstände nur mit eigener Git-Commit-ID sichern. |
| `except A, B:` scheitert unter Python 3.13 | **Behoben:** Ausnahmen gruppiert. Support bleibt auf HA Core 2026.11.x/Python 3.14 beschränkt. |
| b12 als 0.1.0b8 gekennzeichnet | **Behoben:** `manifest.json`, `const.py` auf `0.1.0b13`; keine künstlich rückdatierte Release-Datei. |
| FC06 Slave-ID-Schreibpfad trotz read-only-Diagnose | **Deaktiviert:** Kein Menü und keine aufrufbare FC06-Methode über den alten Formularpfad. Adressen nur lesen. |
| Parallel mutierte Profil-Dictionaries im Executor | **Behoben:** Datei-Ladevorgang im Executor; synchroner Profil-Publish im HA-Eventloop. |
| Disconnect bei RTU außerhalb Bus-Sperre | **Verbessert:** Disconnect jetzt unter demselben ComWinTop-Buslock. Ein anderes ComWinTop-Gerät kann währenddessen keinen Frame senden. |
| Fehler bei Setup-/Unload ohne Cleanup | **Verbessert:** Aufräumen nach Setupfehlern, beim erfolglosen Unload bleiben Pollingtasks aktiv. |
| Negative/85-°C-Temperaturen verworfen | **Offen, bewusst fail-closed:** Signed-Registerformat muss am echten Gerät validiert werden. |
| Unverhältnismäßig lange Backoffs nach Busy | **Behoben:** Pro Ausgangsblock max. 30 s bis zum nächsten geplanten Versuch, soweit kein gesonderter Recovery-Fall. |
| UI-Fehlermeldung beim Kanalintervall | **Verbessert:** `invalid_interval` wird nur noch für tatsächlich ungültige Intervalle angezeigt. |
| Serial-Symlink aus `/dev` | **Behoben:** Auch der aufgelöste Pfad wird gegen `/dev` validiert. |
| Hostnamen uneinheitlich | **Behoben:** Host-Normalisierung auch bei Modbus TCP. |
| Unübersetzter Rohwert-Suffix | **Behoben:** Deutsch und Englisch abhängig von HA-Sprache. Andere Sprachen derzeit nicht voll lokalisiert. |
| `modbus_connection` in requirements nicht separat gepinnt | **Dokumentiert:** Home Assistant `modbus`-Abhängigkeit stellt die API bereit. Die API-Kompatibilität außerhalb HA 2026.11.x ist nicht nachgewiesen. |
| Entity-Attribut `group` | **Zusatzfund:** HA warnt vor reserviertem `group`-Attribut. In `channel_group` umbenannt. |

## Sicherheitsgrenzen

Die normalen Schreibkanäle DO/AO bleiben deaktiviert. Das Entfernen des FC06-Laborflusses schließt auch dessen alte Bestätigungs-URL. Eine erfolgreiche Register-Rücklesung ist keine physikalische Kontaktüberwachung. Not-Aus, Pumpenschutz und Sammelstörungen müssen separat umgesetzt werden.

## Test- und Freigabekriterien

1. GitHub CI: Ruff, Pytest/HA 2026.11, vollständiger read-only-Modbus-Test.
2. Keine FC06-Übertragung durch HA-Formulare; auch bei vorherigem deep link.
3. Bei RTU-Timeout keine Trennung während des aktiven Requests eines anderen Geräts.
4. Bei fehlgeschlagenem Platform-Unload dürfen Koordinatoren nicht tot zurückbleiben.
5. Prüfung auf echtem TM-32DS und MB308N separat vor produktiver Nutzung.
6. Backup-Dateinamen ausschließlich anhand echter Commits/Builds; keine b8-Rückfallbehauptung für b12-Artefakte.

Offen bleibt, ob sämtliche eingebauten Funktionen auf Hardware-Registern korrekt reagieren; eine erfolgreiche CI kann das nicht beweisen.

## Review-Nachtrag A–F (16.11.2026)

- **A – Setup:** Temporäre `HomeAssistantError`-/Modbus-/Timeout-/OS-Fehler werden als `ConfigEntryNotReady` gemeldet. Ungültige Einstellungen bleiben `ConfigEntryError`. `CancelledError` löst denselben lokalen Cleanup-Pfad aus und wird unverändert weitergeworfen. Der Cleanup darf die gemeinsam verwaltete Modbus-Verbindung anderer Geräte nicht schließen.
- **B – Scheduler:** Auf Kanälen mit >30 s Intervall wird bei transientem Fehler nicht schneller als der Normaltakt abgefragt. Die 30-s-Obergrenze gilt nur für kürzere Intervalle. Gesonderte `connection_lost`-/Offline-Recovery behandelt weiterhin die Fehlerqualität pro Gerät.
- **C – Skalierung:** `invalid_scale` ist in strings.json/de.json/en.json ergänzt; skalierte Werte mit NaN/Inf werden ebenfalls diesem Fehler zugeordnet.
- **D – Teilinitialisierung:** `UnitCoordinator` registriert seinen Connection-Lost-Listener zuletzt; beim Konstruktionsfehler werden lokale Unit-Anforderungen zurückgesetzt, aber keine geteilte Modbus-Verbindung zerstört. Das Unit-Handle selbst besitzt in dieser HA-API keine eigenständige Close-Verantwortung.
- **E – Unload:** Die b13-Reihenfolge (Plattformen zuerst, dann Tasks) bleibt. Reload und fehlgeschlagene Platform-Unloads sind vor Release auf Hardware zu testen.
- **F – Schreibpfad:** Veraltete Formular-Texte entfernt, die alten Step-URLs brechen ausdrücklich ab. Der reine Berechnungshelfer `plan_tm32ds_address` bleibt vorerst für dokumentierte spätere L-51a-Arbeit erhalten; er sendet keine Telegramme. Die vorhandenen No-Write-/Wire-Tests bleiben maßgeblich.

Diese Änderungen sind noch keine Hardware-Freigabe. CI- und Hardware-Ergebnisse dürfen erst nach tatsächlichem Test als erfolgreich bezeichnet werden.

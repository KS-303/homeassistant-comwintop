# Test- und Freigabematrix

Stand 18.11.2026. „Hardware geprüft“ bezeichnet **nur den genannten Versuch**,
keine Gesamtabnahme. „Gesperrt“ bedeutet keine produktive Schreib-API.

| Bereich | Implementiert | Automatisiert getestet | Simulator geprüft | An echter Hardware geprüft | Offen / Freigabe |
|---|---|---|---|---|---|
| TM-32DS, FC03 32–63 | Ja; neue Geräte mit einmaliger Kanalerkennung | Ja; Erkennung und Alt-Konfiguration im HA-Simulator | Ja | FC03 mit angeschlossenen DS18B20 gelesen | Erkennungslogik am echten Gerät und 72-h-Abnahme offen |
| DS18B20 `0xFC18`, Wiederanschluss | Ja (Wert unavailable) | Ja | Ja | Abziehen `0xFC18`, Rückkehr beobachtet | Übrige Fehlercodes offen |
| HA-Kommunikation und Wiederverbindung | Ja | Ja | Ja | Lesender Wiederanlauf beobachtet | 72-h- und Störfallnachweis offen |
| L-50 Standard/Override, Block und Stale | Ja | Ja | TCP/RTU und Buslastmessung | **Nein**, gemischte Realintervalle offen | Kein Hardware-Abschluss |
| MB308N AI/DI/AO-/DO-Readback | Ja (lesend) | Ja | Ja | Nein | Geräteabnahme offen |
| b18: Exception-02-Recovery und Entity-Register | Ja | Ja; HA-Reload, Alt-IDs und Nutzer-Deaktivierung | Einzelregisterfehler nach Verbindungsabbruch | Nein | Hardwaretest ausstehend |
| b18: neue MB-Intervalle und Busabstand | 8/8/20/20 s; alte Werte bleiben gespeichert | Ja | Vier echte TCP-Funktionscodes, Abstand und DI-Folge gemessen | Nein | Mehrgeräte-Last und individuelle Kanalphasen offen |
| L-51a Register 16, Slave 1→2 | b15 nur lesend; früherer b6–b12-FC06-Labortest seit b13 gesperrt | Ja | FC06-Retry- und No-Retry-Prototyp; historischer Labortest simuliert | Registerwerk: `0x0104`→`0x0204`, FC03 an 2, nach Neustart gespeichert | **Im aktuellen Paket vollständig gesperrt**; mehrfaches Senden bei Busy möglich |
| L-51b Baudrate/Parität | Nein | Nein | Nein | Nein | **Gesperrt**; Originalgrafik und Gateway-Test offen |
| DO/AO-Befehl | Nur isolierte WriteManager-Engine | Engine und Schreibsperre | Upstream-Wire-Prototyp | Nein | **Gesperrt**; 2-s-Sendeguard, Readback, Grenzen, Lasttest offen |
| Upstream FC05/06/15/16, `retry=False` | Getrennte Patchentwürfe | Skripte, nun isolierte CI | 30 Netzwerk- und 34 PTY-Szenarien | Nein | Maintainer-Review, Veröffentlichung, HA-Abhängigkeit offen |
| Echter HA-Prozessneustart bei unbestätigtem Write | Nein | Nur simulierte Lifecycle-/Cancellation-Fälle | Teilweise | Nein | **Offen**, vor jeder Schreibfreigabe |

Die Simulatormessung in [L-50](l50_test_report.md) beobachtete drei
FC03-Anfragen pro Variante und 96 gegenüber 34 gelesenen Registern in
11,2 s. 255 gegenüber 131 TCP-Bytes sind aus den beobachteten Registerzahlen
berechnet, keine Paketaufzeichnung. Der Vergleich ist keine reale Buslastmessung.

## Version und Release-Gates

`v0.1.0b1` ist der einzige veröffentlichte Stand. `0.1.0b2` und b3 sind
Entwicklungsvorstufen, `0.1.0b4` die Entwicklungsbasis. Das noch nicht
veröffentlichte `0.1.0b5`-Testpaket enthält L-50 und die lesende L-51-
Vorbereitung. `0.1.0b6` ergänzt für **physisch isolierte Einzelgeräte** einen
experimentellen, ausdrücklich bestätigten TM-32DS-FC06-Schreibversuch.
Seit b13 ist auch der FC06-Laborfluss entfernt. b18 bleibt vollständig lesend.
Die normale L-51-/DO/AO-Schreibfreigabe bleibt gesperrt. Das Manifest
und `pyproject.toml` müssen
für ein **konkretes** zukünftiges Paket übereinstimmen. Dokumentations-PRs
ändern die Versionsnummer nicht. Ein Beta-Testpaket kann vor einer
Hardwareabnahme gebaut werden, wenn es klar als Testpaket markiert ist.
Ein neuer Release und Tag erst nach
definiertem Umfang, überprüftem Diff, erfolgreicher CI, Hardwarestatus und
manueller Freigabe. Changelog und Release-Notes müssen je Feature „lesend“,
„simuliert“, „real geprüft“, „offen“ oder „gesperrt“ unterscheiden.

Release-Checkliste: Branch-Abhängigkeiten auflösen; Installations-ZIP
inhaltlich und SHA-256 prüfen; manifest/pyproject/Tag vergleichen;
HA-Testinstanz aktualisieren und Rückbau prüfen; offene Realtests nennen;
keine Schreibentität und keine unerwartete FC05/06/15/16-Übertragung;
historische Commits, Tag-Artefakte und Diagnoseproben vor Veröffentlichung
auf vertrauliche Angaben prüfen; Lizenz bewusst festlegen; Release manuell
erstellen. Keine automatische Tag- oder Release-Aktion existiert im CI-Plan.

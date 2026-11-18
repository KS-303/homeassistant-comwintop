# L-50: Prüfbericht (Entwicklungsbranch auf 0.1.0b4)

Stand: 16.11.2026. Kein Release und keine Hardwarefreigabe. Die beiden
verglichenen lokalen Git-Trees stimmen mit dem GitHub-Tree von
`feature/local-device-profiles` (`7897ef7bd3e7f0c0aef5c4b391894d5800a06afc`)
vor der Änderung überein (`ddd59940694cbe370297d8620910593923af2681`).
`main` und das einzige Release stehen noch auf 0.1.0b1.

## Messung der Buslast

Gleicher HA-Core 2026.11.0, gleicher echter Modbus-Backendpfad und unabhängiger
lokaler TCP-Wire-Simulator. Laufzeit je Versuch 11,2 s, gemessen ab dem ersten
Telegramm. Ein TM-32DS mit 32 Kanälen, FC03 ab Adresse 32; keine künstliche
Fehlerantwort. Vergleichsanforderung: Kanal 1 mindestens alle 5 Sekunden.
Die Ausgangsversion kann das nur mit Gruppenintervall 5 s für alle Kanäle.
L-50 benutzt Gruppenintervall 15 s plus Kanal-1-Override 5 s.

| Aufbau | Beobachtete FC03-Lesezugriffe (s ab Start) | Telegramme | Register | TCP-Bytes* |
|---|---|---:|---:|---:|
| Original 0.1.0b4 | 32/32 bei 0,000; 32/32 bei 5,003; 32/32 bei 10,007 | 3 | 96 | 255 |
| L-50 | 32/32 bei 0,000; 32/1 bei 5,014; 32/1 bei 10,017 | 3 | 34 | 131 |

`32/1` bedeutet Startadresse 32, ein Register. Gemessene Kanal-1-Abstände
liegen bei 5,014 und 5,003 s. Die Zahl der Modbus-Transaktionen ist gleich,
die gelesene Registermenge sinkt um 62 bzw. **64,6 %**. Die anhand der wirklich
beobachteten Anfragegrößen berechneten TCP-Bytes sinken um **48,6 %**.

*Bytezahl ist keine Paketaufzeichnung: Für jedes beobachtete FC03-Telegramm
wurden Anfrage und normale Antwort nach Modbus-TCP-Framing als `21 + 2×Anzahl`
gezählt. Ethernet/IP-Overhead, Retransmits, Gateway-Latenz und serielle
Busruhe sind darin nicht enthalten. Die Telegrammzahl und Zeitpunkte stammen
aus dem laufenden Simulator, die Bytes aus dem protokollierten Register-Count.
Das Nachmessen am realen Waveshare-Gateway bleibt offen.

## Automatisierte Regression

Die Pytest-Suite prüft die echte HA-Konfiguration mit bestehenden Subentries,
Defaults, Overrides, Gruppenänderung, Zurücksetzen auf Standard, Reload und
stabilen Entity-/Unique-IDs. Dazu kommen 32-Kanal-Blöcke, nur fällige Bereiche,
deaktivierte Kanäle, registerweises Eingrenzen von Ausnahmen, Teilantworten,
Timeout/Verbindungsausfall, kanalbezogene Stale-Fristen einschließlich Rohdiagnose,
das real gemessene `0xFC18`-Fehlersignal, zwei Geräte am selben simulierten
RTU-over-TCP-Gateway und die unveränderte Schreibsperre. Ein TCP-Test misst
den 5-s-Kanal mit tatsächlichem Simulator-Timestamp; der RTU-Test prüft
mehrfache Abfragen beider Units bei gemeinsamer Sperre.

Die dokumentierten Softwaretests laufen mit Python 3.14.10,
Home Assistant Core 2026.11.0 und den in `requirements-test.txt`
festgehaltenen direkten Paketversionen. **123 Tests bestanden, 0 fehlgeschlagen;
91 % Statement-Abdeckung.** Ruff (Lint/Format), Paketprüfung und Python-
Compileall bestanden. Fünf Deprecation-Warnungen stammen aus HA-Abhängigkeiten.
Dies ist ein historischer L-50-Lauf. Der aktuelle Gesamtlauf und die Grenzen
stehen im [b18-Testnachweis](evidence/b18-validation.md); alte XML-/Logdateien
wurden wegen überholter Ergebnisse aus dem Entwicklungsbranch entfernt.
Bestehende Beta-Schreibsperren (`HARDWARE_VALIDATED_WRITES` leer; keine produktiven
Switch-/Number-Ausgänge) bleiben bestehen. Die isolierte WriteManager-Engine
ist keine freigegebene Hardware-Schreibfunktion.

## Noch ausstehend

- Gemischte Intervallprofile, Temperaturzeitstempel und Buslast am realen
  TM-32DS und Waveshare über mehrere Stunden messen.
- Abziehen/Wiederanschließen, Gateway-Unterbrechung und erneute Frischmessung
  aller Kanäle einschließlich langsamer Overrides in HA OS prüfen.
- MB308N und eigene lokale Profile auf echter Hardware prüfen; insbesondere
  die bestehende Beta-Schreibsperre weiterhin unangetastet lassen.
- Netzwerk- und Serientiming mit fremden Modbus-Nutzern auf demselben physischem
  Bus ist vom HA-Unterbau abhängig. Die Integration serialisiert ihre eigenen
  Units; die Backend-Sperre muss Integrationsgrenzen abdecken.

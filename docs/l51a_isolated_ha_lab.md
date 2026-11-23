# L-51a – Isolierter TM-32DS-Schreibtest über Home Assistant

**Experimenteller Laborstand, keine produktive Freigabe.** Der Test ist nur für eine physisch isolierte RS485-Verbindung mit genau einem CWT-TM-32DS vorgesehen. Keine angeschlossenen Lasten, keine weiteren Busgeräte oder parallelen Modbus-Master. **Nicht auf einer bestehenden GLT-/Heizungsanlage einsetzen.**

## Technische Begrenzung

Der HA-Core-2026.11.0-Modbus-Unterbau (`modbus-connection==4.12.7`, `tmodbus==1.1.0`) **kann FC06 bei Modbus-Busy wiederholen**. Der separate No-Retry-Upstream-Patch aus Draft-PR #3/#4 wird nicht von einem installierten HA-Core bereitgestellt. Deshalb garantiert der experimentelle HA-Dialog **nur einen logischen Schreibaufruf**, nicht genau ein physisches FC06-Telegramm. Die Bestätigung benennt dies ausdrücklich.

Die Änderung `0x0204 → 0x0304` (Slave-ID 2 auf 3, 9600 8N1) ist als Beispiel gedacht; die verwendete Adresse muss frei sein. Der TM-32DS benutzt Register 16: High-Byte = Slave-ID, Low-Byte unverändert. `0x0104 → 0x0204` wurde vorher mit Registerwerk an echter Hardware getestet, inklusive Persistenz nach Neustart. **Dieser HA-Labortest ist noch nicht an echter Hardware abgenommen.**

## Vorbereitung

1. Home-Assistant-Backup anlegen.
2. Exakt einen TM-32DS am dedizierten Testbus und eine ComWinTop-Geräte-Subentry verwenden. Keine weiteren Teilnehmer auf dem physisch selben Gateway/RS485-Bus.
3. Die bisherige Adresse des Geräts, den Gateway-Modus und die alten seriellen Einstellungen notieren. Bei einem Timeout muss das Gerät unter **alter und neuer ID** lesend gesucht werden können; eine automatische Rückschreibung findet nicht statt.
4. Nur das als *experimenteller Test* gekennzeichnete Paket aus dem betreffenden Entwicklungsbranch installieren; keine Upstream-Entwicklungspatches nach HA kopieren.
5. HA vollständig neu starten und zuerst kontrollieren, dass die Temperaturwerte bei der alten ID sauber gelesen werden.

## HA-Ablauf

1. Einstellungen → Geräte & Dienste → **ComWinTop** → betreffendes TM-32DS-Gerät → **Konfigurieren**.
2. **Slave-ID ändern (isolierter Hardwaretest)** öffnen.
3. Neue freie ID (1–247) eingeben.
4. Bestätigen, dass nur ein isolierter TM-32DS angeschlossen ist, und das Risiko möglicher mehrfacher FC06-Telegramme ausdrücklich akzeptieren.
5. ComWinTop liest FC03/Register 16 frisch, vergleicht die aktuelle ID, bildet den neuen Rohwert unter Erhalt des Low-Bytes und versucht an der Ziel-ID einen Lesetest. Ein positiver Ziel-ID-Lesetest blockiert die Änderung. **Keine Antwort ist kein Beweis für eine freie Adresse; dafür ist die physische Isolation Voraussetzung.**
6. Alte/neue ID und Rohwerte im zweiten Dialog prüfen und einmalig bestätigen.
7. Der Test ruft FC06 an der **alten** ID auf, liest anschließend FC03/Register 16 und einen Temperaturkanal an der **neuen** ID und speichert die neue HA-Unit-ID nur bei konsistentem Ergebnis. Unique-ID, Gerätekennung und Kanalparameter bleiben erhalten.

## Ergebnis und Rückfall

- **Erfolg:** nach HA-Reload neue ID erneut lesen und anschließend einen vollständigen CWT-Strom-Neustart durchführen; damit Persistenz unabhängig bestätigen.
- **Unbestätigter Ausgang:** **nicht erneut auf Schreiben klicken.** Externen Master nur nach Beenden der HA-Abfragen einsetzen und alte/neue Adresse **ausschließlich lesend** prüfen. Notfalls die HA-Unit-ID über den bereits vorhandenen rein lesenden Gerätekonfigurationsdialog korrigieren.
- **Busy/Timeout/Disconnect:** die Anzahl der tatsächlich gesendeten Frames kann vom HA-Backend abhängen. Keine Aussage über garantierte Einmalübertragung machen.

## Testprotokoll

| Prüfpunkt | Erwartung | Beobachtung |
|---|---|---|
| Aktuelle ID / Register 16 vor dem Test | Vergleich stimmt | |
| Neue, isoliert freie Ziel-ID | Kein anderer Slave | |
| Erstes Bestätigungsformular | Ohne beide Häkchen kein FC06 | |
| Zweites Formular | Rohwert unverändert bis Bestätigung | |
| FC06-Registernummer und Wert | Register 16, High-Byte geändert | |
| FC03 Register 16 nach Änderung | Neuer Rohwert an neuer ID | |
| FC03 Temperaturkanal | Sensorwert an neuer ID | |
| HA-Device-/Entity-IDs | Unverändert | |
| CWT-Strom-Neustart | Neue ID bleibt gespeichert | |
| Busy-/Timeout-Fall | Unbestätigter Ausgang, kein erneuter UI-Auftrag | |

**Freigabegrenze:** Diese experimentelle TM-32DS-Adressänderung ist **keine** Freigabe für MB308N-Ausgänge, DO/AO-Automationen, Baudratenänderungen oder einen gemeinsamen produktiven Modbus-Bus. Die abschließende No-Retry-API bleibt ein separates Entwicklungsziel.

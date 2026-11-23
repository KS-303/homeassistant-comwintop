# ComWinTop b22 – Hardwaretestbericht (auszufüllen)

**Status:** Nicht hardwarevalidiert. Kein Nachweis für eine Anlagen- oder
Personenschutzsteuerung. Keine produktiven Schreibvorgänge.

## Aufbau (nur lokale Kopie; private Informationen nicht auf GitHub veröffentlichen)

| Angabe | Eingabe |
|---|---|
| Datum / Uhrzeit / Zeitzone | |
| ComWinTop-Commit (40 Zeichen) | |
| HA Core / Python / Modbus-Bibliotheken | |
| Geräte: TM-32DS, MB308N (Hardware, Firmware) | |
| Modbus-Betriebsart (TCP / TCP-Gateway / RTU-TCP / seriell) | |
| Gateway-Modell und Firmware | |
| Busleitungslänge / Schirmung / Terminierung / Bias | |
| Slave-Adressen (privat dokumentieren) | |
| Anzahl RS485-Master | |
| Unabhängige Mitschnittquelle | |
| Vorgeschriebener Wiederanlauf bei Ausfall | |

## A – 24 Stunden reguläre Leseabfrage

Beginn / Ende, aktive Kanäle und Intervalle, Anzahl TX/RX, Timeout- und
CRC-Zähler, Zeitstempel der Aussetzer, Mittel-/Maximalwerte des
Buslock-Wartens und der vollständigen Leseaufrufe dokumentieren.
Besonders prüfen, ob ein einzelner Timeout die DS18B20-Entitäten
unnötig unavailable macht. Das b17-Protokoll zeigte zwei einzeln fehlende
RTU-Antworten bei 1.916 FC03-Anfragen und weiter verfügbaren Entitäten.

## B – Fehlerfälle an isolierter, unbelasteter Laborhardware

| Fall | Soll | Beobachtung / Mitschnitt-ID |
|---|---|---|
| Erster RTU-Read-Timeout | SUSPECT, alter Wert nur bis Stale-Frist; kein Write | |
| Erneuter Timeout ohne vollständige Antwort | Bus bleibt gesperrt | |
| Reparaturdialog mit nur 1–2 Bestätigungen | Keine Freigabe | |
| Alle Bestätigungen + bestätigter physischer Reset | Freigabe nach Dateireadback | |
| Verspäteter/fragmentierter Frame | Niemals ungeprüft als frischer Kanalwert behaupten | |
| Anderer HA-Nutzer derselben Leitung | Vor Produktivfreigabe gesondert absichern | |

## C – Neustart und Absturz

Normaler HA-Stopp: Polling beendet, geklärter Marker deaktiviert;
Neustart lädt wieder. Stopp während unklarem Request: Marker bleibt aktiv.
Simulierter ungeplanter HA-Prozessausfall: keine automatische Freigabe.
Mehrfaches Reload erzeugt nicht mehrere Shutdown-Listener.

## D – Gateway und Mehrgerätebetrieb

Gateway kurz trennen / neustarten; aufgezeichnete Ursache, Sperrstatus,
Wiederherstellungsweg, Reaktionen weiterer Units und anderer HA-Modbus-Nutzer
dokumentieren. *Kein* automatischer Resync ist nachgewiesen.
Zeitbudget der Gateway-Puffer ist mit Herstellerdaten bzw. Mitschnitt
zu belegen; 8 s Ruhe ist nur eine Heuristik.

## E – Temperaturgrenzen

Mit verifizierter Referenz messen: 0,0 °C, kleiner 0 °C (Eiswasser/Kühlfach),
85,0 °C (Startup vs. echter Wert), −55,0 °C / +125,0 °C nur
per Simulation, niemals unsichere reale Versuche. Negative Temperaturen
werden in b22 nur je Kanal und nach ausdrücklicher Aktivierung angezeigt;
0xFC18 bleibt Fühlerfehler.

## F – Buslast

Beide Geräte, verschiedene DI/DO/AI/AO-Lesegruppen, Kanalintervalle,
Minimalrate aller Units, Pacer-Lücken und Draht-Zeiten dokumentieren.
Ausgangsregister werden **nur gelesen**, keine Belastung anschließen.

## G – 72 Stunden Stabilität

Betrieb mit Ereignissen A–F; keine falsche Antwortzuordnung, keine
ungeklärten nicht verfügbaren Sensoren, keine alten Zustände als neu.
Kontrollieren, dass alle gesperrten Zustände ohne Rücksetzen durch Reload
fortbestehen. Freigabeentscheidung nur durch den Eigentümer.

## Abbruch- und Rückfallkriterien

Bei möglicher Fehlzuordnung, unsicherem Bus oder unklarer Geräteantwort
den Versuch beenden, Bus und Gateway spannungsfrei setzen und b17 nur
nach Sicherungs- und Sicherheitsprüfung wiederherstellen. Keine Änderung
des physischen Gerätezustands durch ComWinTop-Schreibfunktionen zulassen.

**Private Logs niemals ungeprüft veröffentlichen.** Das Werkzeug
`scripts/analyze_rtu_log.py` berechnet nur aggregierte Drahtzahlen;
bei fehlenden Logzeilen kann es keine tatsächliche Bus-Stille beweisen.

## Gesamtergebnis

- [ ] A bestanden
- [ ] B bestanden
- [ ] C bestanden
- [ ] D bestanden
- [ ] E bestanden
- [ ] F bestanden
- [ ] G bestanden
- [ ] Abweichungen bearbeitet und erneut getestet
- [ ] Freigabe ausdrücklich durch Eigentümer erteilt

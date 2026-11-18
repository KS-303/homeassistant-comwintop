# Bus- und Recovery-Audit (18. November 2026)

## Beobachtung und Grenzen

Aus dem vom Anwender exportierten `logs.txt` (17.11. 23:21 bis 18.11. 12:35 MEZ) wurden 3.332 gesendete und 3.326 empfangene RTU-Telegramme gezählt: 3.173 Temperaturabfragen FC03/32 mit zwei Registern und 159 Register-16-Abfragen. Sechs Temperaturabfragen blieben ohne Empfang (18.11. 04:54, 05:04, 05:49, 05:59, 07:24, 11:44). Die jeweils nächste Temperaturabfrage nach etwa 18,1 Sekunden war erfolgreich. Erfolgreiche Antworten kamen median nach 27 ms, maximal 37 ms. Der Export erfasst nur rund 13 Stunden und keine vollständige 24-Stunden-Messung. Der Grund der sechs ausbleibenden Antworten ist damit nicht bewiesen; insbesondere sind weder ein Sensorfehler noch Buskollision, Gateway-Reset oder HA-Last daraus eindeutig ableitbar.

Log-Inhalte und private Konfigurationsdaten werden nicht im Repository gespeichert. Die im Protokoll sichtbaren Diagnose-Lesungen von Register 16 sind **keine** Adressänderungen.

## Vergleich mit Registerwerk

Registerwerk (`renderer/app.js`, `waitBusReady`) überwacht am eigenen RTU-Empfang die letzte Busaktivität und wartet nach Timeout mindestens `max(250 ms, Timeout, Fehlerwartezeit)` auf Ruhe; neue empfangene Bytes verlängern das Fenster. Ein gedeckelter Wartezeitraum verhindert eine Endlosschleife. ComWinTop verwendet den gemeinsam genutzten HA-Modbus-Manager und `bus_lock` pro ComWinTop-Hub sowie 10 ms Nachrichtenabstand. Ein allein durch ComWinTop implementierter Timer sieht weder alle fremden HA-Modbus-Nutzer noch späte Rohbytes auf dem gemeinsamen Link. Eine gleichwertige beobachtete Busruhe wäre deshalb eine öffentliche Erweiterung des gemeinsamen Transport-Unterbaus mit Wire-Tests, nicht ein zusätzlicher TCP-Socket oder Zugriff auf private Bibliotheksobjekte.

## Prüfung und Änderung im Entwicklungsbranch

* Drei **aufeinanderfolgende** fehlgeschlagene Modbus-Abfragen werden pro aktivem Kanal gezählt. Ein anderer erfolgreicher Kanal löscht seinen Fehler nicht. Ein korrekt empfangenes Register setzt den Kommunikationsfehlerzähler dieses Kanals zurück, auch wenn der Messwert selbst einen Sensordefekt anzeigt.
* Nach ein oder zwei fehlgeschlagenen Abfragen bleibt der sichtbare Kommunikationsstatus bei zuvor erfolgreichen Messungen online. Ab drei Fehlern eines aktiven Kanals wird er verdächtig; erst wenn alle aktiven Kanäle betroffen sind, offline. Ein nachweislicher Link-Abbruch oder ein abgestürzter Poll-Task bleibt sofort offline.
* Per-Kanal-Stale-Fristen bleiben unverändert. Deshalb kann ein Wert schon **vor** der dritten Fehlantwort `unavailable` werden; dieser Unterschied ist beabsichtigt. Ein bestätigter Verbindungsabbruch invalidiert Werte sofort. Diagnose enthält nun kanalbezogene Fehlerzähler.
* Der bisherige RTU/RTU-over-TCP-Link-Reset nach *jedem* Timeout bleibt vorerst erhalten: `tmodbus 1.1.0` verwaltet zwar späte Antworten nach Timeout, aber die sichere Behandlung gleichartiger verspäteter Antworten und die Wirkung auf mehrere Slaves müssen vor einer Änderung am Reset-Pfad separat am Draht geprüft werden. Der Reset betrifft die gemeinsame HA-Verbindung und ist eine verbleibende Schwachstelle.
* Keine FC05/06/15/16-Freigabe. Die Integration selbst kann Pumpen oder Heizungen bei Ausfall von HA, Gateway oder RS485 nicht mit Verfügbarkeit garantieren. Schutz und Rückfall sind lokal vorzusehen.

## Freigabekriterien für eine spätere Installationsversion

1. Mindestens 24 Stunden realer Hardwaretest mit mehreren Slaves und getrenntem Bus-/Gateway-Mitschnitt, inkl. absichtlich verlorener und verspäteter Antworten.
2. Messen von tatsächlicher Wartezeit, Reconnects, Gesamt-Buslast und Frische jedes Kanals; die sechs bisher beobachteten Aussetzer nicht nur aus HA-Zuständen ableiten.
3. Regression von Serial, RTU-over-TCP, Modbus TCP, Bus-Scheduler, Kanal-Overrides, Diagnoseabfrage, Reload und Start, einschließlich fremder Nutzer derselben HA-Verbindung.
4. Bei Änderungen am Timeout-Reset: beobachtete Busruhe im öffentlichen gemeinsamen Backend oder Nachweis einer verlässlichen Frame-Quarantäne durch Wire-Tests. Keine zweite Busverbindung.
5. Keine produktive DO/AO-Steuerung allein aufgrund dieses lesenden Fixes. Keine 99-%-Garantie ohne Hardware-Nachweis.

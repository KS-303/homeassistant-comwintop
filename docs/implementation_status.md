# Implementierungsstatus – 0.1.0b15, lesendes Testpaket

L-51 ist für den TM-32DS lesend implementiert. Das historische FC06-Labormenü
aus b6–b12 ist seit b13 vollständig gesperrt. Die verwendete HA-Modbus-Version
kann bei Busy mehrmals senden. Die frühere [Laboranleitung](l51a_isolated_ha_lab.md)
ist **keine** Anleitung für dieses Paket. [L-51-Status](l51_status.md).

Dies ist die erste **lesende Testversion**, kein vollständiger stabiler P0-Release.

| Funktion | Implementierung / Nachweis |
|---|---|
| UI-Verbindungseintrag, mehrere Geräte als Subentries | implementiert; echte HA-Core-Tests |
| Herstellerneutrales Modbus TCP / Gateway-TCP | implementiert; TCP-Simulator mit echten Frames |
| RTU über transparenten TCP-Socket | implementiert; RTU-/CRC-Simulator |
| Serial / USB-RS485-Zugangsweg | implementiert; Linux-PTY-Test; reale USB-/HA-OS-Prüfung offen |
| TM-32DS CH1–CH32 | dokumentierte Adressen und Simulation; einzelne FC03-Lesungen am echten Gerät bestätigt, vollständige 32-Kanal-Abnahme offen |
| TM-32DS negative Temperaturen und Codes | `0xFC18` am abgezogenen DS18B20 real beobachtet und als unavailable behandelt; weitere negative Codes/Temperaturen nicht freigegeben |
| TM-32DS 85 °C | als mehrdeutig unavailable, da Startwert nicht unterscheidbar; kann echte 85 °C ausblenden |
| MB308N AI, AO-Rücklesewerte, DI, DO-Rücklesewerte | implementiert nach Dokument; keine Hardwarevalidierung |
| Individuelles DI-NO/NC | implementiert und getestet |
| AI physisch / Prozent / Zwei-Punkt-Skalierung | implementiert; tatsächlichen Signalmodus je Kanal manuell setzen |
| AO-Skalierung und Eingabevalidierung | Rechenfunktionen/testbare Regeln vorhanden; keine produktive number-Entität |
| Pollintervalle pro Gruppe und Kanal, Stale-Timer, Backoff | L-50 implementiert; TCP-/RTU-Simulator, Konfigurations- und Fehlertests; Hardwaretest der gemischten Intervalle offen |
| Kanaldeaktivierung, stabile UUID, Unit-Adressänderung | implementiert; keine Hardwareadressänderung; neue TM-32DS-Geräte prüfen 32 Register einmalig und starten mit unbestätigten Kanälen deaktiviert |
| Verbindungshost/-port ändern | implementiert mit Lesetest und stabilen IDs |
| Gerät zwischen zwei bestehenden Verbindungseinträgen umziehen | noch nicht in Beta-UI; darf bis Implementierung nicht durch Löschen/Neuanlage simuliert werden |
| Transportart eines bestehenden Eintrags wechseln | noch nicht in Beta-UI; neue Verbindung erforderlich |
| Schreibwarteschlange / 2-s-Frist / Latest-wins / Sperren | isolierte Engine implementiert und getestet; noch kein produktiver Hardware-Executor |
| Schreibrechte als UI-Freigabe | gesperrt; auch alte FC06-Laborformular-URLs brechen ab |
| Switch / Number für reale Ausgänge | technisch nicht angelegt; kein Schreib-Service |
| Automatische Wiederherstellung von Sollwerten | ausgeschlossen; keine Writes bei Setup/Reload/Reconnect |
| Deutsche/englische Einrichtung und Diagnose | implementiert |
| Physischer Kontaktnachweis | nicht vorhanden und nicht behauptet |
| 72-h-Hardwaredauertest | offen; kein verkürzter Softwarelauf ersetzt ihn |
| Vollständige P0-/HACS-Katalogfreigabe | offen; experimenteller Entwicklungsstand |

L-50 bleibt auf einem Entwicklungsbranch; die Aussagen zum produktiven Release
0.1.0b1 bleiben weiterhin separat gültig. Der Vergleich der realen Simulator-
Telegramme steht im [L-50-Prüfbericht](l50_test_report.md).
Einzelversuche und offene Gesamtabnahmen stehen in der zentralen
[Test- und Freigabematrix](test_release_matrix.md).

Der b6-Laborversuch ist ein historischer Zweig und nicht im b15-Paket enthalten.
Slave-ID, DO/AO und L-51b bleiben gesperrt. Der separate WriteManager gehört
nicht zum Installations-ZIP und belegt keine Hardware-Schreibfreigabe.

## Polling-Recovery bei Einzel-Timeout (Entwicklungsbranch)

Der erste fehlgeschlagene Leseversuch nutzt für die nächste Abfrage nur das
normale Kanalintervall. Ab dem zweiten aufeinanderfolgenden Fehler gilt der
begrenzte Backoff; ein Kanal wird bei Fehlern nicht schneller als sein
konfiguriertes Intervall abgefragt. Damit verursacht ein einzelner 3-s-Timeout
bei einem 15-s-Kanal nicht allein durch den Retryplan einen Ablauf seiner
45-s-Stale-Frist. Ein tatsächlicher Verbindungsabbruch invalidiert Messwerte
weiterhin sofort. Dies garantiert keinen ununterbrochenen Betrieb von
Pumpen/Heizungen; deren lokale Sicherheits- und Rückfallfunktion liegt außerhalb
von Home Assistant.

Die Abfrageschleife besitzt zusätzlich eine überwachte Ausführung: Nach einem
unerwarteten Task-Abbruch werden gespeicherte Messwerte ungültig, der Status
wechselt auf OFFLINE und die Abfrage startet höchstens zweimal binnen fünf
Minuten automatisch neu. Danach bleibt sie sichtbar gestoppt, bis die
Integration neu geladen und der Fehler untersucht wurde. Der Diagnoseexport
meldet, ob der Task läuft und wie alt die letzte Modbus-Antwort ist. Diese
Überwachung kann einen physischen Netz- oder RS485-Ausfall nicht beseitigen.

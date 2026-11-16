# Implementierungsstatus – 0.1.0b6-Laborstand auf b5-Basis

L-51 ist für den TM-32DS lesend implementiert. Die **separate b6-Laborversion** bietet unter doppelter ausdrücklicher Bestätigung einen experimentellen FC06-Versuch zur Slave-ID-Änderung bei physisch isoliertem Einzelgerät. Die verwendete HA-Modbus-Version kann bei Busy mehrmals senden. Diese Funktion ist kein No-Retry- oder Produktivnachweis. [Laboranleitung](l51a_isolated_ha_lab.md); [L-51-Status der regulären Beta](l51_status.md).

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
| Kanaldeaktivierung, stabile UUID, Unit-Adressänderung | implementiert; keine Hardwareadressänderung |
| Verbindungshost/-port ändern | implementiert mit Lesetest und stabilen IDs |
| Gerät zwischen zwei bestehenden Verbindungseinträgen umziehen | noch nicht in Beta-UI; darf bis Implementierung nicht durch Löschen/Neuanlage simuliert werden |
| Transportart eines bestehenden Eintrags wechseln | noch nicht in Beta-UI; neue Verbindung erforderlich |
| Schreibwarteschlange / 2-s-Frist / Latest-wins / Sperren | isolierte Engine implementiert und getestet; noch kein produktiver Hardware-Executor |
| Schreibrechte als UI-Freigabe | ausschließlich TM-32DS-Labortest für Slave-ID mit zwei Bestätigungen; keine DO/AO-Freigabe |
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

Die b6-Laborausnahme erlaubt einen ausdrücklich bestätigten FC06-Versuch an Register 16, nur am isolierten TM-32DS. Alle DO/AO-Ausgänge, L-51b und die allgemeine Beta-Schreibfreigabe bleiben gesperrt. Den separaten WriteManager nicht als Nachweis einer getesteten Hardware-Schreibfunktion lesen.

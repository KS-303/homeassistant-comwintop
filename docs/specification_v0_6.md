# ComWinTop for Home Assistant

## Lasten- und Pflichtenheft · konsolidierter Sollumfang und Beta-Abgrenzung

**Dokumentversion:** 0.6 · **Datum:** 15. November 2026  
**Ziel:** Open-Source-Custom-Integration `comwintop` für Home Assistant, GitHub und HACS/Marketplace  
**Freigabestatus:** fachliche Architektur verbindlich entschieden; Hardwaretreiber und Geräteverhalten noch **nicht hardwarevalidiert**  
**Beschlussbasis:** 44 dokumentierte Architekturentscheidungen — **35 JA / 9 NEIN**  
**Priorität:** CWT-TM-32DS, CWT-MB308N, herstellerunabhängige Ethernet–RS485-Gateways und USB–RS485; spätere Erweiterbarkeit weiterer CWT-Familien

> **Verbindlicher Grundsatz:** ComWinTop ist eine **lokale Modbus-I/O-Integration**, keine GLT-/SPS-Regelung und keine sicherheitsgerichtete Steuerung. Sie liest und schreibt geprüfte Hardwarekanäle, bewertet Kommunikationsqualität und liefert Diagnosen. Anlagen-Stopp, Sammelstörung, Pumpenüberwachung, Freigabegruppen, Nachlauf, Verriegelung und Wiederanlaufentscheidung liegen außerhalb der Integration in HA-Automationen bzw. erforderlicher unabhängiger Hardware.

> **Wichtiger Qualitätsvorbehalt:** „Dokumentiert“ bedeutet nicht „am Gerät bestätigt“. Im jetzigen Stand ist **kein schreibender Hardwarekanal als am konkreten Gerät validiert** ausgewiesen. Release-Freigaben müssen je Modell, Revision, Kanalart und Transport nachgewiesen werden.


> **V0.6-Konsolidierung:** Die folgenden Ergänzungen E-01 bis E-14 wurden in der Architekturprüfung am 15.11.2026 festgelegt und präzisieren die bisherigen 44 Entscheidungen. Sie sind verbindlicher Sollumfang. Der getrennte Implementierungsstatus in `implementation_status.md` zeigt, was die erste Testversion tatsächlich bereitstellt. Die erste Beta erfüllt ausdrücklich noch nicht alle P0-Abnahmekriterien.

## Verbindliche Ergänzungen der Prüfrunde

| ID | Beschluss |
|---|---|
| E-01 | Beim ersten ungeklärten gesendeten Write alle wartenden Writes des betroffenen Geräts verwerfen; neue während Recovery ablehnen, nicht puffern. Nach frischer Prüfung nur neu erteilte Aufträge. Andere Geräte bleiben soweit busseitig möglich unabhängig. |
| E-02 | Kanal-Schreibberechtigungen überleben HA-Neustart/Reload. Die Laufzeitfreigabe beginnt immer gesperrt bis zur frischen notwendigen Geräte-/Kanalprüfung. Keine alten Sollwerte wiederherstellen. |
| E-03 | Kanal deaktivieren: keine Auswertung/Kanalstörung, Schreibberechtigung löschen, Warteschlange verwerfen; Ausgang unverändert. Reaktivierung nur lesend. Rohdaten dürfen bei Blocklesen mitkommen. Ausblenden ist davon getrennt. |
| E-04 | Geführte Adressänderung/Busumzug erhält Geräte-UUID, Entity-IDs, Namen und Zuordnungen; Queue verwerfen, frisch prüfen, manuelle Schreibfreigabe erneut verlangen. Keine Änderung der Hardwareadresse durch die Integration. |
| E-05 | Einzelner Lesefehler: letzten gültigen Wert bis maximal drei Gruppen-Pollintervalle seit dessen tatsächlichem Empfang halten; Fehler sofort diagnostizieren. Unabhängiger Ablauf-Timer. Sensorfehler/erkannter Transportausfall sofort unavailable. |
| E-06 | Noch ungesendete Schreibbefehle laufen nach 2 Sekunden ab; Frist am Sendepunkt prüfen, Fehler an Aufrufer. Bereits gesendete Writes begrenzt klären, nicht wiederholen. |
| E-07 | AO wahlweise physisch V/mA oder 0–100 Prozent; genau eine bedienbare Sollwertentität. Elektrischer Readback separat. 50 Prozent = 5 V bei 0–10 V bzw. 12 mA bei 4–20 mA. |
| E-08 | Sollwert außerhalb erlaubtem Bereich: Fehler, kein Write, kein automatisches Clamping. NaN/Inf/ungültige Werte ebenfalls ablehnen. |
| E-09 | Bestätigte Readback-Abweichung außerhalb Profil-Toleranz: Auftrag fehlgeschlagen, Istwert anzeigen, nur betroffenen Kanal sperren. Begrenzte frische Prüfung ohne altes Sollwert-Nachschreiben; erfolglose Prüfung lässt Sperre bestehen. |
| E-10 | Gateways/USB-Adapter herstellerunabhängig. TCP, TCP→RTU, RTU-over-TCP und Serial/RTU getrennt. Konkretes Waveshare-Modell ist kein Entwicklungsblocker. Geräte benötigen weiterhin passende Profile; erste Profile TM-32DS und MB308N. |
| E-11 | AO-Modus-/Skalierungsänderung: betroffenen Kanal manuell neu freigeben; wartende Writes verwerfen. Änderung selbst erzeugt keinen Write und beweist keinen Hardwarejumper. |
| E-12 | Pollintervalle je Gerät und Signalgruppe Temperatur/DI/DO/AI/AO mit Vorgaben/Lastgrenzen. Write-Readbacks unabhängig davon. |
| E-13 | Keine Software-Entprellung im ersten Release. NO/NC-Auswertung sofort auf gültigem DI-Read. Zeitfilter in HA; kurze Impulse können zwischen Polls fehlen. |
| E-14 | Freigabe einer installierbaren Beta erst nach bestandenen verfügbaren Softwareprüfungen; reale HA-/Gerätetests anschließend separat. Keine Hardwarefreigabe durch Simulation. |

## Technische Startwerte der ersten lesenden Beta

Temperatur 15 s (Minimum 5 s), DI/DO 2 s (Minimum 1 s), AI/AO 10 s (Minimum 2 s), Maximum jeweils 3600 s. Request-Obergrenze einschließlich interner Wartezeit 3 s. Keine zusätzlichen App-Lese-Retries im selben Poll; exponentieller Poll-Backoff bis Faktor 30 bei Unit-Kommunikationsfehlern. Timeout allein zunächst SUSPECT, nach drei aufeinanderfolgenden Kommunikationsfehlern OFFLINE; eine gültige Antwort beendet den Kommunikations-Backoff. Register-/Sensorfehler werden separat behandelt. Werte veralten unabhängig von Recovery-Versuchen. Aufgeteilte Registerblöcke werden fair über einen Pollzyklus verteilt. Diese Werte sind Testvorgaben, keine Echtzeitgarantie.

Die ausgelieferte Beta ist strikt lesend. Schreibengine, 2-s-Frist, Latest-wins und Sperrregeln werden separat mit kontrollierbaren Test-Executors geprüft. Kein realer Write-Executor ist freigegeben. Siehe `known_limits.md`: HA 2026.11.0 / modbus-connection 4.12.7 / tmodbus 1.1.0 wiederholt im gemessenen Busy-Fall Schreibtelegramme; die öffentliche HA-Unit-API bietet außerdem keinen finalen Sendeguard für die strikte 2-s-Frist. Keine globale Bibliotheks-Manipulation und kein zweiter Master als Umgehung.

---

# Teil A – Lastenheft (WAS)

## A1. Ausgangslage, Nutzerziele und Abgrenzung

Der Anlagenbetreiber möchte Temperaturen, digitale/analoge Eingänge und digitale/analoge Ausgänge der CWT-/ComWinTop-Hardware lokal in Home Assistant erfassen und bedienen. Mehrere CWT-Slaves sollen einzeln unter einem Waveshare-RS485/Ethernet-Gateway oder einem USB-RS485-Bus hinzugefügt werden. Modelle mit echter direkter Modbus-TCP-Schnittstelle können eigenständig eingebunden werden. Einzelne Geräte dürfen unabhängig konfiguriert, umbenannt oder entfernt werden.

Die Kernintegration muss ohne manuelle Register-YAML auskommen. Die Geräteprofile bringen die Modellkenntnis mit. Basisversion ist vollständig offline und ohne Hersteller-Cloud einsetzbar; Netzwerkkonfiguration und externe Hardwareverdrahtung bleiben Sache des Betreibers.

**Erste Hardwarekonfiguration (P0):**

| Objekt | Rolle | Kanäle / Zweck | Sollweg |
|---|---|---|---|
| CWT-TM-32DS | Temperaturmodul | 32 DS18B20-Kanäle | RTU über Waveshare oder USB |
| CWT-MB308N | I/O-Modul | 8 AI, 4 AO, 8 DI, 8 DO | RTU über Waveshare/USB; echtes TCP nur modellabhängig |
| Waveshare Ethernet–RS485 | Buszugang | Gateway/Bridge, kein Schutzcontroller | Transparentes RTU-over-TCP **oder** TCP→RTU-Konvertierung je Modell |
| USB–RS485-Adapter | alternativer Buszugang | Direkter RTU-Master am HA-Host | Serial/RTU, stabiler Gerätepfad |

Die Namen und numerischen IDs der realen Geräte, die genaue Waveshare-Artikelvariante sowie die MB308N-Hardwarerevision sind **noch aufzunehmen**.

## A2. Verbindliche Entscheidungen – vollständige Ja-/Nein-Matrix

Die folgende Liste ist eine **fachliche Entscheidung**, keine Aussage über bereits fertig implementierte Funktionen. „JA“ bedeutet verbindlicher Sollumfang, „NEIN“ bedeutet ausgeschlossen oder verschoben.

| Nr. | Entscheidung | Beschluss | Priorität / Umsetzung |
|---:|---|:---:|---|
| 01 | CWT-TM-32DS vollständig unterstützen | JA | P0, vollständiger Register-/Kanaltest |
| 02 | CWT-MB308N vollständig unterstützen | JA | P0, DO/AO erst nach Hardwaretest |
| 03 | Mehrere Waveshare-Gateways verwalten | JA | P0, mehrere Verbindungsinstanzen |
| 04 | Beliebig viele CWT-Slaves je Gateway (Busgrenzen beachten) | JA | P0, keine künstliche niedrige Softwaregrenze |
| 05 | CWT-Geräte mit direktem Modbus TCP unterstützen | JA | P0, wenn konkrete Gerätevariante TCP anbietet |
| 06 | RTU über Ethernet-Gateway unterstützen | JA | P0, Transportmodus getrennt behandeln |
| 07 | USB-RS485 direkt in der ersten Version | JA | P0, zusätzliches Test-Gate |
| 08 | Automatische Modellerkennung | NEIN | Manuelle Modell-/Variantenwahl |
| 09 | Weitere CWT-Serien direkt zum ersten Release | NEIN | Erst später, profilweise |
| 10 | 32 Temperaturkanäle des TM-32DS | JA | P0, inklusive Kanal 32 und Fehlercodes |
| 11 | Jeden DI einzeln als NO/NC konfigurieren | JA | P0, reine logische Auswertung |
| 12 | DO-Zustand auslesen und anzeigen | JA | P0, nur bestätigter interner Zustand |
| 13 | Ausgänge standardmäßig nur lesend | JA | P0, sicherer Start ohne Writes |
| 14 | DO/AO einzeln für Schreibzugriff freigeben | JA | P0, zentraler Write-Gatekeeper |
| 15 | Analogeingänge mit Skalierung und Einheit | JA | P0, vom Hardwarebereich abhängig |
| 16 | Analogausgänge mit definierten Wertebereichen | JA | P0, physische Jumper/Varianten beachten |
| 17 | Ungenutzte Kanäle deaktivieren/ausblenden | JA | P0, IDs stabil |
| 18 | Kanalbezogene Verfügbarkeit und Diagnose | JA | P0, soweit Registerzugriff trennbar |
| 19 | Freie manuelle Modbus-Registereingabe für Endanwender | NEIN | Nur geprüfte Modellprofile |
| 20 | Zentrale Bus-Warteschlange pro Verbindung | JA | P0, ggf. via HA shared Modbus |
| 21 | Strenge Prüfung von RTU-/TCP-Antworten | JA | P0, Fehler-/Frame-Tests |
| 22 | Begrenzte Timeouts und Lesewiederholungen | JA | P0, Fairness/Backoff |
| 23 | Keine blinden Schreibwiederholungen | JA | P0, auch Bibliothek-Retries prüfen |
| 24 | Schreibbefehle durch frisches Readback prüfen | JA | P0, physischer Kontakt nicht beweisbar |
| 25 | Bei konkurrierenden Befehlen neuesten vormerken | JA | P0, nur innerhalb gültiger Verbindung |
| 26 | Wartende Befehle bei Verbindungsausfall verwerfen | JA | P0, niemals nachsenden |
| 27 | Fehlerhafte Slaves isolieren statt Gesamtbus blockieren | JA | P0, Busressource bleibt geteilt |
| 28 | Kontrollierte Wiederherstellung je Gerät/Kanal | JA | P0, notwendige Register frisch prüfen |
| 29 | Veraltete Messwerte als unavailable kennzeichnen | JA | P0, kein 0-Ersatzwert |
| 30 | Getrennter Gateway-/Slave-Kommunikationsstatus | JA | P0, Socket ≠ gültige Unit-Antwort |
| 31 | Abfrageintervalle konfigurierbar | JA | P0, Lastschutz und Mindestgrenzen |
| 32 | Diagnose: Timeouts, Fehler, Antwortzeiten | JA | P0, datensparsam |
| 33 | Ausgangszustände nach HA-Neustart automatisch wiederherstellen | NEIN | Readback ja; keine automatischen Writes |
| 34 | Einrichtung vollständig über HA-Oberfläche | JA | P0, Config-/Options-/Subentry-Flow |
| 35 | Deutsche und englische Übersetzung | JA | P0, Fehlertexte eingeschlossen |
| 36 | Automatische Tests und GitHub Actions | JA | P0, CI vor Veröffentlichung |
| 37 | Installation über HACS/Marketplace als Custom Repository | JA | P0, öffentliche Beta nach Test-Gates |
| 38 | Spätere Aufnahme in offiziellen Katalog anstreben | JA | P1, gesondertes Review/PR |
| 39 | Pumpen-Betriebsüberwachung direkt im ComWinTop-Kern | NEIN | Optionale HA-Automation |
| 40 | Sammelstörungslogik direkt im ComWinTop-Kern | NEIN | Optionale HA-Automation |
| 41 | Not-Aus-/Anlagen-Stopp-Logik direkt im Kern | NEIN | Optionale HA-Automation / unabhängige Hardware |
| 42 | Freigabegruppen und Verriegelungen im Kern | NEIN | Optionale HA-Automation / unabhängige Hardware |
| 43 | ESPHome-/Shelly-Watchdog als integriertes Zusatzmodul | NEIN | Hardwareunabhängige I/O-Integration |
| 44 | Separate HA-Automationsvorlagen bereitstellen | JA | P0-Dokumentationsbeispiele, nicht Core |

**Auswertung:** 35 JA, 9 NEIN. Die einzige Änderung gegenüber der vorausgewählten Empfehlung ist **Nr. 07: USB-RS485 ist bereits in Release 1 Pflicht**.

## A3. Widerspruchs- und Änderungsprotokoll gegenüber v0.4

| Punkt | Alter Stand / scheinbarer Widerspruch | Verbindliche Klärung v0.5 |
|---|---|---|
| Anlagen-Stopp/Sammelstörung | v0.2–v0.4 verpflichtende interne Überwachungslogik und reservierte DI/DO | **Entfällt aus Core.** DI/DO bleiben frei konfigurierbare I/O; Automationsvorlagen optional. |
| „Beliebig viele“ | Könnte als unbegrenzte physische Buskapazität verstanden werden | Pro RS485-Bus gültige Unit-IDs und elektrische/zeitliche Grenzen; keine willkürliche Softwaregrenze. |
| Waveshare als Controller | Könnte autonome Schalt-/Schutzlogik suggerieren | Gateway/Bridge ist Kommunikationszugang; keine garantierte Fallback- oder Sicherheitsfunktion. |
| USB-RS485 | Frühere v0.4-Einstufung nur SOLL | **MUSS bereits vor vollständig freigegebenem v1**; geeignete HA-OS-/USB-Tests erforderlich. |

Die früheren **L-19 bis L-24 und Safety-Abschnitte 4.8, safety_monitor.py, safety_config.py, A-27–A-36/A-56/A-58** werden **nicht mehr als Implementierungspflicht des ComWinTop-Kerns** geführt. Inhalt und Gefahrenhinweise bleiben in `docs/examples/` und `docs/safety_boundaries.md` als **optionale, separat zu prüfende Anlagenbeispiele** erhalten. Die späteren Diskussionen zu Fehlerklassen, Freigabegruppen, Pumpennachlauf und Anlagen-Stopp ändern diese Architektur nicht.

## A4. Nicht-Ziele

Keine automatische Geräte-/Firmwareerkennung; kein allgemeiner Modbus-Registereditor; keine Unterstützung weiterer CWT-Familien in der ersten vollständigen Version; keine Firmwareupdates oder Modbus-Adress-/Baudratenänderung; keine verdeckten HA-Automationen; kein Herstellen von physischen Ersatzstellungen beim HA-Neustart; keine Steuerung vorhandener ELWA-/Wärmepumpenregeln; keine funktionale Sicherheit; keine Echtzeitgarantie; kein Umgehen von Modbus-Schutz-/Sicherheitsorganen.

## A5. Prioritäten und Release-Verständnis

- **P0 / MUST**: Alle mit „JA“ und P0 markierten Punkte, außer der späteren Katalogaufnahme (Nr. 38). Vor einer als *vollständig* bezeichneten stabilen Version müssen TM-32DS, MB308N, alle drei Verbindungswege und ihre freigegebenen Kanalfunktionen geprüft sein.
- **P0-beta**: Eine klar als experimentell gekennzeichnete Vorabversion darf Teilfunktionen bereitstellen, muss fehlende oder nicht validierte Schreibfunktionen technisch sperren und dokumentieren. Sie erfüllt **noch nicht** den gesamten Sollumfang.
- **P1**: Offizieller HACS/Marketplace-Katalog, weitere CWT-Modelle und zusätzliche Qualitätsverbesserungen nach stabilem P0-Stand.

---

# Teil B – Pflichtenheft (WIE)

## B1. Zielarchitektur und Gerätehierarchie

```text
Home Assistant 2026.11+  [Minimum-Version vor Build endgültig testen]
└── ComWinTop (custom_components/comwintop)
    ├── Connection A: Waveshare Ethernet–RS485
    │   ├── Unit 1: CWT-TM-32DS → 32 × sensor.temperature
    │   └── Unit 2: CWT-MB308N → 8 AI, 4 AO, 8 DI, 8 DO
    ├── Connection B: USB–RS485 → beliebige gültige, eindeutig adressierte CWT-Units
    ├── Connection C: zweites Waveshare-Gateway → eigene Units
    └── Connection D: direktes Modbus-TCP-CWT-Modul → eigene Unit

Optionale Automationsbeispiele (separat, NICHT im Integrationskern):
  Pumpenrückmeldung | Sammelstörung | Anlagen-Stopp-Meldung |
  Freigabegruppen  | Hardware-Watchdog-Schnittstellen
```

Die **physische Verbindung** ist die Serialisierungs-/Busgrenze. Ein CWT-Gerät besitzt eine **eindeutige Zuordnung aus Verbindung und Unit-ID**. Der Anwender kann dieselbe Unit-ID an unterschiedlichen physischen Verbindungen verwenden, **nicht** zweimal innerhalb derselben Verbindung. Das Setup verhindert doppelte Konfiguration und dokumentiert mögliche externe Zweitmaster, ohne deren Abwesenheit hardwareseitig garantieren zu können.

**UI-Objekte:** Physische Verbindungen werden als Konfigurationseinträge angelegt. CWT-Geräte werden als einzeln verwaltete Geräte bzw. HA-Config-Subentries modelliert; die konkrete stabile HA-API ist vor Implementierung zu prüfen. Der Waveshare kann als logischer Gateway-Knoten dargestellt werden; reine TCP-Erreichbarkeit ist **kein** Beleg für Gerätestatus oder Telemetrie des Gateways. Die HA-Device-Registry erhält CWT-Devices mit stabilen `unique_id`s.

## B2. Kommunikations-Backends – verbindliche drei Wege

| Weg | Verbindungstyp | Benutzereingaben | Prüfpunkt |
|---|---|---|---|
| Direktes CWT Modbus TCP | `ModbusTcpParams`/TCP | Host, Port, Unit-ID | Nur echtes TCP-fähiges CWT-Modell auswählen |
| Waveshare TCP→RTU | Modbus TCP zu konvertierendem Gateway | Host, Port, Unit-ID, Gatewaymodus | Tatsächlicher Konvertermodus aktiviert |
| Waveshare transparent | RTU-over-TCP/Serial-Socket | Host/Socket-Port, Baud-/Parität am Gateway, Unit-ID | Roh-RTU-Framing vollständig erhalten |
| USB-RS485 | Serial/RTU | stabiler Gerätepfad, Baud, Parität, Stopbits, Unit-ID | HA OS erkennt `/dev/serial/by-id/...`; Port exklusiv |

**Kein Port 502 als pauschale Vorgabe:** Der tatsächliche Gatewaymodus bestimmt den Port. Transparente Bridge ≠ TCP-Konverter. Das Gerät „RS485 TO ETH“ und „RS485 TO ETH (B)“ haben unterschiedliche dokumentierte Fähigkeiten. Der Setup-Assistent muss den vom Benutzer gewählten Modus klar ausweisen, nicht heimlich ausprobieren oder umschalten.

**Gemeinsam genutzte HA-Modbus-Verbindungen:** Vorrangig `homeassistant.components.modbus.async_get_unit` und `modbus-connection` verwenden. Die vorhandene HA-Schicht verwaltet Verbindung, Serialisierung und Reconnect. **Keinen zweiten selbstverwalteten Socket/Serial-Master öffnen**, wenn HA die Verbindung bereits besitzt. Für transparentes RTU-over-TCP und USB muss in einem frühen technischen Spike nachgewiesen werden, welche Parameter die konkrete HA-Core-Version unterstützt. Ein nicht abgedeckter Spezialmodus darf nur mit nachgewiesen exklusiver Leitung, automatisierten Tests und dokumentierter Einschränkung implementiert werden; keine konkurrierende Parallelverbindung.

## B3. Einrichtung und Änderungen über die UI

1. **Verbindung hinzufügen:** Ethernet-Bridge (transparent oder Modbus TCP), direkter TCP-Teilnehmer oder USB-RS485; Host/Port bzw. stabiler serieller Pfad.
2. **Gerät hinzufügen:** CWT-Modell und ggf. Revision manuell auswählen; Unit-ID (üblich 1–247; keine Broadcast-ID 0); Gerätename; Duplikatprüfung.
3. **Verbindung prüfen:** ungefährlicher FC03/04/01/02-Lesetest eines **für dieses Modell dokumentierten** Registers; „verbindbar“ ≠ „Modell erkannt“. Kein automatischer Slave-Scan.
4. **Kanaloptionen:** Aktivieren/Ausblenden, Name, Einheit, Skalierung/Offset soweit modellgerecht, individuelles DI-NO/NC, per-DO/AO-Schreibfreigabe.
5. **Reconfigure:** Verbindung, Unit-ID, Pollintervalle und Kanaloptionen ohne Entitätsduplikate ändern; gezielte Migration/Änderung der Registry-ID.
6. **Entfernen:** Gerät entfernen ohne fremde Units oder Gateway zu löschen. Nur die letzte Unit schließt gegebenenfalls die geteilte Verbindung.
7. **Validierungsfehler:** Klare Meldung für falschen Port/Modus, ungültige Unit-ID, fehlende Antwort, Register-Exception, Konflikt/Port belegt.

**Kein automatisch gestarteter Schreibtest.** Testschreiben nur bewusst, in einer sicheren Prüfverdrahtung und nach Hardwarefreigabe des jeweiligen Profils.

## B4. Entitätsmodell

| Hardwarekanal | HA-Plattform | Default | Optionen / Semantik |
|---|---|---|---|
| TM-32DS Temperatur 1–32 | `sensor` (°C) | read-only | Name, Kanalaktivierung, Debug-Rohwert optional |
| MB308N AI0–AI7 | `sensor` | read-only | Modus 4–20mA/0–10V etc., Einheit/Skalierung, physischer Jumper-Hinweis |
| MB308N DI0–DI7 | `binary_sensor` | read-only | **NO oder NC je DI**, Name; keine Software-Entprellung in Release 1 |
| MB308N DO0–DO7 | `binary_sensor` (Roh-/Logikzustand) + optional `switch` | **Nur Lesen** | Schreibschalter nur nach Freigabe, keine optimistische Bestätigung |
| MB308N AO0–AO3 | `sensor` (Rücklesewert) + optional `number` | **Nur Lesen** | Bereich, Auflösung, physischer Modus, explizite Schreibfreigabe |
| Connection / Unit | Diagnostische `binary_sensor`/`sensor` | lesend | Letzte gültige Antwort, Latenz, Timeoutzahl, Datenalter, ungeklärte Writes |

HA-Entity-States folgen ihrer vorgesehenen Plattform (`on`, `off`, Zahlenwert, `unavailable`); Protokoll-Zwischenzustände wie `PENDING`, `UNCONFIRMED`, `REJECTED` werden als **Diagnoseattribute/-entitäten**, nicht als ungültige `switch`-States modelliert.

**NO/NC:** Die Rohinformation muss im Diagnosemodus nachvollziehbar bleiben. Das konfigurierbare NO/NC invertiert den logischen Binary-Sensor entsprechend dem gemessenen elektrischen Kontaktzustand; bei fehlendem Rohwert wird weder ein aktiver noch ein gesunder Zustand erfunden. Ein NC-DI ist **keine** zertifizierte Leitungsbrucherkennung und kein sicherheitsgerichteter Not-Aus.

**Stable identity:** IDs werden aus einer dauerhaft gespeicherten Geräte-UUID und der Kanalposition abgeleitet; Verbindung und Unit-ID sind veränderliche Zuordnungen; Änderungen des Anzeigenamens dürfen keine doppelten Entitäten erzeugen. Bei Wechsel von IP-/Port-Konfiguration muss die Zuordnung erhalten bleiben; bei physischem Geräteumzug auf anderen Bus erfolgt explizite Reconfigure-/Migrationslogik. Keine irreführend als Seriennummer ausgegebene Unit-ID.

## B5. Registerprofile – Dokumentations- und Hardwarestatus

### B5.1 Evidenzstufen

| Status | Definition | Freigaberecht |
|---|---|---|
| **D – dokumentiert** | Registeradresse, FC, Datentyp/Skalierung aus namentlich genannter Quelle | Implementierung erlaubt; keine Behauptung, dass es am Nutzergerät funktioniert |
| **T – teilweise** | Funktion/Register nur teilweise belegbar, z. B. FC oder negatives Vorzeichen offen | Kein produktiver Write |
| **O – offen** | Zu wenig verlässliche Information | Nicht als unterstützt anzeigen |
| **H – hardwarevalidiert** | Revisionsbezogener Realgerätetest und Messvergleich bestanden | Funktion darf als getestet ausgewiesen werden |

**Aktueller Stand 15.11.2026:** Kein Kanalstatus H. Die folgenden Tabellen sind Entwicklungsgrundlage, keine Gewährleistung für alle Firmware-/Hardwarevarianten.

### B5.2 CWT-TM-32DS – P0

**Dokumentierter Zugriff:** Modbus RTU, FC03, 32 Holding-Register ab **PDU-Adresse 32 (`0x20`)**, jeweils 16 Bit, Temperatur laut Geräteanleitung mit Faktor **0,1 °C/LSB**. Register `0x10` enthält Konfigurationsinformation (in v1 **nur lesen**). Überlieferte Datenformatangabe „UINT“ erklärt negative Temperaturwerte und Sonder-/Fehlercodes nicht vollständig. [Q1]

| Kanal | PDU-Adresse dezimal | Hex | FC | Datenformat / Status |
|---|---:|---|---|---|
| CH1 | 32 | `0x20` | 03 | 16 Bit, ×0,1 °C · D |
| CH2 | 33 | `0x21` | 03 | 16 Bit, ×0,1 °C · D |
| CH3–CH30 | 34–61 | `0x22–0x3D` | 03 | je ein 16-Bit-Wert · D |
| CH31 | 62 | `0x3E` | 03 | 16 Bit, ×0,1 °C · D |
| CH32 | 63 | `0x3F` | 03 | 16 Bit, ×0,1 °C · D; hardwareprüfen |
| Konfiguration | 16 | `0x10` | 03 | Kommunikationsparameter · D; kein Write |

**Freigabeblocker:** Sensor abgezogen, Kanal nicht beschaltet, Werte unter 0 °C, DS18B20-Sonderwerte (z. B. Startwert), Kanal 32, interne Aktualisierungszeit und Zahlenformat am echten TM-32DS nachweisen. Die Integration darf bei unsicherem Format **keine plausible Temperatur erfinden**. Falls Blocklesen wegen einzelner Registerfehler scheitert, darf die Implementierung kontrolliert kleinere Blöcke prüfen, ohne die Buslast unbegrenzt zu erhöhen.

### B5.3 CWT-MB308N – P0

**Dokumentierte Kanalanzahl:** 8 AI, 4 AO, 8 DI, 8 DO. Die genaue Variante und bestückte RTU-/Ethernet-Schnittstelle müssen anhand des Typenschilds geprüft werden. Modbus-Digitaladressen werden oft als 1-basierte Referenzen angegeben: **PDU-Adresse 0 ist nicht die Modbus-Unit-ID 0**. [Q2]

| Signal | Herstellerreferenz | 0-basierte PDU | FC | Einordnung |
|---|---|---|---|---|
| AI0–AI7 | `30001–30008` | 0–7 | **04** | UINT16, Modus-Skalierung; D |
| AO0–AO3 | `40001–40004` | 0–3 | **03/06/16** | UINT16, Schreibweg nach Test; D |
| DI0–DI7 | `10001–10008` | 0–7 | **02 erwartet** | Referenz dokumentiert; FC/Bitfolge hardwareprüfen; T |
| DO0–DO7 | `00001–00008` | 0–7 | **01/05 erwartet** | Referenz dokumentiert; Status/Write hardwareprüfen; T |

**AI – physische Betriebsart / Herstellerformel**

| AI-Modus | Umrechnung Rohwert → physischer Wert | Test |
|---|---|---|
| 4–20 mA | `raw × 0,0004 mA` | 4 / 12 / 20 mA + Leitungsbruch |
| 0–20 mA | `raw × 0,0004 mA` | 0 / 10 / 20 mA |
| 0–5 V | `raw × 0,0001 V` | 0 / 2,5 / 5 V |
| 0–10 V | `raw × 0,0002 V` | 0 / 5 / 10 V |
| 1–5 V | noch nicht ausreichend geklärt | Nicht ohne Sonderprofil aktivieren |

**AO – physische Betriebsart / Herstellerformel**

| AO-Modus | Nutzbereich | Schreibwert (UINT16) | Freigabe |
|---|---|---|---|
| 4–20 mA | 4–20 mA | `round(mA × 2500)` = 10000–50000 | Nach Hardwaretest |
| 0–20 mA | 0–20 mA | `round(mA × 2500)` = 0–50000 | Nach Hardwaretest |
| 0–5 V | 0–5 V | `round(V × 5000)` = 0–25000 | Nach Hardwaretest |
| 0–10 V | 0–10 V | `round(V × 5000)` = 0–50000 | Nach Hardwaretest |
| 1–5 V | Offen | **Kein Write** | Nicht freigegeben |

**Jumper-Warnung:** Ein UI-Menü kann einen Hardware-Jumper nicht ändern. Jede Analogkonfiguration muss mit der tatsächlichen Verdrahtung/Betriebsart übereinstimmen. Ein AO-Sollwert darf ohne passende Hardwarekonfiguration nicht physisch ausgegeben werden.

**Relais-Readback:** FC01-Rücklesung beschreibt nur den vom CWT intern gemeldeten logischen Ausgangszustand, **nicht die tatsächliche Kontaktstellung oder Pumpenlaufmeldung**. Für diese gibt es bei Bedarf eine separat verdrahtete DI-, Strom- oder Durchflussüberwachung über HA-Automationen.

### B5.4 Weitere CWT-Serien – ausdrücklich NICHT im ersten Release

Spätere Kandidaten aus älterer Recherche: MB307D, MB307F, MB318C, CWT-BK-Serie und TM-2PT/TM-8PT. Bei MB307D/F liegen AI laut herangezogenen Unterlagen ab **40051 / PDU 50, FC03**, also nicht wie beim MB308N unter FC04/PDU 0. Daher **keine Registervererbung nur wegen gleicher Kanalzahl**. Die Profile werden als Backlog dokumentiert, aber **nicht** im Produkt-Auswahlmenü des ersten Releases angeboten. [Q3]

## B6. Modbus-Request- und Polling-Architektur

### L-51 – Gerätekommunikation parametrieren (noch nicht freigegeben)

L-51a umfasst nur die Slave-ID im High-Byte von Register 16; alle Low-Byte-
Bits werden erhalten. L-51b betrifft Baudrate/Parität und bleibt separat.
Ein Simulatornachweis für mehrere FC06-Sendungen nach Busy durch den
vorhandenen Backendpfad sperrt L-51a bis zu einem öffentlich unterstützten,
buskoordinierten No-Retry-Schreibpfad. Details: [Status](l51_status.md).

Die Geräteadresse und seriellen Parameter gehören zum Gerät; die Verbindung
und das Gateway sind getrennt. Vor einem einzelnen FC06 muss der Rohwert
vollständig gelesen, adress- und busseitig geprüft und die Änderung ausdrücklich
bestätigt sein. Danach sind neues Register und ein Messwert unter den neuen
Parametern frisch zu verifizieren, erst dann darf die HA-Gerätekonfiguration
übernommen werden. Unklare Ergebnisse dürfen weder erneut geschrieben noch
automatisch zurückgeschrieben werden. Die Implementierung bleibt bis zum
Nachweis dieser Invarianten vollständig lesend. [Status](l51_status.md).

### L-50 – kanalbezogene Abfrageintervalle (Ergänzung zum Entwicklungsbranch 0.1.0b4)

Jeder aktivierte Kanal übernimmt ohne Override das vorhandene Gruppenintervall.
In der Kanal-Konfiguration kann stattdessen ein ganzzahliger Wert in Sekunden
gespeichert werden (Temperatur 5–3600 s; DI/DO 1–3600 s; AI/AO 2–3600 s).
Das Zurückstellen auf „Standard“ entfernt nur diesen Override. Kanalname,
Gerätekennung, Entitätskennung und sämtliche bisherigen Einstellungen bleiben.

Der Scheduler führt pro Kanal einen Fälligkeitszeitpunkt. Gleichzeitig fällige
und zusammenhängende Register derselben Gruppe werden mit derselben dokumentierten
Modbus-Lesemethode als Block abgerufen. Nicht fällige Nachbarkanäle werden nicht
vorgezogen; deaktivierte Kanäle werden nicht abgefragt. TM-32DS: FC03,
Startadresse 32, höchstens 32 Temperaturregister pro Block. Bei einer
Registerausnahme wird ausschließlich der betroffene Block endlich halbiert,
bis fehlerhafte Einzelregister isoliert sind. Pro physischem Bus bleiben alle
Zugriffe über die bestehende gemeinsame Sperre serialisiert. Die bestehende
Timeout-/Backoff-Begrenzung und die Wiederaufnahme nach Verbindungsabbruch
bleiben erhalten.

Jeder Kanal hält Zeitstempel des letzten gültigen Messwerts und der letzten
Rohantwort getrennt; seine Stale-Frist beträgt drei effektive Intervalle.
Ungültige Kodierungen, darunter das am TM-32DS gemessene `0xFC18` bei abgezogenem
DS18B20, sind `unavailable`, ohne Nachbarkanäle zu entwerten. Ein tatsächlicher
Verbindungsabbruch invalidiert die betroffenen Geräte und erzwingt danach frische
Lesezugriffe. Die produktive Beta bietet weiterhin keinerlei Schreibentitäten.

Nachweise und offene Hardwaretests: [L-50-Prüfbericht](l50_test_report.md) und
[Hardwaretestplan](ha_test_plan.md).

1. **Shared Connection First:** Für eine identische physische Verbindung den HA-Modbus-Verbindungsmanager nutzen; keine zwei aktiven Master auf derselben RS485-Leitung. HA-Anwendungen können auf der geteilten Verbindung mehrere Units verwalten. [Q4]
2. **Ein Request pro Bus:** RTU-Frames zeitlich serialisieren. Ein TCP/RTU-Gateway darf nicht durch parallele Requests an verschiedene Unit-IDs überfahren werden. Gateway- und Unit-Polling sind voneinander logisch getrennt.
3. **Blocklesen:** Zusammenhängende Register nach FC/Datenart und verträglicher Blocklänge bündeln; bei bekannten Geräte-/Firmwaregrenzen begrenzen. Keine sinnlosen Einzelabfragen von 32 Temperaturregistern.
4. **Fairness:** Fehlende Antworten kosten ein begrenztes Zeitbudget; mehrere defekte Slaves dürfen nicht jeden funktionierenden Teilnehmer dauerhaft verhungern lassen. Exponentieller oder gestufter Backoff mit Obergrenzen.
5. **Konfigurierbare Intervalle:** Je Gerät oder sinnvoller Registergruppe, innerhalb sicherer Min-/Max-Grenzen. Keine 1-ms-Polling-Option, die den Bus dauerhaft blockiert.
6. **Datenalter:** Entität ist nur dann frisch, wenn gültige, neue, dem passenden Request zugeordnete Daten empfangen wurden. Ein offener Socket, ein alter Cachewert oder ein HA-Neustart ist keine frische Messung. Die tatsächliche interne Aktualisierungszeit des Moduls wird **nicht** aus dem Pollintervall abgeleitet.
7. **Diagnose:** Zähler und Zeitstempel getrennt je Verbindung, Unit und Kanalgruppe; kein ungefiltertes Logspam bei längeren Ausfällen.

## B7. Protokollfehler, Timeouts, Resynchronisierung

- **RTU:** Prüfen von Framing, CRC, Unit-ID, erwarteter Funktion, Länge/Byteanzahl; Modbus-Exception erst nach gültigem Frame interpretieren. Pufferfehler, Echo und verspätete Antworten werden durch geprüfte Framevalidierung und Resynchronisierung behandelt. RTU hat keine Transaktionskennung; deshalb sind die getesteten Timingannahmen und Grenzen zu dokumentieren. Eine universelle Never-Misassignment-Garantie ist nicht möglich.
- **TCP:** MBAP-Transaktionskennung, Protocol-ID, Länge, Unit-ID und erwartete FC prüfen; fragmentierte und gebündelte TCP-Segmente korrekt verarbeiten.
- **RTU-over-TCP:** Reines TCP-Transport-ACK ist keine Modbus-Bestätigung; passende RTU-Frame-Prüfung, definierte Busruhe und Ablaufgrenzen.
- **Fehlerklassen:** Timeout, Transport getrennt, Protocol/Exception, CRC/Framing, falsche Slave-ID/FC, Readback-Abweichung, stale, no-route/port-locked, Benutzerabbruch.
- **Fehlerisolation:** Einzelner Request-Timeout = Verdachtsfall, nicht automatisch gesamter Gatewayausfall. Nach wiederholten Fehlschlägen Unit offline; andere Units weiterhin bedienen. Transportfehler setzt betroffene Verbindung auf nicht bereit.
- **Ressourcen:** Empfangspuffer begrenzen; offene, hängen gebliebene Verbindungen kontrolliert schließen; Neustart-/Reconnect-Versuche begrenzen.

Modbus-Stack-Funktionen dürfen nicht „zur Sicherheit“ blind doppelt implementiert werden. Die eigentliche Frameprüfung soll möglichst durch die etablierte Bibliothek erfolgen, mit eigener **Validierung der zu erwartenden Antwort und klarer Diagnose**. Regresstests für die beim Registerwerk beobachteten Echo-, CRC-, Timeout-, Resync- und Verbindungsstatusfehler sind Pflicht.

## B8. Schreiboperationen: Rechte, Ordnung und Readback

**Standard:** Jeder DO/AO beginnt als **read-only**. Die Freigabe erfolgt explizit je Kanal und kann später widerrufen werden. Das Ändern der Berechtigung ändert niemals stillschweigend den realen Ausgangszustand. Ist der Ist-Zustand `ON` oder unbekannt, muss die UI vor Entzug der Schreibfähigkeit warnen.

**Zentraler Schreib-Gatekeeper:** Alle durch ComWinTop angebotenen Switch-/Number-Aktionen werden über dieselbe Rechte- und Kommunikationsprüfung geleitet. Ein externer Modbus-Master ist davon **nicht** erfasst. Ein aktivierter Write-Kanal besitzt **keine** anlagenspezifische Schutzverriegelung; diese Verantwortung liegt außerhalb des Kerns.

**Transaktionsablauf:**

1. Aktuelle Berechtigung, Kanalart, zulässigen AO-Bereich und Verbindungsgeneration prüfen.
2. Maximal **einen** laufenden Schreibvorgang und **einen** jüngsten wartenden Sollwert **pro Kanal** verwalten; ältere wartende Sollwerte explizit als `SUPERSEDED` verwerfen.
3. Sendetransaktion über gemeinsamen Buszugriff serialisieren; FC05/06/16 nur laut verifiziertem Profil. **Kein blindes Write-Retry** – auch nicht versteckt durch verwendete Bibliothek.
4. Nach Write oder unklarer Antwort **frischen** gerätespezifischen Readback anfordern; keinen HA-Cache als Bestätigung verwenden.
5. Bestätigt = gelesener logischer Zustand stimmt mit dem angeforderten überein (bei AO innerhalb dokumentierter Auflösung/Toleranz). Nicht bestätigt = `UNCONFIRMED`/`MISMATCH`/`UNAVAILABLE` mit Diagnose, keine Erfolgsmeldung.
6. Vor Senden eines vorgemerkten Auftrags Rechte und Verbindungsgeneration erneut prüfen. Wartende Befehle verfallen nach genau 2 Sekunden ab Auftragseingang. Prüfung unmittelbar vor der tatsächlichen Übertragung; danach Fehler an Aufrufer. Keine verdeckte Sollwertspeicherung.
7. **Bereits beim ersten ungeklärten gesendeten Schreibvorgang** alle **noch nicht übertragenen** Aufträge für die betroffene Unit bzw. Verbindung verwerfen. Bereits gesendete, unklare Schaltungen bleiben als `UNCONFIRMED` sichtbar.
8. Bei Wiederverbindung und HA-Neustart **keine alten Sollwerte wiederherstellen**, sondern Zustand neu lesen und nur künftig neu angeforderte Befehle akzeptieren.

**Wichtiges Konkurrenzproblem:** Ein späterer Auftrag darf eine unklare laufende Transaktion nicht ohne geordneten Recovery-Prozess überholen. Bei beschädigter RTU-Antwortzuordnung muss die Verbindung erneut synchronisiert werden. Eine Rücklesung bestätigt höchstens die CWT-interne Ausgangsinformation, nicht das reale Relais, den Stromfluss oder eine Sicherheitswirkung.

## B9. Status- und Wiederherstellungsmodell

| Zustand | Bedeutung | Lesebetrieb | Schreiben |
|---|---|---|---|
| `INITIALIZING` | Konfiguration, Registry, erstes Polling | kontrolliert | gesperrt |
| `ONLINE` | erforderliche Kommunikation/Readback aktuell | aktiv | nur individuell freigegebene, geprüfte Kanäle |
| `SUSPECT` | begrenzte Zahl verdächtiger Antworten | Diagnose / neue Prüfungen | unklare Kanäle sperren |
| `OFFLINE` | Unit oder Transport bestätigtermaßen ausgefallen | unavailable | sperren, wartende Writes verwerfen |
| `RECOVERING` | gültige neue Verbindung, Kanalwerte werden geprüft | schrittweise | nur für bereits synchronisierte Kanäle |

**Nicht blockierende Recovery:** Zuerst der Transport, danach die Unit, danach die benötigten Registergruppen, zuletzt pro DO/AO die Schreibfähigkeit. Ein abgezogener Temperaturfühler oder ein deaktivierter Nachbarkanal darf nicht den gesamten MB308N schreibunfähig machen. Falls Readback technisch nicht vorhanden ist, **nicht** fälschlich „vollständig verifiziert“ ausweisen; der konkrete Schreibweg ist dann bis zur geklärten Alternativstrategie nicht freizugeben.

**Geltungsbereich:** Fällt nur Unit 2 hinter dem Waveshare aus, bleibt Unit 1 erreichbar, soweit Transport und Bus selbst funktionieren. Fällt der Waveshare aus, werden alle abhängigen Units als nicht verfügbar markiert. Für kritische Verbraucher garantiert ComWinTop **keine** sichere Ausgabe-/Abschaltstellung bei Offlinebetrieb.

## B10. Sicherheits-, Datenschutz- und Betriebsgrenzen

- **Keine sicherheitsgerichtete Steuerung:** Weder DI-NO/NC, noch DO-Readback, noch Software-Watchdog-Zustand sind Sicherheitsnachweise. Anlagen-/Personenschutz über fachgerecht ausgewählte, unabhängig wirkende Hardware.
- **Keine internen Not-Aus-/Sammelstörungs-Automatikfunktionen:** Alle betreffenden Automationsbeispiele sind optional. Das Basismodul nimmt keine heimlichen Schalt- oder Latch-Eingriffe vor.
- **Modbus TCP ist ohne Authentifizierung/Verschlüsselung:** Nur vertrauenswürdiges Segment; keine öffentliche Portweiterleitung, kein fremder Internetzugriff. [Q5]
- **Logs:** Keine privaten IPs, Tokens, Klartext-Zugangsdaten oder vollständige private Payloads im standardmäßig exportierten Diagnosebericht. Verbose Debug nur bewusst aktiviert und zeitlich begrenzt.
- **Verfügbarkeit:** Nach HA-Ausfall keine Annahme, dass ComWinTop Ausgänge deaktivieren oder Freigaben zurücknehmen kann.
- **Schnittstellen nach außen:** Optionale Automationen können auf Entity-Verfügbarkeit und Diagnosesensoren reagieren. Ein gültiger HA-Status ist kein unabhängiger Watchdog und garantiert keine physische Störungsabschaltung.

## B11. Optionale Automationsbeispiele (außerhalb des Kerns)

Separate, ausdrücklich **nicht automatisch installierte** Beispiele unter `examples/automations/`:

| Beispiel | Datenquellen | Bedingung / Grenze |
|---|---|---|
| Pumpe Betriebsmeldung | CWT-DO + DI oder Stromsensor | Nur wenn eine echte Rückmeldung vorhanden ist; kein garantiertes Pumpenlaufen nur aus DO-Status |
| Sammelstörung | HA-Binärsensoren / Diagnosen | Best-Effort innerhalb HA; ohne externen Watchdog keine Alarmgarantie bei HA-Ausfall |
| Anlagen-Stopp-Meldung | frei gewählter CWT-DI (NO/NC) | Meldesignal, nicht hardwarewirksamer Not-Aus; verbundene Automationen können bei HA-/Busausfall ausfallen |
| Freigabegruppen | HA-Automationen/Helfer | Anlagenspezifische Zuständigkeit; kein Kernfeature, kein globaler DO-Lock im Core |
| Lebenszeichen-/Watchdog-Schnittstelle | Diagnosedaten/optional Helfer | Keine hardwareseitige Schutzbehauptung |

**Nicht Teil der Veröffentlichung als „fertig sicher“:** konkrete Heizstab-/WP-Freigabeschaltungen, Pumpennachlauf bei Störung, feste Ersatztemperaturen, verbindliche Relais-Verdrahtungspläne. Solche Vorlagen müssen vor realer Übernahme vom Anlagenbetreiber geprüft werden.

---

# Teil C – Qualität, Test und Veröffentlichung

## C1. Nichtfunktionale Qualitätsanforderungen

| Kennung | Muss-Kriterium | Nachweis |
|---|---|---|
| N-01 Stabilität | HA-Reboot/Reload und Netz-Reconnect lösen **null ungeforderte Writes** aus | Automatisierter Trace + Hardwaretest |
| N-02 Reaktionsverhalten | Polling und Timeouts begrenzt; definierte Fairness für mindestens zwei Units | Bus-/Latenzmessung; Profil festhalten |
| N-03 Datenintegrität | Kein veralteter Messwert als neu; kein Schreib-Echo als Kontaktbeweis | Fault-Injection-Tests |
| N-04 Ressourcen | Asynchron und begrenzte Puffer; keine Task-/Socket-Leaks | 72-h-Dauertest, Profiling |
| N-05 Registry-Stabilität | Keine Doppel-Entitäten nach Reconfigure/Neustart | HA-Integrationstests |
| N-06 API-Nutzung | Gemeinsamer HA-Modbus-Stack bevorzugt; keine veraltete `get_hub`-Abhängigkeit | Codeprüfung gegen Zielversion |
| N-07 Dokumentation | Deutsch/Englisch, Anschluss- und Betriebsarten, bekannte Grenzen | README-/Doc-Review |
| N-08 Datenschutz | Standarddiagnose maskiert personenbezogene Netzdetails | Test Diagnoseexport |
| N-09 CI | Unit-/Integrationstests, Ruff, Hassfest, HACS Action erfolgreich | GitHub Actions |
| N-10 Wartbarkeit | Profilspezifische Definition statt Copy-Paste-Modbus-Code | Architekturreview |

**Zielwerte zur Erprobung, noch keine Messbehauptung:** TM-32DS Pollintervall initial 15 s; DI/DO initial 1–5 s je Buslast; AI/AO initial 5–15 s; Request-Timeout und Backoff modell-/gatewayabhängig testen. Diese Werte sind konfigurierbare *Startvorschläge*, keine Echtzeit- oder Sicherheitsfristen. Freigabe erst nach gemessener Gesamtabfragelast bei 9.600 Baud und mindestens zwei Units.

## C2. Verbindlicher Abnahmekatalog

**Verbindung und Einrichtung**

- **T-01** UI: mehrere Verbindungen und mehrere CWT-Units ohne YAML anlegen, ändern, entfernen; stabile HA-IDs.
- **T-02** Zwei gültige Units an einem Waveshare; keine gleichzeitigen RTU-Requests; kein doppeltes Unit-ID-Paar.
- **T-03** Zwei separate Waveshare-Verbindungen parallel ohne Cross-Talk und ohne gemeinsame Geräte-IDs.
- **T-04** Transparentes RTU-over-TCP versus TCP→RTU-Gateway korrekt unterschieden; falscher Modus ergibt Diagnose statt Scheinerfolg.
- **T-05** USB-RS485 auf HA OS: stabiler Portpfad, Reboot, Stecker ziehen/stecken, Portkonflikt, keine zweite Masterinstanz.
- **T-06** Echtes TCP-CWT (falls passende Variante vorhanden): normale TCP-Unit ohne Gateway-Konvertierung.
- **T-07** Manuelle Modellauswahl; kein versteckter Auto-Scan, keine automatische Schreiben von Unit-ID/Baudrate.

**Register und Kanalinterpretation**

- **T-08** TM-32DS CH1, CH16, CH32 und vollständiger 32er Registerblock korrekt.
- **T-09** TM-32DS abgesteckter Sensor, negative und hohe Testtemperatur, Startup-/Fehlercodes korrekt und ohne plausibel klingende Ersatzwerte.
- **T-10** MB308N AI0–AI7 einzeln mit Referenzgenerator; korrekte Umrechnung je Jumpermodus.
- **T-11** MB308N AO0–AO3 einzeln am unbelasteten Messkreis; Grenzwerte, FC06/16, Rücklesung, Jumperkonformität.
- **T-12** MB308N DI0–DI7 einzeln bei Kontakt offen/geschlossen; NO/NC pro Kanal unabhängig und nach Neustart stabil.
- **T-13** MB308N DO0–DO7 einzeln; FC01/05, eindeutige Unit-/Kanaladresse, nachweisbarer interner Status.
- **T-14** Ungenutzte Kanäle deaktiviert/ausgeblendet; Reaktivierung ohne Registry-Duplikate.
- **T-15** AO-/DO-Default „Nur Lesen“ und spätere Freigabe/Entzug je Kanal; keine ungefragte physische Umschaltung.

**Modbus-Protokoll & Registerwerk-Regressionsfälle**

- **T-16** RTU: CRC falsch, FC falsch, Slave-ID falsch, falsche Länge, abgeschnittenes Telegramm und gültige Exception sauber behandelt.
- **T-17** TCP: MBAP-Transaktionskennung, Längenfeld, Fragmentierung, verkettete Pakete, fehlerhafte Protocol-ID korrekt verarbeitet.
- **T-18** RTU-over-TCP: verspätete Fremdantwort, lokales Sende-Echo und Quarantäne/Resync ohne falsche Zuordnung.
- **T-19** Ein MB308N-Timeout behindert den erreichbaren TM-32DS nicht dauerhaft.
- **T-20** TCP verbunden, aber kein gültiger Modbus-Slave antwortet: Gateway-/Slave-Status eindeutig getrennt.
- **T-21** Endlossende-/Pufferbelastung: begrenzter Speicher, kein HA-Blockieren, keine Logflut.
- **T-22** Registerblock-Fehler isoliert betroffene Kanäle, soweit sinnvoll und durch Einzel-/Teilblocklesung belegbar.
- **T-23** Beschränkte Lese-Retries und Backoff; Fairness bei drei oder mehr Slaves plus einem defekten Slave.

**Schreibbefehle, Wiederherstellung und Neustart**

- **T-24** FC05/06-/FC16-Antwort und lokales Echo ohne Readback ergibt **keinen** behaupteten physischen Schalterfolg.
- **T-25** Unbestätigter Write: genau definierte Folge-Readbacks; keine automatische Write-Wiederholung, auch nicht innerhalb der Bibliothek.
- **T-26** HA sendet EIN, dann AUS, dann EIN: nur neueste gültige wartende Anforderung bleibt; ältere erhalten „überholt“.
- **T-27** Kommunikationsausfall nach Queuing: alle noch nicht gesendeten Aufträge der betroffenen Unit/Verbindung werden verworfen.
- **T-28** Kommunikationsausfall nach möglichem Senden: Zustand bleibt `UNCONFIRMED` bis frischem Readback oder eindeutiger Fehleranzeige.
- **T-29** Reconnect: Unit-/Kanalregister frisch synchronisieren; keine alten Setpoints oder Relay-Zustände nachschreiben.
- **T-30** HA-Reboot/Integration-Reload bei geschaltetem DO/AO: null ungeforderte Writes, Rohzustand frisch auslesen.
- **T-31** Entzug der Schreibfreigabe bei wartendem Befehl: Queue-Eintrag verworfen, tatsächlicher Ausgang nicht heimlich verändert.
- **T-32** Ein defekter AI- oder Temperaturkanal blockiert nicht alle anderen funktionierenden Kanäle bzw. DO.
- **T-33** `stale`/`unavailable`/`unknown`: keine automatische Interpretation als `off`, `0 °C` oder „gesund“.

**Veröffentlichung und Bedienbarkeit**

- **T-34** HA UI-Flow, Options-/Reconfigure-Flow, DE/EN Übersetzungen und stabile Registry mit Automatisierungstests.
- **T-35** Anonymisierbare Diagnostics inklusive Transport-/Unit-Fehlerzähler, letzter Antwort, Pollalter und Schreibstatus.
- **T-36** Dokumentierte Beispielautomationen sind getrennt, optional und werden nicht automatisch installiert oder ausgeführt.
- **T-37** CI: Unit- und Integrationstests, Ruff, Hassfest, HACS Action und Dependency-/Security-Checks erfolgreich.
- **T-38** 72-Stunden-Lesedauertest: TM-32DS und MB308N zusammen am realen Gateway inklusive kontrollierter Fehlerunterbrechungen.
- **T-39** USB-RS485-Hardwaretest separat mit beiden Geräten; Verfügbarkeit und Port-Exklusivität protokollieren.
- **T-40** Hardware-Write-Test je MB308N-DO/AO mit sicherer Testverdrahtung, Originalantwort, Readback und externer Referenzmessung.
- **T-41** Konformität des ausgelieferten Pakets mit HACS/Marketplace-Custom-Repository-Struktur, Releases und Installationsanleitung.

**Abnahmeentscheidung:** Ein Release darf nur das als „funktioniert“ bezeichnen, was durch T-Tests und Hardware-Revisionsprotokoll belegt ist. **Vollständig freigegeben** erst nach T-01–T-41, soweit für die tatsächlich unterstützte Hardware sinnvoll; erweiterte Automatiken aus `examples/` sind davon getrennt.

## C3. GitHub-/Marketplace-Projektstruktur

```text
homeassistant-comwintop/
├── custom_components/comwintop/
│   ├── __init__.py
│   ├── manifest.json
│   ├── const.py
│   ├── config_flow.py
│   ├── coordinator.py
│   ├── sensor.py
│   ├── binary_sensor.py
│   ├── switch.py
│   ├── number.py
│   ├── diagnostics.py
│   ├── device_profile.py
│   ├── write_manager.py       # Rechte, Single-flight, Queuing, Readback
│   ├── status.py              # Gateway/Unit/Kanal getrennt
│   ├── strings.json
│   ├── translations/de.json
│   ├── translations/en.json
│   └── profiles/{tm_32ds,mb_308n}.py
├── tests/
│   ├── test_register_profiles.py
│   ├── test_transport_modes.py
│   ├── test_usb_serial.py
│   ├── test_di_polarity.py
│   ├── test_write_readback.py
│   ├── test_queue_drop.py
│   ├── test_recovery.py
│   └── test_config_flow.py
├── examples/automations/
│   ├── pump_feedback.yaml
│   ├── collective_fault.yaml
│   └── plant_stop_notification.yaml
├── docs/
│   ├── architecture.md
│   ├── register_profiles.md
│   ├── hardware_validation.md
│   ├── safety_boundaries.md
│   └── supported_hardware.md
├── .github/workflows/{tests,hassfest,hacs,lint,security}.yml
├── hacs.json
├── README.md
├── CHANGELOG.md
├── SECURITY.md
└── LICENSE
```

Das Repository enthält **genau eine** Custom Integration unter `custom_components/comwintop/`; `examples/` sind reine manuell zu übernehmende Beispiele, keine automatisch installierte Steuerung. Das Python-Backend kann interne Dateien anders organisieren, solange Schnittstellen, Testbarkeit und Verantwortungstrennung erhalten bleiben.

**Namensrecht:** `ComWinTop` sachlich als Bezug auf kompatible Hardware verwenden, ohne offiziellen Herstellerstatus oder Markenrechte zu behaupten. Lizenz des eigenen Quellcodes gesondert festlegen (MIT empfohlen); urheberrechtlich geschützte Herstellerhandbücher nur verlinken, nicht ungefragt spiegeln.

## C4. Entwicklungsphasen und Freigabe-Gates

| Gate | Ergebnis | Freigabevoraussetzung |
|---|---|---|
| G0 | Repository und Architektur | HA-Version und softwareseitige Transportfähigkeiten geprüft; konkrete Adapter und Revisionen erst vor der jeweiligen Hardwareabnahme erfassen |
| G1 | Modbus-/Profil-Mocks | alle Registerdecoder und Protokollfehler/Queue-Tests grün |
| G2 | TM-32DS lesend | 32 Kanäle, negative Werte, Sensorfehler, Dauertest |
| G3 | MB308N lesend | AI/DI, DO/AO-Readback, NO/NC, skalierte Werte |
| G4 | 3 Transportwege | Transparente Bridge, echter Gateway/TCP-Weg sofern Hardware, USB-RS485 real geprüft |
| G5 | MB308N schreibend | DO/AO einzeln hardwarevalidiert, Readback und keine Blind-Retries |
| G6 | HACS/Marketplace Custom Beta | CI, Doku, bekannte Limits, Warnungen, Releasenachweis |
| G7 | Vollständige stabile Version | alle P0-Entscheidungen, relevant dokumentierte Tests bestanden |
| G8 | Default-Katalog (später) | HACS Action, Hassfest, gültiges Release, Brands/PR-Anforderungen erfüllt |

Kein öffentlicher Releasetext darf „ausfallsichere Schaltung“, „Not-Aus-Funktion“ oder „Relaisstellung garantiert“ behaupten.

## C5. Risiken, offene Hardwareinformationen und Blocker

| Risiko / offene Information | Konsequenz | Erforderliche Klärung |
|---|---|---|
| Exakter Waveshare-Typ/Betriebsmodus unbekannt | falsches Frameformat/Port | Typenschild, Weboberfläche, Modus und Port erfassen |
| TM-32DS negative Werte/Sondercodes offen | falsche Messwerte | echte Rohantwort bei Negativwert und Sensor-Ausfall |
| TM-32DS CH32 noch nicht real verifiziert | unvollständige 32-Kanal-Zusage | gezielter CH32-Test |
| MB308N genaue Variante/Revision/Jumper unbekannt | falscher Analogbereich; falscher TCP-Modus | Typenschild, Handbuchversion, Verdrahtung dokumentieren |
| MB308N DI/DO-FC nicht ausreichend belegt | Gefahr falscher Schreibfunktion | Originalprotokolltest/FC01/02/05 |
| Modbus-Stack-Support für transparenten Gatewaymodus | nicht jeder HA-Adaptermodus direkt unterstützt | früher minimaler API-Prototyp auf HA 2026.11 |
| USB-RS485-Adapter/Portexklusivität | Adapter wechselt Pfad, zweiter Master greift zu | per-ID-Pfad und exklusiver Zugriff; HA-OS-Test |
| Externer Modbus-Master | kann Write-Gatekeeper umgehen | Dokumentation, Netzzugriff begrenzen, exklusive Busnutzung |
| Kein physischer Kontaktnachweis bei DO-Readback | Scheinerfolg möglich | Warnung, bei Bedarf separate Ist-Rückmeldung außerhalb Core |
| HA-Ausfall oder Netztrennung | keine aktive Schutzreaktion möglich | erforderliche Anlagen-/Personenschutzhardware separat |

**Vor dem ersten Hardwaretest zu erfassen:** Fotos der beiden CWT-Typenschilder (inkl. Revision), Waveshare-Modell/Modus und Schnittstellenparameter, USB-RS485-Modell/Serienpfad, Unit-IDs, AI/AO-Jumper-/Signalmodi, CWT-Firmware soweit verfügbar.

---

# Teil D – Quellen, Status und Übergabe

## D1. Nachweisliste (Abruf am 15.11.2026)

- **[Q1]** CWT-TM-32DS Register und Kanalanzahl: https://manuals.plus/asin/B0F4DN8JKK ; Herstellerprodukt: https://store.comwintop.com/products/32-channels-18b20-rs485-modbus-output-temperature-acquisition-module
- **[Q2]** CWT-MB308N Register/Skalierung (Handbuchkopie): https://www.scribd.com/document/985065733/CWT-MB308N-8di-8do-8ai-4ao-manual
- **[Q3]** Ältere MB307D/F-Unterlagen, nur späterer Backlog: https://www.scribd.com/document/985065749/CWT-MB307D-8di-8do-8ai-manual ; https://www.scribd.com/document/985065746/CWT-MB307F-8di-8ai-manual
- **[Q4]** Offizielle Modbus-Entwicklerdokumentation, gemeinsames Connection-/Unit-Modell: https://contributors.home-assistant.io/core/internals/modbus/
- **[Q5]** Home Assistant Modbus, Zugangswege und Security: https://www.home-assistant.io/integrations/modbus/
- **[Q6]** Waveshare „RS485 TO ETH“, Einschränkungen: https://www.waveshare.com/wiki/RS485_TO_ETH
- **[Q7]** Waveshare „RS485 TO ETH (B)“, transparent/Modbus TCP→RTU: https://www.waveshare.com/wiki/RS485_TO_ETH_%28B%29
- **[Q8]** HA Serial/USB-/Socket-Ports: https://www.home-assistant.io/connectivity/serial/
- **[Q9]** Home Assistant Config/Subentry-Flows: https://developers.home-assistant.io/docs/config_entries_config_flow_handler/
- **[Q10]** HACS/Marketplace-Integrationsanforderungen: https://hacs.dev/docs/publish/integration/
- **[Q11]** Offizieller Default-Katalog-Aufnahmeweg: https://hacs.dev/docs/publish/include/
- **[Q12]** Home Assistant Modbus-Migration `async_get_unit` ab 2026.9: https://contributors.home-assistant.io/blog/2026/09/02/modbus-get-hub-deprecation/

**Quellenqualität:** Soweit Herstellerinformationen nur über Manuals+- oder Scribd-Spiegel vorliegen, sind die Register als **D (dokumentiert, aber nicht am Gerät geprüft)** oder **T (teilweise)** markiert. Fremde Zusammenfassungen können generationenspezifisch oder fehlerhaft sein. Für alle schreibbaren Funktionen muss eine Originalunterlage und/oder ein nachvollziehbarer Rohtelegramm-Hardwaretest herangezogen werden.

## D2. Übergabe an Work / Entwicklerteam

1. Diese **v0.6** ersetzt v0.5 als verbindliche fachliche Basis. Die 44 Ja-/Nein-Entscheidungen sind nicht ohne ausdrücklichen Change Request zu ändern.
2. Den Integrationskern ausschließlich als Modbus-I/O-Integration entwickeln. Frühere Safety-/GLT-Logik **nicht** in die Core-Module übertragen.
3. Mit `modbus-connection`/`async_get_unit` beginnen, zunächst Transportprobe und P0-Geräteprofile simuliert testen, danach echte Hardware.
4. USB-RS485 ist **Pflicht bereits für den ersten vollständigen Release** und hat ein separates Hardwaretest-Gate.
5. Jedes Feature nach **implementiert / dokumentiert / hardwarevalidiert** kennzeichnen; nicht durch bloße Dokumentation als getestet deklarieren.
6. Vor dem ersten öffentlichen Write-Release Tests für FC, Registeradressen, AO-Jumper, Readback, Timeout, Reconnect und Queued-Write-Verwerfung abschließen.
7. Getestete Automationsbeispiele in einem separaten Verzeichnis liefern und ausdrücklich mit Nicht-Sicherheits-Hinweis versehen.

**Endstatus:** Fachliche Architektur **bestätigt**. Umsetzung, Originalregisterprüfung und reale Abnahme **ausstehend**.

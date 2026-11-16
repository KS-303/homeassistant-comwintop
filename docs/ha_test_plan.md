# Hardwareabnahme – lesende Beta und L-50-Entwicklungsbranch

## L-51 vor jeder Schreibfreigabe

L-51a ist bislang ausschließlich ein Simulator- und Codebefund: Bei Busy
wiederholt der vorhandene Backendpfad FC06. Ein realer HA-Schreibtest ist
gesperrt. Nach einem öffentlichen No-Retry-Pfad zuerst TCP und RTU physisch
auf exakt ein Telegramm je Fehlerfall prüfen; das CWT an einem isolierten Bus
mit eindeutiger Adresse testen. L-51b (Baudrate/Parität) bleibt ein eigener
Testblock, einschließlich Gateway- und Multidrop-Verhalten.

Register 16 am TM-32DS zunächst lesend mit Registerwerk vergleichen.
Originaldokumentation für sämtliche Codes und Bits verifizieren. Für jeden
Transport und Fehlerpfad eine einzige physische FC06-Übertragung nachweisen,
einschließlich Busy, Timeout, Abbruch und HA-Neustart. Adresse 1→2,
Persistenz, Rücklesen und Messwert an neuer Adresse am isolierten Gerät
prüfen. Danach Multidrop-Bus mit zweitem Slave und Wiederherstellungsplan
testen. MB308N erst nach eigenem Register- und Hardwarebeleg freigeben.

Stand: vollständige Abnahme **noch nicht durchgeführt**. Softwaretests sind kein Hardwaretest.
Der separate L-50-Abfragetest steht noch aus. Der TM-32DS wurde zwischenzeitlich
mit zwei DS18B20 am Waveshare-Gateway lesend geprüft (FC03, Adressen 32/33,
9600 8N1). Ein abgezogener Fühler lieferte `0xFC18` (−100,0 °C) und erholte
sich nach Wiederanschluss. Das ersetzt keinen Test gemischter Intervalle.
Erster Test auf einer Home-Assistant-Testinstanz, zunächst mit TM-32DS;
MB308N separat ergänzen.

## Vorbereitung

- HA-Backup, genaue Core-Version, CWT-Modell/Firmware und Gateway-Modell notieren.
- Echte Betriebsart des Gateways klären: Modbus TCP→RTU oder transparenter
  RTU-Tunnel. Host, Port, Baudrate, Parität, Stopbits und Unit-ID notieren.
- Einen parallelen externen Modbus-Master für denselben RTU-Bus stoppen.
  Bestehende HA-Modbus-Nutzung wird über den HA-Unterbau geteilt; doppelte
  Geräteabfragen trotzdem vermeiden. DNS-/IP-Aliase nicht als zweite Verbindung anlegen.
- Installationsschritte aus README befolgen. Die Beta besitzt keine Schreibentitäten.

## Prüffolge

| Schritt | Durchführung | Erwartung / Abnahmekriterium |
|---|---|---|
| 1 | Verbindung und TM-32DS als Gerät hinzufügen | Lesetest erfolgreich; keine Modellerkennung behauptet |
| 2 | Ein bekannter Fühler, dann CH1 und CH32 prüfen | Richtige Zuordnung, plausible Temperatur; keine Kanalverschiebung |
| 3 | Gleichen Rohwert separat mit Registerwerk lesen, ohne gleichzeitigen zweiten Master | FC03, Register 32–63 (0-basiert), Rohwert und Temperatur stimmen überein |
| 4 | Fühler an einem unbenutzten Testkanal abziehen | Nur betroffener Kanal unavailable; rohe Fehlerkennung dokumentieren |
| 5 | Temperaturänderung und Neustart des Moduls | Kein 85-°C-Startwert als gültige Temperatur; echte 85 °C sind derzeit ebenfalls unavailable |
| 6 | Netzwerk/Bus kurz trennen und wieder verbinden | Fehlerdiagnose, Werte spätestens nach Stale-Frist unavailable; frische Werte nach Recovery; keine Writes |
| 7 | Bei zwei Units nur eine abschalten | Gesunde Unit läuft weiter; bei RTU-Resync kann Bus kurz unterbrochen werden |
| 8 | Kanal in Gerätekonfiguration deaktivieren/reaktivieren | Deaktiviert keine Auswertung; anschließend gleiche Unique-ID; kein physischer Ausgangswechsel |
| 9 | Integration neu laden, dann HA neu starten | IDs bleiben gleich; zuerst keine alten gültigen Messwerte; danach frische Werte |
| 10 | Gruppenintervall verändern | Abfragerate folgt Einstellung; 3×Intervall ist Stale-Grenze, Monitorauflösung 0,5 s |
| 11 | MB308N separat: DI NO/NC, AI mit bekanntem Referenzsignal | NO/NC korrekt; Modus passt zu Jumper; AI-Endpunkte/Mitte verifizieren |
| 12 | MB308N AO/DO ausschließlich rücklesen | Tatsächliche Readbacks sichtbar; kein Switch/Number-Schreibpfad vorhanden |
| 13 | 72 Stunden protokollierter Hardwarebetrieb | Fehlerzahlen, Latenzen, Ausfälle und Recovery dokumentieren; keine ungeklärten Fehler |

## L-50: zusätzlich am realen TM-32DS prüfen

1. Zwei bis sieben Kanäle aktivieren; z. B. Gruppenintervall 15 s, Overrides
   5 s, 10 s, 30 s und 60 s. Zeitstempel und Rohtelegramme über mindestens
   zwei volle Perioden aufzeichnen; das Referenzgerät nicht parallel als
   zweiter Master betreiben.
2. Beim gleichzeitigen ersten Poll FC03/32–63 bzw. bei deaktivierten Kanälen
   nur die tatsächlich fälligen zusammenhängenden Adressen erwarten. Nach
   5 s darf der 60-s-Kanal keinen neuen Messzeitstempel erhalten.
3. Fühler abziehen: `0xFC18` nur am betroffenen Kanal als `unavailable`,
   andere Kanäle gültig. Fühler wieder anschließen; frische Werte prüfen.
4. Gruppenintervall ändern und Override erhalten; Override entfernen und
   Gruppenintervall übernehmen. Konfiguration neu laden und HA neu starten;
   Namen, Entity-IDs, Unique-IDs und die Schreibsperre vergleichen.
5. Gateway trennen/wieder verbinden; betroffene Kanäle unmittelbar unavailable,
   kontrollierte Neueinlesung auch für langsame Kanäle. Zwei Geräte an einem
   Gateway gleichzeitig betreiben und Antwortzeiten sowie Timeoutzähler prüfen.

Buslast und Simulatordaten stehen im [L-50-Prüfbericht](l50_test_report.md).

Für 4–20 mA sind 4 / 12 / 20 mA die drei Referenzpunkte. AI und AO haben
teilweise unterschiedliche Rohwertskalierung. Elektrische Referenzsignale nur
mit geeignetem Messgerät/Signalgeber und entsprechend Geräteunterlagen anlegen.
Negative Temperaturen bleiben bis zum eindeutigen Encoding-Nachweis gesperrt.

## Rückmeldung pro Fehler

Core-Version, Transportart, Gerät/Firmware, Unit-ID, Zeitpunkt, betroffener Kanal,
Rohwert, erwarteter Wert und anonymisierte Integrationsdiagnose angeben.
Keine Passwörter oder Zugriffstoken erforderlich. Einen erfolgreichen Test nicht
aus einem einzelnen plausiblen Wert ableiten.

## Getrennte spätere Schreibabnahme

Noch nicht mit dieser Beta möglich. Voraussetzungen: Busy-Retry nachweislich
ausgeschlossen, 2-s-Frist am tatsächlichen Sendezeitpunkt gewährleistet,
geeignete Hardwarevalidierung und begrenztes Readback-Verfahren implementiert.
Anschließend ausschließlich unbelastete Testausgänge, Wertebereichsgrenzen,
Mismatch, Kabelabbruch, Neustart/Recovery und fehlenden Sollwert-Replay prüfen.
Ein Register-Readback beweist keinen physischen Relaiskontakt.

## Rückbau

ComWinTop-Verbindungseintrag in HA entfernen, HA stoppen, ausschließlich den
Ordner `custom_components/comwintop` entfernen, HA starten. Keine physische
Ausgangsstellung wird dabei verändert oder zurückgesetzt.

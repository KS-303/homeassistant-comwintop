# Hardwareabnahme – lesende Beta 0.1.0b1

Stand: noch **nicht durchgeführt**. Softwaretests sind kein Hardwaretest.
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

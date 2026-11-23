# L-51a – manueller Wechsel der TM-32DS-Slave-ID (Spezifikation)

Stand: 16.11.2026. Dies beschreibt den künftigen Ablauf. **In der Beta gibt
es keine freigegebene Konfigurations-Schreibfunktion.** Baudrate und Parität
gehören zu L-51b und werden nicht geändert.

## Vorprüfung

1. Nur das ausdrücklich ausgewählte TM-32DS-Gerät und dessen bestehende
   Verbindung verwenden. Keine neue Socket-/RS485-Verbindung öffnen.
   Schreibauftrag und laufendes Polling über denselben gemeinsamen
   Bus-Transport koordinieren. Für den gesamten Vorgang einen anderen
   Master und parallele Parametrierung ausschließen.
2. Unter der vorhandenen Verbindung FC03/16 frisch lesen und exakt einen
   16-Bit-Wert verlangen. Das High-Byte muss der aktuellen HA-Unit-ID
   entsprechen. Rohwert vor jeder Bestätigung zusammen mit Zeitpunkt und
   alter Adresse festhalten. Bei widersprüchlichem Register: abbrechen.
3. Zieladresse als Integer 1–247 validieren (die Herstellerangabe 1–250
   erweitert den derzeitigen HA-Bereich nicht). Identische, 0, Broadcast-
   und außerhalb liegende Adressen ablehnen. Alle ComWinTop-Subentries am
   Gateway sowie bekannte andere HA-Modbus-Teilnehmer auf Konflikte prüfen.
4. Zieladresse auf demselben Bus lesend abfragen. Jede plausible Antwort
   sperrt die Änderung. **Keine Antwort beweist keine Adressfreiheit**:
   in diesem Fall nur nach bestätigter physischer Isolation des zu
   parametrierenden Geräts oder einer extern verifizierten vollständigen
   Bus-Topologie fortfahren. Bei unbekannten Slaves abbrechen.
5. Neuen Rohwert als `(ziel_id << 8) | (alter_rohwert & 0x00FF)` bilden.
   Jeden Low-Byte-Bitwert unverändert lassen; kein Baud-/Paritätsencode
   wird aus der Zweitdokumentation geraten. Alter/neuer Rohwert und
   gewünschte Buswirkung im Dialog anzeigen. Der Benutzer bestätigt
   diese *eine* Änderung ausdrücklich; die Bestätigung ist nur für den
   aktuellen gelesenen Rohwert und diese Zieladresse gültig.

## Einmaliger Änderungsversuch

6. Vor dem ersten Senden Rohwert/Zielkonflikt nochmals prüfen und die
   laufenden ComWinTop-Polls dieses Geräts für die Verifikation anhalten.
   Der gemeinsame Modbus-Manager muss die Busserialisierung auch gegenüber
   anderen Integrationen garantieren. Falls Exklusivität für die
   erforderliche Verifikationsphase nicht möglich ist: auf einem
   Multidrop-Bus sperren und isolierte Konfiguration verlangen.
7. Genau einen FC06 an die **alte** Unit-ID, Register 16, neuer Rohwert,
   mit öffentlich freigegebenem `retry=False` senden. Keine Wiederholung
   nach Busy, Timeout, Disconnect, Cancellation oder HA-Neustart. Kein
   persistierter Auftrag und kein automatischer Rückschreibversuch.

## Prüfung und Ergebnis

8. Bei erfolgreichem Reply: FC03/16 an der neuen ID frisch lesen und
   exakte Übereinstimmung verlangen. Zusätzlich einen dokumentierten
   Temperaturkanal (FC03/32) unter der neuen ID frisch lesen. Danach die
   alte ID vorsichtig auf mögliche andere Teilnehmer prüfen; eine Antwort
   darf nicht als zweites Gerät derselben Identität fehlinterpretiert
   werden. Bei unerwarteten Antworten **unbestätigt** lassen.
9. Nur nach konsistenter neuer Register- und Temperaturantwort und
   konfliktfreier alter Adresse die vorhandene HA-Subentry auf die neue
   Unit-ID aktualisieren und reloaden. `device_uid`, Kanalnamen,
   Entity-IDs/Unique-IDs, Intervalle und Konfiguration bleiben gleich.
   Die Antwort `0x0204` allein belegt keine korrekte physische Identität;
   der Vorgang braucht die zuvor isoliert bestätigte Bustopologie.
10. Bei Timeout, Busy, Verbindungsabbruch, HA-Neustart oder mehrdeutiger
    Verifikation: Zustand **„Änderung unbestätigt“** dokumentieren, alten
    HA-Eintrag nicht automatisch umstellen, keine erneute Übertragung.
    Nach Wiederverbindung alte **und** neue ID ausschließlich lesend
    prüfen. Ein späterer manueller Abgleich ist ein neuer, explizit
    bestätigter Vorgang. Bis dahin Sensorqualität konservativ behandeln.

Diese Schritte sind vor einem produktiven FC06 mit Simulatoren, HA-Restart,
isolierter TM-32DS-Hardware und gemeinsamem Bus zu prüfen. Ein einzelnes
Software-Telegramm beweist bei fehlendem Reply keine einzelne Geräteausführung.

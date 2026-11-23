# Bekannte Grenzen – ComWinTop 0.1.0b30

ComWinTop b30 ist eine **experimentelle Beta**, keine vollständig hardwarevalidierte Steuerung.

- **Schreiben:** Nur FC05 für das Profil **CWT MB-307D(II)-S** über **RTU-over-TCP** ist nach ausdrücklicher Freigabe pro Relais im Labor möglich. FC06/FC15/FC16, sonstige Geräte-/Transport-Schreibpfade und AO-Schreiben bleiben gesperrt.
- **Ausgänge:** Eine erfolgreiche FC01-Rücklesung bestätigt nur den gemeldeten Coil-Zustand, nicht die tatsächliche Relaisstellung oder angeschlossene Last. Bei Schreibfehlern und unklaren Antworten wird sicherheitsorientiert gesperrt. Keine automatische Wiederholung von FC05.
- **Buslast:** Wartende Schreibtransaktionen haben Priorität vor neuen ComWinTop-Polls. Laufende Reads und Anfragen anderer Integrationen können nicht unterbrochen werden; die 2-s-Sendefrist kann deshalb trotzdem ablaufen.
- **RTU:** Verspätete Gateway-Antworten können ohne Transaktions-ID mehrdeutig bleiben. Die ComWinTop-Sperre ist keine globale Quarantäne für andere Modbus-Master.
- **Sensorik:** Der TM-32DS-Fehlerwert `0xFC18` wird verworfen. Der Wert 85 °C ist als möglicher DS18B20-Startwert mehrdeutig. Negative Temperaturen erfordern eine ausdrückliche Kanaloption.
- **Hardwaretests:** Gemischte Kanalintervalle und längere Ausfall-/Wiederanlauftests sind noch offen. Das MB-308N-Profil ist nicht vollständig an realer Hardware abgenommen.

Keine Verwendung für sicherheitskritische Steuerungen oder unbeaufsichtigte Lastschaltungen. Der dokumentierte Teststand ersetzt keine reale Geräteabnahme.

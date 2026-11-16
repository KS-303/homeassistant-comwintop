# L-51: Stand und Freigabesperre

Stand 16.11.2026. Basis: L-50-Entwicklungsbranch auf 0.1.0b4. Kein Release.

Beim realen TM-32DS wurden an FC03/FC06 Register `0x0010` die Rohwerte
`0x0104` (Slave 1) und `0x0204` (Slave 2) bei 9600 8N1 beobachtet. Die
Adressänderung blieb nach Neustart erhalten. Die [Hersteller-Produktseite](https://store.comwintop.com/products/32-channels-18b20-rs485-modbus-output-temperature-acquisition-module)
nennt FC03 und FC06 für das Parameterregister, zeigt die Registerkarte aber
als Bild. Vollständige Codes, Masken und Speichersemantik sind damit für die
Software nicht zuverlässig belegt. Für MB308N fehlt ein abgesichertes
Kommunikationsprofil. Unbekannte Bits werden nicht interpretiert.

Die neue HA-Oberfläche liest TM-32DS-Register 16 über den vorhandenen
Unit-Client mit gemeinsamer Bussperre. Sie zeigt nur beim belegten Low-Byte
`0x04` Baudrate 9600, Parität N, 8 Datenbits und 1 Stoppbit. Andernfalls
erscheint „?“. MB308N und lokale Profile erhalten keine Konfigurations-Reads.
Es existiert **kein** L-51-Schreibpfad, kein Auftragsspeicher und kein
automatischer Wechsel von Slave-ID oder Gateway-Parametern.

Der benutzte HA-Modbus-Unterbau kapselt mehrere Backends. Ein einzelner
`write_register`-Aufruf ist noch kein Nachweis für genau eine physische
FC06-Übertragung unter Busy, Timeout, Abbruch und Wiederverbindung. Solange
dieser Nachweis je Transport fehlt, bleiben sämtliche L-51-Writes gesperrt.
Auch das bestehende freie „Name / Unit-Adresse“-Feld ändert nur den HA-Eintrag
nach Lesetest, **nicht** die Hardwareadresse.

Offen: vollständige Originalregisterkarte, dokumentierte Bitmasken je Modell,
prüfbare Adressfreiheit, atomare Koordination mit Polling, explizite
Bestätigung, einmalige Write-Übertragung, Verifikation am neuen Busparameter,
unklarer Zustand und Wiederherstellungsanleitung. Erst danach ist eine
Schreibfunktion samt Hardware- und Simulatortests denkbar.

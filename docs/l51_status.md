# L-51: Stand und Freigabesperre

## Aufteilung

- **L-51a – Slave-ID:** Die reine Berechnung ersetzt ausschließlich das
  High-Byte von Register 16 und erhält alle acht Low-Byte-Bits. Sie verwirft
  ungültige IDs, einen abweichenden gelesenen Istwert und bereits im HA-Eintrag
  vergebene IDs. Adressfreiheit auf dem gesamten Bus bleibt ungeklärt. Der
  Berechnungshelfer löst keinen Schreibvorgang aus.
- **L-51b – Baudrate/Parität:** separat; keine Änderung am Low-Byte, an der
  Verbindung oder am Gateway implementiert. Daten-/Stoppbits nicht als
  veränderbar angenommen.

Stand 16.11.2026. Basis: L-50-Entwicklungsbranch auf 0.1.0b4. Kein Release.

Beim realen TM-32DS wurden an FC03/FC06 Register `0x0010` die Rohwerte
`0x0104` (Slave 1) und `0x0204` (Slave 2) bei 9600 8N1 beobachtet. Die
Adressänderung blieb nach Neustart erhalten. Die [Hersteller-Produktseite](https://store.comwintop.com/products/32-channels-18b20-rs485-modbus-output-temperature-acquisition-module)
nennt FC03 und FC06 für das Parameterregister, zeigt die Registerkarte aber
als Bild. Vollständige Codes, Masken und Speichersemantik sind damit für die
Software nicht zuverlässig belegt. Für MB308N fehlt ein abgesichertes
Kommunikationsprofil. Unbekannte Bits werden nicht interpretiert.
Die [unabhängige Manuals+-Fassung](https://manuals.plus/asin/B0F4DN8JKK)
beschreibt High-Byte 1–250, Paritätsbits 4–3 und Baudbits 2–0
(einschließlich zweier 9600-Codes). Die originale Hersteller-Registergrafik
ist textlich nicht zugänglich und wurde noch nicht visuell gegen diese
Transkription geprüft. Für L-51a genügt der beobachtete High-Byte-Wechsel
bei unverändertem Low-Byte; L-51b darf aus der Zweitquelle nicht freigegeben
werden. HA unterstützt derzeit nur Unit-Adressen 1–247.

Die neue HA-Oberfläche liest TM-32DS-Register 16 über den vorhandenen
Unit-Client mit gemeinsamer Bussperre. Sie zeigt nur beim belegten Low-Byte
`0x04` Baudrate 9600, Parität N, 8 Datenbits und 1 Stoppbit. Andernfalls
erscheint „?“. MB308N und lokale Profile erhalten keine Konfigurations-Reads.
Es existiert **kein** L-51-Schreibpfad, kein Auftragsspeicher und kein
automatischer Wechsel von Slave-ID oder Gateway-Parametern.

## Reale Backend-Übertragung im Simulator

Mit Home Assistant Core 2026.11.0, `modbus-connection` 4.12.7 und
`tmodbus` 1.1.0 wurde ein einzelner direkter `write_register(16, 0x0204)`-
Aufruf am unabhängigen TCP- und RTU-over-TCP-Wire-Simulator beobachtet.
Bei einer Busy-Exception (Code 6) kamen **mindestens zwei FC06-Telegramme**
je Aufruf an. Damit scheitert das zwingende Kriterium „höchstens eine
physische Schreibübertragung“. `retry_never` der Response-Strategie genügt
nicht: `tmodbus` kombiniert sie mit `retry_on_device_busy=True` (Standard).
Dieser Befund ist ein Simulatornachweis, kein Test am CWT.

Bei stiller Antwort und Verbindungsabbruch beobachtete der Test jeweils ein
FC06-Telegramm; nach erneutem lesenden Zugriff wurde kein alter Schreibauftrag
ausgeführt. Ein fehlender Reply kann dennoch bedeuten, dass das Gerät die
Änderung bereits ausgeführt hat. Daher ist bei Timeout der Zustand unbestätigt
und ein automatisches Wiederholen oder Zurückschreiben verboten. Ein separater
HA-Flow-Test mit Busy, Timeout und Abbruch prüft Rückkehr zum lesenden Betrieb
ohne FC06. Neustart und reale Busübertragung sind nicht hardwarevalidiert.
Die gesamte Regression einschließlich L-50: 144 Tests bestanden, 92 %
Statement-Abdeckung; Ruff und Paketprüfung erfolgreich.

Technisch benötigt L-51a einen **öffentlichen, pro Schreibauftrag garantierten
No-Retry-Pfad** im gemeinsamen HA-Modbus-Manager, der Busy-, Response-,
Timeout- und Reconnect-Retries für genau diesen FC06-Befehl deaktiviert und
dieselbe Bus-Serialisierung nutzt. Alternativ muss der Upstream ein geprüftes
API für genau eine physische Übertragung bereitstellen. Eine private
Client-Manipulation oder eine zweite Verbindung zum selben Bus scheiden aus.
Erst nach dieser Änderung wären Vorprüfung, Adresskonflikterkennung,
explizite Bestätigung und Verifikation vor Aktualisierung des HA-Eintrags
implementierbar.

Der benutzte HA-Modbus-Unterbau kapselt mehrere Backends. Ein einzelner
`write_register`-Aufruf ist noch kein Nachweis für genau eine physische
FC06-Übertragung unter Busy, Timeout, Abbruch und Wiederverbindung; unter
Busy ist das Gegenteil tatsächlich beobachtet worden. Daher bleiben
sämtliche L-51-Writes gesperrt.
Auch das bestehende freie „Name / Unit-Adresse“-Feld ändert nur den HA-Eintrag
nach Lesetest, **nicht** die Hardwareadresse.

Offen: vollständige Originalregisterkarte, dokumentierte Bitmasken je Modell,
prüfbare Adressfreiheit, atomare Koordination mit Polling, explizite
Bestätigung, einmalige Write-Übertragung, Verifikation am neuen Busparameter,
unklarer Zustand und Wiederherstellungsanleitung. Erst danach ist eine
Schreibfunktion samt Hardware- und Simulatortests denkbar.

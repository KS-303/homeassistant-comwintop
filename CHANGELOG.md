# Änderungen

## L-51 (Draft; Konfigurationsschreiben gesperrt)

- Lesende Anzeige des TM-32DS-Kommunikationsregisters 16 unter gemeinsamer
  Bussperre; nur real bestätigte 9600/N/8/1-Kodierung `0x04` dargestellt.
- MB308N und unbekannte Codes bleiben ohne Schreibfunktion; keine
  Kommunikationseinstellungen, Ausgänge oder Entity-IDs geändert.

## L-50 (Entwicklungsbranch auf Basis 0.1.0b4; kein Release)

- Kanalbezogene Abfrageintervalle mit optionalem Override; vorhandene
  Gruppenintervalle und gespeicherte Geräteidentitäten bleiben erhalten.
- Fällige, benachbarte Register werden zusammen gelesen. Registerausnahmen
  werden begrenzt aufgeteilt, damit ein fehlerhafter Kanal die anderen nicht sperrt.
- Kanalbezogene Stale-Fristen, kontrollierte Neueinlesung nach Verbindungsabbruch
  und erweiterte anonymisierte Diagnose; keine neuen Schreibpfade.
- TCP- und RTU-Simulatortests sowie reproduzierbarer Buslastvergleich ergänzt.

## 0.1.0b4 (HA-Oberfläche)

- Verbindungsart, Parität, Kanäle, Signalbereich und Anzeigeformat erhalten
  sichtbare Beschriftungen direkt im Auswahlfeld. Technische Werte bleiben
  intern unverändert, bestehende Verbindungen und Gerätekennungen ebenfalls.

## 0.1.0b3 (lokaler Entwicklungszweig)

- Deklarative, lokal gespeicherte Geräteprofile für bereits geprüfte Lesemethoden
  und Decoder; keine Schreibmethoden oder frei programmierbaren Formeln.
- Registervorschau im Einrichtungsdialog für neue lokale Modelle.
- Fehlerhafte Profile fallen auf die letzte validierte Fassung zurück; eine
  vorherige gültige Version wird für manuelle Rücknahme gesichert.

## 0.1.0b2 (Vorbereitung)

Ausgeschriebene, übersetzte Kanal- und Auswahlbezeichnungen. Ein Icon mit
Hausmotiv, Signalwegen und KS-303 liegt im Integrationsordner. Entitäts- und
Gerätekennungen bleiben stabil. Die Hardwareabnahme aus 0.1.0b1 steht noch aus;
Schreibfunktionen bleiben technisch gesperrt.

## 0.1.0b1

Erste lesende Beta für HA Core 2026.11.0. Vier Transportvarianten,
TM-32DS-/MB308N-Profile, UI-Einrichtung, Kanaloptionen, Datenqualität und Diagnose.
Pflichtenheft v0.5 mit den anschließenden Entscheidungen zu v0.6 konsolidiert.
Schreib-Engine isoliert testbar; produktive Ausgänge wegen offener
Transport-/Hardware-Nachweise technisch nicht angelegt.

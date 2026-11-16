# Änderungen

## 0.1.0b8 (getrennte Kommunikationsfelder und Diagnose, Laborstand)

- TM-32DS-Kommunikation über Home Assistant als **acht einzeln beschriftete, echte schreibgeschützte Felder**: Geräte-ID, konfigurierte HA-ID, Register-16-Rohwert, Baudrate, Parität, Datenbits, Stoppbits und Lesestatus. Der rohe Inhalt wird nicht mehr als editierbarer Textblock dargestellt.
- Beim Hinzufügen und Bearbeiten eines Geräts wird die Modbus-Adresse als Zahlen-Eingabefeld (`1–247`) statt als Schieberegler angezeigt.
- Neue Diagnose-Entität `Kommunikationsregister 16` nur beim TM-32DS: Zustand ist der letzte erfolgreich gelesene Rohwert, z. B. `0x0204`. Attribute: Geräte-/HA-Adresse, Baudrate, Parität, Datenbits, Stoppbits und Lesestatus.
- Alle Diagnoseattribute stammen aus **einer gemeinsamen FC03-Lesung**; kein Modbus-Request pro Entity. Initiales Lesen ca. fünf Sekunden nach Start, danach etwa alle fünf Minuten und beim Öffnen des Konfigurationsdialogs.
- Nach Lesefehlern zeigt die Diagnoseentität `unavailable` und behält keinen scheinbar gültigen alten Registerwert bei.
- Die separate experimentelle TM-32DS-Laboradressänderung aus b6/b7 bleibt bestehen. Keine produktiven DO-/AO-Schreibfunktionen und keine neue Serial-Parametrierung. Keine Änderungen an `main`.

## 0.1.0b7 (HA-Dialog-Reparatur, Labor, kein Release)

- Fehler aus dem realen HA-2026.11-UI-Video korrigiert: Die Kommunikationsdaten werden zusätzlich als sichtbarer Textfeldwert ausgegeben, selbst wenn HA den Beschreibungstext nicht lädt.
- Experimentelle TM-32DS-Adressänderung nutzt ein Zahleneingabefeld statt 247er-Schieberegler. Ein sichtbarer Warnhinweis und die zweite Bestätigung enthalten Adressen und Registerrohwerte auch bei fehlender Beschreibungstranslation.
- Deutsche/englische Übersetzungsschlüssel und Tests erweitert; nur eine physisch isolierte TM-32DS-Slave-ID-Änderung bleibt als Schreib-Laborversuch erlaubt.
- Kein produktives FC06-No-Retry und keine DO-/AO-Ausgangsschreibfunktion. Die 0.1.0b6-Testbasis bleibt unverändert; b7 wird separat überprüft.

## 0.1.0b6 (TM-32DS-FC06-Labortest, nicht freigegeben)

- Über HA ist eine **experimentelle Änderung der TM-32DS-Slave-ID** auf einem ausdrücklich bestätigten, physisch isolierten Ein-Geräte-Bus testbar.
- Zwei Bestätigungsstufen; FC03/Register 16 vor und unmittelbar vor dem Schreiben lesen; Ziel-ID vorab lesen; High-Byte berechnen, Low-Byte unverändert erhalten; anschließend neue ID und Kanal 1 lesend prüfen; bestehende HA-Subentry nur bei konsistenter Verifikation übernehmen.
- **Keine No-Retry-Garantie:** Der eingesetzte HA-Modbus-Transport kann bei Busy denselben FC06-Schreibbefehl mehrfach übertragen. Der Testdialog benennt dieses Risiko; er darf nur mit physisch isoliertem TM-32DS verwendet werden.
- Keine Baudraten-/Paritätsänderung und **keine produktiven DO-/AO-Schreibbefehle**.
- HA-Simulator-Regressionen für fehlende Bestätigung, Abbruch, veralteten Rohwert und erfolgreiche Adressänderung; echte Hardwareabnahme ausstehend.
- `0.1.0b6` ist ein Labor-Installationspaket, keine automatische GitHub-Veröffentlichung; der letzte formelle Release bleibt `v0.1.0b1`.

## 0.1.0b5 (HA-Testpaket, Draft; kein Release)

- L-50 mit individuellen Kanalintervallen und blockoptimiertem Polling sowie
  die lesende L-51-Registeranzeige auf der b4-Basis als Testpaket gebündelt.
- Repository-Dokumentation, Vorlagen und isolierte Upstream-Test-CI liegen
  im Entwicklungszweig. Keine Upstream-Patches im Installationsarchiv.
- Versionsangaben in Manifest, Konstanten und Projektmetadaten angeglichen.
- Produktive Modbus-Schreibfunktionen bleiben technisch gesperrt. Gemischte
  L-50-Intervalle und MB308N sind weiterhin nicht real abgenommen.

## L-51a-Untersuchung (Draft, Writes weiterhin gesperrt)

- Adresse im High-Byte unter Erhalt sämtlicher Low-Byte-Bits rein rechnerisch
  vorbereitet; Bereichs- und bekannte Konfliktprüfung ergänzt.
- Ein FC06-Aufruf des vorhandenen Backends führte bei Busy im TCP- und
  RTU-over-TCP-Simulator zu mehreren Telegrammen. Timeout, Abbruch und
  Wiederanlauf separat geprüft. Deshalb keine Schreibfreigabe.
- Baudrate/Parität als L-51b abgegrenzt; keine Änderung am Gateway.

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

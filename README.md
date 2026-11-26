# ComWinTop für Home Assistant

**Lokale Modbus-I/O-Integration für CWT-Geräte – ohne Cloud und ohne Register-YAML für die integrierten Modelle.**

**Aktuelle Version:** `0.1.0b31` (Beta) · **Home Assistant:** ab 2026.11

## Unterstützte Geräte und Register

Die Adressen sind **nullbasiert**; FC bezeichnet den Modbus-Funktionscode. Die Integration verwendet diese Zuordnung automatisch.

| Gerät | Funktion | Adresse | FC |
| --- | --- | --- | --- |
| **TM-32DS** | 32 DS18B20-Temperaturen | 32–63 | 03 |
| | Kommunikationsparameter (lesend) | 16 | 03 |
| **MB-308N** | 8 Digitaleingänge (DI) | 0–7 | 02 |
| | 8 Relaiszustände (DO, lesend) | 0–7 | 01 |
| | 8 Analogeingänge (AI) | 0–7 | 04 |
| | 4 Analogausgänge (AO, Rücklesewerte) | 0–3 | 03 |
| **MB-307D(II)-S** | 8 Digitaleingänge (DI) | 0–7 | 02 |
| | 8 Relaiszustände (DO) | 0–7 | 01 |
| | 8 Analogeingänge (AI) | 50–57 | 03 |
| | Relais schalten – **nur Laborfreigabe** | 0–7 | 05 |

Die Analogskalierung des MB-307D(II)-S und die vollständige Hardwareabnahme des MB-308N stehen noch aus.

## Installation

1. Im **Home Assistant Marketplace** das Repository `https://github.com/KS-303/homeassistant-comwintop` als benutzerdefinierte **Integration** hinzufügen.
2. ComWinTop installieren (Beta `0.1.0b31` wählen) und Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → ComWinTop** öffnen.

## Verbindung einrichten

| Verbindungstyp in Home Assistant | Benötigte Einstellungen |
| --- | --- |
| **Modbus über Netzwerk** | IP/Hostname und TCP-Port |
| **Modbus über Netzwerk-Seriell-Gateway** | IP/Hostname und TCP-Port eines Modbus-TCP-Gateways |
| **Transparente serielle Verbindung über Netzwerk** | IP/Hostname, TCP-Port und serielle RS485-Parameter (RTU-over-TCP) |
| **Direkte serielle Verbindung** | Gerätepfad, z. B. `/dev/serial/by-id/…`, und serielle Parameter |

Für serielle Verbindungen sind **9600 Baud, 8 Datenbits, keine Parität und 1 Stoppbit (8N1)** voreingestellt. Die Einstellungen müssen zum Gerät und Gateway passen. Den **TCP-Port entsprechend der Gateway-Konfiguration** eingeben; es gibt keinen universellen Standardport für alle Betriebsarten.

Anschließend in der Verbindung **Gerät hinzufügen** wählen, Modell, Namen und **Modbus-Adresse (Unit-ID 1–247)** eingeben. Mehrere Geräte können eine Verbindung nutzen, benötigen dort aber unterschiedliche Unit-IDs.

## Kurzanleitung zur Bedienung

Unter **Einstellungen → Geräte & Dienste → ComWinTop → Gerät konfigurieren** stehen die Funktionen bereit:

- **Name / Modbus-Adresse:** Gerät benennen oder Unit-ID anpassen.
- **Kanal konfigurieren:** Kanal aktivieren, benennen und ein eigenes Abfrageintervall wählen; bei DI auch **NO/NC**, bei AI den Signalbereich (0–10 V, 0–5 V, 0–20 mA oder 4–20 mA) und die Anzeige/Skalierung.
- **Abfrageintervalle:** Intervalle je Kanalgruppe einstellen; neue Werte **5–3600 Sekunden**. Einzelkanäle können die Gruppeneinstellung übernehmen oder überschreiben.
- **TM-32DS:** Beim Hinzufügen werden angeschlossene Temperaturfühler lesend erkannt. Deaktivierte Kanäle lassen sich später manuell aktivieren; negative Temperaturen müssen pro Kanal erlaubt werden.
- **MB-307D(II)-S:** Unter **Relais-Schreibfreigaben (DO1–DO8)** Ausgänge einzeln freigeben. **FC05 ist nur über RTU-over-TCP als Laborfunktion verfügbar**; der gemeldete Zustand wird über FC01 rückgelesen.
- **Relais-Wiederanlauf:** Je DO unter Kanal konfigurieren AUS, EIN oder keine Zustandsvorgabe (Standard) wählen. Nur freigegebene MB307D-Relais über RTU-over-TCP; bei einer RTU-Sperre erst nach bestätigter Reparatur. Kein Hardware-Watchdog.
- **Modbus-Kommunikation anzeigen:** Beim TM-32DS die Kommunikationsparameter und Register 16 lesend prüfen.

ComWinTop stellt Messwerte, Zustände und Diagnoseinformationen als Home-Assistant-Entitäten bereit. Zusätzliche **lesende Geräteprofile** können unter `/config/comwintop/profiles/` abgelegt werden.

## Beta-Hinweise

b31 ist eine **Testversion**. Relaisbefehle sind ausschließlich im beschriebenen Laborumfang freigegeben; andere Schreibfunktionen bleiben gesperrt. Eine bestätigte Rücklesung beweist keine tatsächliche Kontaktstellung. **Nicht für sicherheitskritische Steuerungen oder unbeaufsichtigte Lastschaltungen verwenden.**

[Beta-Release](https://github.com/KS-303/homeassistant-comwintop/releases/tag/v0.1.0b31) · [Änderungen](CHANGELOG.md) · [Bekannte Grenzen](docs/known_limits.md) · [Fehler melden](https://github.com/KS-303/homeassistant-comwintop/issues)

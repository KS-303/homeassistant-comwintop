# ComWinTop

**Lokale Modbus-Integration für Home Assistant** – CWT-I/O-Geräte ohne Cloud anbinden.

**Beta 0.1.0b30** · Home Assistant 2026.11 oder neuer

## Unterstützte Geräte

| Modell | Funktionen |
| --- | --- |
| **CWT TM-32DS** | 32 DS18B20-Temperaturkanäle |
| **CWT MB-308N** | 8 DI, 8 AI sowie DO-/AO-Rücklesewerte |
| **CWT MB-307D(II)-S** | 8 DI, 8 DO und 8 AI; begrenzter FC05-Labortest |

## Funktionen

- Modbus TCP, RTU-over-TCP, TCP/RTU-Gateway und USB-RS485
- Mehrere Geräte, individuell konfigurierbare Kanäle und Abfrageintervalle
- Geräte- und Kommunikationsdiagnose mit Fehlerüberwachung
- Lokale Geräteprofile; Einrichtung auf Deutsch und Englisch
- **Experimentell:** einzeln freizugebende FC05-Relaisbefehle für MB-307D(II)-S über RTU-over-TCP mit Rückleseprüfung

## Installation

1. In **Home Assistant → Marketplace** dieses Repository als benutzerdefinierte Integration hinzufügen: `https://github.com/KS-303/homeassistant-comwintop`
2. Beta-Version auswählen und installieren.
3. Home Assistant neu starten.
4. Unter **Einstellungen → Geräte & Dienste** ComWinTop hinzufügen und Geräte konfigurieren.

## Beta-Status

Die Integration befindet sich in der Hardwareerprobung. **FC05-Schreibzugriffe sind ausschließlich für das angegebene MB-307D(II)-S-Profil und RTU-over-TCP als ausdrücklich freizugebende Laborfunktion verfügbar.** Andere Schreibfunktionen bleiben gesperrt. Schaltbefehle können bei Busstörungen abgewiesen werden; der tatsächliche Relaiszustand ist separat zu prüfen. Nicht für sicherheitskritische Steuerungen einsetzen.

Unabhängiges Community-Projekt, keine offizielle Herstellerintegration.

[Änderungen](CHANGELOG.md) · [Bekannte Grenzen](docs/known_limits.md) · [Fehler melden](https://github.com/KS-303/homeassistant-comwintop/issues)

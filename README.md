# ComWinTop

**Lokale Modbus-Integration für Home Assistant** – CWT-I/O-Geräte ohne Cloud anbinden.

**Beta 0.1.0b24** · Home Assistant **2026.11 oder neuer** · **nur lesend**

## Unterstützte Geräte

| Gerät | Funktionen |
| --- | --- |
| **CWT TM-32DS** | 32 DS18B20-Temperaturkanäle, automatische Kanalerkennung |
| **CWT MB-308N** | 8 DI, 8 AI, Rücklesen von 8 DO und 4 AO |

## Funktionen

- Modbus TCP, RTU-over-TCP, TCP/RTU-Gateways und USB-RS485
- Individuelle Abfrageintervalle und Kanaleinstellungen
- Lokale Geräteprofile sowie deutsche und englische Einrichtung
- Kommunikationsüberwachung, Fehlerdiagnose und kontrollierte RTU-Wiederherstellung

## Installation

<!-- ha-marketplace:exclude-start -->
1. Im **Home Assistant Marketplace** dieses GitHub-Repository als benutzerdefinierte **Integration** hinzufügen: `https://github.com/KS-303/homeassistant-comwintop`
2. Die gewünschte Beta-Version auswählen und installieren. Für Vorabversionen die Pre-Release-Option aktivieren.
3. Home Assistant neu starten und unter **Einstellungen → Geräte & Dienste** ComWinTop hinzufügen.
<!-- ha-marketplace:exclude-end -->

## Beta-Hinweis

Diese Version ist für die Erprobung vorgesehen. **Schreibzugriffe und Ausgangsschaltungen sind in b24 gesperrt.** Die Hardwarevalidierung ist noch nicht abgeschlossen; insbesondere das MB-308N-Profil benötigt weitere Tests. Keine Verwendung für sicherheitskritische Anwendungen. ComWinTop ist ein unabhängiges Community-Projekt.

[Änderungen](CHANGELOG.md) · [Bekannte Grenzen](docs/known_limits.md) · [Fehler melden](https://github.com/KS-303/homeassistant-comwintop/issues)

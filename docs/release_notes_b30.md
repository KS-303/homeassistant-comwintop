# ComWinTop 0.1.0b30 – Beta

Lokale Modbus-Integration für Home Assistant 2026.11 oder neuer.

## Änderungen
- CWT TM-32DS, MB-308N und MB-307D(II)-S als Geräteprofile.
- Kanalbezogene Messwertabfrage, Kommunikationsdiagnose und RTU-Wiederherstellung.
- **MB-307D(II)-S (Labor):** FC05-Relaisbefehle über RTU-over-TCP mit Einzelversuch, ausdrücklicher Freigabe je Kanal und FC01-Rücklesung.
- b30: Schreibbefehle haben Vorrang vor wartenden ComWinTop-Leseabfragen; 2-s-Sendefrist bleibt bestehen.

## Hinweise
**Vorabversion – Hardwarevalidierung nicht abgeschlossen.** Die FC05-Funktion ist experimentell; nur ohne angeschlossene Lasten erproben. Andere Ausgangsschreibfunktionen sind nicht freigegeben. Kein Einsatz für sicherheitskritische Steuerungen. Ein Rücklesewert bestätigt nicht den tatsächlichen Kontaktzustand.

Nach Installation Home Assistant vollständig neu starten. Das Installationsarchiv und seine SHA-256-Prüfsumme sind als Assets beigefügt.

# Roadmap und offene Entscheidungen

| Thema | Nächster überprüfbarer Schritt | Blocker |
|---|---|---|
| L-50 | Mischintervalle, Frische und FC03-Buslast über Waveshare/TM-32DS messen | Reale HA-OS-Messung und 72-h-Test offen |
| L-51a | Upstream-Patches in den Herkunftsprojekten reviewen; nach offizieller Verfügbarkeit isolierten HA-Dialog mit Konfliktprüfung, Bestätigung, einmaligem FC06 und unbestätigtem Timeout implementieren | Produktiver HA-Unterbau ohne öffentliches No-Retry; Multidrop und Restart-Test |
| L-51b | Hersteller-Registergrafik bitgenau prüfen, Gateway- und Multidrop-Wechsel separat spezifizieren | Hardware- und Dokumentationsbeleg fehlt |
| MB308N | AI/DI/Readbacks samt Signalmodi und Fehlerfällen an echter Hardware abnehmen | Realtest und 72-h-Betrieb offen |
| DO/AO | Transport-No-Retry, 2-s-Frist direkt vor Senden, Grenzen, Readback und kein Sollwert-Replay unabhängig nachweisen | Produktive Writes gesperrt |
| Veröffentlichung/HACS | Lizenz, Privacy-Audit der gesamten Historie, Brands-Eintrag und HACS-Prüfungen | Separate Freigabe nötig |

72-h-TM-32DS/Waveshare- und MB308N-Abnahme bleiben bewusst sichtbar offen.
Neue Issues erst anlegen, wenn ein konkreter Testtermin oder ein klarer
Verantwortlicher vorhanden ist. Die vorhandenen vier Draft-PRs erfassen
bereits ihre Entwicklungsarbeit; keine Doppel-Issues erzeugen.

# L-50: TM-32DS/Waveshare – 72-Stunden-Messprotokoll

**Status: Vorlage, keine durchgeführte Abnahme.** Zugehörig zu [Hardware-Issue #7](https://github.com/KS-303/homeassistant-comwintop/issues/7) und [Testplan](ha_test_plan.md). Die Tests sind ausschließlich lesend. Kein L-51-FC06, kein DO/AO-Schreiben.

## Testkopf (vor Beginn ausfüllen)

| Feld | Eintrag |
|---|---|
| HA Core / HA OS | |
| ComWinTop-Version und Git-Commit | |
| CWT-Modell / Firmware, soweit bekannt | |
| Gatewaytyp und Übertragungsart (TCP, TCP→RTU, transparentes RTU-TCP) | |
| Serielle Einstellungen ohne IP/Hostnamen | |
| Slave-ID (ohne sonstige Topologiedaten) | |
| Anzahl angeschlossener DS18B20 und verwendete Kanalnummern | |
| Beginn / Ende mit Zeitzone | |
| Testperson / internes Protokollkennzeichen (nicht öffentlich personenbezogen) | |

Vor Beginn ein HA-Backup anlegen. Externen Modbus-Master wie Registerwerk während des HA-Tests trennen. Keine privaten IP-Adressen, WLAN-Zugangsdaten, Authentifizierungstoken, persönlichen Sensornamen oder vollständige HA-Logs im öffentlichen Issue veröffentlichen.

## Messkonfiguration

Eine kleine, nachvollziehbare Auswahl aktiver Temperaturkanäle verwenden, z. B. CH1–CH4 mit Gruppenintervall **15 s** und CH1 **5 s**, CH2 **10 s**, CH3 **30 s**, CH4 **60 s**. CH5–CH32 können deaktiviert bleiben; den tatsächlichen Aufbau dokumentieren. Dabei darf ein 5-s-Kanal die nicht fälligen Nachbarn nicht dauerhaft mit abfragen.

Die Software soll nach drei **effektiven** Kanalintervallen ohne gültige Probe den betreffenden Wert als nicht verfügbar behandeln. Das ist pro Kanal zu prüfen, nicht nur für die Gruppe.

## Protokolltabelle (echte Beobachtungen, keine Schätzwerte)

| Zeitpunkt | Testschritt / Störung | Soll | Ist (ohne private Daten) | Fehler-/Timeoutzähler | Ergebnis |
|---|---|---|---|---|---|
| T+0 | Neustart und Erstabfrage | Nur gültige neue Werte, stabile IDs | | | |
| T+5 min | 5/10/30/60-s-Kanäle vergleichen | Eigene Aktualisierungsabstände | | | |
| T+1 h | Blockzugriffe / Buslast | Nur fällige zusammenhängende Register | | | |
| T+24 h | Zwischenkontrolle | Keine ungeklärten Ausfälle | | | |
| T+48 h | Zwischenkontrolle | Keine ungeklärten Ausfälle | | | |
| T+72 h | Abschluss | Alle Zähler und Auffälligkeiten dokumentiert | | | |

**Zusätzliche gezielte Prüfungen, mit genauem Zeitpunkt:**

- Ein DS18B20 abziehen: der real beobachtete Rohcode `0xFC18` darf nur den betroffenen Messwert ungültig machen; danach Fühler wieder anschließen und neue Probe dokumentieren.
- Kurzzeitigen Gateway-Ausfall und Wiederverbindung auf einer sicheren Testinstallation prüfen: keine veralteten Temperaturen als aktuelle Messwerte ausgeben.
- Bei einem langsamen Kanal (z. B. 60 s) prüfen, dass seine Aktualisierungszeit nicht durch häufige CH1-Reads künstlich erneuert wird.
- Gruppenintervall ändern, individuelle Overrides erhalten, Override zurücksetzen, gespeicherte Einstellungen und IDs nach Integrations-Reload und HA-Neustart vergleichen.
- Bei zwei Slaves die gegenseitige Beeinflussung messen, **nur wenn** ein zweites Gerät mit eindeutiger Adresse tatsächlich verfügbar ist. Sonst als offen kennzeichnen.

## Nachweise und Auswertung

Erfasse die für den Test relevanten Modbus-Funktionscodes und Registerbereiche (ohne private Netzwerkadressen), Anzahl Lesezugriffe, tatsächliche Stichproben-Zeitabstände, Ausfallzeiten, Timeout-/Protokollfehler, Wiederanlaufzeiten und die Änderungen der individuellen Zähler. Die anonymisierte Home-Assistant-Integrationsdiagnose kann dafür genutzt werden. Vor öffentlicher Freigabe jedes Protokoll auf Identifikatoren prüfen.

| Kennzahl | Vorher | Nach 72 Stunden | Differenz / Bewertung |
|---|---|---|---|
| Erfolgreiche Antworten | | | |
| Timeouts | | | |
| Geräte-Exceptions | | | |
| Transportfehler | | | |
| Protokollfehler | | | |
| Unerwartete Fehler | | | |
| Wertfehler / Sensorcodes | | | |
| Längster beobachteter Ausfall | | | |
| Abweichungen von Soll-Pollintervallen | | | |

**Abnahmestatus:** `OFFEN` / `BESTANDEN` / `NICHT BESTANDEN` / `TEILWEISE GETESTET`

**Offene Einzelfälle:**

**Abweichungen und reproduzierbare Schritte:**

**Git-Commit, Testergebnis, Datum und Link auf anonymisierten Nachweis:**

Die 72-Stunden-Hardwareabnahme darf erst nach vollständiger Laufzeit und belastbarer Auswertung in [Issue #7](https://github.com/KS-303/homeassistant-comwintop/issues/7) als bestanden markiert werden. Simulator- und PTY-Tests sind kein Ersatz. L-51a, L-51b und DO/AO bleiben unabhängig hiervon gesperrt.

# Bekannte Grenzen und Releaseblocker (0.1.0b22)

**Nicht hardwarevalidiert.** Dieser Entwicklungsstand ist nur für einen
kontrollierten, isolierten und rein lesenden Laboraufbau gedacht.

- RTU-Antworten enthalten keine Transaktionsnummer. Auch nach 8 s Busruhe
  kann ein Gateway einen noch älteren Frame liefern. ComWinTop sperrt
  eigene Reads nach wiederholten Timeouts und Transportfehlern. Andere
  HA-Nutzer auf demselben physikalischen Bus sind nicht über den lokalen
  Guard geschützt. Erst eine gemeinsam genutzte Upstream-Quarantäne plus
  Gateway-Nachweis könnte die Zuordnung belastbar sichern.
- Die neue Repairs-Freigabe prüft bewusste Bestätigungen. Die Software
  erkennt nicht selbst, ob Gateway und angeschlossene RTU-Geräte physisch
  spannungsfrei waren oder ob Puffer leer sind.
- Bei normalen HA-Stops wird der geklärte Marker deaktiviert; bei
  unsicheren Sitzungen oder unclean Shutdown bleibt er aktiv.
- Während einer Kommunikationsstörung bleiben Werte höchstens bis
  3 × ihrem effektiven Abfrageintervall als verfügbar markiert.
  Ein plausibler, aber falsch zugeordneter RTU-Frame kann dadurch
  nicht automatisch erkannt werden.
- Vorzeichenbehaftete negative TM-32DS-Temperaturen sind opt-in und
  nicht durch Hardwaremessung bestätigt. 0xFC18 ist als abgezogener
  Fühler beobachtet; der Rohwert 850 ist mehrdeutig.
- MB308N-Register/Funktionscodes und die physikalischen DO/AO-Zustände
  sind noch nicht an echter Hardware validiert.
- Bei mehreren Geräten gelten die Abfrageintervalle je Kanal; ein
  globaler genauer Bus-Scheduler mit messbarer Drahtzeit fehlt.
- Reparatur- und Test-Logs können Geräte- oder Benutzerdaten enthalten.
  Nur anonymisierte Aggregationen öffentlich teilen.
- Schreibzugriffe FC05, FC06, FC15, FC16 sowie jede Anlagensteuerung
  bleiben vollständig gesperrt. Die experimentellen Upstream-Patches
  werden nicht automatisch installiert.
- Lizenzentscheidung und 24-/72-h-Laborbericht fehlen weiterhin.

Siehe [Hardwaretest-Vorlage](hardware_test_report_template.md),
[RTU-Untersuchung](rtu_timeout_solution.md) und [HACS-Update](../README.md).

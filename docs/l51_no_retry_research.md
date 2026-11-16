# L-51a: No-Retry-Pfad im gemeinsamen Modbus-Unterbau

Stand: 16.11.2026, separater Draft auf Basis von L-51-PR #2.
Produktionsschreiben bleiben gesperrt.

## Ursache in den installierten Versionen

Home Assistant Core 2026.11.0 gibt über `async_get_unit` denselben
`modbus-connection`-Client für denselben Endpoint aus. ComWinTop serialisiert
eigene Units zusätzlich mit einer Bussperre. `modbus-connection` 4.12.7
verwendet hier tmodbus 1.1.0 und übergibt `response_retry_strategy` mit
`retry_never` und `auto_reconnect=False`, aber nicht
`retry_on_device_busy=False`. tmodbus setzt diesen Parameter auf `True` und
kombiniert die Retry-Strategie mit `retry_if_exception_type(ServerDeviceBusyError)`.
Der `send_and_receive`-Loop kann den *gleichen Write-PDU* deshalb erneut
senden. Ein einzelner Python-Aufruf garantiert keine einzelne Übertragung.

## Kleinstmögliche öffentliche Ergänzung

Zwei getrennte [Patchentwürfe](../upstream_patches/README.md):

1. tmodbus: `retry: bool = True` bei `execute` und FC05/06/15/16, plus
   `send_and_receive_once` an `AsyncSmartTransport` unter derselben
   Kommunikationssperre. Der Einmalpfad ruft `_reconnect_send_and_receive`
   genau einmal auf; eine nach dem Send auftretende Exception wird nicht
   erneut gesendet. Das alternative API an der Basisklasse verweigert
   unbekannte Transportimplementierungen ausdrücklich.
2. modbus-connection: dasselbe optionale Keyword an den vier öffentlichen
   `ModbusUnit`-Methoden und beiden Backend-Adaptern. Das tmodbus-Backend
   reicht es weiter. pymodbus wird derzeit mit `retries=0` konstruiert;
   seine signaturkompatible Implementierung wurde separat über PTY geprüft.

Home Assistant muss keinen privaten Client freigeben, keine neue Verbindung
öffnen und keinen globalen Retry-Schalter umstellen. Das bestehende
`async_get_unit` liefert bereits das öffentliche `ModbusUnit`-Protokoll.
Andere Integrationen behalten ohne das neue Keyword das alte Verhalten,
einschließlich Busy-Retry; sie müssen nicht migrieren. Spätere Upstream-
Versionen benötigen eine explizite Mindestversion und HA-Abhängigkeitsprüfung.
Der Patch ist noch nicht von den Maintainers geprüft und keine nutzbare
Produktionsabhängigkeit.

## Wire-Prüfung des isolierten Prototyps

Bei `retry=False` wurden 26 Kombinationen durchlaufen: FC05, FC06, FC15,
FC16 über TCP; FC05/FC06 über RTU-over-TCP; jeweils normale Antwort,
Busy 06, Timeout, Abbruch. Pro Write kam exakt **ein** Write-Telegramm an.
Nach Fehlern löste ein normaler Read keine verspätete Write-Wiederholung
aus. Zwei zusätzliche Reads an verschiedenen Slaves konkurrierten mit
einem Write auf derselben Verbindung; der Telegrammtrace enthielt drei
serialisierte Zugriffe ohne doppelten Write. Ein 27. Versuch bestätigte,
dass der Legacy-Aufruf ohne `retry=False` bei Busy weiterhin wiederholt.
Das [Wire-Skript](../upstream_patches/wire_check.py) wurde mit isolierten,
gepatchten Kopien ausgeführt; in der unveränderten HA-Testumgebung bleiben
die produktiven Reads und L-50-Regression erhalten. Der HA-Reload-Test
belegt nur, dass die weiterhin lesende ComWinTop-Integration keinen
aufgeschobenen Write startet; ein echter HA-Neustart während eines FC06
ist **nicht** nachgewiesen.

Zusätzlich liefen **34 serielle PTY-Szenarien**: FC05/06/15/16 mit tmodbus
und pymodbus bei Normalantwort, Busy 06, Timeout und geschlossenem PTY.
Der unabhängige Parser prüfte CRC und die wirklich empfangenen Frames.
Jeder Write wurde einmal übertragen. Je zwei TCP- und PTY-Versuche brachen
einen bereits gesendeten FC06 per asyncio-Cancellation ab. Nach Schließen
und Neuöffnen der Verbindung kam kein alter Write nach. pymodbus meldete
Cancellation teilweise als `ModbusTimeoutError`; der Wire-Trace blieb
eindeutig. Ein tatsächlicher HA-Prozessneustart während eines unbestätigten
Write ist weiterhin **nicht** nachgewiesen.

## Zwei-Sekunden-Frist für DO/AO, nicht für L-51a

Der ComWinTop-WriteManager verwendet eine monotone Frist von zwei Sekunden
und einen `guard()`. `retry=False` reicht diesen Guard nicht zum tatsächlichen
Senden durch. Ein Check vor dem Aufruf kann während Lock-Wartezeit, Pacer,
Verbindungsaufbau oder Busruhe ablaufen. Benötigt wird ein öffentliches,
optionales `before_send` oder `expires_at`, das **unter dem gemeinsamen
Transportlock unmittelbar vor dem physischen Send** geprüft wird. Unbekannte
Backends müssen dabei fail-closed reagieren. Der hier vorliegende Patch
enthält diesen Hook noch nicht. Deadline-Tests mit belegtem Lock und
Connect-Verzögerung sind offen. Diese Frist gilt für spätere produktive
DO-/AO-Schaltbefehle und ist kein Blocker der manuellen L-51a-Parametrierung.
Deren [Vorprüfung und Bestätigung](l51a_address_change.md) sind getrennt.

## Offizielle Upstream-Repositories und Versionen

- `https://github.com/wlcrs/tmodbus`, Patchbasis **1.1.0**. Die
  `.github/CONTRIBUTING.md` verlangt vorherige Besprechung mit den
  Maintainers. Die AI-Richtlinie verlangt menschliches Verstehen und
  untersagt autonome Issues/PRs.
- `https://github.com/home-assistant-libs/modbus-connection`, Patchbasis
  **4.12.7**. AI-Richtlinie ebenso; `CLAUDE.md` verlangt bei öffentlicher
  API-Änderung README und Referenzdokumentation.
- HA Core **2026.11.0** pinnt `tmodbus==1.1.0`,
  `modbus-connection[tmodbus]==4.12.7` und `pymodbus==3.13.1` in
  `homeassistant/components/modbus/manifest.json`. L-51a benötigt
  *künftige* Releases beider geänderter Bibliotheken und eine HA-Version,
  die beide pinnt. Noch unveröffentlichte Versionsnummern dürfen nicht
  erfunden werden. Keine Änderung durch eine Custom-Integration erzwingen.

## Grenze und Freigabe

„Höchstens eine Übertragung durch diesen Softwaretransport“ bedeutet
**nicht** „genau eine Ausführung am entfernten Gerät“. Bei Timeout oder
Verbindungsabbruch kann das Gerät den Befehl bereits umgesetzt haben.
Modbus, TCP-Gateway und RS485 bieten hier keine End-to-End-Transaktion.
Nach unklarem Ausgang muss L-51a alte und neue Adresse lesend prüfen und
den Zustand als unbestätigt dokumentieren, ohne automatischen Retry oder
Rollback. Für DO/AO gilt dies ebenso; dort sind zusätzliche Hardware-
Interlocks und Zustandsverifikation nötig. Der API-Patch allein hebt keine
Beta-Schreibsperre auf.

Vor L-51a-Freigabe: Upstream-Merge/Releases beider Pakete, HA-Kompatibilität,
Wire-Tests einschließlich serieller PTY und pymodbus, tatsächlicher
HA-Neustart während unklarer Änderung, Buskonfliktprüfung, expliziter
Bestätigungsdialog, Leseverifikation an alter/neuer ID und isolierter
TM-32DS-Hardwaretest. Bis dahin bleibt `write_enabled=False`.
Die [Blocker](l51_blockers.md) für L-51a, L-51b und DO/AO sind getrennt.

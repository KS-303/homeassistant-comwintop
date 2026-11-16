# L-51a: No-Retry-Pfad im gemeinsamen Modbus-Unterbau

Stand: 16.11.2026, Draft auf L-51-PR #2. Produktionsschreiben bleiben gesperrt.

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
   seine signaturkompatible Implementierung benötigt eigene Wire-Tests.

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

# RTU-Timeout: Untersuchung und erforderliche Lösung

Ein Wire-Test mit dem tatsächlich verwendeten `modbus-connection 4.12.7` und
`tmodbus 1.1.0` sendet zwei FC03-Anfragen an dieselbe Slave-Adresse und
unterschiedliche Register mit gleicher Antwortlänge. Die erste Antwort wird
erst nach dem zweiten Request geliefert. Ohne ComWinTops Disconnect übernimmt
der Unterbau den alten Wert für den zweiten Request. Die RTU-Antwort enthält
keine Registeradresse und keine Transaktionsnummer. Der Test belegt das
Fehlverhalten; er ist kein Freigabetest. Im separaten Test wird ein verspätetes
Telegramm von Slave 1 nicht als Antwort von Slave 2 übernommen.

Ein bloßer Pacer von einer Sekunde ist keine Garantie, wenn ein Gateway ein
Telegramm länger zurückhält. Auch das Schließen eines Sockets belegt allein
nicht, dass das Gateway seine serielle Warteschlange geleert hat. Deshalb
bleibt die bisherige Disconnect-Strategie als bekannter Kompromiss bestehen;
sie garantiert weder korrekte Zuordnung noch ununterbrochenen Betrieb.

Eine belastbare Lösung benötigt einen öffentlichen, gemeinsam genutzten
Transportzustand: nach Timeout im gleichen Serialisierungsbereich neue
Anfragen pausieren, eingehende Bytes beobachten und verwerfen, die Ruhezeit
nach jedem Byte neu beginnen lassen und ein begrenztes Wartebudget angeben.
Wird dieses Budget überschritten oder kann die maximale Verzögerung des
Gateways nicht begrenzt werden, muss der betroffene Bus als nicht sicher
synchronisiert gelten und Diagnose/Recovery auslösen. Fremde HA-Modbus-Nutzer
müssen denselben Zustand teilen. Ein bloßer lokaler Sleep oder ein zweiter
Socket genügt nicht. Die Grenze für die maximale Verzögerung muss am echten
Gateway belegt oder vom Hersteller zugesichert werden.

Ein Upstream-Entwurf muss neben RTU-over-TCP auch echtes serielles PTY,
fragmentierte verspätete Antworten, gleiche und verschiedene Slave-Adressen,
gleiche und verschiedene Funktionscodes, mehrere Nutzer derselben HA-
Verbindung, Wiederverbindung, Abbruch und Dauerlast am Draht testen. Das
Fehlerverhalten im Test muss vor einem Produktivwechsel bestehen bleiben;
danach muss der Test nachweisen, dass keine alte Antwort als neuer Messwert
erscheint. Das ist noch nicht implementiert und kein Hardware-Nachweis.

## Experimenteller tmodbus-Prototyp

`upstream_patches/tmodbus-1.1.0-rtu-quarantine-experiment.patch` ergänzt auf
einer **isolierten Kopie** des RTU-Protokolls eine optionale busweite Sperre.
Sie startet nach einem Timeout oder einer Abbruchanforderung nach dem Senden,
verwirft eintreffende Bytes, wartet die angenommene maximale Verspätung und
danach die erforderliche Ruhezeit ab. Weitere Anfragen warten am selben
Protokoll-Lock; andauernde Bytes über die Warteobergrenze hinaus sperren die
Anfrage. Ohne aktivierte Einstellung bleibt das bisherige Verhalten erhalten.
Der Test `python scripts/test_rtu_quarantine_experiment.py` kopiert die lokal
installierte Version 1.1.0 temporär, wendet den Patch dort an und prüft
Telegramme über RTU-over-TCP und eine serielle PTY. Er verändert die
installierte Bibliothek nicht.

Der Stand ist **noch kein verwendbarer HA-Patch**: Die Einstellung ist bisher
nur am Protokoll verfügbar, noch nicht an der öffentlichen gemeinsamen
`modbus-connection`-Unit. Ein neuer Protokollzustand nach Disconnect oder
HA-Neustart übernimmt die laufende Sperre nicht. Insbesondere die Behandlung
dieser Fälle muss in einer langlebigen gemeinsamen Verbindung erfolgen und
getestet werden, bevor ComWinTop den Reset ersetzen darf. Eine unzureichende
Annahme für `max_late` kann weiterhin falsche Zuordnungen erlauben. Die
Testwerte 0,20/0,08/0,35 s sind Simulatordaten und keine Hardwareempfehlung.


## b20 – zusätzlicher ComWinTop-Leseschutz (keine Upstream-Freigabe)

Eine RTU-Antwort besitzt keine Transaktionsnummer. Eine beliebig lange
verzögerte Antwort ist nicht nachweisbar frisch. Die in b20 integrierte
`RtuSessionGuard`-Schicht stellt daher **keinen automatischen Resync** in
Aussicht, sondern stoppt ComWinTop-Leseanforderungen nach Timeout,
Protokollfehler, Abbruch oder Verbindungsverlust. Alle Koordinatoren
derselben ComWinTop-Verbindung werden sofort ungültig und OFFLINE.
Die Kommunikation wird auch bei Reconnect nicht stillschweigend freigegeben.

Die Guard-Schicht speichert vor dem ersten Lesezugriff ein aktives
Sitzungskennzeichen in der HA-Storage-Datenbank. Nur ein sauberer Unload
ohne unklaren Request deaktiviert es. Ein ungeplanter Prozessabbruch
erfordert dagegen eine kontrollierte manuelle Wiederinbetriebnahme;
ein automatischer Neustart darf die Sperre nicht umgehen.
Die Sperre wird nicht durch ein gewöhnliches Reload nach Fehler gelöscht.

**Wichtige Grenze:** Dies sperrt nur *ComWinTop-eigene* Aufrufe.
Andere Integrationen, die den öffentlichen HA-Modbus-Manager auf derselben
Leitung nutzen, werden dadurch nicht gesperrt. Für verbindliche
systemweite Sicherheit bleibt eine öffentlich unterstützte,
gemeinsam genutzte Upstream-Sperre bzw. Transport-Eigentümerschaft
erforderlich. Auch Konfigurations-Probes verwenden noch eine temporäre Unit.
Deshalb ist b20 ein Entwicklungsstand und **kein freigegebenes**
Test-/Installationspaket für einen unkontrollierten Multidrop-Bus.

### Physische Freigabebedingungen

1. Jeder physische RS485-Bus ist eindeutig einem HA-Modbus-Verbindungsmanager
   zugeordnet; weder zweiter Master noch Alias-Verbindungen dürfen still
   an der Bus-Sperre vorbeigehen.
2. Nach einer unsicheren Antwort Bus und Gateway physisch vollständig
   spannungsfrei zurücksetzen und die Geräte-/Gateway-Ausgangspuffer nach
   Herstellerangabe als leer nachweisen; andernfalls **keine Wiederfreigabe**.
3. HA vor Eingriffen in die lokalen Sitzungsmarker vollständig herunterfahren.
   Ein Zurücksetzen der Marker ist *kein* Ersatz für den physisch belegten Reset.
   Der Ablauf muss als eigener, bestätigter Wartungsdialog geprüft werden;
   bis dahin keine automatische Freigabe.
4. Verspätete/fragmentierte Frames, Busunterbrechung, Neustart, weitere
   Teilnehmer und fremde HA-Nutzer am Draht erfassen. Die verschärfte
   Python-Warnungsprüfung und 72-h-Hardware-Dauerprüfung nachholen.
5. DO/AO, FC05/06/15/16 und Anlagensteuerung bleiben gesperrt.

Ein positives CI-Ergebnis beweist nur die von der CI ausgeführten Fälle,
nicht die maximale physische Gateway-Verzögerung.

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

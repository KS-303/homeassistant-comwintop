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

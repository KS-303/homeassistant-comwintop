# Sicherheitsmeldungen und Entwicklungsgrenzen

Produktive Modbus-Schreibfunktionen sind gesperrt. Bitte keine Zugangsdaten,
private Netzwerkadressen oder unveränderten HA-Diagnoseexporte in Issues
oder Pull Requests posten. Für eine vertrauliche Schwachstelle zunächst den
[Sicherheitsbereich des Repositorys](https://github.com/KS-303/homeassistant-comwintop/security)
prüfen. GitHubs private Schwachstellenmeldung ist aktiviert.

Unterstützter veröffentlichter Stand: `v0.1.0b1`, rein lesende Beta.
Die b22-Entwicklungsversion ist ein ausdrücklich **nicht freigegebener
Teststand**. Keine Softwareprüfung ersetzt die reale
Modbus-/Gateway-Abnahme. Veraltete RTU-Antworten können nicht ohne
Upstream-Quarantäne zuverlässig einer neuen Anfrage zugeordnet werden.

Eine RTU-Sicherheitssperre darf nur über den von Home Assistant
angezeigten Reparaturdialog **nach drei Hardwareprüfungen** gelöst werden.
Das Löschen eines HA-Integrationseintrags darf den Marker nicht löschen.
Nur die eigene, nachweislich saubere HA-Abschaltung löst eine
ungeklärte aktive Sitzung gerade **nicht** auf.

Eine Lizenzdatei fehlt bis zur ausdrücklichen Entscheidung des
Rechteinhabers. Keine implizite öffentliche Nachnutzungslizenz.

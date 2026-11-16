# Repository-Sicherheit und Administrationsschritte

Stand 16.11.2026 nach der vom Inhaber vorgenommenen öffentlichen Freigabe.
`main` ist nun mit einer klassischen GitHub-Branchregel geschützt (GitHub
meldet `protected: true`). Erforderlich sind ein Pull Request, der erfolgreiche
Statuscheck `test` von GitHub Actions und das Auflösen offener Review-Gespräche.
Die Regel gilt auch für Administratoren; Force-Push und Branch-Löschung sind
nicht erlaubt. Eine fremde Zustimmung ist im derzeitigen Ein-Maintainer-
Repository nicht vorgeschrieben, damit spätere geprüfte PRs integrierbar
bleiben. Kein PR wurde durch diese Regel gemergt.

Actions verwenden `contents: read`, SHA-gepinnte Drittaktionen und
`persist-credentials: false`. Der Produktjob nutzt unveränderte
Abhängigkeiten. Der zweite Job kopiert gepinnte Bibliotheken ausschließlich
in ein temporäres Verzeichnis, patcht sie dort und führt Netzwerk-/PTY-
Wire-Tests aus. Er installiert keine Patches in Home Assistant. Direkte
Test-Abhängigkeiten sind versionsgenau gepinnt; transitiver pip-Resolve ist
noch nicht vollständig gelockt. Dependabot schlägt künftig pip- und
Actions-Updates als PR vor; Änderungen bleiben reviewpflichtig.
Der Standard-`GITHUB_TOKEN` besitzt nur Leserechte; Actions dürfen keine PRs
erstellen oder genehmigen. SHA-Pinning ist als Repository-Regel eingeschaltet.
Workflows aus externen Fork-PRs benötigen vor der Ausführung eine Freigabe.

`scripts/check_package.py` prüft die leere Schreibfreigabe über AST und
Produktdateien. `scripts/build_package.py` nimmt nur Python, JSON und
Brand-PNG aus `custom_components/comwintop/` in das ZIP und verifiziert
alle Bytes. Keine Logs, Profile, Testquellen oder Patches ins Paket.
Vor jedem neuen Release Commits, Tags, Assets und Diagnose-Dateien nochmals
auf Tokens, private IPs und identifizierende Metadaten prüfen. Vor der
Sichtbarkeitsänderung wurden alle 13 erreichbaren Commits und 163 einzigartige
Datei-Versionen sowie PR-/Issue-Texte gesichtet. Beide Release-Asset-Digests
entsprechen exakt einem Neubau aus dem b1-Commit. Das Screening ist keine
forensische Garantie für externe Kopien oder zukünftige Beiträge.

## Aktive Sicherheits- und Projektfunktionen

- Dependency Graph, Dependabot Alerts und Security Updates waren aktiv.
  Dependabot-Versionierungs-PRs sind auf diesem Entwicklungsbranch per
  `.github/dependabot.yml` vorbereitet und gelten erst nach Integration in
  den Default-Branch; keine automatische Zusammenführung.
- Private Vulnerability Reporting und Secret-Scanning-Alerts wurden aktiviert.
  Push Protection wird in der Oberfläche als **aus** angezeigt; der Schalter
  ließ sich in dieser Sitzung nicht aktivieren. Keine Schutzwirkung behaupten.
- Bestehende GitHub-Labels `bug` und `enhancement` werden weiterverwendet.
  Ergänzt wurden `hardware-test`, `blocked` und `security-review`. Die beiden
  Hardware-Issues und die fünf Draft-PRs wurden passend gekennzeichnet.
- Eine verpflichtende Zustimmung durch eine zweite Person kann später bei
  einem zusätzlichen Maintainer aktiviert werden. Sie ist derzeit **offen**.
  Vor jeder manuellen Release-Freigabe die
  [Release-Matrix](test_release_matrix.md) durchgehen.

Keine Zugangsdaten in Issues posten. Für vertrauliche Fehler GitHubs privaten
Meldeweg nutzen, falls eingerichtet, andernfalls über das GitHub-Profil des
Maintainers zunächst einen privaten Kontaktweg abstimmen.

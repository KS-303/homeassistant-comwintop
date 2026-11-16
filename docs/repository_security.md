# Repository-Sicherheit und Administrationsschritte

Stand 16.11.2026. Repository bleibt privat. Die Branch-API nennt `main`
ungeschützt. Detaillierte Branch-Protection liefert für die Integration 403;
die Rulesets-API meldet eine Tarifgrenze für private Repositories. Deshalb
hier keine Schutzregel als tatsächlich aktiviert behaupten.

Actions verwenden `contents: read`, SHA-gepinnte Drittaktionen und
`persist-credentials: false`. Der Produktjob nutzt unveränderte
Abhängigkeiten. Der zweite Job kopiert gepinnte Bibliotheken ausschließlich
in ein temporäres Verzeichnis, patcht sie dort und führt Netzwerk-/PTY-
Wire-Tests aus. Er installiert keine Patches in Home Assistant. Direkte
Test-Abhängigkeiten sind versionsgenau gepinnt; transitiver pip-Resolve ist
noch nicht vollständig gelockt. Dependabot schlägt künftig pip- und
Actions-Updates als PR vor; Änderungen bleiben reviewpflichtig.

`scripts/check_package.py` prüft die leere Schreibfreigabe über AST und
Produktdateien. `scripts/build_package.py` nimmt nur Python, JSON und
Brand-PNG aus `custom_components/comwintop/` in das ZIP und verifiziert
alle Bytes. Keine Logs, Profile, Testquellen oder Patches ins Paket.
Vor jedem öffentlichen Stand alle Git-Commits, Tags, Release-Assets und
Diagnose-Dateien nochmals auf Tokens, private IPs und identifizierende
Metadaten prüfen. Das aktuelle Dokumentations-Screening ist keine
forensische Garantie für vergangene oder externe Kopien.

## Administrator: prüfen und bei verfügbarem Tarif einstellen

1. Repository **Settings → Rules → Rulesets** oder **Branches** öffnen;
   `main` als Ziel wählen. PR vor Merge verlangen, mindestens einen Review
   und den konkreten erfolgreichen `Validate read-only beta / test`-Check
   fordern. Force-Push und Löschung untersagen; keine Admin-Ausnahme für
   normale Änderungen setzen. Falls der Tarif die Funktion nicht anbietet,
   Upgrade oder späteren öffentlichen Status **separat** entscheiden; jetzt
   keine Sichtbarkeitsänderung.
2. **Settings → Actions → General → Workflow permissions** auf nur lesenden
   `GITHUB_TOKEN` setzen; PR-Erstellung per Actions nicht erlauben. Die
   Workflow-Dateien verlangen bereits nur `contents: read`.
3. **Settings → Security & analysis**: verfügbare Dependabot Alerts,
   Dependency Graph und Secret Scanning/Push Protection prüfen und aktivieren,
   soweit im privaten Tarif angeboten. Freie Features unterscheiden sich nach
   Konto und Plan; tatsächliche Aktivierung in GitHub nachsehen.
4. **Settings → General**: automatische Merges deaktiviert lassen; Release-
   und Branch-Löschen nicht automatisieren. Vor Freigabe eines Releases die
   [Release-Matrix](test_release_matrix.md) durchgehen.
5. Unter **Issues → Labels** die fünf vorgeschlagenen Labels
   `type: bug`, `type: feature`, `type: hardware`, `status: blocked` und
   `security: review` anlegen. Danach die drei Issue-Formulare auf ihre
   jeweiligen `type:`-Labels einstellen. Der GitHub-Connector kann Labels
   hier nicht anlegen; die Vorlagen behaupten deshalb keine automatische
   Zuordnung.

Keine Zugangsdaten in Issues posten. Für vertrauliche Fehler GitHubs privaten
Meldeweg nutzen, falls eingerichtet, andernfalls über das GitHub-Profil des
Maintainers zunächst einen privaten Kontaktweg abstimmen.

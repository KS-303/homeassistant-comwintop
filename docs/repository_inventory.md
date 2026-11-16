# GitHub-Bestandsaufnahme und Integration

Stand 16.11.2026; private GitHub-Repository-Branches, Commit-Eltern, Pull Requests,
Releases, Tags und Actions direkt geprüft. Vor einem Merge die Bestandsaufnahme
erneut mit GitHub vergleichen. Keine Branches und keine Historie umgeschrieben.

| Stand | HEAD | Direkte Herkunft / Zweck | PR |
|---|---|---|---|
| `main` | `ce208393` | 0.1.0b1, veröffentlicht | – |
| `feature/clear-names-icon` | `45589a4a` | `main`; ausgeschriebene Namen, Icon, b2-Vorstufe | – |
| `feature/local-device-profiles` | `7897ef7b` | b2 → `7a4cfd5d` Profile → b4-Beschriftungen; b3-/b4-Vorstufe | – |
| `feature/l50-channel-poll-intervals` | `74342405` | b4; kanalbezogenes Polling | [#1](https://github.com/KS-303/homeassistant-comwintop/pull/1), Draft |
| `feature/l51-communication-inspection` | `482abfba` | L-50 → `2143b8ea` lesende Registeranzeige → Busy-Befund | [#2](https://github.com/KS-303/homeassistant-comwintop/pull/2), Draft |
| `feature/l51-no-retry-upstream-proposal` | `56c08c66` | PR #2; getrennte Upstream-Entwürfe | [#3](https://github.com/KS-303/homeassistant-comwintop/pull/3), Draft |
| `feature/l51-upstream-wire-review` | `79fc0cfb` | PR #3 → `771070cd` PTY → `a8ec5145` Cancellation → Review | [#4](https://github.com/KS-303/homeassistant-comwintop/pull/4), Draft |

Bei der ersten Bestandsaufnahme waren vier Draft-PRs und keine eigenständigen
offenen Issues vorhanden. Für die zwei konkret offenen Hardwareabnahmen wurden
anschließend [#6](https://github.com/KS-303/homeassistant-comwintop/issues/6)
und [#7](https://github.com/KS-303/homeassistant-comwintop/issues/7)
angelegt. Der Aufbereitungs-Draft ist [#5](https://github.com/KS-303/homeassistant-comwintop/pull/5).
Einziger Release und Tag: `v0.1.0b1`, beide auf `ce208393`, zwei Release-Dateien.
Die letzte PR-#4-Actions-Ausführung (`43865376760`) war erfolgreich. Diese
Ausführung deckt die Upstream-PTY-Skripte noch nicht als eigenen CI-Job ab.
Zum Zeitpunkt dieser ersten Bestandsaufnahme war `main` ungeschützt. Nach der
öffentlichen Freigabe wurde eine klassische Branch-Schutzregel eingerichtet;
GitHub meldet jetzt `protected: true`. Details und weitere Sicherheitseinstellungen
stehen in [Repository-Sicherheit](repository_security.md). Es gibt weiterhin
keinen zusätzlichen Ruleset-Eintrag.

## Sichere spätere Integrationsfolge

1. b2-Vorstufe (`clear-names-icon`) getrennt prüfen und integrieren.
2. b3-Profile und b4-Beschriftungen im nachfolgenden Branch prüfen. Bei Bedarf
   vor dem Merge in zwei eigene, nachvollziehbare PRs aufteilen; keine
   Versionsnummer allein durch einen Branch-Merge veröffentlichen.
3. PR #1 gegen die integrierte b4-Basis prüfen; reale L-50-Mischintervalle
   bleiben bis zur Hardwareabnahme offen.
4. PR #2 (lesende L-51-Inspektion und gesperrter Schreibweg) prüfen.
5. PR #3 und #4 als Forschungspaket auf der jeweiligen Basis prüfen.
   Upstream-Patches im Repo sind **keine** gepatchte produktive HA-Laufzeit.
6. Diesen Aufbereitungs-PR nach #4 prüfen. Nach jedem vorgelagerten Merge
   abhängige Diffs und CI neu prüfen; bestehende Drafts nicht blind auf `main`
   retargeten, rebasen oder squashen.

L-51a (manuelle Slave-ID) ist ein eigener künftiger Funktions-PR **nach**
einem akzeptierten, von HA bereitgestellten No-Retry-Weg. L-51b (serielle
Parameter) und DO/AO (Ausgangsschreiben) erhalten getrennte spätere PRs.

## Konsistenz und offene Arbeiten

- `manifest.json` und `pyproject.toml` nennen 0.1.0b4 auf dem Entwicklungsstand,
  während `main` und Release b1 bleiben. Entwicklung ≠ Veröffentlichung.
- Die alten Testausgaben in `docs/evidence/` sind datierte Momentaufnahmen,
  keine Aussage über den aktuellen HEAD. Neue JUnit/XML-Ausgaben gehen in
  kurzlebige CI-Artefakte; alte Nachweise bleiben ohne Löschung erhalten.
- Der L-50-Prüfbericht zählt 123 Tests auf seiner damaligen Basis; spätere
  Summen dürfen ihn nicht stillschweigend ersetzen. Aktuelle CI separat nennen.
- `docs/implementation_status.md` bezeichnet Hardwarestände stellenweise zu
  pauschal als unvalidiert. Die zentrale [Testmatrix](test_release_matrix.md)
  trennt einzelne reale Befunde von einer vollständigen Geräteabnahme.
- `custom_components/comwintop/` enthält das einzige Produktpaket; `tests/`,
  `scripts/`, `docs/` und `upstream_patches/` sind bereits zweckmäßig getrennt.
  Eine Verschiebung würde Verweise und Archive ohne Nutzen riskieren.

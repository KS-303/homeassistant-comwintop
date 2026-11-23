# HACS und öffentliche Bereitstellung: Vorbereitung

Die Integration liegt als einziges Verzeichnis unter
`custom_components/comwintop/`. Das Manifest enthält `domain`, `name`,
`documentation`, `issue_tracker`, `codeowners` und `version`. Diese
Struktur entspricht den [HACS-Anforderungen an Integrationen](https://hacs.dev/docs/publish/integration/).
Das lokale HA-Icon in `brand/` ist **kein** Nachweis eines Eintrags im
separaten Home-Assistant-Brands-Projekt; HACS verlangt diesen Eintrag für
eine offizielle Aufnahme. Releases sind bei HACS optional, aber ein
öffentlicher Release muss den tatsächlichen freigegebenen Code enthalten.
Das Repository ist öffentlich, aber noch keine offizielle HACS-Quelle.

Vor einem Vorschlag an den [HACS-Katalog](https://hacs.dev/docs/publish/include/):
Lizenz bewusst festlegen, Marken-/Icon-Rechte prüfen, Herstellerabgrenzung
beibehalten, History/Tags/Assets auf private Daten prüfen, stabile
Installations- und Rückbauanleitung prüfen, HA-Kompatibilität und die
Testmatrix aktualisieren und Brands-Anforderung erfüllen. Derzeit **kein**
HACS-Aufnahmeantrag, keine Lizenzentscheidung und keine weitere Freigabe
von Code oder Schreibfunktionen.

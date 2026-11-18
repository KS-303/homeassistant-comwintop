# ComWinTop for Home Assistant

> **Entwicklungsstand 0.1.0b18 (b17-Stabilisierung, noch kein Release):**
> Basis ist b17. Das Installationspaket enthält nur fest freigegebene
> Integrationsdateien; der ungenutzte Schreibmanager bleibt außerhalb des ZIP.
> Die experimentelle Slave-ID-Schreibfunktion (FC06) sowie DO/AO-Schreiben
> bleiben vollständig gesperrt. Die Slave-ID und Diagnose sind lesbar.
> Unterstützter und getesteter HA-Zielstand: **Home Assistant Core 2026.11.x,
> Python 3.14**. Python-3.13-Syntax wird geprüft, aber ältere HA-Modbus-APIs
> sind **nicht** als kompatibel zugesichert.
>
> Negative Temperaturen und der mehrdeutige 85,0-°C-Rohwert bleiben bis zu
> einem hardwarevalidierten TM-32DS-Registertest bewusst `unavailable`.
> Bitte dieses Testpaket nicht als Anlagen- oder Personenschutzsteuerung
> verwenden. Ein früheres als b8 beschriftetes Paket enthielt tatsächlich
> neuere Dateien und ist kein verlässlicher Rückfallstand.
> [Befundliste und Korrekturstatus](docs/b13_security_audit.md).


ComWinTop verbindet CWT-I/O-Geräte lokal über Modbus mit Home Assistant.
Der veröffentlichte Stand ist **v0.1.0b1 (lesende Beta)**. Das
**0.1.0b18-Testpaket** baut auf b17 auf und ist kein GitHub-Release.
Die Integration ist
herstellerunabhängig beim Gateway,
aber für die mitgelieferten Registerprofile gerätespezifisch. Sie ist kein
Produkt des Geräteherstellers und enthält keine Anlagenregelung.
Eine explizite Lizenzdatei fehlt derzeit; Rechte zur Nachnutzung sind damit
nicht erteilt. Vor einer Freigabe zur Nachnutzung ist die Lizenzwahl
durch den Rechteinhaber zu klären.

**Vor der Installation:** [Funktionen und reale Nachweise](docs/test_release_matrix.md),
[Einschränkungen](docs/known_limits.md),
[schrittweiser HA-Test](docs/ha_test_plan.md).

**L-51a:** Das frühere FC06-Labormenü aus b6–b12 wurde in b13 entfernt.
Auch alte Formular-URLs brechen ab. Der HA-Unterbau kann bei Busy einen
Schreibaufruf wiederholen; deshalb sind Slave-ID-Änderungen, DO/AO und L-51b
(Baudrate/Parität) in diesem Paket gesperrt. Die alte
[Laboranleitung](docs/l51a_isolated_ha_lab.md) gilt nur für den historischen
isolierten Laborzweig und darf nicht als Anleitung für b15 verwendet werden.

**HA-Anzeige b15:** Die Kommunikationsübersicht zeigt Register 16 und alle
Kommunikationsparameter als einzeln beschriftete schreibgeschützte Felder.
Die Modbus-Adresse wird auch beim normalen Gerät-Anlegen und -Bearbeiten als
Zahlenfeld statt als Schieberegler angezeigt. Eine eigene Diagnose-Entität
„Kommunikationsregister 16“ zeigt den gelesenen Rohwert und alle Parameter
als Attribute; die einmalige Registerabfrage wird gemeinsam genutzt und
nicht pro Entität durchgeführt. Nach HACS-Installation HA vollständig neu
starten und die Browseransicht neu laden.
Die getrennte, ausschließlich lesende Kommunikationsinspektion bleibt erhalten.
Dies ist **kein stabiler Release** und kein produktiv freigegebenes Modul.

**L-50 – in 0.1.0b18 weiter ausschließlich lesend.**
Dies ist noch kein Installationsrelease. Die veröffentlichte Version 0.1.0b1
bleibt davon unberührt.

Lokale Modbus-I/O-Integration für CWT-TM-32DS und CWT-MB308N. Gateways und
USB-RS485-Adapter sind herstellerunabhängig. Für die beiden mitgelieferten
Modelle ist keine Register-YAML erforderlich.
Keine Cloud, keine Anlagenregelung, keine Sicherheitssteuerung.

## Stand

- Mehrere Verbindungen, mehrere CWT-Geräte als einzeln verwaltete Subentries.
- Modbus TCP, TCP→RTU-Gateway, transparentes RTU-over-TCP, Serial/USB-RS485.
- TM-32DS: 32 DS18B20-Temperaturkanäle, beim Anlegen lesend geprüft. In der
  Geräteverwaltung lassen sich Kanalbereiche manuell gesammelt deaktivieren oder
  aktivieren. Feuchtefühler sind an diesen Eingängen nicht unterstützt; ein
  separater RS485-Feuchtesensor braucht ein eigenes validiertes Geräteprofil.
  Nach dem Aktivieren ohne angeschlossenen Fühler bleibt der Kanal `unavailable`.
  MB308N: 8 Analogeingänge, 4 analoge
  Ausgangs-Readbacks, 8 Digitaleingänge und 8 digitale Ausgangs-Readbacks.
- NO/NC pro DI; Skalierung/Signalbereich pro AI; Gruppen- und optionale
  individuelle Kanal-Abfrageintervalle. Beim Eingeben eines Einzelwerts muss
  im Kanalformular „Individuell“ gewählt sein; ein versehentlich unter
  „Standard“ eingegebener Wert wird mit einer Fehlermeldung zurückgewiesen.
  Der Diagnoseexport zeigt je Kanal Gruppen-/Einzelwert, effektive Sekunden
  und den Abstand der letzten beiden gültigen Messungen.
- Stabile Geräte-UUIDs, Kanalqualität, Ablauf veralteter Daten, anonymisierte Diagnose.
- Ausgeschriebene Kanalnamen in Deutsch und Englisch; eigenes Integrationsicon
  mit dem Projekthandle KS-303.
- Weitere kompatible Modelle über lokal gespeicherte, strikt geprüfte YAML-Profile;
  Profilvorschau vor dem Anlegen eines Geräts, ohne automatische Veröffentlichung.
- **Keine produktiven DO-/AO-Schreibentitäten oder Schreibdienste.** Hardwaretests und
  ein nachgewiesenes Busy-Retry des HA-Unterbaus verhindern derzeit deren Freigabe.

Vollständige Abgrenzung: [Implementierungsstatus](docs/implementation_status.md),
[bekannte Grenzen](docs/known_limits.md), [Pflichtenheft v0.6](docs/specification_v0_6.md).

## Installation

1. Home Assistant **Core 2026.11.0 oder neuer**. Automatisiert geprüft ist zunächst 2026.11.0.
2. Vorher ein HA-Backup erstellen.
3. Aus dem geprüften Installationsarchiv den Ordner `custom_components/comwintop`
   nach `/config/custom_components/comwintop` kopieren. Keine bestehende
   `configuration.yaml` ersetzen. Das Archiv enthält nur diese Integration.
4. Home Assistant vollständig neu starten.
5. **Einstellungen → Geräte & Dienste → Integration hinzufügen → ComWinTop**.
6. Verbindungstyp und tatsächlichen Port einstellen. Bei USB möglichst
   `/dev/serial/by-id/...` verwenden. RTU-Leitungsparameter am Gateway separat passend einstellen.
7. Am Verbindungseintrag **Gerät hinzufügen**: Modell, eindeutige Unit-ID,
   Name und Kenntnis des Beta-Status. Es erfolgt nur ein dokumentierter Lesetest,
   keine Modellerkennung, kein Scan, kein Schreiben.
8. Analogkanäle über **Gerät konfigurieren → Kanal konfigurieren** entsprechend
   tatsächlichem Jumper/Signalbereich einrichten. Ohne Modus sind diese Werte unavailable.
9. Für Rohtelegrammvergleiche die standardmäßig deaktivierte jeweilige
   `... Rohwert`-Diagnoseentität in HA aktivieren. Ein Rohwert ist keine validierte Temperatur.

Unter **Gerät konfigurieren → Abfrageintervalle** bleiben die Standardwerte
je Kanalgruppe einstellbar. Unter **Gerät konfigurieren → Kanal konfigurieren →
Abfrageintervall** wählt man „Standard (Gruppenintervall übernehmen)“ oder
„Individuell“ samt Sekundenwert. Das Zahlenfeld wird bei „Standard“ ignoriert.
Neu einstellbar: 5–3600 s je Kanalart. Neu angelegte MB-308N starten mit
DI/DO 8 s und AI/AO 20 s. Bereits gespeicherte kürzere Gruppen- und
Einzelintervalle werden unverändert geladen; im Dialog sind neu eingegebene
Werte unter 5 s nicht mehr zulässig. Lokal definierte Profile übernehmen die
neuen Eingabegrenzen. Bei vielen Geräten oder getrennt fälligen Einzelkanälen
garantiert selbst 5 s nicht, dass die gemeinsame Buskapazität reicht.
Die Diagnose `minimum_read_rate_hz` zeigt eine optimistische Untergrenze je
Gerät; ab 0,9 Anfragen/s warnt die Integration. Weitere Geräte und
getrennte Kanalblöcke erhöhen die wirkliche Last.

Nur fällige zusammenhängende Kanäle werden zu Modbus-Blöcken gebündelt.
Beim TM-32DS liegt der vollständige Temperaturblock auf FC03, Adressen 32–63
(0-basiert). Ein schneller Kanal zieht langsamere Nachbarn nicht mit;
ausgelassene oder deaktivierte Kanäle können zusätzliche Blöcke erforderlich
machen. Jeder Kanal wird nach drei effektiven Intervallen ohne gültigen Wert
`unavailable`. Ein abgezogener DS18B20 lieferte am geprüften TM-32DS
`0xFC18` (−100,0 °C); die Integration verwirft diesen Wert als ungültig.
Ein Register-Readback belegt keine physische Ausgangsstellung.

Bei einem Update bleiben Gerätekennungen und die bestehenden Entitäts-IDs
erhalten. Anzeigenamen werden ausgeschrieben; manuell umbenannte Entitäten
behalten ihre eigenen Namen. Home Assistant 2026.11 kann das Icon direkt aus
`custom_components/comwintop/brand/` laden. Nach einem Update ist ein
vollständiger Neustart erforderlich.

Beim erstmaligen Anlegen eines TM-32DS liest die Integration die bekannten
32 Temperaturregister dreimal über die gemeinsam genutzte HA-Modbus-Verbindung.
Nur Kanäle mit zwei gültigen frischen Werten werden eingeschaltet; `0xFC18`,
85,0 °C und der mehrdeutige Rohwert null werden vorerst deaktiviert. Der erste
Block ist ein Start-/Umwandlungsvorlauf. Die Erkennung prüft weder alle Slave-IDs
noch den tatsächlichen Anschluss elektrisch. Deaktivierte Kanäle werden beim
neuen Gerät nicht als Entitäten angelegt; sie bleiben jederzeit über
**Gerät konfigurieren → Kanal konfigurieren** einzeln aktivierbar. Bestehende
Geräte werden beim Update nicht erneut automatisch bewertet. Bei einem
Transportfehler wird das Anlegen abgebrochen statt alle Kanäle zu deaktivieren.
Vorhandene Registereinträge deaktivierter Kanäle bleiben mit ihrer Entity-ID
als „durch die Integration deaktiviert“ erhalten; bei Aktivierung erscheinen
sie wieder. Ein Gerät ohne aktive Kanäle zeigt „Keine aktiven Kanäle“.

Die Beta wird manuell per ZIP installiert. Der Default-Branch `main` und der
einzige veröffentlichte Release enthalten noch b1. Eine HACS-Adresse für
dieses Repository wählt ohne explizite Entwicklungsreferenz keinen geprüften
Beta-Stand aus.
Eine Aufnahme in den HACS-Katalog ist noch nicht erfolgt.
[Schrittweiser HA-Test](docs/ha_test_plan.md).

**0.1.0b18-Bustest:** ComWinTop fordert beim öffentlichen gemeinsamen
Modbus-Manager eine Sekunde Pause vom Ende der letzten Anfrage/Antwort bis
zum Start der nächsten an. Zusammenhängende fällige TM-32DS-Register werden
weiterhin als Block gelesen. Die Pause ersetzt keine Prüfung auf verspätete
Rohbytes und behebt die sechs beobachteten unbeantworteten Anfragen bei
15 Sekunden Abstand nicht nachweislich. Bei vielen Kanälen mit kurzen,
unterschiedlichen Intervallen kann die Ein-Sekunden-Grenze einzelne
Sollintervalle verzögern; die kanalbezogene Stale-Frist bleibt maßgeblich.
Ein neuer Diagnose-Binärsensor je aktiviertem Temperaturkanal meldet nach
drei gültig beantworteten Telegrammen mit dem nachgewiesenen Fehlerwert `0xFC18` eine
**Fühlerstörung**. Fehlende Telegramme melden keinen Fühlerdefekt.
`bus_lock_wait_ms` misst die Wartezeit auf die ComWinTop-Hub-Sperre;
`read_call_ms` umfasst den öffentlichen Leseaufruf einschließlich einer
möglichen internen Pause. `latency_ms` ist bewusst leer: Die öffentliche
HA-Modbus-API liefert keinen tatsächlichen Sendezeitpunkt. Die Antwortzeit
des Geräts ist nur mit unabhängigem Busmitschnitt zu messen.

### Update und vollständige Entfernung

Vor einem Update HA-Backup erstellen, Integrationsversion und Paket-SHA-256
prüfen, nur `/config/custom_components/comwintop` aus dem gewünschten
**geprüften** Installationspaket ersetzen und Home Assistant neu starten.
Wenn das ZIP unter `/config` liegt, lautet der Update-Befehl im HA-Terminal:

```bash
cd /config
mv custom_components/comwintop custom_components/comwintop.backup
unzip comwintop-0.1.0b18-install.zip
```

Das Archiv legt ausschließlich `/config/custom_components/comwintop/` an.
Keine Entwicklungszweig-Dateien und keine Upstream-Patches direkt in die
produktive Installation kopieren. Danach Verbindung, Entitätskennungen,
Kanalnamen und ausschließlich lesende Daten prüfen; bei Problemen Backup
wiederherstellen. Bereits angelegte Geräte- und Kanaloptionen liegen in HA,
nicht im Integrationsordner.
Nach erfolgreichem Neustart und Datenprüfung kann ausschließlich der
Backup-Ordner entfernt werden. Durch das Ersetzen des ganzen Ordners bleiben
keine alten Python-Dateien wie `write_manager.py` zurück. Wer über eine
HA-Update-Entität aktualisiert, prüft deren angezeigte Zielversion und Quelle.

Zur Entfernung in **Einstellungen → Geräte & Dienste** die ComWinTop-
Verbindungseinträge entfernen, Home Assistant stoppen, nur
`/config/custom_components/comwintop` löschen und HA erneut starten.
Bei Bedarf lokale Profile unter `/config/comwintop/profiles` und deren
Sicherungen unter `/config/comwintop/last_valid` nach eigener Prüfung separat
entfernen. Den gesamten Ordner `custom_components` nicht löschen.

### Diagnose und Fehlerberichte

In der Integration die Diagnose herunterladen und den betroffenen Kanal,
Core-Version, Transportart, Modell, Zeitpunkt und erwarteten Rohwert mit
einem [Bugbericht](https://github.com/KS-303/homeassistant-comwintop/issues/new/choose)
melden. Vor dem Teilen Diagnose, Hostnamen, Netzwerkadressen, Unit-IDs und
eigene Kanalnamen nochmals selbst prüfen. Keine Passwörter, Tokens oder
vollständigen privaten Logs einstellen. Für Hardwaretests gibt es eine
eigene Vorlage. Die [Testmatrix](docs/test_release_matrix.md) trennt
Simulation von realer Prüfung.

## Weitere Geräteprofile lokal pflegen

Ein eigenes Modellprofil liegt als `/config/comwintop/profiles/<modellkennung>.yaml`
in Home Assistant, außerhalb der Integrationsdateien. Die Kennung im Inhalt muss
dem Dateinamen entsprechen. Das Format, die zulässigen Decoder und die Grenzen
stehen in [Lokale Geräteprofile](docs/local_profiles.md). Die Integration liest
Profile beim Start sowie beim Öffnen von „Gerät hinzufügen“. Änderungen an einem
bereits eingerichteten Gerät erfordern einen Neustart. Vor dem Anlegen zeigt HA
die Lesezugriffe und führt nach Bestätigung einen Lesetest aus. Der Test erkennt
das Modell und die korrekte Registerdeutung nicht selbstständig.

Eine fehlerhafte Datei wird abgewiesen; die letzte **syntaktisch validierte**
Fassung bleibt lokal unter `/config/comwintop/last_valid/` erhalten. Bei einer
gültigen Änderung wird dort zusätzlich eine vorherige Fassung mit Endung
`.previous` gesichert. Die Sicherung ist keine Hardwarefreigabe. Profile geben
keine Schreibfunktionen frei; sensible Verbindungsdaten gehören nicht hinein.

## Entwicklung / Tests

Python 3.14.2 oder neuer. Die getesteten Versionen stehen in `requirements-test.txt`.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-test.txt
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest --cov=custom_components.comwintop --cov-report=term-missing
.venv/bin/python scripts/check_package.py
.venv/bin/python scripts/build_package.py
```

Die regulären Tests kombinieren Grenzwerte/Properties, Zustands- und Konkurrenzfälle,
einen unabhängigen Modbus-Wire-Simulator, einen seriellen Linux-PTY und den echten
HA-Kern. Sie ersetzen keine echte Hardwareabnahme. Die erste Version garantiert
weder Relaiskontakte noch physischen Stromfluss.
Der [L-50-Prüfbericht](docs/l50_test_report.md) enthält gemessene Intervalle,
die Buslast vor/nach der Änderung und offene Hardwareprüfungen.
Die getrennten Upstream-Patches werden nur auf temporären Paketkopien mit
`python scripts/test_upstream_prototype.py` und in einem eigenen Workflow
geprüft. [Bestandsaufnahme und Merge-Reihenfolge](docs/repository_inventory.md),
[Roadmap](docs/roadmap.md), [Repository-Sicherheit](docs/repository_security.md).

## English

Local, manufacturer-neutral Modbus connections with model-specific CWT profiles.
Published v0.1.0b1 is a read-only beta; this unreleased 0.1.0b18 read-only test
package builds on b17. TM-32DS offers 32 temperature
channels; MB308N offers
8 analog inputs, 8 digital inputs and read-only output register values.
Connect through Modbus TCP, TCP-to-RTU gateway, transparent RTU over TCP, or
serial/USB RS485. Install the tested ZIP's `custom_components/comwintop`
directory into HA's `/config/custom_components/`, restart HA, add the
ComWinTop integration, then add a device with its known unit address. In
device options, set channel names, modes and group polling intervals; optional
per-channel intervals inherit the group default unless overridden. Temperature
intervals range from 5 to 3600 seconds. Download diagnostics after checking
them for private data. For updates, replace only this integration directory
and restart. To remove it, delete its HA connection entries, stop HA, remove
only `/config/custom_components/comwintop`, and start HA. Setup UI is
translated into English and German. **All production FC05/FC06/FC15/FC16
writes remain locked.** Readbacks do not prove physical output state.
See the [test/release matrix](docs/test_release_matrix.md) and
[known limitations](docs/known_limits.md) before hardware use.

## Lizenz / Herstellerbezug

Lizenzentscheidung noch offen. Bis zur Festlegung keine Open-Source-Lizenzfreigabe;
alle Rechte vorbehalten. Kein offizielles Herstellerprodukt.
Herstellerunterlagen werden nur verlinkt, nicht mitgeliefert.

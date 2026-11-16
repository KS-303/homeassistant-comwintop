# ComWinTop for Home Assistant

> **Entwicklungsstand b13 (Sicherheitsprüfung, noch kein Release):**
> Basis ist b12. Diese Version behebt Syntaxfehler, benennt die Version
> eindeutig und sperrt die experimentelle Slave-ID-Schreibfunktion (FC06)
> vollständig – auch für alte Flow-URLs. DO und AO bleiben ausschließlich
> lesbar. Die angezeigte Slave-ID und die Diagnose sind weiterhin verfügbar.
> Unterstützter und getesteter HA-Zielstand: **Home Assistant Core 2026.11.x,
> Python 3.14**. Python-3.13-Syntax wird geprüft, aber ältere HA-Modbus-APIs
> sind **nicht** als kompatibel zugesichert.
>
> Negative Temperaturen und der mehrdeutige 85,0-°C-Rohwert bleiben bis zu
> einem hardwarevalidierten TM-32DS-Registertest bewusst `unavailable`.
> Bitte b13 nicht als vollständige Anlagen- oder Personenschutzsteuerung
> verwenden. Das ältere b8-Installationspaket im zuvor erzeugten privaten
> Backup war falsch beschriftet und ist **kein** Rückfallstand.
> [Befundliste und Korrekturstatus](docs/b13_security_audit.md).


ComWinTop verbindet CWT-I/O-Geräte lokal über Modbus mit Home Assistant.
Der veröffentlichte Stand ist **v0.1.0b1 (lesende Beta)**. Das
**0.1.0b8-Labortestpaket** baut auf b7 auf und erweitert die Kommunikationsdiagnose;
es ist noch kein GitHub-Release. Die Integration ist
herstellerunabhängig beim Gateway,
aber für die mitgelieferten Registerprofile gerätespezifisch. Sie ist kein
Produkt des Geräteherstellers und enthält keine Anlagenregelung.

**Vor der Installation:** [Funktionen und reale Nachweise](docs/test_release_matrix.md),
[Einschränkungen](docs/known_limits.md),
[schrittweiser HA-Test](docs/ha_test_plan.md).

**L-51a – isolierter HA-Hardwaretest (0.1.0b8-Laborbranch):** Unter
„Gerät konfigurieren → Slave-ID ändern (isolierter Hardwaretest)“ kann ein
einziger, ausdrücklich bestätigter TM-32DS-Testaufbau erstmals FC06/Register
16 über HA ausprobieren. **Nicht an produktiven RS485-Bussen einsetzen.**
Der HA-Unterbau kann einen FC06-Schreibaufruf bei Busy mehrfach übertragen;
die Funktion bietet ausdrücklich **keine No-Retry-Garantie**. Bei unbestätigtem
Ergebnis keine erneute Schreibübertragung auslösen. Alle DO-/AO-Ausgänge,
andere Gerätemodelle und L-51b (Baudrate/Parität) bleiben schreibend gesperrt.
[Labortestanleitung, Sicherheit und Wiederherstellung](docs/l51a_isolated_ha_lab.md).

**HA-Anzeige b8:** Die Kommunikationsübersicht zeigt Register 16 und alle
Kommunikationsparameter als einzeln beschriftete schreibgeschützte Felder.
Die Modbus-Adresse wird auch beim normalen Gerät-Anlegen und -Bearbeiten als
Zahlenfeld statt als Schieberegler angezeigt. Eine eigene Diagnose-Entität
„Kommunikationsregister 16“ zeigt den gelesenen Rohwert und alle Parameter
als Attribute; die einmalige Registerabfrage wird gemeinsam genutzt und
nicht pro Entität durchgeführt. Nach HACS-Installation HA vollständig neu
starten und die Browseransicht neu laden.
Die getrennte, ausschließlich lesende Kommunikationsinspektion bleibt erhalten.
Dies ist **kein stabiler Release** und kein produktiv freigegebenes Modul.

**L-50 – in der 0.1.0b8-Laborversion weiter ausschließlich lesend.**
Dies ist noch kein Installationsrelease. Die veröffentlichte Version 0.1.0b1
bleibt davon unberührt.

Lokale Modbus-I/O-Integration für CWT-TM-32DS und CWT-MB308N. Gateways und
USB-RS485-Adapter sind herstellerunabhängig. Für die beiden mitgelieferten
Modelle ist keine Register-YAML erforderlich.
Keine Cloud, keine Anlagenregelung, keine Sicherheitssteuerung.

## Stand

- Mehrere Verbindungen, mehrere CWT-Geräte als einzeln verwaltete Subentries.
- Modbus TCP, TCP→RTU-Gateway, transparentes RTU-over-TCP, Serial/USB-RS485.
- TM-32DS: 32 Temperaturkanäle. MB308N: 8 Analogeingänge, 4 analoge
  Ausgangs-Readbacks, 8 Digitaleingänge und 8 digitale Ausgangs-Readbacks.
- NO/NC pro DI; Skalierung/Signalbereich pro AI; Gruppen- und optionale
  individuelle Kanal-Abfrageintervalle.
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
Temperatur: 5–3600 s; DI/DO: 1–3600 s; AI/AO: 2–3600 s. Lokal definierte
Profile übernehmen die Mindestintervalle ihrer Kanalarten. Vorhandene
Konfigurationen ohne Override nutzen unverändert ihre Gruppenintervalle.

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

Die Beta wird manuell per ZIP installiert. Eine Aufnahme in den HACS-Katalog
ist noch nicht erfolgt.
[Schrittweiser HA-Test](docs/ha_test_plan.md).

### Update und vollständige Entfernung

Vor einem Update HA-Backup erstellen, Integrationsversion und Paket-SHA-256
prüfen, nur `/config/custom_components/comwintop` aus dem gewünschten
**freigegebenen** Installationspaket ersetzen und Home Assistant neu starten.
Keine Entwicklungszweig-Dateien und keine Upstream-Patches direkt in die
produktive Installation kopieren. Danach Verbindung, Entitätskennungen,
Kanalnamen und ausschließlich lesende Daten prüfen; bei Problemen Backup
wiederherstellen. Bereits angelegte Geräte- und Kanaloptionen liegen in HA,
nicht im Integrationsordner.

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
Published v0.1.0b1 is a read-only beta; this unreleased 0.1.0b8 lab test package
builds on the 0.1.0b4 development base. TM-32DS offers 32 temperature
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

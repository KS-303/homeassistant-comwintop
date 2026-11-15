# ComWinTop for Home Assistant

**0.1.0b3 – ausschließlich lesende Entwicklungsversion.** Die veröffentlichte
Version 0.1.0b1 bleibt für den laufenden Hardwaretest verfügbar.

Lokale Modbus-I/O-Integration für CWT-TM-32DS und CWT-MB308N. Gateways und
USB-RS485-Adapter sind herstellerunabhängig. Für die beiden mitgelieferten
Modelle ist keine Register-YAML erforderlich.
Keine Cloud, keine Anlagenregelung, keine Sicherheitssteuerung.

## Stand

- Mehrere Verbindungen, mehrere CWT-Geräte als einzeln verwaltete Subentries.
- Modbus TCP, TCP→RTU-Gateway, transparentes RTU-over-TCP, Serial/USB-RS485.
- 32 Temperaturkanäle; MB308N 8 AI / 4 AO-Readbacks / 8 DI / 8 DO-Readbacks.
- NO/NC pro DI; Skalierung/Signalbereich pro AI; Gruppen-Pollintervalle.
- Stabile Geräte-UUIDs, Kanalqualität, Ablauf veralteter Daten, anonymisierte Diagnose.
- Ausgeschriebene Kanalnamen in Deutsch und Englisch; eigenes Integrationsicon
  mit dem Projekthandle KS-303.
- Weitere kompatible Modelle über lokal gespeicherte, strikt geprüfte YAML-Profile;
  Profilvorschau vor dem Anlegen eines Geräts, ohne automatische Veröffentlichung.
- **Keine produktiven Schreibentitäten oder Schreibdienste.** Hardwaretests und
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

Bei einem Update bleiben Gerätekennungen und die bestehenden Entitäts-IDs
erhalten. Anzeigenamen werden ausgeschrieben; manuell umbenannte Entitäten
behalten ihre eigenen Namen. Home Assistant 2026.11 kann das Icon direkt aus
`custom_components/comwintop/brand/` laden. Nach einem Update ist ein
vollständiger Neustart erforderlich.

Die Beta wird manuell per ZIP installiert. Eine Aufnahme in den HACS-Katalog
ist noch nicht erfolgt.
[Schrittweiser HA-Test](docs/ha_test_plan.md).

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

Die Tests kombinieren Grenzwerte/Properties, Zustands- und Konkurrenzfälle,
einen unabhängigen Modbus-Wire-Simulator, einen seriellen Linux-PTY und den echten
HA-Kern. Sie ersetzen keine echte Hardwareabnahme. Die erste Version garantiert
weder Relaiskontakte noch physischen Stromfluss.

## English

Local, manufacturer-neutral Modbus connections with model-specific CWT profiles.
This initial beta is read-only. Hardware writes are locked, not merely disabled
by a default setting. Setup UI is translated into English and German. See the
implementation matrix and known limitations before testing. No cloud dependency,
no automatic output restoration, no plant safety logic.

## Lizenz / Herstellerbezug

Lizenzentscheidung noch offen. Bis zur Festlegung keine Open-Source-Lizenzfreigabe;
alle Rechte vorbehalten. Kein offizielles Herstellerprodukt.
Herstellerunterlagen werden nur verlinkt, nicht mitgeliefert.

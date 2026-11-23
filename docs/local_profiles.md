# Lokale ComWinTop-Geräteprofile

Stand: 0.1.0b5-HA-Testpaket auf b4-Basis. Die Integration bleibt ausschließlich lesend.
Die beiden mitgelieferten Modelle sind unveränderlich. Ein neues Profil wird nur
für ein anhand von Herstellerunterlagen und Messungen geprüftes Modell angelegt.
Ein erfolgreicher Modbus-Lesezugriff bestätigt **nicht** den Gerätetyp, die
Kanalbelegung oder die physikalische Einheit.

## Aufbau

Verzeichnis: `/config/comwintop/profiles/`. Ein Profil ist eine UTF-8-Datei mit
Endung `.yaml`, maximal 16 KiB. `model` enthält nur Kleinbuchstaben, Ziffern und
Unterstriche, beginnt mit einem Buchstaben und ist zugleich der Dateiname ohne
Endung. Erlaubt sind ausschließlich folgende Felder:

| Feld | Bedeutung |
| --- | --- |
| `version` | Exakt `1` |
| `model` | Stabile technische Kennung, mindestens drei Zeichen |
| `name` | Modellname für die Geräteauswahl |
| `groups` | Eine bis fünf Lesegruppen, höchstens eine je Kanalart |

Jede Gruppe benötigt exakt `kind`, `method`, `decoder`, `start` und `count`.
Adressen in `start` sind **nullbasiert**. `count` liegt zwischen 1 und 64; die
letzte Adresse darf 65535 nicht überschreiten. Gleiche Kanalarten dürfen nicht
mehrfach vorkommen. Folgende Kombinationen sind derzeit fest freigegeben:

| `kind` | `method` | `decoder` | Bedeutung |
| --- | --- | --- | --- |
| `temperature` | `read_holding_registers` | `tm_32ds_temperature` | Zehntelgrad, nur 0 bis 125 °C; 85 °C bleibt gesperrt |
| `di` | `read_discrete_inputs` | `digital_input` | Digitaler Eingang |
| `do` | `read_coils` | `digital_output_readback` | Gelesener Ausgangszustand |
| `ai` | `read_input_registers` | `mb_308n_analog_input` | Analogeingang mit explizitem Signalmodus |
| `ao` | `read_holding_registers` | `mb_308n_analog_output_readback` | Gelesener Analogausgang mit explizitem Signalmodus |

Diese Decoder dürfen nur dann für ein anderes Modell verwendet werden, wenn
dessen Registerdarstellung nachweislich gleich ist. Die vorhandenen Formeln
werden nicht durch YAML umdefiniert. Ein anderes Registerformat erfordert eine
geprüfte Änderung der Integration.

## Ablauf und Rücknahme

1. Registerliste und Codierung mit der Herstellerdokumentation abgleichen.
2. Datei im Profilverzeichnis anlegen. Keine Geräteadressen, IP-Adressen,
   Personen- oder Hausnamen in die Profilfelder aufnehmen.
3. In Home Assistant beim Hinzufügen des Geräts das Modell wählen und die
   Vorschau mit Registeradressen und Leseart prüfen.
4. Bestätigen. Die Integration prüft einen einzelnen Registerwert der ersten
   Gruppe; danach Kanalwerte und Rohwerte am echten Gerät vergleichen.
5. Bei einem Fehler die Datei korrigieren und den Eintrag neu öffnen. Bei einem
   beschädigten Profil wird die letzte syntaktisch gültige Kopie aus
   `/config/comwintop/last_valid/` verwendet. Für eine bewusst gewünschte
   Rückkehr nach einer gültigen Änderung zuerst die `.previous`-Datei in
   `profiles/<modellkennung>.yaml` zurückkopieren und HA neu starten.

Das Verzeichnis bleibt auf dem eigenen HA-System und wird nicht automatisch
übertragen. Eine Kopie von `profiles/` und `last_valid/` gehört ins HA-Backup.
Neue Profile schalten keine Ausgangssteuerung frei. Auch ein Modbus-Readback
beweist keine physische Relaiskontaktstellung.

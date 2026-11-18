# Bekannte Grenzen und Releaseblocker (0.1.0b18)

Die b18-Korrekturen sind Simulator- und HA-Core-geprüft, aber noch nicht am
realen Gateway abgenommen. Bei mehr als einem Gerät oder stark versetzten
Einzelintervallen kann die feste Ein-Sekunden-Buspause die gewünschten
Abfragezeiten überschreiten. Ein RTU-Timeout setzt weiterhin die gemeinsame
Verbindung zurück. Die öffentliche HA-Modbus-Unit bietet keine echte
Gerätelatenz-Metrik; `latency_ms` bleibt deshalb leer. Für einen 24-Stunden-
Hardwaretest sind Busframes und Frische jedes aktiven Kanals zu prüfen.

## Nachgewiesenes Busy-Retry im HA-Unterbau

Getestete Abhängigkeiten: Home Assistant 2026.11.0, modbus-connection 4.12.7,
tmodbus 1.1.0. Ein unabhängiger TCP-Server beantwortet FC05 mit Exception 06
(Server Device Busy). Der Unterbau sendet FC05 erneut. Im ersten ungekürzten
Versuch wurden zehn Übertragungen innerhalb rund einer Minute beobachtet.

Ursache aus Quellprüfung: modbus-connection übergibt response_retry_strategy mit
retry_never und retry_on_device_failure=False. tmodbus AsyncSmartTransport ergänzt
jedoch den standardmäßig wahren Parameter retry_on_device_busy. Dieser wird vom
HA-Adapter nicht abgeschaltet. Die Integration verändert weder diese privaten
Objekte noch globalen HA-Code. Der kurze Regressionstest bestätigt den Fehler
und die bestehende produktive Schreibsperre; er wird nicht als Write-Freigabe gewertet.

Vor einer schreibenden Beta: passende vorgelagerte Korrektur oder geprüfte,
öffentliche Steuerungsmöglichkeit erforderlich; sämtliche tatsächlichen
Sendetraces für Timeout, Busy und Disconnect erneut prüfen. Die historische
b6-Laborausnahme konnte bei Busy mehrfach senden. Sie wurde in b13 entfernt
und ist in b15 nicht enthalten. [Historische Laboranleitung](l51a_isolated_ha_lab.md).

## Harte 2-Sekunden-Frist für spätere DO/AO-Schaltbefehle

Eine Prüfung vor dem Aufruf einer shared-unit-Methode beweist nicht, dass ein
Telegramm binnen 2 Sekunden gesendet wird: die Methode kann intern hinter einer
anderen Integration warten. Die isolierte Write-Engine besitzt deshalb einen
Sendeguard-Contract. Der aktuelle HA-Unit-Adapter ist noch kein zertifizierter
Write-Executor. Kein Write-Release ohne nachgewiesenen Guard am realen Sendepunkt.
Die manuelle L-51a-Slave-ID-Parametrierung hat einen eigenen frischen
Bestätigungs- und Verifikationsablauf; die Ausgangs-Schaltfrist blockiert sie
nicht. Der FC06-Weg bleibt aus anderen Gründen gesperrt.

## Sensor- und Hardwaregrenzen

- Negative TM-32DS-Werte und unbekannte Codes werden nicht als Temperaturen erfunden.
- 85 °C ist bis Klärung des Startup-Verhaltens mehrdeutig und unavailable.
- AI/AO-Modi zunächst ungeklärt: physische Interpretation erst nach Konfiguration.
- AI 0–5 V und AO 0–5 V nutzen laut Ausgangsdokument verschiedene Skalierungen;
  genau das muss am Gerät geprüft werden.
- DI/DO-Funktionscodes stammen aus einem noch nicht hardwarebestätigten Profil.
- RTU hat keine Transaktionskennung. Disconnect/Resync und Busruhe reduzieren
  Fehlzuordnungen innerhalb geprüfter Grenzen; keine absolute Garantie bei beliebig
  spät vom Gateway erneut eingespeisten Frames.
- PTY ist ein serieller Softwaretest, kein Nachweis eines konkreten USB-Adapters.
- DNS-Aliase/IP-Adressen, die denselben Gateway bezeichnen, sind nicht immer als
  identisch erkennbar. Nur eine Verbindung je physischem Bus konfigurieren.
- Keine internen Anlagenverriegelungen, keine Schutzabschaltung, kein Echtzeitbetrieb.

## Kanalerkennung bei neuer TM-32DS-Einrichtung

Nur die bekannte Slave-Adresse wird dreimal als FC03-Block 32–63 gelesen. Das
ist kein Bus-Scan und kein elektrischer Anschlussnachweis. Zwei frische Werte
müssen dem aktuell unterstützten Decoder entsprechen. Null, 85,0 °C und
negative/unklare Codes bleiben vorerst deaktiviert, auch wenn ein tatsächlich
angeschlossener Sensor diesen Wert liefert. Solche Kanäle können manuell
freigegeben werden. Die Erkennung greift ausschließlich beim Anlegen; ein
späterer Fehler deaktiviert keine zuvor gespeicherte Kanaloption.

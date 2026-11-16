# Getrennte Freigabebedingungen

## L-51a – manuelle Slave-ID

- Noch kein upstream veröffentlichtes, von HA gepinntes No-Retry-API.
  Die beiden Patchentwürfe brauchen menschlichen Maintainer-Review und
  Tests in ihren jeweiligen Projekten. Der pymodbus-Adapter prüft im
  Entwurf die tatsächlich instanziierte Retryzahl; bei `retry=False` und
  einer Abweichung von null verweigert er jeden Write.
- Der [vollständige künftige Dialog](l51a_address_change.md) samt
  Adresskonflikt-/Bustopologieprüfung, exklusivem Buszugriff, expliziter
  Bestätigung, FC06 und Verifikation ist noch nicht implementiert.
- Echter HA-Neustart während eines unbestätigten Writes, isolierter
  TM-32DS-Test und Multidrop-Test sind offen. Bei Timeout bleibt das
  Ergebnis unbestätigt und der Auftrag darf nicht wiederholt werden.
- Die **2-Sekunden-Schaltbefehlsfrist gilt nicht für die manuelle
  L-51a-Geräteparametrierung**. Deren eigener Bestätigungsdialog muss
  dennoch an den frisch geprüften Rohwert gebunden sein. Eine alte
  Bestätigung darf nicht unbegrenzt weiterverwendet werden.

## DO/AO – spätere produktive Ausgangsbefehle

- Zusätzlich zu No-Retry, getrenntem Hardwaretest, Readback und
  Sicherheitsgrenzen ist die bestehende **2-Sekunden-Frist** einzuhalten.
- Der WriteManager prüft die Frist bisher nur in einem Executor-Guard.
  Es fehlt ein öffentlicher Hook, der nach allen Locks, Pacer-/Busruhe-
  und Connect-Wartezeiten unmittelbar vor der physischen Übertragung
  fail-closed prüft. `retry=False` löst dies nicht.
- Cancellation nach begonnenem Senden und fehlender Reply ergeben einen
  unbestätigten Zustand. Keine unkontrollierte Wiederholung oder
  Freigabe produktiver Switch-/Number-Entitäten.

## L-51b – Baudrate und Parität

Originale Herstellerregistergrafik, isolierter Busparameterwechsel,
Gatewayumstellung und Verifikation unter den neuen seriellen Parametern
sind eigenständig offen. L-51b bleibt vollständig gesperrt.

# Wien EV Quellen

## Offizielle aktuelle Anker

- Statistik Austria, Pkw-Bestand 2025:
  https://www.statistik.at/fileadmin/announcement/2026/02/20260224KfzBestand2025.pdf
  Verwendung:
  - aktueller Wiener Pkw-Bestand: `741.985`
  - Wiener Anteil Elektro-Pkw am Pkw-Bestand: `6,1 %`
  - daraus als explizite Inferenz:
    - aktueller Wiener BEV-Bestand grob `45.300`
  Hinweis:
  - diese Inferenz bezieht sich auf reine Elektro-Pkw, nicht auf Hybride

## Offizielle Wiener Ziel- und Szenarioquellen

- Stadt Wien, Wiener Weg zur E-Mobilitaet:
  https://www.wien.gv.at/umwelt/e-mobilitaet
  Verwendung:
  - offizieller Wien-Zielanker:
    - `2030 werden circa 30 Prozent aller Autos E-Fahrzeuge sein`
    - `2040 sollen 100 Prozent der Pkw elektrisch betrieben`
  - qualitative Einordnung:
    - Wien koppelt Antriebswende und Verkehrswende bewusst gemeinsam

- Stadt Wien, Wiener Klimafahrplan Mobilitaet:
  https://www.wien.gv.at/spezial/klimafahrplan/klimaschutz-wien-wird-klimaneutral/mobilitat/
  Verwendung:
  - offizieller Motorisierungszielwert:
    - `250 private Pkw je 1.000 Einwohner*innen bis 2030`
  - offizieller Zielwert fuer Neuzulassungen:
    - `100 % nicht-fossile Antriebe bei Neuzulassungen bis 2030`

- Stadt Wien, Bevoelkerungsprognose:
  https://www.wien.gv.at/statistik/bevoelkerung/prognose/index.html
  Verwendung:
  - offizieller Wien-2030-Bevoelkerungsanker:
    - `2.083.630 Einwohner*innen`
  - daraus als grobe Inferenz fuer 2030:
    - `250 / 1.000 * 2.083.630 = ~520.900 private Pkw`
    - bei `30 %` elektrischen Autos entspraeche das grob `~156.300 E-Pkw`
  Hinweis:
  - das ist nur eine abgeleitete Groessenordnung aus zwei offiziellen Zielankern, keine offizielle Fahrzeugprognose

- Stadt Wien / Wien Energie, Stadt am Strom(e):
  https://positionen.wienenergie.at/wp-content/uploads/2025/06/Stadt-am-Strome.pdf
  Verwendung:
  - offizieller Wiener Strombedarfs-Szenariorahmen fuer E-Mobilitaet:
    - `2030: 697 bis 915 GWh/a`
    - `2040: 1.775 bis 2.802 GWh/a`
  - damit ist fuer Zukunftsszenarien die Energieseite belastbarer als eine reine Fahrzeugzaehlinferenz

## Aktueller kWh-Anker fuer V1

- Umweltbundesamt, Modellannahmen Elektro-Pkw:
  https://www.umweltbundesamt.at/fileadmin/site/publikationen/dp147.pdf
  Verwendung:
  - technische V1-Annahme fuer einen durchschnittlichen Elektro-Pkw:
    - Stromverbrauch `0,2 kWh/km`
    - Jahresfahrleistung `13.000 km/a`
  - daraus als explizite Inferenz:
    - `2,6 MWh pro BEV und Jahr`

## Daraus abgeleitete V1-Groessenordnung fuer Wien

- aktueller Wiener BEV-Bestand:
  - grob `45.300`
- aktueller Wiener BEV-Strombedarf:
  - grob `45.300 * 2,6 MWh/a = 118 GWh/a`

Hinweise:
- Diese `118 GWh/a` sind nur ein grober V1-Anker fuer den heutigen BEV-Bestand.
- Fuer Zukunftsszenarien sollten die offiziellen Wiener Ladebedarfs-Szenarien aus `Stadt am Strom(e)` bevorzugt werden.
- Die heutigen `~118 GWh/a` beziehen sich nur auf eine grobe BEV-Pkw-Inferenz;
  die Wiener Zukunfts-Szenarien `697-915 GWh/a` bzw. `1.775-2.802 GWh/a` beziehen sich dagegen auf den breiteren strassengebundenen E-Mobilitaetsbedarf.
- Fuer die Gebaeudestrom-Bilanz gilt:
  - EV bleibt als eigener Verkehrsblock
  - EV wird nicht in `residential` oder `non_residential` hineingezwungen
  - die elektrische EV-Last muss aber natuerlich in der Gesamtstrombilanz des Systems gedeckt werden

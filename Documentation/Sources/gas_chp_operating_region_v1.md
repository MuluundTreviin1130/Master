# Gas-CHP V1 Operating Region

Diese Notiz definiert den **bevorzugten V1-Methodenschnitt** fuer den Wiener
`district_gas_chp`-Pfad. Ziel ist **noch keine direkte Implementierung**,
sondern eine saubere fachliche Vorentscheidung fuer einen spaeteren
Dispatch-Umbau.

## 1. Problem im aktuellen Repo-Pfad

Der aktive `district_gas_chp` ist derzeit als **fixer CHP-Punkt** modelliert:

- feste `eta_el`
- feste `eta_th`
- damit festes Strom-Waerme-Verhaeltnis

Konsequenz im Dispatch:

- in [milp_day_ahead.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/modes/milp_day_ahead.py)
  und [milp_two_stage.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/modes/milp_two_stage.py)
  wird `district_gas_chp` derzeit ueber ein konstantes
  `gas_ratio = eta_el / eta_th` gekoppelt
- mehr CHP-Waerme bedeutet damit automatisch proportional mehr CHP-Strom und
  einen starren Fuel-zu-Waerme-/Fuel-zu-Strom-Zusammenhang

Das ist fuer einen ersten Benchmarkpfad okay, aber fachlich zu starr fuer die
aktuellen Thermflex-/Peakfragen.

## 2. Fachliche Zielvorstellung

Fuer die Wiener Story ist folgender Mechanismus plausibel:

- bei **hohen Strompreisen / Netzbedarf** wird die Anlage stromlastiger gefahren
- dann ist der **elektrische Output pro Fuel** hoeher
- gleichzeitig ist der **DH-Waermeoutput pro Fuel** geringer
- ausserhalb elektrischer Spitzen kann die Anlage **waermelastiger** fahren
  und mehr DH-Waerme auskoppeln

Das ist fachlich **keine freie Zeitreihe fuer `eta_el(t)` und `eta_th(t)`**,
sondern eine **zulaessige Betriebsregion** einer
`extraction-condensing CHP`.

## 3. Empfohlener V1-Schnitt

### 3.1 Grundidee

`district_gas_chp` soll im V1 nicht mehr als fixer Wirkungsgradpunkt, sondern
als **kleine Menge zulaessiger Betriebspunkte** modelliert werden.

Minimaler V1:

- `power_led`
- `mixed`
- `heat_led`

Jeder Betriebspunkt beschreibt einen physikalisch plausiblen Zusammenhang
zwischen:

- `fuel_input_kwh`
- `electric_generation_kwh`
- `thermal_generation_kwh`

### 3.2 MILP-Form

Pro Stunde `t`:

- Einfuehren von Gewichten `lambda[k,t] >= 0`
- optional wie heute weiterhin ein `gas_on[t]`-Binary

V1-Nebenbedingungen:

- `sum_k lambda[k,t] <= gas_on[t]`
- `p_el[t] = sum_k lambda[k,t] * p_el_k`
- `q_th[t] = sum_k lambda[k,t] * q_th_k`
- `fuel[t] = sum_k lambda[k,t] * fuel_k`

Damit:

- bleibt das Modell linear / MILP-tauglich
- kann der Dispatch pro Stunde zwischen stromlastigem und waermelastigem
  Betrieb waehlen
- ohne dass heuristische zeitabhaengige Wirkungsgrade hardcodiert werden

### 3.3 Warum das besser ist als dynamische `eta`

Nicht empfohlen:

- `eta_el(t)` / `eta_th(t)` direkt vom Strompreis abhaengig setzen
- ein manuelles Umschalten zwischen zwei Wirkungsgradpaaren

Grund:

- das waere zu heuristisch
- es bildet keine saubere physische Huelle ab
- und ist spaeter schwerer gegen Literatur oder Katalogwerte zu validieren

## 4. Empfohlene V1-Betriebsmodi

### `power_led`

Interpretation:

- Stromspitzen / Ancillary-/Balancing-nahe Situation
- hoher Stromoutput
- geringer DH-Waermeoutput pro Fuel

### `mixed`

Interpretation:

- Normalbetrieb
- mittlerer Punkt zwischen Strom- und Waermefokus

### `heat_led`

Interpretation:

- waermegefuehrter Betrieb
- niedrigerer Stromoutput
- hoeherer DH-Waermeoutput pro Fuel

## 5. Literatur-/Quellenbasis fuer die Richtung

### Dänische Systemintegrationsliteratur

Die Richtung des V1-Schnitts wird gut durch den bereits gesammelten dänischen
Integrationsanker getragen:

- zentrale CHP-Anlagen koennen zwischen stromlastigerem und
  DH-/KWK-Betrieb wechseln
- bei hohem Strombedarf kann die Stromproduktion erhoeht und die
  DH-Waermeerzeugung reduziert werden
- die Anlagen werden gemaess Strompreisen und Systemdienstleistungsbedarf
  optimiert

Quelle:

- `Summary of Danish experiences enabling maximum wind power integration`
  [EA Energy Analyses PDF](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/README.md)
  bzw. online referenziert in [dh_economics_quellen.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/dh_economics_quellen.md)

Wichtige inhaltliche Punkte daraus:

- CHP plants can switch between electricity-only / condensation-like operation
  and cogeneration mode
- in power-driven situations district heat can be reduced or omitted
- this flexibility is used to optimize against power prices and balancing needs

### Weitere Literaturanker

Bereits dokumentiert in
[dh_economics_quellen.md](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Documentation/Sources/dh_economics_quellen.md):

- DEA technology catalogue landing page
- CCGT + DH coordinated control paper
- reduced DH temperatures / extraction-condensing flexibility paper

Diese Quellen sollten spaeter fuer die **eigentlichen Eckpunkte** des
V1-Kennfelds ausgewertet werden.

## 5.1 Konkreter V1-Anker fuer die Betriebspunkte

Fuer den Wiener V1-Schnitt wird die **Balmorel-/DEA-Idee der
Extraction-CHP als Betriebsregion** uebernommen, die **eigentlichen
Eckpunkte** werden aber bewusst als **Wien-/anlagenplausibler CCGT-Proxy**
gesetzt.

Das ist hier die saubere Trennung:

- **aus Balmorel / DEA uebernommen**
  - nicht mehr ein fixer CHP-Punkt
  - sondern eine kleine zulaessige Power-Heat-Betriebsregion
- **nicht aus Balmorel / DEA uebernommen**
  - die exakten Wirkungsgradpaare der Wiener Eckpunkte

Grund:

- fuer den aktiven Wiener Story-Pfad ist fachlich gesetzt, dass selbst im
  stromgefuehrten Fall noch relevante DH-Waerme aus dem Dampfpfad bzw. der
  Auskopplung in das DH-System anfaellt
- der generische Balmorel-`condensing`-Punkt mit `q_th = 0` bildet diese
  Anlageninterpretation nicht gut ab

## 5.2 Wiener CCGT-Proxy fuer die V1-Betriebsregion

### Explizite Eckpunkte

Die V1-Region wird daher ueber folgende drei Punkte definiert:

#### `power_led`

- `eta_el = 0.55`
- `eta_th = 0.30`
- `eta_total = 0.85`

Interpretation:

- stromgefuehrter Betrieb
- Netz-/Stromspitzenlogik
- DH-Waerme bleibt positiv, ist aber relativ klein

#### `mixed`

- `eta_el = 0.425`
- `eta_th = 0.425`
- `eta_total = 0.85`

Interpretation:

- einfacher mittlerer V1-Punkt
- bewusst als symmetrischer Zwischenmodus zwischen Strom- und Waermefokus

#### `heat_led`

- `eta_el = 0.30`
- `eta_th = 0.55`
- `eta_total = 0.85`

Interpretation:

- waermegefuehrter Betrieb
- hoehere DH-Auskopplung
- Stromertrag bleibt positiv, aber deutlich geringer als im `power_led`-Modus

### Normalisierung fuer spaetere Settings

Die Punkte sollen spaeter auf die heute bereits vorhandene
`installed_kw_el_max`-SSOT normiert werden.

Ein sauberer V1-Normierungsvorschlag ist:

- elektrische Nennbasis:
  - `p_el_norm = 1.0` im `power_led`-Punkt
- daraus:
  - `fuel_norm = 1 / 0.55 = 1.818`
  - `q_th_norm(power_led) = 0.30 / 0.55 = 0.545`
  - `p_el_norm(mixed) = 0.425 / 0.55 = 0.773`
  - `q_th_norm(mixed) = 0.425 / 0.55 = 0.773`
  - `p_el_norm(heat_led) = 0.30 / 0.55 = 0.545`
  - `q_th_norm(heat_led) = 0.55 / 0.55 = 1.000`

Damit ist der waermelastige Punkt gleichzeitig der Punkt mit maximalem
DH-Output relativ zur elektrischen Nennbasis.

## 5.3 Wichtige methodische Einordnung

Diese Eckpunkte sind bewusst:

- **kein** DEA-Katalogwert fuer eine generische Anlage
- **kein** direkt aus Balmorel uebernommener `Cb`/`Cv`-Satz
- sondern ein **Wien-/anlagenplausibler CCGT-Proxy**, der die fachlich
  gewuenschte Interpretation des Dampf- und DH-Pfads abbildet

Das muss im Paper bzw. in den Source Notes klar so gerahmt werden.

Balmorel bleibt trotzdem wichtig:

- als Vorbild fuer die **Modellform**
- also:
  - Betriebsregion statt fixer CHP-Punkt
  - mehrere zulaessige Modi statt dynamische Ad-hoc-`eta`

Der Nutzen fuer die Wien-/Thermflex-Story ist damit:

- bei Stromspitzen kann die Anlage stromlastiger gefahren werden,
  **ohne** dass DH-Waerme auf null faellt
- ausserhalb elektrischer Spitzen kann die Anlage waermelastiger fahren
- die relationale Fuel-, Strom- und Waermelogik bleibt trotzdem ueber klare
  Betriebspunkte explizit und settings-getrieben

## 6. Was fuer V1 bewusst noch **nicht** hinein soll

Bewusst spaeter:

- Startkosten
- Rampen
- Steam-bypass als eigener vierter Modus
- temperaturabhaengige Kennfelder
- vollstaendige nichtlineare Turbinenkennlinie

V1 soll klein, klar und testbar bleiben.

## 7. Konkreter Repo-Schnitt fuer spaeteren Umbau

### Settings

[district_gas_chp.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Settings/technical/district_gas_chp.py)

Ergaenzen um:

- expliziten Modus-Schalter
  - `operating_mode_model = "fixed_ratio" | "piecewise_power_heat_v1"`
- Liste von Betriebspunkten

### Dispatch

[milp_day_ahead.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/modes/milp_day_ahead.py)

- festen `gas_ratio`-Pfad fuer `district_gas_chp` optional ersetzen
- `lambda[k,t]`-basierte CHP-Region nur aktivieren, wenn
  `operating_mode_model == "piecewise_power_heat_v1"`

Analog spaeter in:

- [milp_two_stage.py](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/dispatch/modes/milp_two_stage.py)

### Reporting

Spaeter exportieren:

- aktiver CHP-Modus / Modusanteile
- effektiver stündlicher Strom-Waerme-Punkt
- damit man paperseitig zeigen kann, wann die Einheit strom- vs waermelastig
  gefahren wird

## 8. Offene Punkte vor Implementierung

- konkrete Eckpunkte `power_led`, `mixed`, `heat_led` aus Literatur/Katalog
  festziehen
- entscheiden, auf welcher Leistungsbasis die Punkte formuliert werden:
  - pro installierter `kW_el`
  - oder absolut
- pruefen, ob der Wiener Story-Pfad eher eine echte
  `extraction-condensing CHP` oder einen engeren CCGT-/Fernwaerme-Proxy braucht

## 9. Empfohlene naechste Reihenfolge

1. Literatur-/Katalogwerte fuer 2-3 CHP-Betriebspunkte extrahieren
2. Settings-SSOT dafuer explizit definieren
3. zuerst nur `milp_day_ahead` umbauen
4. dann gegen die bestehende fixe-CHP-Version vergleichen
5. erst danach `milp_two_stage` nachziehen

# Wi-Fi kamermeting: meerdere BSSID's per kamer

Deze versie meet **alle afzonderlijk zichtbare accesspoints (BSSID's)** die hetzelfde SSID uitzenden, niet uitsluitend het accesspoint waarmee je Mac op dat moment verbonden is. Elke kamer krijgt standaard **4 CoreWLAN-scans**. Een Bash-script stelt vragen; een kleine lokaal op jouw Mac gecompileerde Swift-helper voert de scans uit; Python 3 slaat de statistieken veilig op als JSON. Alles blijft op jouw Mac.

Speciaal ingericht voor **macOS Sequoia 15.5** met Engelstalige systeemmenu's. Er zijn geen Homebrew-pakketten of online services nodig, maar **Apple Command Line Tools** en **Python 3** moeten beschikbaar zijn.

## Update voor macOS Sequoia 15.5

De vorige versie bevatte ten onrechte `CLAuthorizationStatus.authorizedWhenInUse` in de Swift-code. Deze status is op macOS niet beschikbaar. In deze versie gebruikt de helper voor de statuscontrole uitsluitend `.authorizedAlways`. Het Bash-script bouwt de scanner automatisch opnieuw als `WifiScan.swift` of `Info.plist` nieuwer is dan de aanwezige app.

## 1. Starten

Pak de ZIP uit en open Terminal in de uitgepakte map (bijvoorbeeld sleep de map na `cd ` in Terminal). Voer daarna uit:

```bash
xcode-select --install   # Alleen nodig als Apple Command Line Tools nog ontbreken
chmod +x start.sh
./start.sh
```

`start.sh` is het enige startpunt. De app controleert zelf of de Wi-Fi-scanner gebouwd of bijgewerkt moet worden en start de lokale resultatenserver op de achtergrond. Daarna zie je drie keuzes: **Kamers meten**, **Resultaten bekijken** en **Meer opties**, plus Stoppen.

**Meten doe je in Terminal. De browser is voor je resultaten.** De browser opent wanneer je Resultaten bekijken kiest. Laat het terminalvenster open zolang je de app gebruikt. Met Stoppen of Ctrl+C sluit de app de eigen server; de opgeslagen metingen blijven bewaard. Als een ander appvenster dezelfde server al gebruikt, wordt die hergebruikt. Een bezette poort wordt automatisch opgevangen.

De projectindeling is bewust eenvoudig:

- `start.sh`: centrale launcher.
- `app/`: interne scripts, Python-code, webinterface en Swift-broncode.
- `data/`: persoonlijke meetbestanden; deze map wordt door Git genegeerd.
- `.runtime/`: lokaal gebouwde macOS-app; deze map wordt door Git genegeerd.
- `docs/`: documentatie.
- `examples/`: uitsluitend geschoonde voorbeelddata.
- `tests/`: automatische tests.

**Bij de eerste start, of na een wijziging van de scannerbron**, bouwt de applicatie automatisch `.runtime/WifiKamermeting.app` uit de bronbestanden in `app/`. Een actuele scanner wordt hergebruikt. Xcode zelf is niet verplicht; de Command Line Tools volstaan. Tijdens de eerste scan kan macOS vragen om Location Services: **Allow While Using App** voor **WifiKamermeting**. Geef die toestemming, want zonder deze toestemming kan CoreWLAN de BSSID van *andere* AP's verhullen, ook al werken de Shortcuts voor je verbonden AP. Als de scanner niet gebouwd kan worden, blijven opgeslagen resultaten beschikbaar; via Meer opties kun je de voorbereiding opnieuw proberen.

Controleer bij problemen **System Settings → Privacy & Security → Location Services → WifiKamermeting**. Verwijder/verplaats de `.app` liever niet nadat je deze eenmaal autorisatie hebt gegeven. Wijzigen/recompileren kan ertoe leiden dat macOS opnieuw toestemming vraagt.

Je bestaande Shortcuts heten nog steeds **`WiFi-SSID`** en **`WiFi-BSSID`**. Het Bash-script gebruikt ze om de *actuele verbinding* aan het begin en einde van de kamermeting vast te leggen.

Bij problemen kun je apart `./start.sh controle` uitvoeren. Als deze controle zowel RSSI als **verschillende BSSID's** teruggeeft, werkt de scan op jouw Mac. Zie je geen BSSID's of staat er `denied`, dan zijn de onafhankelijke AP-scans nog niet bruikbaar; het script verzint in dat geval géén signalen.

## 2. Meetronde

```bash
./start.sh
```

Kies **Kamers meten**. De applicatie laat je een nieuwe ronde starten of een eerdere ronde hervatten, stelt het huidige SSID voor en toont de instellingen voordat de meting begint. Tijdens het meten zie je de verstreken tijd. Daarna zie je een korte bevestiging van het gemeten signaal en drie keuzes:

1. Nieuwe kamer meten.
2. Andere acties: vorige kamer opnieuw meten of accesspoints een naam geven.
3. Meetronde afronden.

Na afronden keer je terug in het hoofdmenu. Resultaten bekijken is dan de standaardkeuze. Je hoeft geen server te starten of bestanden te openen.

Na iedere kamer schrijft het script het **complete JSON-bestand atomair** weg. Een afgebroken ronde kun je later via het startmenu hervatten, of expliciet met:

```bash
./start.sh meten --resume wifi-meting-YYYYMMDD-HHMMSS.json
```

### Accesspoints een naam geven

Kies tijdens een meetronde **Andere acties → Accesspoints een naam geven**. Loop naar ieder fysiek accesspoint en start daar via het menu een korte identificatiescan. De gevonden BSSID's staan op signaalsterkte gesorteerd. Kies één nummer, of meerdere nummers als verschillende radio's/BSSID's bij hetzelfde fysieke apparaat horen, en geef ze samen een naam zoals `Overloop` of `AP kantoor`.

De koppeling wordt in het meetbestand opgeslagen en verschijnt bij de uitgebreide analyse in de browser. Je kunt de naam op dezelfde manier wijzigen. Omdat één fysiek accesspoint meerdere 2,4/5/6GHz-radio's kan hebben, voegt het programma BSSID's niet op basis van een gok automatisch samen.

De scans duren zelf ook enkele seconden. Standaard gebeurt er viermaal een scan, met twee seconden *pauze tussen* de scans. Wil je meer of minder:

```bash
./start.sh meten --scans 6 --interval 3
```

Standaard komt het meetbestand in `data/`. Je kunt vooraf ook een eigen bestandsnaam opgeven; een losse bestandsnaam wordt eveneens in `data/` geplaatst:

```bash
./start.sh meten "mijn-meting.json"
```

Bestaat dat bestand al, dan wordt het niet overschreven. Gebruik in dat geval `--resume` om bewust verder te gaan.

## 3. JSON (schema 3)

De bestaande velden blijven bewaard: `kamer`, `ssid`, `bssid`, `rssi_dbm`, `vorige_bssid`, `accesspoint_gewisseld`, `kanaal`, enzovoort. Deze verwijzen nog steeds naar de **actieve verbinding**.

Op het hoogste niveau bevat `accesspoint_namen` de blijvende koppeling van BSSID naar de zelfgekozen naam. Oudere bestanden zonder dit veld blijven leesbaar en krijgen in het dashboard de automatische labels `AP 1`, `AP 2`, enzovoort.

Velden per kamer voor de multi-AP-metingen:

- `accesspoints`: per BSSID de gemiddelden, minimum en maximum RSSI, kanaal, aantal scans waarin het AP is gezien, en of het AP bij afsluiten de huidige verbinding was.
- `scan_details`: de **ruwe waarnemingen van elke scan**, met tijdstip, verbonden BSSID/RSSI en de gemeten BSSID/RSSI van alle zichtbare radios die dit SSID aanbieden.
- `sterkste_bssid`: sterkste gemeten AP voor dat SSID, bepaald op basis van de gemiddelde scan-RSSI.
- `verschil_sterkste_en_verbonden_db`: verschil tussen gemiddelde **scan-RSSI** van de sterkste BSSID en die van de verbonden BSSID. `null` als geen eerlijke vergelijking beschikbaar is.
- `verbonden_bssid_tijdens_scans`: BSSID's waarop de Mac tijdens deze kamerwaarneming verbonden is geweest (voor zover zichtbaar).

`rssi_dbm` bij de kamer is de gemiddelde **link-RSSI** van de Mac. Dit kan enigszins afwijken van de afzonderlijke scan-RSSI van hetzelfde AP. Deze verschillende meettechnieken worden niet onderling vergeleken voor een 'beste AP'-oordeel.

**Belangrijk:** een Wi-Fi-scan observeert alleen radios die de Mac op dat moment kan ontvangen. De actieve scan kan netwerkverkeer kort beïnvloeden; niet elke scan is onafhankelijk (macOS kan resultaten cachen). Eén fysiek accesspoint kan meerdere BSSID's hebben. Het sterkste signaal is niet automatisch de beste verbinding. macOS bepaalt roaming zelf; dit script forceert geen andere verbinding.

Wanneer CoreWLAN op jouw macOS de BSSID van alternatieve AP's afschermt, worden die resultaten **niet** als anonieme AP's samengevoegd. Je krijgt een waarschuwing en blijft de gegevens van de huidige verbinding zien. De bestaande Shortcuts kunnen dat afschermen bij andere AP's niet opheffen.

## 4. Dashboard

```bash
./start.sh dashboard
```

Normaal kies je **Resultaten bekijken** in het hoofdmenu. Het commando hierboven opent de resultaten direct en laat de terminalapp beschikbaar om te meten. De server gebruikt normaal **http://127.0.0.1:8765** en kiest zo nodig zelf een vrije poort. De browser toont als eerste de laatst bijgewerkte meetronde en controleert elke drie seconden op opgeslagen wijzigingen.

- Het eerste overzicht toont één kaart per kamer: goed, redelijk, zwak of onbekend signaal. Bij herhalingen telt de laatste meting per kamer.
- **Meetdetails** toont de exacte waarde, het tijdstip en eventuele waarschuwingen. Goed is vanaf −65 dBm, redelijk vanaf −75 dBm; dit zijn indicatieve signaalcategorieën, geen snelheidsmeting.
- **Uitgebreide analyse** bevat de grafieken, accesspointnamen, signaalmatrix, roaming en ruwe scans.
- Via **Meer opties** kun je meetrondes vergelijken of een meetbestand handmatig openen. Vergelijken is nooit het standaardoverzicht.
- Als je bewust een oudere ronde bekijkt, blijft die geselecteerd wanneer nieuwe resultaten binnenkomen. Uitgeklapte meetdetails blijven open bij updates binnen dezelfde ronde.

Voor direct gebruik van `app/index.html` zonder server kun je via **Meer opties → Meetbestand openen** een bestand kiezen. De lokale server gebruikt Python 3 zonder externe pakketten en luistert uitsluitend op 127.0.0.1. De browser kan geen scan starten; dat gebeurt uitsluitend in Terminal.

## 5. Privacy en beperkingen

De metingen verlaten jouw computer niet. De app gebruikt Location Services uitsluitend om macOS toestemming te laten geven voor Wi-Fi-identificaties; de code leest/schrijft geen geografische coördinaten. Dit is lokaal door jezelf te compileren, niet als vooraf gecompileerd programma ondertekend door een externe ontwikkelaar.

Meetbestanden kunnen SSID's, BSSID's, kamernamen, notities en tijdstippen bevatten. Daarom negeert `.gitignore` zowel `data/` als alle `*.json`-bestanden. Voeg een meetbestand nooit met `git add -f` toe. `examples/VOORBEELD.multiap.json.voorbeeld` bevat uitsluitend synthetische netwerkgegevens en kan wel veilig worden gedeeld.

Automatische tests: `python3 -B -m unittest discover -v` en, met Node.js geïnstalleerd, `node tests/test_dashboard.cjs`. De startflow, scannerbuild, resultatenserver en browserweergave zijn op macOS gecontroleerd. De berekeningen worden met fictieve datasets getest. Voor een echte scan en controle van de locatietoegang gebruik je **Meer opties → Wi-Fi en locatietoegang controleren**.

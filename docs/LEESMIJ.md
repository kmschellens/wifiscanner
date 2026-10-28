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

`start.sh` is het enige startpunt. Het hoofdmenu kan een meting starten of hervatten, het dashboard openen, de systeemcontrole uitvoeren en de lokale helper opnieuw bouwen. De begeleide meetflow voert je met genummerde keuzes door vier stappen: Mac controleren, meetronde instellen, accesspoints voorbereiden en kamers meten.

De projectindeling is bewust eenvoudig:

- `start.sh`: centrale launcher.
- `app/`: interne scripts, Python-code, webinterface en Swift-broncode.
- `data/`: persoonlijke meetbestanden; deze map wordt door Git genegeerd.
- `.runtime/`: lokaal gebouwde macOS-app; deze map wordt door Git genegeerd.
- `docs/`: documentatie.
- `examples/`: uitsluitend geschoonde voorbeelddata.
- `tests/`: automatische tests.

**Bij de eerste meting** bouwt de applicatie automatisch `.runtime/WifiKamermeting.app` uit de bronbestanden in `app/`. Xcode zelf is niet verplicht; de Command Line Tools volstaan. macOS kan vragen om Location Services: **Allow While Using App** voor **WifiKamermeting**. Geef die toestemming, want zonder deze toestemming kan CoreWLAN de BSSID van *andere* AP's verhullen, ook al werken de Shortcuts voor je verbonden AP.

Controleer bij problemen **System Settings → Privacy & Security → Location Services → WifiKamermeting**. Verwijder/verplaats de `.app` liever niet nadat je deze eenmaal autorisatie hebt gegeven. Wijzigen/recompileren kan ertoe leiden dat macOS opnieuw toestemming vraagt.

Je bestaande Shortcuts heten nog steeds **`WiFi-SSID`** en **`WiFi-BSSID`**. Het Bash-script gebruikt ze om de *actuele verbinding* aan het begin en einde van de kamermeting vast te leggen.

Bij problemen kun je apart `./start.sh controle` uitvoeren. Als deze controle zowel RSSI als **verschillende BSSID's** teruggeeft, werkt de scan op jouw Mac. Zie je geen BSSID's of staat er `denied`, dan zijn de onafhankelijke AP-scans nog niet bruikbaar; het script verzint in dat geval géén signalen.

## 2. Meetronde

```bash
./start.sh
```

De applicatie stelt het huidige SSID voor, toont alle instellingen voordat de meting begint en laat tijdens iedere scan de verstreken tijd zien. Na een kamer verschijnt steeds hetzelfde menu:

1. Nieuwe kamer meten.
2. Vorige kamer opnieuw meten.
3. Accesspoint identificeren of benoemen.
4. Meetronde afronden.

Na iedere kamer schrijft het script het **complete JSON-bestand atomair** weg. Een afgebroken ronde kun je later via het startmenu hervatten, of expliciet met:

```bash
./start.sh meten --resume wifi-meting-YYYYMMDD-HHMMSS.json
```

### Accesspoints een naam geven

Na het kiezen van het SSID kun je eerst een **accesspoint-ronde** doen. Loop naar ieder fysiek accesspoint en start daar via het menu een korte identificatiescan. De gevonden BSSID's staan op signaalsterkte gesorteerd. Kies één nummer, of meerdere nummers als verschillende radio's/BSSID's bij hetzelfde fysieke apparaat horen, en geef ze samen een naam zoals `Overloop` of `AP kantoor`.

De koppeling wordt in het meetbestand opgeslagen en verschijnt automatisch in de terminal en het dashboard. Ook tijdens de kamerronde kun je via keuze 3 nog een accesspoint benoemen of een bestaande naam wijzigen. Omdat één fysiek accesspoint meerdere 2,4/5/6GHz-radio's kan hebben, voegt het programma BSSID's niet op basis van een gok automatisch samen.

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

Aan het einde van een meetronde biedt de terminalapp deze keuze automatisch aan. Los starten kan met het commando hierboven; de browser opent dan vanzelf op **http://127.0.0.1:8765**. De server zoekt automatisch alle `.json`-meetbestanden in `data/`. Het dashboard heeft:

- Grafiek met **alle BSSID's per kamer**, ieder een eigen kleur.
- Zelfgekozen accesspointnamen in legenda's, tabellen, grafieken en roamingsoverzichten.
- **Signaalmatrix**: één rij per BSSID, één kolom per kamer, met gemiddelde/minimum/maximum RSSI.
- Een sectie met **uitklapbare losse scans** per kamer.
- De bestaande grafieken voor de *verbonden* AP, roamings en vergelijking van oudere JSON-bestanden blijven beschikbaar.

Voor direct gebruik van `app/index.html` zonder server kun je de JSON-bestanden met de knop **Open JSON-bestanden** selecteren. De lokale server gebruikt Python 3 zonder externe pakketten en luistert uitsluitend op 127.0.0.1.

## 5. Privacy en beperkingen

De metingen verlaten jouw computer niet. De app gebruikt Location Services uitsluitend om macOS toestemming te laten geven voor Wi-Fi-identificaties; de code leest/schrijft geen geografische coördinaten. Dit is lokaal door jezelf te compileren, niet als vooraf gecompileerd programma ondertekend door een externe ontwikkelaar.

Meetbestanden kunnen SSID's, BSSID's, kamernamen, notities en tijdstippen bevatten. Daarom negeert `.gitignore` zowel `data/` als alle `*.json`-bestanden. Voeg een meetbestand nooit met `git add -f` toe. `examples/VOORBEELD.multiap.json.voorbeeld` bevat uitsluitend synthetische netwerkgegevens en kan wel veilig worden gedeeld.

**Getest:** syntax van Bash, Swift-broncode parsing, JavaScript-syntax en Python JSON-bewerking en AP-aggregatie met gesimuleerde datasets in een Linux-testomgeving. **Niet live getest op macOS 15.5:** Apple CoreWLAN is niet beschikbaar in deze omgeving. Controleer dus eerst `./start.sh controle` op je Mac.

# Muutosloki

Versiointi: pienet muutokset nostavat numeroa 0.1 -> 0.11 -> 0.12 ..., isommat muutokset 0.1 -> 0.2 -> ... -> 1.0.
Numero on tiedostossa `version.py` ja näkyy sovelluksen alareunassa sekä Excelin Tiedot-välilehdellä.

## 0.19
(Sisältää kaiken, mikä oli aiemmin kirjattu versioksi 0.18.)
- Lähikuvasta luetaan UIB:n lisäksi muutkin kentät, jos ne erottuvat siinä: tyhjä tai epävarma kenttä täydennetään lähikuvan varmalla luvulla, ja huomautukseen kirjataan "Lähikuvasta täydennetty: …" tai "Lähikuva varmisti: …". Jos lähikuvan luku poikkeaa alkuperäisestä, käytetään lähikuvan lukua, kenttä merkitään epävarmaksi ja molemmat luvut kirjataan huomautukseen.
- Lukuohjeeseen lisätty sääntö: lähempää otettu etiketin kuva, jossa on muitakin kenttiä, luetaan etiketiksi.
- Automaattinen lähetys: jos ruudulla ei ole huomautettavaa (ei "Kuvaa uudelleen" eikä "Sama rulla kuvattu useammin kuin kerran"), Excel lähtee sähköpostiin ilman painallusta. Jos huomautuksia on, "Lähetä Excel sähköpostiin" -painike jää käyttöön. Jo lähetettyä tilaa ei lähetetä uudelleen sivun päivityksessä, ja epäonnistunut lähetys ei toistu itsestään.

- Valintaruutu "Lähetä automaattisesti, kun huomautettavaa ei ole" (oletuksena päällä, valinta jää puhelimen muistiin). Ruksi pois: Excel lähtee vain painikkeesta.
- Otetut kuvat tallennetaan puhelimen muistiin (IndexedDB): lähettämättömät ja luetut kuvat säilyvät, vaikka näyttö sammuu tai selain lataa sivun uudelleen. Muisti tyhjenee, kun Excel on lähetetty. Kun aloitat uuden kuorman (eri tunniste), vanhan kuorman luetut kuvat poistuvat listalta.

- Kun Excel on jo lähetetty eikä kuormaan ole tullut muutoksia, sivun uudelleenlatauksessa ei enää näytetä "Valmis lähetettäväksi?" -kehotetta.

- Lähikuvat jonoon: lähikuva ei enää lähde heti. Kuvaaja voi ottaa kaikki tarvittavat lähikuvat peräkkäin ("✓ Lähikuva otettu, odottaa lukua"), ja ne luetaan yhdellä painalluksella ("Lue N lähikuvaa"). Jono säilyy puhelimen muistissa, ja saman rullan lähikuvan voi ottaa uudelleen.
- Korjaus: jos lähikuvan UIB oli sama kuin jo toisella rullalla, rivit yhdistyivät Excelissä ja rullia jäi vähemmän (3 -> 2). Nyt tällaista lähikuvaa ei käytetä, rullat säilyvät erillisinä ja kuvaajaa pyydetään ottamaan kyseisen rullan oma viivakoodi.

## 0.17
- Uusi kulku: kuvat luetaan ensin ("Lue kuvat"), eikä Excel lähde vielä sähköpostiin. Kuvat pysyvät sovelluksessa (✓ = luettu), ja lähikuvat voi lisätä ennen lopullista lähetystä. Excel lähtee vasta painikkeesta "Lähetä Excel sähköpostiin".
- Lähikuvan otto korjattu: tiedostokenttä on aina sivulla (aiemmin se luotiin napautuksessa ja valinta saattoi kadota kameran avautuessa). Jos sivu latautuu uudelleen kameran jälkeen, sovellus palaa kuorman tilaan tunnisteen perusteella.
- Sähköpostin lähetyskytkin poistettu (lähetys on aina oma vaihe).

## 0.16
- Lukuohjeeseen lisätty Anjalankoski Mills -etiketin asettelu (UNIT NUMBER, WIDTH, LENGTH, GRAMMAGE, THICKNESS, DIAMETER, CORE, WEIGHT) ja sääntö: epäselvässä kuvassa kentät saa täyttää asettelun paikan mukaan, mutta ne merkitään epävarmoiksi ja huomautukseen tulee maininta "Täytetty etiketin asettelun mukaan, epävarma". THICKNESS (paksuus) kirjataan vain huomautukseen. Muiden tehtaiden asettelut lisätään myöhemmin.

## 0.15
- Kuvien määrä näkyy ennen lähetystä ("Valittu N kuvaa"), jotta tuplat ja puuttuvat kuvat huomaa ajoissa.
- "Kuvaa uudelleen" -laatikossa näkyy pikkukuva siitä kuvasta, jota ilmoitus koskee. Kuvaa napauttamalla se aukeaa isompana, ja uusi napautus sulkee sen.
- Uudelleenyritykset 4 -> 3.
- Valinnainen Haiku-ensin-luku lisätty, mutta se on oletuksena pois (`FAST_MODEL=off`), koska vertailussa se ohitti yhden epävarman rullanumeron. Luku toimii siis kuten versiossa 0.14.

## 0.14
- "Lataa Excel" -painike piilotettu kuvaajalta (Excel tulee sähköpostiin).
- Jos samasta rullasta on useampi kuva, kuvaajalle näytetään maininta, jotta hän huomaa mahdollisen kuvaamatta jääneen rullan.

## 0.13
- Kuvaajalle näytetään vain asiat, jotka korjaantuvat kuvaamalla uudelleen (UIB puuttuu tai ristiriita, etikettiä ei näy). Tarkistettavat rivit, painoerot ja huomiot jäävät vain sähköpostin yhteenvetoon ja Exceliin.

## 0.12
- Selain ei enää välimuistita sivua: päivitykset näkyvät heti (Cache-Control: no-cache).

## 0.11
- Nimi-kenttä: nimi tulee vain Excel-liitteeseen (Tiedot-välilehti ja tiedoston tekijä).
- Alareunassa tekijä (Samuli Riisiö) ja versionumero.
- Tiedot-välilehti: kuorma, nimi, luontiaika (Suomen aika), versio.

## 0.1
- Ensimmäinen toimiva versio: kuvat -> Excel -> sähköposti, lähikuvakorjaus UIB:lle.
- Korjaus: API-kutsu ei pakota työkalun käyttöä (malli ei tue sitä).

# Muutosloki

Versiointi: pienet muutokset nostavat numeroa 0.1 -> 0.11 -> 0.12 ..., isommat muutokset 0.1 -> 0.2 -> ... -> 1.0.
Numero on tiedostossa `version.py` ja näkyy sovelluksen alareunassa sekä Excelin Tiedot-välilehdellä.

## 0.15
- Kustannusten pienentäminen: kuvat luetaan ensin halvalla Haiku-mallilla pienemmästä kuvasta (1600 px). Vain epävarmat kuvat (puuttuva tai epävarma kenttä, viivakoodi ja alla oleva numero eivät täsmää, ei etikettiä) luetaan uudelleen Sonnet-mallilla 2000 px:n kuvasta.
- Uudelleenyritykset 4 -> 3.
- **Jos ongelmia ilmaantuu** (virheellisiä lukuja): aseta Renderissä `FAST_MODEL=off`, jolloin toimitaan kuten versiossa 0.14. Kuvan kokoa voi nostaa muuttujalla `API_IMAGE_MAX_SIDE=2000`.

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

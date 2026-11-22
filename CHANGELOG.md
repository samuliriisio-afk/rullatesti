# Muutosloki

Versiointi: pienet muutokset nostavat numeroa 0.1 -> 0.11 -> 0.12 ..., isommat muutokset 0.1 -> 0.2 -> ... -> 1.0.
Numero on tiedostossa `version.py` ja näkyy sovelluksen alareunassa sekä Excelin Tiedot-välilehdellä.

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

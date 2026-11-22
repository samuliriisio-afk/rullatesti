# Muutosloki

Versiointi: pienet muutokset nostavat numeroa 0.1 -> 0.11 -> 0.12 ..., isommat muutokset 0.1 -> 0.2 -> ... -> 1.0.
Numero on tiedostossa `version.py` ja näkyy sovelluksen alareunassa sekä Excelin Tiedot-välilehdellä.

## 0.12
- Selain ei enää välimuistita sivua: päivitykset näkyvät heti (Cache-Control: no-cache).

## 0.11
- Nimi-kenttä: nimi tulee vain Excel-liitteeseen (Tiedot-välilehti ja tiedoston tekijä).
- Alareunassa tekijä (Samuli Riisiö) ja versionumero.
- Tiedot-välilehti: kuorma, nimi, luontiaika (Suomen aika), versio.

## 0.1
- Ensimmäinen toimiva versio: kuvat -> Excel -> sähköposti, lähikuvakorjaus UIB:lle.
- Korjaus: API-kutsu ei pakota työkalun käyttöä (malli ei tue sitä).

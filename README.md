# Rullat Exceliin

Puhelimella otetut rullaetikettien kuvat → Excel → sähköpostiin (oletus: samuli.riisio@nurminenlogistics.com).

## Miten se toimii
1. Avaat sovelluksen puhelimen selaimessa, kirjoitat kuorman tunnisteen (esim. FFF111) ja otat kuvat.
2. Palvelin lukee jokaisesta kuvasta Code 128 -viivakoodin (oma lukija) ja kysyy Claudelta etiketin tekstin.
   UIB varmistetaan: viivakoodi ja alla oleva numero täsmäävät = varma. Ilman viivakoodia rivi merkitään Tarkistettavaksi.
3. Excel (`kuorma_<tunniste>.xlsx`, välilehdet Rullat ja Kuvat, automaattitarkistukset) rakennetaan ja lähetetään sähköpostiin.
   Sovellus näyttää myös ruudulla tarkistettavat rivit ja pyytää lähikuvan viivakoodista, jos UIB jäi lukematta.
4. Sama tunniste = sama kuorma. Lisäkuvat luetaan vain kerran (sama kuva tunnistetaan), ja Excel rakennetaan koko kuormasta uudelleen.

## Käyttöönotto (Docker)
```bash
cp .env.example .env      # täytä ANTHROPIC_API_KEY, APP_CODE ja sähköpostin asetukset
docker build -t rullat .
docker run -d --restart=always --env-file .env -v rullat-data:/data -p 8000:8000 rullat
```
Puhelinkamera vaatii **https**-yhteyden. Laita sovelluksen eteen https-välityspalvelin
(esim. Caddy, Cloudflare Tunnel tai palveluntarjoajan oma https) ja avaa osoite puhelimella.
Valitse selaimen valikosta "Lisää aloitusnäyttöön", niin se toimii kuin sovellus.

Ilman Dockeria: `pip install -r requirements.txt` ja `gunicorn -w 1 --threads 8 --timeout 300 -b 0.0.0.0:8000 app:app`.
Aja aina vain yhdellä prosessilla (`-w 1`), koska kuormien lukitus on prosessin muistissa.

## Asetukset (.env)
| Muuttuja | Merkitys |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API -avain (console.anthropic.com). Käyttö laskutetaan kuvien mukaan. |
| `CLAUDE_MODEL` | oletus `claude-sonnet-5-5`; `claude-opus-5-5` on tarkempi mutta kalliimpi |
| `APP_CODE` | käyttökoodi, jonka sovellus kysyy puhelimessa. Pakollinen, jos palvelin on julkinen. |
| `MAIL_TO` | vastaanottaja (oletus samuli.riisio@nurminenlogistics.com) |
| `MAIL_FROM` | lähettäjä. Resendissä vahvistetun domainin osoite, SMTP:ssä yleensä sama kuin käyttäjä |
| `RESEND_API_KEY` | helpoin lähetystapa (resend.com), tai |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` | oma SMTP (esim. Microsoft 365: smtp.office365.com, 587; SMTP AUTH pitää sallia IT:n kautta) |
| `DATA_DIR` | tallennuskansio (kuvat, tulokset, Excelit) |

## Tiedostot
- `app.py` Flask-palvelin ja rajapinnat, `static/` puhelinsovellus (PWA)
- `pipeline.py` kuorman käsittely ja UIB-logiikka, `extract.py` Clauden kutsu ja lukuohjeet (muokkaa `SYSTEM`-tekstiä, jos etikettityyppejä tulee lisää)
- `bardecode.py` viivakoodinlukija, `build_rullat.py` Excelin rakentaja, `mailer.py` sähköposti

## Huomioita
- Kuvia ja Exceleitä ei poisteta automaattisesti. Siivoa `DATA_DIR/kuormat` tarvittaessa.
- Sähköpostiin lähtevä Excel ei ole tarkistettu: Tarkistettava-rivit pitää katsoa läpi ennen käyttöä.
- Kaavat lasketaan Excelissä avattaessa. Sähköpostin esikatselu voi näyttää tarkistussarakkeet tyhjinä.

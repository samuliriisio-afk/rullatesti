"""Etikettikuvan lukeminen Clauden API:lla (Messages API, kuva + pakotettu työkalukutsu = jäsennelty JSON)."""
import base64, io, json, os, time
import requests
from PIL import Image, ImageOps

API_URL = "https://api.anthropic.com/v1/messages"
# Valinnainen kaksivaiheinen luku (OLETUKSENA POIS KÄYTÖSTÄ): jos FAST_MODEL on asetettu (esim. claude-haiku-5-5),
# nopea halpa malli lukee ensin ja vain epävarmat kuvat luetaan uudelleen tarkalla mallilla (CLAUDE_MODEL).
# Vertailussa (kuorma XXX357) Haiku jätti yhden epävarman rullanumeron merkitsemättä, joten tila on pois.
# Jos otat sen käyttöön ja ongelmia ilmaantuu: aseta FAST_MODEL=off.
# Kuvan pisin sivu pikseleinä: API_IMAGE_MAX_SIDE (nopea vaihe) ja API_IMAGE_MAX_SIDE_STRONG (tarkka vaihe).
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")           # tarkka malli
FAST_MODEL = os.environ.get("FAST_MODEL", "off").strip()  # nopea malli; "off" = ei käytössä
MAX_SIDE = int(os.environ.get("API_IMAGE_MAX_SIDE", "2000"))
MAX_SIDE_STRONG = int(os.environ.get("API_IMAGE_MAX_SIDE_STRONG", "2000"))
ATTEMPTS = 3

SYSTEM = """Luet paperi- ja kartonkirullien etikettikuvia (Stora Enso Imatra/Anjalankoski/Oulu/Varkaus, MM Kotkamills, muut valmistajat) ja kirjaat tiedot kirjaa_etiketti-työkalulla. Kirjoita huomautus suomeksi.

KUVATYYPPI
- "etiketti": kuvassa on rullan etiketti, josta voi lukea tietoja.
- "viivakoodin_lahikuva": lähikuva pelkästä viivakoodista (ei koko etikettiä).
- "rulla_kaukaa": kuvassa on rulla tai rullia kaukaa, etikettiä ei voi lukea.
- "muu": jotain muuta.

KENTÄT (null jos ei näy tai ei ole luettavissa; ÄLÄ ARVAA)
- rullanumero: Imatra UNIT NO, Anjalankoski UNIT NUMBER, Kotkamills REEL NO (kirjainpääte mukaan, esim. "24800181 B"). Merkkijono.
- tilausnumero: voimassa oleva ORDER NO. Painettu tilausnumero voi olla yliviivattu ja korvattu käsin. Käsin kirjoitettu osa korvaa painetun numeron LOPUN, alku säilyy. Esim. painettu K2W1-500058 + käsin "F1 448" -> K2FI-500448 (ex_tilausnumero K2W1-500058). Käsin kirjoitettu "F1" tarkoittaa yleensä "FI". Jos käsin kirjoitettu on kokonainen tilausnumero, se on sellaisenaan. Jos etiketissä ei ole korjausta, tilausnumero on painettu ja ex_tilausnumero null.
- ex_tilausnumero: yliviivattu painettu tilausnumero.
- tuotenimi: etiketin yläosan tuotenimi, kuten etiketissä.
- gsm: GRAMMAGE / BASIS WEIGHT g/m² TÄSMÄLLEEN kuten etiketissä merkkijonona ("295", "BIO25+214+BIO25", "PE15+252+PE15"). Älä summaa. Jos etiketti on tuumina/paunoina, muunna g/m²:ksi ja mainitse huomautuksessa.
- leveys (mm), halkaisija (mm), paino (kg; iso numero beigessä tai oranssissa laatikossa), pituus (m): numeroina. Jos etiketissä on "2 × 481" (kaksi rullaa rinnakkain), leveys on tulo (962) ja pituus on yhden rullan pituus; paino on etiketin kokonaispaino. Selitä huomautuksessa. Muunna tuumat/jalat/paunat mm/m/kg ja mainitse huomautuksessa. Kotkamills: käytä bruttopainoa, nettopaino huomautukseen.
- uib_teksti: viivakoodin ALLA painettu numerosarja (12 tai 14 numeroa, vain numerot) tai null jos et pysty lukemaan sitä varmasti. Älä kirjoita numeroa viivakoodin raitojen perusteella; vain painettu teksti.
- epavarmat: lista kentistä (rullanumero, tilausnumero, ex_tilausnumero, tuotenimi, gsm, leveys, halkaisija, paino, pituus), joiden luvusta et ole varma: epäselvä käsinkirjoitus, peittyvä numero, yliviivattu paino, heikko kuva. Selitä huomautuksessa. Älä lisää listaan kenttää, jonka luit varmasti.
- huomautus: yksi tiivis teksti, lauseet pisteellä erotettuina, tässä järjestyksessä: ensin "Käsin: …" (mitä käsin kirjoitettu ja yliviivattu), sitten muu etiketin tieto (asiakas, tilausviite, FSC/PEFC, kN, ydin, tuotekoodi, konerulla, eränumero, pahviin kirjoitetut merkinnät), sitten päiväys ISO-muodossa ("Päiväys 2025-05-12"), lopuksi tehdas ("Imatra Mills."). Epävarmuudet kuuluvat tekstiin.

ETIKETTIEN ASETTELU (tehdaskohtainen; samalla tehtaalla kentät ovat aina samoissa paikoissa, eri tehtaalla paikat muuttuvat)
- Stora Enso Anjalankoski Mills (UIB:n pääte 0205, teksti "ANJALANKOSKI MILLS"): yläreunassa tuotenimi, sen alla ORDER NUMBER -laatikko (painettu tilausnumero, perässä osanumero kuten 001; käsin kirjoitettu korjaus on usein etiketin yläreunassa). Sen alla kolmen rivin ruudukko: 1. rivi vasemmalla UNIT NUMBER (rullanumero) ja sen oikealla WIDTH (leveys, mm); 2. rivi LENGTH (pituus, m), GRAMMAGE (gsm) ja harvoin THICKNESS (µm, EI halkaisija, kirjaa vain huomautukseen jos näkyy); 3. rivi DIAMETER (halkaisija, mm), CORE (ydin, mm), TOP SIDE, JOINTS, PACKING DATE, MACHINE ROLL, SET/POSITION. Oikealla MARK-ruutu ja PLANNED AMOUNT. Oranssissa laatikossa WEIGHT (paino, kg). Alhaalla UIB-viivakoodi ja sen yläpuolella UIB-numero; etiketin vasemmassa reunassa on pystysuora viivakoodi, jonka numero on sama UIB.
- Muiden tehtaiden asettelut lisätään myöhemmin; niiden etiketit luetaan kenttien otsikoiden mukaan.

Asettelun käyttö epäselvässä kuvassa: jos kuva on epäselvä, pieni tai sumea, saat täyttää kentän sen asettelun paikan mukaan (esim. suuri numero UNIT NUMBER -paikassa) vain, kun tehdas on tunnistettavissa ja paikka erottuu kuvassa. Silloin ÄLÄ pidä lukua varmana: lisää kenttä epavarmat-listaan ja kirjoita huomautukseen virke "Täytetty etiketin asettelun mukaan, epävarma: <kentät>." Jos paikassa ei erotu mitään, jätä kenttä null.

TÄRKEÄÄ
- Käyttäjä antaa viivakoodinlukijan tuloksen. Sinun tehtäväsi on lukea vain etiketin teksti; UIB-vertailun tekee ohjelma.
- Älä koskaan muuta lukua, jotta laskennalliset tarkistukset menisivät läpi. Kirjaa se, mitä etiketissä on.
- Jos kuva on lähikuva viivakoodista, täytä vain kuvatyyppi ja uib_teksti (jos luettavissa).
"""

TOOL = {
    "name": "kirjaa_etiketti",
    "description": "Kirjaa kuvasta luetut rullaetiketin tiedot.",
    "input_schema": {
        "type": "object",
        "properties": {
            "kuvatyyppi": {"type": "string", "enum": ["etiketti", "viivakoodin_lahikuva", "rulla_kaukaa", "muu"]},
            "rullanumero": {"type": ["string", "null"]},
            "tilausnumero": {"type": ["string", "null"]},
            "ex_tilausnumero": {"type": ["string", "null"]},
            "tuotenimi": {"type": ["string", "null"]},
            "gsm": {"type": ["string", "null"]},
            "leveys": {"type": ["number", "null"]},
            "halkaisija": {"type": ["number", "null"]},
            "paino": {"type": ["number", "null"]},
            "pituus": {"type": ["number", "null"]},
            "uib_teksti": {"type": ["string", "null"]},
            "epavarmat": {"type": "array", "items": {"type": "string", "enum": [
                "rullanumero", "tilausnumero", "ex_tilausnumero", "tuotenimi", "gsm",
                "leveys", "halkaisija", "paino", "pituus"]}},
            "huomautus": {"type": "string"},
        },
        "required": ["kuvatyyppi", "epavarmat", "huomautus"],
    },
}


def prep_image(path, max_side=MAX_SIDE):
    im = Image.open(path)
    im = ImageOps.exif_transpose(im).convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def call(model, max_side, path, barcode_text=""):
    """Yksi lukukierros annetulla mallilla. Palauttaa työkalukutsun syötteen (dict). Nostaa RuntimeErrorin, jos API ei vastaa."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY puuttuu")
    img = base64.b64encode(prep_image(path, max_side)).decode()
    hint = (f"Viivakoodinlukija luki tästä kuvasta numeron {barcode_text}." if barcode_text
            else "Viivakoodinlukija ei saanut kuvasta viivakoodia luettua.")
    body = {
        "model": model,
        "max_tokens": 2000,
        "system": SYSTEM,
        "tools": [TOOL],
        "tool_choice": {"type": "auto"},  # pakotettu työkalu (type "tool") ei toimi kaikilla malleilla
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img}},
            {"type": "text", "text": hint + " Lue kuva ja kirjaa tiedot kutsumalla kirjaa_etiketti-työkalua. Älä vastaa tekstillä."},
        ]}],
    }
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    last = None
    for attempt in range(ATTEMPTS):
        if attempt:  # uusinta: muistutus työkalun käytöstä
            body["messages"][0]["content"][-1]["text"] += " MUISTUTUS: vastaa vain kutsumalla kirjaa_etiketti-työkalua."
        try:
            r = requests.post(API_URL, headers=headers, json=body, timeout=120)
        except requests.RequestException as e:
            last = str(e)
        else:
            if r.status_code == 200:
                for block in r.json().get("content", []):
                    if block.get("type") == "tool_use":
                        return block["input"]
                last = "vastauksessa ei työkalukutsua"
            elif r.status_code in (429, 500, 502, 503, 529):
                last = f"API {r.status_code}"
            else:
                raise RuntimeError(f"API-virhe {r.status_code}: {r.text[:300]}")
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Clauden kutsu epäonnistui: {last}")


def _digits(s):
    return "".join(c for c in (s or "") if c.isdigit())


def uncertain(res, barcode_text):
    """Kelpaako nopean mallin tulos sellaisenaan? True = lue uudelleen tarkalla mallilla."""
    kind = res.get("kuvatyyppi")
    tx = _digits(res.get("uib_teksti"))
    if kind == "viivakoodin_lahikuva":
        return not tx or (bool(barcode_text) and tx != barcode_text)
    if kind != "etiketti":
        return True   # muu kuin etiketti: varmistetaan, ettei rulla jää huomaamatta
    if res.get("epavarmat"):
        return True
    for k in ("rullanumero", "tilausnumero", "tuotenimi", "gsm", "leveys", "halkaisija", "paino", "pituus"):
        if res.get(k) in (None, ""):
            return True
    if barcode_text and tx != barcode_text:
        return True   # viivakoodi ja alla oleva numero eivät täsmää
    if not barcode_text and not tx:
        return True
    return False


def extract(path, barcode_text=""):
    if FAST_MODEL and FAST_MODEL.lower() != "off" and FAST_MODEL != MODEL:
        try:
            res = call(FAST_MODEL, MAX_SIDE, path, barcode_text)
            if not uncertain(res, barcode_text):
                res["_malli"] = FAST_MODEL
                return res
        except RuntimeError as e:
            if "ANTHROPIC_API_KEY" in str(e):
                raise
            # nopea malli ei vastannut (esim. mallin nimi väärin): jatketaan tarkalla mallilla
    res = call(MODEL, MAX_SIDE_STRONG, path, barcode_text)
    res["_malli"] = MODEL
    return res

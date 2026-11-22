"""Etikettikuvan lukeminen Clauden API:lla (Messages API, kuva + pakotettu työkalukutsu = jäsennelty JSON)."""
import base64, io, json, os, time
import requests
from PIL import Image, ImageOps

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
MAX_SIDE = int(os.environ.get("API_IMAGE_MAX_SIDE", "2000"))

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


def extract(path, barcode_text=""):
    """Palauttaa työkalukutsun syötteen (dict). Nostaa RuntimeErrorin, jos API ei vastaa."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY puuttuu")
    img = base64.b64encode(prep_image(path)).decode()
    hint = (f"Viivakoodinlukija luki tästä kuvasta numeron {barcode_text}." if barcode_text
            else "Viivakoodinlukija ei saanut kuvasta viivakoodia luettua.")
    body = {
        "model": MODEL,
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
    for attempt in range(4):
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

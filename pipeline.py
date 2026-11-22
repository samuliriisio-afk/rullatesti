"""Kuorman käsittely: kuvat -> luku (viivakoodi + Claude) -> rivit -> Excel -> yhteenveto -> sähköposti."""
import hashlib, io, json, os, re, threading, time
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps

import bardecode, build_rullat as B, extract as X, mailer
from version import VERSION

DATA = Path(os.environ.get("DATA_DIR", Path(__file__).parent / "data")) / "kuormat"
PLACEHOLDER = "EI-LUETTAVISSA-"
_locks, _guard = {}, threading.Lock()
_wlock2 = threading.Lock()


def safe_name(s):
    s = re.sub(r"[^A-Za-z0-9_-]+", "-", (s or "").strip()).strip("-")[:40]
    if not s:
        raise ValueError("Kuorman tunniste puuttuu")
    return s


def lock_for(t):
    with _guard:
        return _locks.setdefault(t, threading.Lock())


def ld(t):
    d = DATA / t
    (d / "kuvat").mkdir(parents=True, exist_ok=True)
    (d / "tulokset").mkdir(exist_ok=True)
    return d


def read_json(p, default):
    try:
        return json.loads(Path(p).read_text("utf8"))
    except Exception:
        return default


_wlock = threading.Lock()


def write_json(p, obj):
    with _wlock:
        tmp = Path(f"{p}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), "utf8")
        tmp.replace(p)


def set_status(t, **kw):
    d = ld(t)
    with _wlock2:
        st = read_json(d / "tila.json", {})
        st.update(kw)
        st["paivitetty"] = time.time()
        write_json(d / "tila.json", st)


def set_meta(t, **kw):
    d = ld(t)
    with _wlock2:
        m = read_json(d / "meta.json", {})
        m.update(kw)
        write_json(d / "meta.json", m)


def get_status(t):
    return read_json(ld(t) / "tila.json", {"tila": "tuntematon"})


def digits(s):
    return re.sub(r"\D", "", s or "")


# ---------- kuvien vastaanotto ----------
def add_image(t, data, name, kohde=None):
    """Tallentaa kuvan kuormaan. Palauttaa avaimen tai None, jos sama kuva on jo olemassa."""
    d = ld(t)
    idx = read_json(d / "indeksi.json", {"kuvat": []})
    sha = hashlib.sha256(data).hexdigest()
    if any(i["sha"] == sha for i in idx["kuvat"]):
        return None
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    key = f"k{len(idx['kuvat']) + 1:02d}"
    im.save(d / "kuvat" / f"{key}.jpg", "JPEG", quality=92)
    idx["kuvat"].append({"key": key, "sha": sha, "nimi": name, "aika": time.time(), "kohde": kohde})
    write_json(d / "indeksi.json", idx)
    return key


# ---------- yksittäisen kuvan luku ----------
def process_image(t, key):
    d = ld(t)
    path = str(d / "kuvat" / f"{key}.jpg")
    out = d / "tulokset" / f"{key}.json"
    bc = ""
    try:
        bc = bardecode.read_number(path)
    except Exception:
        bc = ""
    res = X.extract(path, bc)
    res["bc"] = bc
    write_json(out, res)
    return res


# ---------- rivien rakennus ----------
def make_row(key, path, res):
    bc, tx = res.get("bc") or "", digits(res.get("uib_teksti"))
    ep = list(res.get("epavarmat") or [])
    hm = (res.get("huomautus") or "").strip()
    if bc:
        uib, src = bc, "Viivakoodi"
        if tx and tx != bc:
            ep.append("uib")
            hm = (hm + f" UIB: viivakoodi {bc}, viivakoodin alla oleva teksti {tx}: tarkista.").strip()
    elif tx:
        uib, src = tx, "Teksti"
        ep.append("uib")
    else:
        uib, src = PLACEHOLDER + key, "Teksti"
        ep.append("uib")
        hm = (hm + " UIB:tä ei saatu luettua kuvasta: otettava lähikuva viivakoodista suoraan edestä.").strip()
    return {"kuvatiedosto": key, "kuva": path, "rullanumero": res.get("rullanumero"),
            "tilausnumero": res.get("tilausnumero"), "ex_tilausnumero": res.get("ex_tilausnumero") or "",
            "tuotenimi": res.get("tuotenimi") or "(ei etiketissä)", "gsm": res.get("gsm"),
            "leveys": res.get("leveys"), "halkaisija": res.get("halkaisija"), "paino": res.get("paino"),
            "pituus": res.get("pituus"), "uib": uib, "uib_lahde": src, "epavarmat": sorted(set(ep)),
            "huomautus": hm}


def build_rows(t):
    d = ld(t)
    idx = read_json(d / "indeksi.json", {"kuvat": []})
    rows, attach, notes, fixes = [], [], [], []
    tuplat = {}   # rivin kuvatiedosto -> kuvat, joissa sama rulla on useammin kuin kerran
    retake = {}   # kuva -> {kuva, rulla, syy, nappi}: vain asiat, jotka kuvaaja voi korjata kuvaamalla uudelleen
    for im in idx["kuvat"]:
        key = im["key"]
        res = read_json(d / "tulokset" / f"{key}.json", None)
        path = str(d / "kuvat" / f"{key}.jpg")
        if res is None:
            notes.append(f"Kuvaa {key} ei saatu luettua (virhe tai kesken).")
            continue
        if im.get("kohde"):
            fixes.append((im, res, path))
            continue
        kind = res.get("kuvatyyppi")
        if kind == "etiketti":
            row = make_row(key, path, res)
            bc0, tx0 = res.get("bc") or "", digits(res.get("uib_teksti"))
            if bc0 and tx0 and bc0 != tx0:
                retake[key] = {"kuva": key, "rulla": row.get("rullanumero"), "syy": "Viivakoodi ja sen alla oleva numero eivät täsmää", "nappi": True}
            same = next((r for r in rows if not str(row["uib"]).startswith(PLACEHOLDER) and r["uib"] == row["uib"]), None)
            if same:   # sama rulla kuvattu uudelleen: liitetään lisäkuvaksi
                same.setdefault("lisakuvat", []).append({"tiedosto": key, "kuva": path, "kuvaus": "sama rulla, toinen kuva"})
                if row["uib_lahde"] == "Viivakoodi" and same["uib_lahde"] != "Viivakoodi":   # toinen kuva varmisti UIB:n viivakoodilla
                    same["uib_lahde"] = "Viivakoodi"
                    same["epavarmat"] = [e for e in same["epavarmat"] if e != "uib"]
                tuplat.setdefault(same["kuvatiedosto"], [same["kuvatiedosto"]]).append(key)
            else:
                rows.append(row)
        elif kind == "viivakoodin_lahikuva":
            u = res.get("bc") or digits(res.get("uib_teksti"))
            if u:
                attach.append({"uib": u, "lisakuvat": [{"tiedosto": key, "kuva": path, "kuvaus": "viivakoodin lähikuva"}]})
            else:
                notes.append(f"Lähikuvasta {key} ei saatu viivakoodia luettua.")
                retake[key] = {"kuva": key, "rulla": None, "syy": "Lähikuvasta ei saatu viivakoodia luettua", "nappi": False}
        else:
            notes.append(f"Kuvaa {key} ei käytetty ({'rulla kaukaa' if kind == 'rulla_kaukaa' else 'ei etikettiä'}).")
            retake[key] = {"kuva": key, "rulla": None, "syy": "Kuvassa ei näy etikettiä luettavasti", "nappi": False}
    for im, res, path in fixes:
        row = next((r for r in rows if r["kuvatiedosto"] == im["kohde"]), None)
        bc, tx = res.get("bc") or "", digits(res.get("uib_teksti"))
        if row is None:
            notes.append(f"Lähikuvan {im['key']} kohderullaa {im['kohde']} ei löytynyt.")
            continue
        if not (bc or tx):
            notes.append(f"Lähikuvasta {im['key']} ei saatu UIB:tä luettua (rulla {row.get('rullanumero')}).")
            retake[im["kohde"]] = {"kuva": im["kohde"], "rulla": row.get("rullanumero"), "syy": "Lähikuvasta ei saatu UIB:tä luettua", "nappi": True}
            row.setdefault("lisakuvat", []).append({"tiedosto": im["key"], "kuva": path, "kuvaus": "lähikuva (ei luettu)"})
            continue
        row["uib"], row["uib_lahde"] = (bc or tx), ("Viivakoodi" if bc else "Teksti")
        retake.pop(im["kohde"], None)
        row["epavarmat"] = [e for e in row["epavarmat"] if e != "uib"] + (["uib"] if (not bc) else [])
        row["huomautus"] = row["huomautus"].replace(
            "UIB:tä ei saatu luettua kuvasta: otettava lähikuva viivakoodista suoraan edestä.", "UIB luettu lähikuvasta.").strip()
        row.setdefault("lisakuvat", []).append({"tiedosto": im["key"], "kuva": path, "kuvaus": "viivakoodin lähikuva"})
    kaksoiskuvat = [{"rulla": next((r.get("rullanumero") for r in rows if r["kuvatiedosto"] == k), None), "kuvia": len(v)}
                    for k, v in tuplat.items()]
    return rows, attach, notes, list(retake.values()), kaksoiskuvat


def make_info(t, kuorma_nimi):
    meta = read_json(ld(t) / "meta.json", {})
    return [("Kuorma", kuorma_nimi), ("Nimi", meta.get("nimi") or ""),
            ("Luotu", datetime.now(ZoneInfo("Europe/Helsinki")).strftime("%Y-%m-%d %H:%M")), ("Sovelluksen versio", VERSION)]


def build_excel(t, rows, attach, kuorma_nimi):
    out = ld(t) / f"kuorma_{t}.xlsx"
    params = dict(B.DEFAULTS)
    new = [B.norm_row(r) for r in rows] + [B.norm_row(a) for a in attach]
    merged = []
    warn = [e for e in B.merge(merged, new)]
    B.build(merged, params, str(out), kuorma_nimi, info=make_info(t, kuorma_nimi))
    return out, merged, warn, params


def summarize(t, merged, warn, params, notes):
    tark, ei_ok, ilman_uib = [], [], []
    for r in merged:
        label = f"rulla {r.get('rullanumero') or '?'} ({r.get('kuvatiedosto')})"
        reasons = []
        if r["epavarmat"]:
            reasons.append("epävarma: " + ", ".join(r["epavarmat"]))
        if r["uib_lahde"] != "Viivakoodi":
            reasons.append("UIB ei viivakoodista")
        if reasons:
            tark.append({"rulla": label, "syy": "; ".join(reasons)})
        st = B.calc_checks(r, params)[3]
        if st != B.ST_OK:
            ei_ok.append({"rulla": label, "syy": st})
        if str(r.get("uib", "")).startswith(PLACEHOLDER):
            ilman_uib.append({"kuva": r["kuvatiedosto"], "rulla": r.get("rullanumero")})
    uibs = {len(str(r["uib"])) for r in merged if not str(r["uib"]).startswith(PLACEHOLDER)}
    huomiot = list(notes)
    if len(uibs) > 1:
        huomiot.append("Kuormassa on eri pituisia viivakoodeja: " + ", ".join(str(n) for n in sorted(uibs)) + " numeroa.")
    for w in warn:
        if w["kind"] in ("puuttuu", "tupla", "lisakuva_ei_rullaa"):
            huomiot.append(w["text"])
    return {"rullia": len(merged), "paino_yht": sum(int(r["paino"]) for r in merged if isinstance(r.get("paino"), (int, float))),
            "tarkistettavat": tark, "paino_ei_ok": ei_ok, "ilman_uib": ilman_uib, "huomiot": huomiot}


def uudelleen_lista(summary, retake):
    """Kuvaajalle näytettävät asiat: vain ne, jotka korjaantuvat kuvaamalla uudelleen."""
    out = [{"kuva": x["kuva"], "rulla": x["rulla"], "syy": "UIB puuttuu", "nappi": True} for x in summary["ilman_uib"]]
    seen = {x["kuva"] for x in out}
    out += [x for x in retake if x["kuva"] not in seen]
    return out


def mail_text(t, s, paivitys):
    L = [f"Kuorma {t}: {s['rullia']} rullaa, paino yhteensä {s['paino_yht']} kg." + (" (päivitetty versio)" if paivitys else ""), ""]
    if s["ilman_uib"]:
        L.append("UIB puuttuu (otettava viivakoodista lähikuva): " + ", ".join(f"rulla {x['rulla'] or '?'}" for x in s["ilman_uib"]))
    if s["tarkistettavat"]:
        L.append("Tarkistettavat rivit:")
        L += [f"  - {x['rulla']}: {x['syy']}" for x in s["tarkistettavat"]]
    if s["paino_ei_ok"]:
        L.append("Automaattitarkistus ei mennyt läpi:")
        L += [f"  - {x['rulla']}: {x['syy']}" for x in s["paino_ei_ok"]]
    if s["huomiot"]:
        L.append("Huomiot:")
        L += [f"  - {h}" for h in s["huomiot"]]
    if not (s["ilman_uib"] or s["tarkistettavat"] or s["paino_ei_ok"] or s["huomiot"]):
        L.append("Kaikki rivit luettiin varmasti ja automaattitarkistus meni läpi.")
    L += ["", "Excel on liitteenä. Tarkista rivit ennen käyttöä."]
    return "\n".join(L)


def _mail(t, summary, out, merged, params):
    """Lähettää Excelin sähköpostiin. Palauttaa tilarivin ruudulle."""
    d = ld(t)
    first = not read_json(d / "tila.json", {}).get("lahetetty_kerran")
    try:
        size_mb = out.stat().st_size / 1e6
        attach_path = out
        if size_mb > 20:  # liian iso liite: lähetä kevyt versio ilman kuvia
            light = d / f"kuorma_{t}_kevyt.xlsx"
            B.build(merged, params, str(light), t, ilman_kuvia=True, info=make_info(t, t))
            attach_path = light
        mailer.send(f"Rullakuorma {t}: {summary['rullia']} rullaa" + ("" if first else " (päivitetty)"),
                    mail_text(t, summary, not first), str(attach_path))
        return f"Lähetetty osoitteeseen {mailer.MAIL_TO}"
    except Exception as e:
        return "Sähköpostin lähetys epäonnistui: " + str(e)


def send_mail(t):
    """Lähettää kuorman nykyisen Excelin sähköpostiin (kuvaaja painaa lopuksi 'Lähetä Excel')."""
    with lock_for(t):
        d = ld(t)
        st = read_json(d / "tila.json", {})
        if st.get("tila") != "valmis" or not st.get("yhteenveto"):
            raise RuntimeError("Kuorma ei ole valmis")
        out = d / f"kuorma_{t}.xlsx"
        rows, attach, notes, retake, kaksoiskuvat = build_rows(t)
        _, merged, warn, params = build_excel(t, rows, attach, t)
        msg = _mail(t, st["yhteenveto"], out, merged, params)
        extra = {"lahetetty_kerran": True} if msg.startswith("Lähetetty") else {}
        set_status(t, sposti=msg, **extra)
        return msg


# ---------- koko kuorman käsittely ----------
def process_load(t, laheta_posti=True):
    with lock_for(t):
        d = ld(t)
        set_status(t, tila="kasittelyssa", virhe=None, sposti=None)
        idx = read_json(d / "indeksi.json", {"kuvat": []})
        todo = [i["key"] for i in idx["kuvat"] if not (d / "tulokset" / f"{i['key']}.json").exists()]
        done = [0]
        set_status(t, edistyminen=f"0/{len(todo)}")

        def work(k):
            try:
                process_image(t, k)
            except Exception as e:  # yksittäinen virhe ei kaada koko kuormaa
                write_json(d / f"virhe_{k}.json", {"virhe": str(e)})
            done[0] += 1
            set_status(t, edistyminen=f"{done[0]}/{len(todo)}")

        with ThreadPoolExecutor(max_workers=int(os.environ.get("WORKERS", "3"))) as ex:
            list(ex.map(work, todo))

        errs = [read_json(p, {}).get("virhe") for p in d.glob("virhe_*.json")]
        for p in d.glob("virhe_*.json"):
            p.unlink()
        if todo and errs and len(errs) == len(todo):
            set_status(t, tila="virhe", virhe="Kuvien luku epäonnistui: " + str(errs[0]))
            return
        rows, attach, notes, retake, kaksoiskuvat = build_rows(t)
        if not rows:
            set_status(t, tila="virhe", virhe="Kuvista ei löytynyt yhtään rullan etikettiä.")
            return
        out, merged, warn, params = build_excel(t, rows, attach, t)
        summary = summarize(t, merged, warn, params, notes)
        summary["uudelleen"] = uudelleen_lista(summary, retake)
        summary["kaksoiskuvat"] = kaksoiskuvat
        status = {"tila": "valmis", "yhteenveto": summary, "excel": out.name, "sposti": None}
        if laheta_posti:
            status["sposti"] = _mail(t, summary, out, merged, params)
            status["lahetetty_kerran"] = True if status["sposti"].startswith("Lähetetty") else None
            if status["lahetetty_kerran"] is None:
                del status["lahetetty_kerran"]
        set_status(t, **status)

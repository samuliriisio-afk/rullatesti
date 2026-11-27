"""Rullaetiketit -> Excel: Flask-palvelin. Käynnistys: gunicorn -w 1 --threads 8 -b 0.0.0.0:8000 app:app"""
import envload  # noqa: F401  (lukee .env ensin)
import hmac, os, threading
from pathlib import Path
from flask import Flask, jsonify, request, send_file, send_from_directory, abort

import mailer, pipeline as P
from version import VERSION

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024
APP_CODE = os.environ.get("APP_CODE", "")


def authorized():
    if not APP_CODE:
        return True
    return hmac.compare_digest(request.headers.get("X-Koodi", ""), APP_CODE)


@app.before_request
def guard():
    if request.path.startswith("/api/") and request.path != "/api/asetukset" and not authorized():
        return jsonify(virhe="Väärä käyttökoodi"), 401


@app.after_request
def no_cache(resp):
    # sivu ja skriptit haetaan aina tuoreena (muuten selain voi näyttää vanhaa versiota tuntikausia)
    if not request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json")


@app.get("/sw.js")
def sw():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")


@app.get("/api/asetukset")
def settings():
    return jsonify(koodi_vaaditaan=bool(APP_CODE), sposti=mailer.MAIL_TO, sposti_valmis=mailer.configured(),
                   tekija=os.environ.get("TEKIJA") or "Samuli Riisiö", versio=VERSION)


def start(t, send_mail):
    threading.Thread(target=P.process_load, args=(t, send_mail), daemon=True).start()


@app.post("/api/laheta")
def upload():
    try:
        t = P.safe_name(request.form.get("tunniste", ""))
    except ValueError as e:
        return jsonify(virhe=str(e)), 400
    files = request.files.getlist("kuvat")
    if not files:
        return jsonify(virhe="Ei kuvia"), 400
    added = 0
    for f in files:
        try:
            if P.add_image(t, f.read(), f.filename):
                added += 1
        except Exception:
            return jsonify(virhe=f"Kuvaa {f.filename} ei voitu avata"), 400
    send_mail = request.form.get("sposti", "0") == "1"
    nimi = request.form.get("nimi", "").strip()[:80]
    if nimi:
        P.set_meta(t, nimi=nimi)
    P.set_status(t, tila="kasittelyssa", edistyminen="0/0")
    start(t, send_mail)
    return jsonify(tunniste=t, lisatty=added)


@app.post("/api/kuorma/<t>/lahikuva")
def closeup(t):
    t = P.safe_name(t)
    target = request.form.get("rivi", "")
    f = request.files.get("kuva")
    if not f or not target:
        return jsonify(virhe="Kuva tai rivi puuttuu"), 400
    try:
        key = P.add_image(t, f.read(), f.filename, kohde=target)
    except Exception:
        return jsonify(virhe="Kuvaa ei voitu avata"), 400
    P.set_status(t, tila="kasittelyssa", edistyminen="0/0")
    start(t, request.form.get("sposti", "0") == "1")
    return jsonify(tunniste=t, kuva=key)


@app.post("/api/kuorma/<t>/lahikuvat")
def closeups(t):
    """Usea lähikuva kerralla: kentät 'kuvat' ja 'rivit' (samassa järjestyksessä). Luku käynnistetään vain kerran."""
    t = P.safe_name(t)
    files = request.files.getlist("kuvat")
    targets = request.form.getlist("rivit")
    if not files or len(files) != len(targets):
        return jsonify(virhe="Kuvat tai rivit puuttuvat"), 400
    added = 0
    for f, target in zip(files, targets):
        try:
            if P.add_image(t, f.read(), f.filename, kohde=target):
                added += 1
        except Exception:
            return jsonify(virhe="Lähikuvaa ei voitu avata"), 400
    P.set_status(t, tila="kasittelyssa", edistyminen="0/0")
    start(t, False)
    return jsonify(tunniste=t, lisatty=added)


@app.post("/api/kuorma/<t>/posti")
def mail_now(t):
    t = P.safe_name(t)
    if not (P.ld(t) / "tila.json").exists():
        return jsonify(virhe="Kuormaa ei löydy"), 404
    try:
        return jsonify(sposti=P.send_mail(t))
    except Exception as e:
        return jsonify(virhe=str(e)), 400


@app.get("/api/kuorma/<t>/tila")
def status(t):
    return jsonify(P.get_status(P.safe_name(t)))


@app.get("/api/kuorma/<t>/excel")
def excel(t):
    t = P.safe_name(t)
    p = P.ld(t) / f"kuorma_{t}.xlsx"
    if not p.exists():
        abort(404)
    return send_file(p, as_attachment=True, download_name=p.name)


@app.get("/api/kuorma/<t>/kuva/<key>")
def picture(t, key):
    """Kuorman kuva esikatselua varten: ?koko=pieni (pikkukuva) tai iso."""
    import io, re as _re
    from PIL import Image
    t = P.safe_name(t)
    if not _re.fullmatch(r"k\d{1,5}", key):
        abort(404)
    p = P.ld(t) / "kuvat" / f"{key}.jpg"
    if not p.exists():
        abort(404)
    side = 260 if request.args.get("koko") == "pieni" else 1600
    im = Image.open(p).convert("RGB")
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    buf.seek(0)
    return send_file(buf, mimetype="image/jpeg")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

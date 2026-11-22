#!/usr/bin/env python3
"""Rakentaa rullaetiketti-Excelin (välilehdet Rullat + Kuvat) JSON-riveistä ja kuvista.

Käyttö:
  python build_rullat.py --rows rivit.json --out /mnt/user-data/outputs/rullat_etiketit.xlsx
  python build_rullat.py --rows uudet.json --base vanha.xlsx --out uusi.xlsx   # lisää olemassa olevaan

Koko työkirja rakennetaan joka kerta alusta, joten ulkoasu, kaavat ja tarkistukset ovat aina samat.
--base lukee vanhan tiedoston rivit, kuvat, rajat ja käsin tehdyt Tarkistus-valinnat mukaan.
"""
import argparse, io, json, math, re, subprocess, sys
from pathlib import Path
from copy import copy
from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.drawing.image import Image as XLImage
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.hyperlink import Hyperlink
from PIL import Image, ImageOps

KEYS = ['kuva', 'kuvatiedosto', 'rullanumero', 'tilausnumero', 'ex_tilausnumero', 'tuotenimi', 'gsm', 'leveys',
        'halkaisija', 'paino', 'uib', 'uib_lahde', 'pituus', 'tarkistus', 'huomautus']
HEADS = ['Kuva', 'Kuvatiedosto', 'Rullanumero', 'Tilausnumero', 'Ex-tilausnumero', 'Tuotenimi', 'GSM (g/m²)',
         'Leveys (mm)', 'Halkaisija (mm)', 'Paino (kg)', 'UIB / viivakoodin numero', 'UIB-lähde', 'Pituus (m)',
         'Tarkistus', 'Huomautus', 'Laskettu paino (kg)', 'Paino-poikkeama', 'Tiheys (kg/m³)', 'Automaatti-tarkistus']
WIDTHS = [30, 12, 19, 17, 17, 30, 18, 12, 15, 11, 24, 20, 11, 15, 70, 16, 15, 14, 40]
LET = {k: chr(65 + i) for i, k in enumerate(KEYS)}          # kenttä -> sarakekirjain (A..O)
NUMERIC = ('leveys', 'halkaisija', 'paino', 'pituus')
REQUIRED = ('rullanumero', 'tilausnumero', 'tuotenimi', 'gsm', 'leveys', 'halkaisija', 'paino', 'uib', 'pituus')
MILL_SUFFIX = {'0201': 'Imatra', '0205': 'Anjalankoski', '0216': 'Kotkamills'}   # UIB:n 4 viimeistä numeroa

DEFAULTS = {'tol': 0.05, 'dmin': 400, 'dmax': 950}
LBL_TOL, LBL_DMIN, LBL_DMAX = 'Sallittu painopoikkeama', 'Tiheys min (kg/m³)', 'Tiheys max (kg/m³)'
ST_MISSING = 'Tietoja puuttuu tai GSM ei tulkittavissa'
ST_OK = 'OK'
ST_WEIGHT = 'Paino ei täsmää: tarkista pituus, GSM ja leveys'
ST_BOTH = 'Tarkista paino ja halkaisija'
ST_DIAM = 'Halkaisija ei täsmää painoon'

NOTE_MAIN = ('Klikkaa kuvatiedoston numeroa (sarake B) → avautuu etiketin kuva Kuvat-välilehdellä. Huomautussarake O '
 'näyttää vain alun: koko teksti aukeaa kun solun valitsee (kaavapalkki) tai hiiren vienti solun päälle. Keltainen '
 'solu = epävarma tieto (Tarkistus-sarakkeessa Tarkistettava): tarkista kuvasta, korjaa tarvittaessa arvo ja valitse '
 'Tarkistus-sarakkeen valikosta Hyväksytty tai Korjattu → solut muuttuvat vihreiksi. Punertava paino = ei täsmää '
 'leveyteen, pituuteen ja gsm:ään (poikkeama yli 5 %). Pituussarake M on piilotettu. UIB-lähde: Viivakoodi = luettu '
 'viivakoodista (numero vastaa etiketin tekstiä). Tilausnumero = voimassa oleva (käsin kirjoitettu uusi tilaus; jos '
 'korjausta ei ole, etiketin painettu tilausnumero). Ex-tilausnumero = etiketin alkuperäinen painettu, yliviivattu '
 'tilausnumero. Käsin korvataan usein vain osa merkeistä, ja loput säilyvät painetusta.')
NOTES_AUTO = [
 'Automaattitarkistus (sarakkeet P–S): Laskettu paino = leveys × pituus × kokonais-GSM. GSM-sarake säilyy etiketin '
 'mukaisena; kokonais-GSM luetaan vain laskennassa summaamalla tekstin luvut (BIO25+214+BIO25 → 264, 214+PE15 → 229).',
 'Paino-poikkeama = (etiketin paino / laskettu paino) − 1. Tiheys = paino / (π/4 × halkaisija² × leveys); karkea '
 'järkevyysraja, joka ei huomioi ydintä. Rajat ovat muokattavissa (sininen teksti).',
 'Punertava solu = ylittää rajan. Jos vain paino on pielessä ja tiheys kunnossa, virhe on todennäköisesti '
 'pituudessa, GSM:ssä tai leveydessä; jos vain tiheys on pielessä, halkaisijassa.']

# ---------- tyylit ----------
THIN = Side(style='thin', color='00BFBFBF')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
F_BASE = Font(name='Arial')
F_BOLD = Font(name='Arial', bold=True)
F_ITAL = Font(name='Arial', italic=True)
F_LINK = Font(name='Arial', color='000563C1', underline='single')
F_HEAD = Font(name='Arial', bold=True, color='00FFFFFF')
F_INPUT = Font(name='Arial', color='000000FF')
FILL_HEAD = PatternFill('solid', start_color='001F4E78', end_color='001F4E78')
FILL_GREEN = PatternFill('solid', start_color='00C6E0B4', end_color='00C6E0B4')
FILL_YELLOW = PatternFill('solid', start_color='00FFF2CC', end_color='00FFF2CC')
FILL_RED = PatternFill('solid', start_color='00F8CBAD', end_color='00F8CBAD')
A_VC = Alignment(vertical='center')
A_VCW = Alignment(vertical='center', wrap_text=True)
A_CC = Alignment(horizontal='center', vertical='center')
COLFMT = {  # sarake: (fontti, tasaus, numeromuoto)
    'A': (F_BASE, A_VC, 'General'), 'B': (F_LINK, A_CC, 'General'), 'C': (F_BASE, A_VCW, '@'),
    'D': (F_BASE, A_VC, '@'), 'E': (F_BASE, A_VC, '@'), 'F': (F_BASE, A_VCW, 'General'),
    'G': (F_BASE, A_VC, '#,##0'), 'H': (F_BASE, A_VC, '#,##0'), 'I': (F_BASE, A_VC, '#,##0'),
    'J': (F_BASE, A_VC, '#,##0'), 'K': (F_BASE, A_VC, '@'), 'L': (F_BASE, A_VC, 'General'),
    'M': (F_BASE, A_VC, '#,##0'), 'N': (F_BASE, A_CC, 'General'), 'O': (F_BASE, A_VCW, 'General'),
    'P': (F_BASE, A_VC, '#,##0'), 'Q': (F_BASE, A_VC, '+0.0%;-0.0%;0.0%'), 'R': (F_BASE, A_VC, '#,##0'),
    'S': (F_BASE, A_VCW, 'General')}

# ---------- apufunktiot ----------
def gsm_total(g):
    """Kokonais-GSM tekstistä: summaa kaikki luvut (BIO25+214+BIO25 -> 264). Sama logiikka kuin Excel-kaavassa."""
    if g is None or str(g).strip() == '':
        return None
    s = re.sub(r'BIO|PE', '', str(g)).replace(' ', '')
    parts = s.split('+')
    try:
        return sum(int(re.sub(r'\D', '', p) or 0) for p in parts)
    except ValueError:
        return None

def calc_checks(row, p):
    """Sama laskenta kuin sarakkeiden P–S kaavat. Palauttaa (laskettu, poikkeama, tiheys, tila)."""
    try:
        W, D, kg, L = (float(row[k]) for k in ('leveys', 'halkaisija', 'paino', 'pituus'))
    except (TypeError, ValueError, KeyError):
        return None, None, None, ST_MISSING
    gt = gsm_total(row.get('gsm'))
    if not gt:
        return None, None, None, ST_MISSING
    calc = W / 1000 * L * gt / 1000
    dev = kg / calc - 1 if calc > 0 else None
    dens = kg / (math.pi / 4 * (D / 1000) ** 2 * (W / 1000)) if D > 0 and W > 0 else None
    if dev is None or dens is None:
        return calc, dev, dens, ST_MISSING
    w_ok, d_ok = abs(dev) <= p['tol'], p['dmin'] <= dens <= p['dmax']
    st = ST_OK if (w_ok and d_ok) else (ST_BOTH if (not w_ok and not d_ok) else (ST_WEIGHT if not w_ok else ST_DIAM))
    return calc, dev, dens, st

def prep_image(src):
    """Palauttaa (iso_jpeg_bytes, (w,h), pikkukuva_bytes, (tw,th)). Korjaa EXIF-kierron, max 900 px."""
    im = Image.open(io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else str(src))
    im = ImageOps.exif_transpose(im).convert('RGB')
    im.thumbnail((900, 900))
    big = io.BytesIO(); im.save(big, 'JPEG', quality=82)
    th = im.copy(); th.thumbnail((112, 84)); tb = io.BytesIO(); th.save(tb, 'JPEG', quality=80)
    tw, thh = round(im.width * 42 / im.height), 42          # näyttökoko: 42 px korkea
    return big.getvalue(), im.size, tb.getvalue(), (tw, thh)

def derive_id(path):
    stem = Path(str(path)).stem
    runs = re.findall(r'\d{4,}', stem)
    return runs[-1] if runs else stem

def norm_row(r):
    r = dict(r)
    for k in NUMERIC:
        v = r.get(k)
        if v not in (None, ''):
            try: r[k] = int(round(float(str(v).replace(' ', '').replace(',', '.'))))
            except ValueError: pass
    g = r.get('gsm')
    if isinstance(g, str) and re.fullmatch(r'\d+', g.strip()): r['gsm'] = int(g.strip())
    for k in ('rullanumero', 'tilausnumero', 'ex_tilausnumero', 'uib', 'kuvatiedosto'):
        if r.get(k) is not None: r[k] = str(r[k]).strip()
    r['epavarmat'] = list(r.get('epavarmat') or [])
    r['lisakuvat'] = list(r.get('lisakuvat') or [])
    if not r.get('kuvatiedosto') and r.get('kuva') and not isinstance(r['kuva'], (bytes, bytearray)):
        r['kuvatiedosto'] = derive_id(r['kuva'])
    for e in r['lisakuvat']:
        if not e.get('tiedosto') and e.get('kuva') and not isinstance(e['kuva'], (bytes, bytearray)):
            e['tiedosto'] = derive_id(e['kuva'])
    if r['epavarmat'] and not r.get('tarkistus'): r['tarkistus'] = 'Tarkistettava'
    if r.get('uib_lahde') in (None, ''): r['uib_lahde'] = 'Viivakoodi'
    if r['uib_lahde'] != 'Viivakoodi' and not r.get('tarkistus'): r['tarkistus'] = 'Tarkistettava'
    return r

# ---------- vanhan tiedoston luku ----------
def read_base(path):
    wb = load_workbook(path)
    ws, wk = wb['Rullat'], wb['Kuvat']
    imgs = {im.anchor._from.row + 1: im._data() for im in wk._images}
    main_head, extras = {}, {}
    for r in range(1, wk.max_row + 1):
        v = wk.cell(r, 1).value
        if isinstance(v, str) and v.startswith('Kuva '):
            m = re.match(r'^Kuva (\S+) – rulla (.*?)(?: \((.*)\))?$', v)
            if not m: continue
            fid, desc = m.group(1), m.group(3) or ''
            mm = re.search(r'sama rulla kuin (\S+)', desc)
            if mm:
                kuvaus = re.sub(r',?\s*sama rulla kuin \S+', '', desc).strip()
                extras.setdefault(mm.group(1), []).append({'tiedosto': fid, 'kuvaus': kuvaus, 'kuva': imgs.get(r + 1)})
            else:
                main_head[fid] = r
    unc = {}
    for cf in ws.conditional_formatting:
        sq = str(cf.sqref)
        if ':' in sq: continue
        cells = sq.split()
        if not any(re.fullmatch(r'N\d+', c) for c in cells): continue
        for c in cells:
            m = re.fullmatch(r'([A-Z])(\d+)', c)
            if m and m.group(1) not in ('N', 'O'):
                unc.setdefault(int(m.group(2)), set()).add(m.group(1))
    inv = {v: k for k, v in LET.items()}
    rows, r = [], 2
    while ws.cell(r, 2).value not in (None, ''):
        d = {k: ws.cell(r, i + 1).value for i, k in enumerate(KEYS) if k != 'kuva'}
        fid = str(d['kuvatiedosto'])
        d['kuva'] = imgs.get(main_head[fid] + 1) if fid in main_head else None
        d['lisakuvat'] = extras.get(fid, [])
        d['epavarmat'] = [inv[c] for c in sorted(unc.get(r, ()))]
        rows.append(d); r += 1
    params = dict(DEFAULTS)
    for rr in range(r, ws.max_row + 1):
        lab, val = ws.cell(rr, 1).value, ws.cell(rr, 2).value
        if isinstance(val, (int, float)):
            if lab == LBL_TOL: params['tol'] = val
            elif lab == LBL_DMIN: params['dmin'] = val
            elif lab == LBL_DMAX: params['dmax'] = val
    return [norm_row(x) for x in rows], params

# ---------- rakennus ----------
def gsm_formula(r):
    return ('SUMPRODUCT(--("0"&TRIM(MID(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(SUBSTITUTE(G%d&"","BIO",""),"PE","")," ",""),'
            '"+",REPT(" ",20)),({1,2,3,4,5,6}-1)*20+1,20))))' % r)

def build(rows, params, out, kuorma_nimi=None, ilman_kuvia=False, arvot=False):
    wb = Workbook(); ws = wb.active; ws.title = 'Rullat'; wk = wb.create_sheet('Kuvat')
    n = len(rows); L = n + 1
    R_NOTE, R_ST, R_PAR, R_AST, R_AN = L + 2, L + 4, L + 9, L + 14, L + 18
    P_TOL, P_MIN, P_MAX = f'$B${R_PAR + 1}', f'$B${R_PAR + 2}', f'$B${R_PAR + 3}'

    for i, (h, w) in enumerate(zip(HEADS, WIDTHS)):
        c = ws.cell(1, i + 1, h); c.font, c.fill, c.border = F_HEAD, FILL_HEAD, BORDER
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        ws.column_dimensions[chr(65 + i)].width = w
    ws.column_dimensions['M'].hidden = True
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = 'C2'

    wk['A1'] = 'Etikettikuvat'; wk['A1'].font = Font(name='Arial', bold=True, size=14)
    wk.column_dimensions['A'].width = 20
    krow = 3
    uncertain_cf = []
    for idx, row in enumerate(rows):
        r = idx + 2
        ws.row_dimensions[r].height = 34
        for i, k in enumerate(KEYS):
            col = chr(65 + i)
            c = ws.cell(r, i + 1)
            if k != 'kuva': c.value = row.get(k) if row.get(k) != '' else None
            f, a, nf = COLFMT[col]; c.font, c.alignment, c.number_format, c.border = f, a, nf, BORDER
            if k == 'gsm' and isinstance(row.get(k), str): c.number_format = 'General'
        for col in 'PQRS':
            f, a, nf = COLFMT[col]; c = ws[f'{col}{r}']; c.font, c.alignment, c.number_format, c.border = f, a, nf, BORDER
        g = gsm_formula(r)
        ws[f'P{r}'] = f'=IFERROR(IF(AND(ISNUMBER(H{r}),ISNUMBER(M{r}),G{r}<>""),H{r}/1000*M{r}*{g}/1000,""),"")'
        ws[f'Q{r}'] = f'=IF(AND(ISNUMBER(P{r}),ISNUMBER(J{r})),IF(P{r}>0,J{r}/P{r}-1,""),"")'
        ws[f'R{r}'] = (f'=IF(AND(ISNUMBER(I{r}),ISNUMBER(H{r}),ISNUMBER(J{r})),IF(AND(I{r}>0,H{r}>0),'
                       f'J{r}/(PI()/4*(I{r}/1000)^2*(H{r}/1000)),""),"")')
        ws[f'S{r}'] = (f'=IF(OR(Q{r}="",R{r}=""),"{ST_MISSING}",IF(AND(ABS(Q{r})<={P_TOL},R{r}>={P_MIN},R{r}<={P_MAX}),'
                       f'"{ST_OK}",IF(ABS(Q{r})>{P_TOL},IF(AND(R{r}>={P_MIN},R{r}<={P_MAX}),"{ST_WEIGHT}","{ST_BOTH}"),'
                       f'"{ST_DIAM}")))')
        if row.get('huomautus'):
            t = str(row['huomautus']); cm = Comment(t, 'Etikettianalyysi')
            cm.width, cm.height = 380, 40 + 15 * math.ceil(len(t) / 50); ws[f'O{r}'].comment = cm
        # kuvat
        fid = row.get('kuvatiedosto')
        if row.get('kuva') is not None and not ilman_kuvia:
            big, (w, h), tb, (tw, th) = prep_image(row['kuva'])
            thumb = XLImage(io.BytesIO(tb)); thumb.width, thumb.height = tw, th; ws.add_image(thumb, f'A{r}')
            blocks = [(fid, f'Kuva {fid} – rulla {row["rullanumero"]}', big, h)]
        else:
            blocks = []
        for e in ([] if ilman_kuvia else row['lisakuvat']):
            if e.get('kuva') is None: continue
            eb, (ew, eh), _, _ = prep_image(e['kuva'])
            kv = f' ({e["kuvaus"]}, ' if e.get('kuvaus') else ' ('
            blocks.append((e.get('tiedosto'), f'Kuva {e.get("tiedosto")} – rulla {row["rullanumero"]}{kv}sama rulla kuin {fid})', eb, eh))
        first = True
        for (bid, title, data, h) in blocks:
            if first:
                ws[f'B{r}'].hyperlink = Hyperlink(ref=f'B{r}', location=f'Kuvat!A{krow}'); ws[f'B{r}'].font = F_LINK; first = False
            wk[f'A{krow}'] = title; wk[f'A{krow}'].font = F_BOLD
            wk[f'C{krow}'] = '← Takaisin taulukkoon'; wk[f'C{krow}'].font = F_LINK
            wk[f'C{krow}'].hyperlink = Hyperlink(ref=f'C{krow}', location=f'Rullat!B{r}'); wk[f'C{krow}'].font = F_LINK
            im = XLImage(io.BytesIO(data)); wk.add_image(im, f'A{krow + 1}')
            krow += math.ceil(h / 20) + 3
        # ehdollinen väri epävarmoille soluille
        if row.get('tarkistus') or row['epavarmat']:
            cells = [f'{LET[k]}{r}' for k in row['epavarmat'] if k in LET] + [f'N{r}', f'O{r}']
            uncertain_cf.append((' '.join(cells), r))

    # --- yhteenvedot ---
    def put(ref, val, font=F_BASE, center=False, nf=None):
        c = ws[ref]; c.value = val; c.font = font
        if center: c.alignment = Alignment(horizontal='center')
        if nf: c.number_format = nf
    put(f'A{R_NOTE}', NOTE_MAIN, F_ITAL)
    put(f'A{R_ST}', 'Tarkistuksen tilanne', F_BOLD)
    for j, lab in enumerate(('Tarkistettava', 'Hyväksytty', 'Korjattu')):
        put(f'A{R_ST + 1 + j}', lab)
        put(f'B{R_ST + 1 + j}', f'=COUNTIF($N$2:$N${max(L, 2)},"{lab}")', center=True)
    put(f'A{R_PAR}', 'Automaattitarkistuksen rajat', F_BOLD)
    for j, (lab, val, nf) in enumerate(((LBL_TOL, params['tol'], '0%'), (LBL_DMIN, params['dmin'], '#,##0'),
                                        (LBL_DMAX, params['dmax'], '#,##0'))):
        put(f'A{R_PAR + 1 + j}', lab); put(f'B{R_PAR + 1 + j}', val, F_INPUT, True, nf)
    put(f'A{R_AST}', 'Automaattitarkistuksen tilanne', F_BOLD)
    put(f'A{R_AST + 1}', 'OK'); put(f'B{R_AST + 1}', f'=COUNTIF($S$2:$S${max(L, 2)},"OK")', center=True)
    put(f'A{R_AST + 2}', 'Huomioitavaa')
    put(f'B{R_AST + 2}', f'=COUNTA($S$2:$S${max(L, 2)})-B{R_AST + 1}', center=True)
    for j, t in enumerate(NOTES_AUTO): put(f'A{R_AN + j}', t, F_ITAL)
    R_SUM = R_AN + 4
    put(f'A{R_SUM}', 'Kuorman yhteenveto', F_BOLD)
    put(f'A{R_SUM + 1}', 'Kuorma'); put(f'B{R_SUM + 1}', kuorma_nimi or '', center=True)
    put(f'A{R_SUM + 2}', 'Rullia'); put(f'B{R_SUM + 2}', f'=COUNTA($B$2:$B${max(L, 2)})', center=True)
    put(f'A{R_SUM + 3}', 'Paino yhteensä (kg)'); put(f'B{R_SUM + 3}', f'=SUM($J$2:$J${max(L, 2)})', center=True, nf='#,##0')

    if arvot:   # lähetysversio: kaavojen tilalle lasketut arvot, jotta esikatselu näyttää ne ilman Exceliä
        for idx, row in enumerate(rows):
            r = idx + 2
            calc, dev, dens, st = calc_checks(row, params)
            ws[f'P{r}'], ws[f'Q{r}'], ws[f'R{r}'], ws[f'S{r}'] = calc, dev, dens, st
        for j, lab in enumerate(('Tarkistettava', 'Hyväksytty', 'Korjattu')):
            ws[f'B{R_ST + 1 + j}'] = sum(1 for row in rows if row.get('tarkistus') == lab)
        n_ok = sum(1 for row in rows if calc_checks(row, params)[3] == ST_OK)
        ws[f'B{R_AST + 1}'], ws[f'B{R_AST + 2}'] = n_ok, n - n_ok
        ws[f'B{R_SUM + 2}'] = n
        ws[f'B{R_SUM + 3}'] = sum(int(r['paino']) for r in rows if isinstance(r.get('paino'), (int, float)))
    if ilman_kuvia:
        for idx in range(n): ws[f'B{idx + 2}'].font = F_BASE
        del wb['Kuvat']
        put(f'A{R_SUM + 4}', 'Tämä on kevyt lähetysversio: kuvat on poistettu liitteen koon takia. Kuvat ovat kuorman alkuperäisessä Excelissä.', F_ITAL)

    # --- pudotusvalikko + ehdollinen muotoilu ---
    if n:
        dv = DataValidation(type='list', formula1='"Tarkistettava,Hyväksytty,Korjattu"', allow_blank=True,
                            errorTitle='Virheellinen arvo', error='Valitse: Tarkistettava, Hyväksytty tai Korjattu',
                            promptTitle='Tarkistus', prompt='Valitse tila kun olet tarkistanut tiedon kuvasta')
        dv.add(f'N2:N{L}'); ws.add_data_validation(dv)
        for cells, r in uncertain_cf:
            ws.conditional_formatting.add(cells, FormulaRule(formula=[f'OR($N{r}="Hyväksytty",$N{r}="Korjattu")'],
                                                             fill=FILL_GREEN, stopIfTrue=True))
            ws.conditional_formatting.add(cells, FormulaRule(formula=[f'AND($N{r}<>"Hyväksytty",$N{r}<>"Korjattu")'],
                                                             fill=FILL_YELLOW))
        rng = lambda c: f'{c}2:{c}{L}'
        bad_w = f'AND(ISNUMBER($Q2),ABS($Q2)>{P_TOL})'
        bad_d = f'AND(ISNUMBER($R2),OR($R2<{P_MIN},$R2>{P_MAX}))'
        for c, fm in (('J', bad_w), ('Q', bad_w), ('R', bad_d), ('I', bad_d)):
            ws.conditional_formatting.add(rng(c), FormulaRule(formula=[fm], fill=FILL_RED))
        ws.conditional_formatting.add(rng('S'), FormulaRule(formula=['$S2="OK"'], fill=FILL_GREEN))
        ws.conditional_formatting.add(rng('S'), FormulaRule(formula=['$S2<>"OK"'], fill=FILL_RED))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)

def merge(rows, new, replace=False):
    """Lisää uudet rivit olemassa oleviin (rows muuttuu paikallaan).
    Palauttaa tapahtumalistan [{kind, id, text}]. kind: puuttuu | uib | tehdas | korvattu | tupla | lisakuva | lisakuva_ei_rullaa"""
    ev = []
    def add(kind, i, text): ev.append({'kind': kind, 'id': i, 'text': f'{i}: {text}'})
    def merge_extras(target, extras):
        have = {e.get('tiedosto') for e in target['lisakuvat']} | {target.get('kuvatiedosto')}
        added = [e for e in extras if e.get('tiedosto') not in have]
        target['lisakuvat'] = target['lisakuvat'] + added
        return [e.get('tiedosto') for e in added]
    # rivi ilman pääkuvaa mutta lisäkuvilla = pelkkä lähikuva, liitetään UIB:n perusteella olemassa olevaan rullaan
    is_attach = [(not r.get('kuva')) and bool(r['lisakuvat']) for r in new]
    for r, att in zip(new, is_attach):
        if att: continue
        fid = r.get('kuvatiedosto')
        miss = [k for k in REQUIRED if r.get(k) in (None, '')]
        if miss: add('puuttuu', fid, f'puuttuu {", ".join(miss)}')
        u = r.get('uib') or ''
        if u and not re.fullmatch(r'\d{14}', u): add('uib', fid, f'UIB ei ole 14 numeroa ({u})')
        elif u and u[-4:] not in MILL_SUFFIX: add('tehdas', fid, f'UIB:n loppu {u[-4:]} ei vastaa tunnettua tehdasta')
        dup = next((i for i, o in enumerate(rows) if (u and o.get('uib') == u) or (o.get('kuvatiedosto') == fid)), None)
        if dup is None: rows.append(r)
        elif replace: rows[dup] = r; add('korvattu', fid, 'korvasi vanhan rivin')
        else:
            added = merge_extras(rows[dup], r['lisakuvat'])
            add('tupla', fid, 'JO OLEMASSA (sama UIB tai kuvatiedosto), rivi ohitettu' + (f'; lisäkuvat liitetty: {", ".join(map(str, added))}' if added else ''))
    for r, att in zip(new, is_attach):
        if not att: continue
        u = r.get('uib')
        tgt = next((o for o in rows if u and o.get('uib') == u), None)
        if tgt is None:
            for e in r['lisakuvat']: add('lisakuva_ei_rullaa', e.get('tiedosto'), f'lisäkuva (UIB {u}): rullaa ei löytynyt, ohitettu')
        else:
            added = merge_extras(tgt, r['lisakuvat'])
            add('lisakuva', tgt.get('kuvatiedosto'), f'lisäkuva liitetty: {", ".join(map(str, added)) or "ei uusia (jo mukana)"}')
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rows', help='JSON-tiedosto: lista rivejä (uudet rullat)')
    ap.add_argument('--base', help='olemassa oleva Excel, johon rivit lisätään')
    ap.add_argument('--out', default='/mnt/user-data/outputs/rullat_etiketit.xlsx')
    ap.add_argument('--replace', action='store_true', help='korvaa vanha rivi, jos UIB tai kuvatiedosto on jo olemassa')
    ap.add_argument('--no-recalc', action='store_true')
    ap.add_argument('--kuorma', help='kuorman nimi (näkyy yhteenvedossa)')
    a = ap.parse_args()

    rows, params = ([], dict(DEFAULTS))
    if a.base: rows, params = read_base(a.base)
    new = [norm_row(x) for x in json.load(open(a.rows, encoding='utf8'))] if a.rows else []
    warn = [e['text'] for e in merge(rows, new, a.replace)]
    build(rows, params, a.out, a.kuorma)

    print(f'Rivejä yhteensä {len(rows)} (uusia syötetty {len(new)}) -> {a.out}')
    print('kuva | rulla | poikkeama | tiheys | tila')
    for r in rows:
        calc, dev, dens, st = calc_checks(r, params)
        print(f'{r.get("kuvatiedosto")} | {r.get("rullanumero")} | '
              f'{"" if dev is None else format(dev, "+.1%")} | {"" if dens is None else round(dens)} | {st} | {r.get("tarkistus") or ""}')
    for w in warn: print('HUOM:', w)
    if not a.no_recalc:
        for p in ('/mnt/skills/public/xlsx/scripts/recalc.py', str(Path(__file__).parent / 'recalc.py')):
            if Path(p).exists():
                res = subprocess.run([sys.executable, p, a.out, '90'], capture_output=True, text=True)
                print('recalc:', res.stdout.strip().replace('\n', ' ')[:300]); break
        else:
            print('recalc: ohitettu (recalc.py ei löytynyt); Excel laskee kaavat avattaessa')

if __name__ == '__main__':
    main()

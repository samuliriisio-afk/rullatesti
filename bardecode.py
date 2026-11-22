"""Lukee Code 128 -viivakoodit kuvista. Käyttö: python3 -I viivakoodi.py kuva1.jpg kuva2.jpg ...
Tulostaa: tiedosto<TAB>luettu_numero (tyhjä jos ei luettu). Tarkistussumma varmistetaan."""
import sys, cv2
import numpy as np
from PIL import Image
T="212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 122132 122231 113222 123122 123221 223211 221132 221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 212123 212321 232121 111323 131123 131321 112313 132113 132311 211313 231113 231311 112133 112331 132131 113123 113321 133121 313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 112412 122114 122411 142112 142211 241211 221114 413111 241112 134111 111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 214121 412121 111143 111341 131141 114113 114311 411113 411311 113141 114131 311141 411131 211412 211214 211232".split()
PAT={p:i for i,p in enumerate(T)}
STOP="2331112"
def runs(row):
    b=(row<row.mean()*0.8+row.min()*0.2).astype(int)
    r=[];c=b[0];n=1
    for v in b[1:]:
        if v==c:n+=1
        else:r.append((c,n));c=v;n=1
    r.append((c,n));return r
def decode_runs(r):
    # drop leading white
    if r[0][0]==0:r=r[1:]
    w=[n for _,n in r]
    for off in range(0,len(w)-12):
        # start must begin at a black run
        out=try_at(w,off)
        if out:return out
def match(ws):
    t=sum(ws);u=t/11.0
    q=[max(1,min(4,round(x/u))) for x in ws]
    return PAT.get(''.join(map(str,q)))
def try_at(w,off):
    syms=[];i=off
    while i+6<=len(w):
        s=match(w[i:i+6])
        if s is None:return None
        syms.append(s);i+=6
        if len(syms)==1 and s not in(103,104,105):return None
        if len(syms)>=4 and False:pass
        if len(syms)>=3 and i+7<=len(w):
            # check for stop
            t=sum(w[i:i+7]);u=t/13.0
            q=''.join(str(max(1,min(4,round(x/u)))) for x in w[i:i+7])
            if q==STOP:
                chk=syms[-1];body=syms[:-1]
                tot=body[0]+sum(k*v for k,v in enumerate(body[1:],1))
                if tot%103!=chk:return None
                return body,chk
    return None
def to_text(body):
    mode=body[0];s=''
    for v in body[1:]:
        if mode==105 and v<100:s+='%02d'%v
        elif v==100 and mode!=104:mode=104
        elif v==99:mode=105
        elif v==101:mode=103
        elif mode in(103,104) and v<96:s+=chr(32+v)
    return s
def scan_arr(im,rows=40):
    res={}
    for y in np.linspace(0,im.shape[0]-1,rows).astype(int):
        r=runs(im[y,:])
        for rr in (r,r[::-1]):
            d=decode_runs(rr)
            if d:
                t=to_text(d[0]);res[t]=res.get(t,0)+1
    return res
def scan(path,box,rows=40):
    im=np.asarray(Image.open(path).convert('L'),float)
    x0,y0,x1,y1=box
    res={}
    for y in np.linspace(y0,y1,rows).astype(int):
        row=im[y,x0:x1]
        r=runs(row)
        for rr in (r,r[::-1]):
            d=decode_runs(rr)
            if d:
                t=to_text(d[0]);res[t]=res.get(t,0)+1
    return res

def cands(g):
    gx=cv2.Sobel(g,cv2.CV_32F,1,0,ksize=-1);gy=cv2.Sobel(g,cv2.CV_32F,0,1,ksize=-1)
    d=cv2.convertScaleAbs(cv2.subtract(cv2.absdiff(gx,0*gx),cv2.absdiff(gy,0*gy)))
    d=cv2.blur(d,(9,9));_,t=cv2.threshold(d,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    t=cv2.morphologyEx(t,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_RECT,(31,9)))
    t=cv2.erode(t,None,iterations=3);t=cv2.dilate(t,None,iterations=3)
    cs,_=cv2.findContours(t,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    out=[]
    for c in sorted(cs,key=cv2.contourArea,reverse=True)[:8]:
        x,y,w,h=cv2.boundingRect(c)
        if w>150 and h>30: out.append((x,y,w,h))
    return out
def tryimg(g):
    found={}
    for (x,y,w,h) in cands(g):
        pad=20
        box=(max(0,x-pad),max(0,y),min(g.shape[1],x+w+pad),min(g.shape[0],y+h))
        sub=g[box[1]:box[3],box[0]:box[2]]
        for ang in (0,-3,3,-6,6,-10,10):
            if ang:
                M=cv2.getRotationMatrix2D((sub.shape[1]/2,sub.shape[0]/2),ang,1)
                s2=cv2.warpAffine(sub,M,(sub.shape[1],sub.shape[0]),borderMode=cv2.BORDER_REPLICATE)
            else:s2=sub
            for sc in (1.0,1.5,0.7):
                s3=cv2.resize(s2,None,fx=sc,fy=sc) if sc!=1 else s2
                res=scan_arr(s3.astype(float))
                for k,v in res.items():found[k]=found.get(k,0)+v
        if found:break
    return found
def run(path):
    g0=cv2.imread(path,0)
    for rot in (None,cv2.ROTATE_90_CLOCKWISE,cv2.ROTATE_90_COUNTERCLOCKWISE):
        g=g0 if rot is None else cv2.rotate(g0,rot)
        f=tryimg(g)
        if f:return f
    return {}

def read_number(path):
    """Palauttaa kuvasta luetun viivakoodin numeron (tyhjä merkkijono jos ei luettu)."""
    f=run(path)
    return max(f,key=f.get) if f else ""

if __name__=="__main__":
    for p in sys.argv[1:]:
        f=run(p)
        best=max(f,key=f.get) if f else ""
        print(p+"\t"+best)

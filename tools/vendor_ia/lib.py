import sys,struct; sys.path.insert(0,'/tmp/claude-0/-home-claude/10cc0d22-93cc-5dc0-99ad-1cc1766cb9ed/scratchpad/w')
import esf
from esf import *
def strings(d):
    t=d['tail']; q=0
    n=struct.unpack_from('<I',t,q)[0]; q+=4
    for _ in range(n):
        l=struct.unpack_from('<H',t,q)[0]; q+=2+2*l+4
    n=struct.unpack_from('<I',t,q)[0]; q+=4; asc={}
    for _ in range(n):
        l=struct.unpack_from('<H',t,q)[0]; q+=2; s=t[q:q+l].decode('latin-1'); q+=l; asc[struct.unpack_from('<I',t,q)[0]]=s; q+=4
    return asc
def vi(x):
    t=x.t;r=x.raw
    return {0x14:0,0x15:1}.get(t, r[0] if t==0x16 else struct.unpack('<H',r)[0] if t==0x17 else int.from_bytes(r,'big') if t==0x18 else struct.unpack('<I',r)[0] if t==0x08 else None)
def kids(n): return [x for el in n.kids for x in el] if n.block else n.kids
def fnd(N,n,nm):
    if isinstance(n,Rec):
        if N[n.name]==nm: return n
        for k in kids(n):
            r=fnd(N,k,nm)
            if r: return r
def load(p):
    d=esf.load(p); d['asc']=strings(d); N=d['names']
    fa=fnd(N,d['root'],'FACTION_ARRAY'); d['fac']={}
    for el in fa.kids:
        f=el[0]; k=d['asc'][struct.unpack('<I',[x for x in f.kids if isinstance(x,Val) and x.t==0x0f][0].raw)[0]]; d['fac'][k]=f
    d['order']=list(d['fac']); return d
def dip(d,key):
    f=d['fac'][key]; dm=[k for k in f.kids if isinstance(k,Rec) and d['names'][k.name]=='DIPLOMACY_MANAGER'][0]
    arr=[k for k in dm.kids if isinstance(k,Rec)][0]
    return [vi(el[0].kids[0]) if isinstance(el[0],Rec) else vi(el[0]) for el in arr.kids]
def u16strings(d):
    t=d['tail']; q=0; out={}
    n=struct.unpack_from('<I',t,q)[0]; q+=4
    for _ in range(n):
        l=struct.unpack_from('<H',t,q)[0]; q+=2; s=t[q:q+2*l].decode('utf-16le'); q+=2*l; out[struct.unpack_from('<I',t,q)[0]]=s; q+=4
    return out
def resolved(d,x):
    if x.t==0x0f: return ('A',d['asc'].get(struct.unpack('<I',x.raw)[0]))
    if x.t==0x0e: return ('U',d['u16'].get(struct.unpack('<I',x.raw)[0]))
    return (x.t,x.raw)
def sdiff(da,a,db,b,path,out):
    if type(a)!=type(b): out.append((path,'type')); return
    if isinstance(a,Rec):
        pn=path+'/'+da['names'][a.name]
        if da['names'][a.name]!=db['names'][b.name]: out.append((pn,'name')); return
        ka,kb=(a.kids,b.kids)
        if len(ka)!=len(kb): out.append((pn,'count %d/%d'%(len(ka),len(kb)))); return
        if a.block:
            for x,y in zip(ka,kb):
                if len(x)!=len(y): out.append((pn,'elemlen')); continue
                for u,v in zip(x,y): sdiff(da,u,db,v,pn,out)
        else:
            for u,v in zip(ka,kb): sdiff(da,u,db,v,pn,out)
    elif isinstance(a,Arr):
        if a.raw!=b.raw: out.append((path,'arr%02x %d/%d'%(a.t,len(a.raw),len(b.raw))))
    else:
        ra,rb=resolved(da,a),resolved(db,b)
        if ra!=rb: out.append((path,'%s -> %s'%(ra,rb)))

import sys,struct,copy,os,subprocess; sys.path.insert(0,'.')
from lib import *
import startpos_tool as T

# ---------- string tables ----------
def parse_tail(t):
    q=0; out={'u16':[], 'asc':[]}
    n=struct.unpack_from('<I',t,q)[0]; q+=4
    for _ in range(n):
        l=struct.unpack_from('<H',t,q)[0]; q+=2; s=t[q:q+2*l].decode('utf-16le'); q+=2*l; out['u16'].append((s,struct.unpack_from('<I',t,q)[0])); q+=4
    n=struct.unpack_from('<I',t,q)[0]; q+=4
    for _ in range(n):
        l=struct.unpack_from('<H',t,q)[0]; q+=2; s=t[q:q+l].decode('latin-1'); q+=l; out['asc'].append((s,struct.unpack_from('<I',t,q)[0])); q+=4
    assert q==len(t); return out
def build_tail(tb):
    b=struct.pack('<I',len(tb['u16']))
    for s,i in tb['u16']: e=s.encode('utf-16le'); b+=struct.pack('<H',len(e)//2)+e+struct.pack('<I',i)
    b+=struct.pack('<I',len(tb['asc']))
    for s,i in tb['asc']: e=s.encode('latin-1'); b+=struct.pack('<H',len(e))+e+struct.pack('<I',i)
    return b
class Doc:
    def __init__(s,path):
        s.d=esf.load(path); s.N=s.d['names']; s.tb=parse_tail(s.d['tail'])
        assert build_tail(s.tb)==s.d['tail'],'tail roundtrip'
        s.a2i={x:i for x,i in s.tb['asc']}; s.i2a={i:x for x,i in s.tb['asc']}
        s.next_asc=max(i for _,i in s.tb['asc'])+1
    def asc(s,x):
        if x not in s.a2i: s.a2i[x]=s.next_asc; s.i2a[s.next_asc]=x; s.tb['asc'].append((x,s.next_asc)); s.next_asc+=1
        return s.a2i[x]
    def finish(s): s.d['tail']=build_tail(s.tb)
def sget(doc,v): return doc.i2a[struct.unpack('<I',v.raw)[0]]
def sset(doc,v,x): v.raw=struct.pack('<I',doc.asc(x))
def subst(doc,node,smap):
    if isinstance(node,Rec):
        for k in kids(node): subst(doc,k,smap)
    elif isinstance(node,Val) and node.t==0x0f:
        s=sget(doc,node)
        if s in smap: sset(doc,node,smap[s])
    elif isinstance(node,Arr) and node.t==0x4f:
        out=b''
        for i in range(0,len(node.raw),4):
            s=doc.i2a[struct.unpack_from('<I',node.raw,i)[0]]; out+=struct.pack('<I',doc.asc(smap.get(s,s)))
        node.raw=out
def remap(node,m):
    if isinstance(node,Rec):
        for k in kids(node): remap(k,m)
    elif isinstance(node,Val) and node.t in (0x17,0x08):
        v=vi(node)
        if v in m: node.raw=struct.pack('<H' if node.t==0x17 else '<I',m[v])
    elif isinstance(node,Arr) and node.t==0x57:
        b=bytearray(node.raw)
        for i in range(0,len(b),2):
            v=struct.unpack_from('<H',b,i)[0]
            if v in m: struct.pack_into('<H',b,i,m[v])
        node.raw=bytes(b)
def setint(v,x):
    v.raw=struct.pack({0x17:'<H',0x08:'<I',0x16:'<B'}[v.t],x)
def sub(doc,n,nm): return [k for k in n.kids if isinstance(k,Rec) and doc.N[k.name]==nm][0]
def subs(doc,n,nm): return [k for k in n.kids if isinstance(k,Rec) and doc.N[k.name]==nm]
def walk_find(doc,n,nm,out):
    if isinstance(n,Rec):
        if doc.N[n.name]==nm: out.append(n)
        for k in kids(n): walk_find(doc,k,nm,out)
    return out
def fkey(doc,el):   # faction key of a faction-sized table element
    x=el[0]; cand=x.kids if isinstance(x,Rec) else el
    for y in cand:
        if isinstance(y,Val) and y.t==0x0f: return sget(doc,y)
def clone_el(el): return [copy.deepcopy(x) for x in el]

def refscan(D,T,tid):
    import collections
    cnt=collections.Counter()
    def w(n,path):
        if isinstance(n,Rec):
            p=path+'/'+D.N[n.name]
            for k in kids(n): w(k,p)
        elif isinstance(n,Val):
            if n.t in (0x17,0x08) and vi(n)==tid: cnt[(path,'val%02x'%n.t)]+=1
            if n.t==0x0f and D.i2a[struct.unpack('<I',n.raw)[0]]==T: cnt[(path,'str')]+=1
        elif isinstance(n,Arr):
            if n.t==0x57:
                for i in range(0,len(n.raw),2):
                    if struct.unpack_from('<H',n.raw,i)[0]==tid: cnt[(path,'arr57')]+=1
            if n.t==0x4f:
                for i in range(0,len(n.raw),4):
                    if D.i2a[struct.unpack_from('<I',n.raw,i)[0]]==T: cnt[(path,'arr4f')]+=1
    w(D.d['root'],'')
    return cnt

def dump(D,n,ind=0,maxd=6,out=None,lim=60):
    pad='  '*ind
    if isinstance(n,Rec):
        print(pad+D.N[n.name], 'block' if n.block else '', 'n=%d'%len(n.kids), 'v%d'%getattr(n,'ver',0))
        if ind<maxd:
            ks=n.kids[:lim]
            for k in ks:
                if n.block:
                    print(pad+' [el]');
                    for x in k: dump(D,x,ind+2,maxd)
                else: dump(D,k,ind+1,maxd)
    elif isinstance(n,Val):
        r=n.raw
        if n.t==0x0f: s=D.i2a.get(struct.unpack('<I',r)[0])
        else: s=vi(n) if n.t in (0x08,0x16,0x17,0x18,0x14,0x15) else r.hex()
        print(pad+'V%02x %s'%(n.t,s))
    else:
        print(pad+'A%02x len=%d %s'%(n.t,len(n.raw),n.raw[:40].hex()))

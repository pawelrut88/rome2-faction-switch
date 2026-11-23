import struct, sys

FIXED = {
 0x01:1,0x02:1,0x03:2,0x04:4,0x05:8,0x06:1,0x07:2,0x08:4,0x09:8,0x0a:4,0x0b:8,
 0x0c:8,0x0d:12,0x0e:4,0x0f:4,0x10:2,
 0x12:0,0x13:0,0x14:0,0x15:0,0x16:1,0x17:2,0x18:3,
 0x19:0,0x1a:1,0x1b:2,0x1c:3,0x1d:0,0x1e:0,0x1f:0,
}

def read_varint(d,p):
    v=0
    while True:
        b=d[p]; p+=1
        v=(v<<7)|(b&0x7f)
        if not b&0x80: return v,p

def write_varint(v):
    out=[v&0x7f]; v>>=7
    while v:
        out.append((v&0x7f)|0x80); v>>=7
    return bytes(reversed(out))

def vi(v,raw):
    # reuse original (possibly padded) varint bytes if they still encode the same value
    if raw is not None and read_varint(raw,0)[0]==v: return raw
    return write_varint(v)

class Val:
    __slots__=('t','raw')
    def __init__(s,t,raw): s.t=t; s.raw=raw
    def enc(s): return bytes([s.t])+s.raw
class Arr:
    __slots__=('t','raw','szraw')
    def __init__(s,t,raw,szraw=None): s.t=t; s.raw=raw; s.szraw=szraw
    def enc(s): return bytes([s.t])+vi(len(s.raw),s.szraw)+s.raw
class Rec:
    __slots__=('name','ver','kids','block','special','long','szraw','cntraw','elraw')
    def __init__(s,name,ver,kids,block=False,special=None,long=False):
        s.name=name;s.ver=ver;s.kids=kids;s.block=block;s.special=special;s.long=long
        s.szraw=None;s.cntraw=None;s.elraw=None
    def header(s):
        if s.special is not None: return s.special
        if s.long:
            f=0x80|0x20|(0x40 if s.block else 0)
            return bytes([f])+struct.pack('<H',s.name)+bytes([s.ver])
        info=0x8000|(0x4000 if s.block else 0)|((s.ver&0xf)<<9)|(s.name&0x1ff)
        return struct.pack('>H',info)
    def enc(s):
        if s.block:
            body=b''
            for i,el in enumerate(s.kids):
                eb=b''.join(n.enc() for n in el)
                raw=s.elraw[i] if s.elraw is not None and i<len(s.elraw) else None
                body+=vi(len(eb),raw)+eb
            return s.header()+vi(len(body),s.szraw)+vi(len(s.kids),s.cntraw)+body
        body=b''.join(n.enc() for n in s.kids)
        return s.header()+vi(len(body),s.szraw)+body

def parse_seq(d,p,end):
    nodes=[]
    while p<end:
        n,p=parse_node(d,p)
        nodes.append(n)
    if p!=end: raise AssertionError(('overrun',p,end))
    return nodes

def parse_node(d,p):
    b=d[p]
    if b&0x80:
        block=bool(b&0x40); long=bool(b&0x20)
        if long:
            name=struct.unpack_from('<H',d,p+1)[0]; ver=d[p+3]; p+=4
        else:
            info=(d[p]<<8)|d[p+1]
            ver=(info>>9)&0xf; name=info&0x1ff; p+=2
        p0=p
        size,p=read_varint(d,p); szraw=d[p0:p]
        if block:
            p1=p
            count,p=read_varint(d,p); cntraw=d[p1:p]
            end=p+size
            els=[]; elraw=[]
            for _ in range(count):
                p2=p
                sz,p=read_varint(d,p); elraw.append(d[p2:p])
                els.append(parse_seq(d,p,p+sz)); p+=sz
            if p!=end: raise AssertionError(('block end',p,end,name))
            r=Rec(name,ver,els,True,long=long); r.szraw=szraw; r.cntraw=cntraw; r.elraw=elraw
            return r,p
        end=p+size
        r=Rec(name,ver,parse_seq(d,p,end),long=long); r.szraw=szraw
        return r,end
    if 0x40<b<0x80:
        size,q=read_varint(d,p+1)
        return Arr(b,d[q:q+size],d[p+1:q]),q+size
    n=FIXED.get(b)
    if n is None: raise ValueError('unknown type %02x at %d'%(b,p))
    return Val(b,d[p+1:p+1+n]),p+1+n

def load(path):
    d=open(path,'rb').read()
    magic,_,ts,off=struct.unpack_from('<IIII',d,0)
    assert magic==0xabca
    n=struct.unpack_from('<H',d,off)[0]; q=off+2; names=[]
    for _ in range(n):
        l=struct.unpack_from('<H',d,q)[0]; names.append(d[q+2:q+2+l].decode()); q+=2+l
    tail=d[q:]
    hdr=d[16:20]
    size,p=read_varint(d,20)
    assert p+size==off,(p+size,off)
    kids=parse_seq(d,p,off)
    root=Rec(0,0,kids,special=hdr); root.szraw=d[20:p]
    return dict(ts=ts,names=names,tail=tail,root=root,hdr16=d[:16])

def save(doc,path):
    body=doc['root'].enc()
    off=16+len(body)
    out=bytearray(doc['hdr16'])
    struct.pack_into('<I',out,12,off)
    out+=body
    out+=struct.pack('<H',len(doc['names']))
    for nm in doc['names']:
        b=nm.encode(); out+=struct.pack('<H',len(b))+b
    out+=doc['tail']
    open(path,'wb').write(out)

def walk(n,depth=0,maxd=3,names=None):
    pad='  '*depth
    if isinstance(n,Rec):
        nm=names[n.name] if names else n.name
        print(f"{pad}{'[]' if n.block else '{}'} {nm} v{n.ver} ({len(n.kids)})")
        if depth<maxd:
            if n.block:
                for i,el in enumerate(n.kids[:2]):
                    print(f"{pad}  elem {i}:")
                    for k in el: walk(k,depth+2,maxd,names)
            else:
                for k in n.kids: walk(k,depth+1,maxd,names)
    elif isinstance(n,Arr): print(f"{pad}arr 0x{n.t:02x} len={len(n.raw)}")
    else: print(f"{pad}val 0x{n.t:02x} {n.raw.hex()}")

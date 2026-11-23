# Windows replacement for the lzenc helper (LZMA1 raw stream, known size, NO end marker).
# Uses any liblzma >= 5.4 through ctypes (LZMA_FILTER_LZMA1EXT); default: Inkscape's copy.
#   python lzwin.py in out dict_size lc lp pb        (same args as lzenc)
#   python lzwin.py --check file.lz props_hex usize   (verify: decodes to usize bytes, no EOS marker)
import sys, os, struct, lzma, ctypes as C
DLL = os.environ.get('LIBLZMA', r'C:\Program Files\Inkscape\bin\liblzma-5.dll')
FILTER_LZMA1EXT = 0x4000000000000002
VLI_UNKNOWN = 0xFFFFFFFFFFFFFFFF

class Opts(C.Structure):          # lzma_options_lzma (5.4+)
    _fields_ = [('dict_size', C.c_uint32), ('preset_dict', C.c_void_p), ('preset_dict_size', C.c_uint32),
                ('lc', C.c_uint32), ('lp', C.c_uint32), ('pb', C.c_uint32), ('mode', C.c_int),
                ('nice_len', C.c_uint32), ('mf', C.c_int), ('depth', C.c_uint32),
                ('ext_flags', C.c_uint32), ('ext_size_low', C.c_uint32), ('ext_size_high', C.c_uint32),
                ('r_int4', C.c_uint32), ('r_e1', C.c_int), ('r_e2', C.c_int), ('r_e3', C.c_int), ('r_e4', C.c_int),
                ('r_p1', C.c_void_p), ('r_p2', C.c_void_p)]
class Filter(C.Structure):
    _fields_ = [('id', C.c_uint64), ('options', C.c_void_p)]
class Stream(C.Structure):        # lzma_stream
    _fields_ = [('next_in', C.c_void_p), ('avail_in', C.c_size_t), ('total_in', C.c_uint64),
                ('next_out', C.c_void_p), ('avail_out', C.c_size_t), ('total_out', C.c_uint64),
                ('allocator', C.c_void_p), ('internal', C.c_void_p),
                ('rp', C.c_void_p * 4), ('ri', C.c_uint64 * 2), ('rs', C.c_size_t * 2), ('re', C.c_int * 2)]

def _lib():
    os.add_dll_directory(os.path.dirname(DLL))
    l = C.CDLL(DLL); l.lzma_version_string.restype = C.c_char_p
    assert l.lzma_version_number() >= 50040002, 'need liblzma >= 5.4, got %s' % l.lzma_version_string()
    return l

def compress(data, ds, lc, lp, pb):
    l = _lib(); o = Opts()
    assert l.lzma_lzma_preset(C.byref(o), 6) == 0
    o.dict_size, o.lc, o.lp, o.pb = ds, lc, lp, pb
    o.ext_flags = 0                                   # no LZMA_LZMA1EXT_ALLOW_EOPM
    o.ext_size_low, o.ext_size_high = len(data) & 0xFFFFFFFF, len(data) >> 32
    flt = (Filter * 2)(Filter(FILTER_LZMA1EXT, C.cast(C.pointer(o), C.c_void_p)), Filter(VLI_UNKNOWN, None))
    s = Stream()
    r = l.lzma_raw_encoder(C.byref(s), flt); assert r == 0, 'lzma_raw_encoder %d' % r
    inb = C.create_string_buffer(data, len(data)); cap = len(data) + len(data) // 2 + 65536
    outb = C.create_string_buffer(cap)
    s.next_in, s.avail_in = C.cast(inb, C.c_void_p), len(data)
    s.next_out, s.avail_out = C.cast(outb, C.c_void_p), cap
    r = l.lzma_code(C.byref(s), 3)                    # LZMA_FINISH
    n = s.total_out; l.lzma_end(C.byref(s))
    assert r == 1, 'lzma_code %d' % r                 # LZMA_STREAM_END
    return outb.raw[:n]

def encode(fin, fout, ds, lc, lp, pb):
    data = open(fin, 'rb').read()
    blob = compress(data, ds, lc, lp, pb)
    check(blob, bytes([(pb * 5 + lp) * 9 + lc]) + struct.pack('<I', ds), len(data), data)
    open(fout, 'wb').write(blob)

def check(blob, props, usz, expect=None):
    out = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(props + struct.pack('<Q', usz) + blob)
    assert len(out) == usz and (expect is None or out == expect), 'roundtrip mismatch'
    d = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)  # unknown size: an EOS marker would set eof
    try: d.decompress(props + b'\xff' * 8 + blob)
    except lzma.LZMAError: pass
    assert not d.eof, 'stream has an end marker'

if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == '--check':
        check(open(a[1], 'rb').read(), bytes.fromhex(a[2]), int(a[3])); print('ok')
    else:
        encode(a[0], a[1], *map(int, a[2:6]))

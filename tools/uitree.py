"""Read an etwng ui2xml file into a tree of uientry blocks (by line ranges) and print it.

usage: python uitree.py <file.xml> [max_depth] [name_filter]
Each node: depth, name, line range, child count, x/y offset, first state's size.
"""
import re, sys


class Node:
    def __init__(self, start, depth, parent):
        self.start, self.end, self.depth, self.parent = start, None, depth, parent
        self.children, self.name = [], None


def parse(lines):
    root = Node(0, -1, None)
    cur = root
    for i, l in enumerate(lines):
        s = l.strip()
        if s == "<uientry>":
            n = Node(i, cur.depth + 1, cur)
            cur.children.append(n)
            cur = n
        elif s == "</uientry>":
            cur.end = i
            cur = cur.parent
        elif cur is not root and cur.name is None:
            m = re.match(r"<s>(.*)</s><!-- title -->", s)
            if m:
                cur.name = m.group(1)
    return root


def info(lines, n):
    off = []
    size = None
    for i in range(n.start, min(n.end, n.start + 400)):
        s = lines[i].strip()
        if "<!-- x offset -->" in s or "<!-- y offset -->" in s:
            off.append(re.sub(r"<[^>]+>", "", s.split("<!--")[0]))
        if size is None and "<!-- x size -->" in s and "<state>" in "".join(lines[max(n.start, i - 4):i]):
            size = (re.sub(r"<[^>]+>", "", s.split("<!--")[0]),
                    re.sub(r"<[^>]+>", "", lines[i + 1].split("<!--")[0].strip()))
        if s == "<uientry>" and i != n.start:
            break
    return off[:2], size


def walk(lines, n, maxd, flt, out):
    for c in n.children:
        if c.depth <= maxd and (not flt or flt in (c.name or "")):
            off, size = info(lines, c)
            out.append("%s%s  [%d-%d] kids %d off %s size %s" % ("  " * c.depth, c.name, c.start + 1, c.end + 1,
                                                                 len(c.children), ",".join(off), size))
        walk(lines, c, maxd, flt, out)


if __name__ == "__main__":
    lines = open(sys.argv[1], encoding="utf-8-sig").read().split("\n")
    maxd = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    flt = sys.argv[3] if len(sys.argv) > 3 else None
    out = []
    walk(lines, parse(lines), maxd, flt, out)
    print("\n".join(out))

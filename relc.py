#!/usr/bin/python3

import sys
import sqlite3

class Predicate:
    def __init__(self, p, args):
        self.p = p
        self.args = args
    def __str__(self):
        return self.p + '(' + ', '.join(self.args) + ')'
    def __repr__(self):
        return self.p + '(' + ', '.join(self.args) + ')'

class LookAhead:
    def __init__(self, it):
        self._it = iter(it)
        self._x = None
        self._cached = False
        self._popcount = 0

    def _fillcache(self):
        if not self._cached:
            self._x = next(self._it)
            self._cached = True

    def hasnext(self):
        try:
            self._fillcache()
            return True
        except StopIteration:
            return False

    def peek(self):
        self._fillcache()
        return self._x

    def pop(self):
        self._fillcache()
        self._cached = False
        self._popcount += 1
        return self._x

    def get_popcount(self):
        return self._popcount

    def undo(self, oldcount):
        d = self.get_popcount() - oldcount
        if d == 0:
            return True
        elif self._cached is None and d == 1:
            self.cached = True
            return True
        else:
            return False

def sequence(parsers):
    def parsesequence(stream):
        result = []
        for p in parsers:
            x = p(stream)
            if x is None:
                return None
            result.append(x)
        return result
    return parsesequence

def alternative(parsers):
    def parsealternative(stream):
        c = stream.get_popcount()
        for p in parsers:
            x = p(stream)
            if x is not None:
                return x
            if not stream.undo(c):
                return None
    return parsealternative

def many(parser):
    def parsemany(stream):
        result = []
        while True:
            c = stream.get_popcount()
            x = parser(stream)
            if x is None:
                if stream.undo(c):
                    return result
                else:
                    return None
            result.append(x)
    return parsemany

def many1(parser):
    return sequence(parser, many(parser))

def eof(stream):
    if stream.hasnext():
        return None
    else:
        return True

def string(x):
    def parsestring(stream):
        if stream.hasnext() and stream.peek() == x:
            return stream.pop()
    return parsestring

def comma(stream):
    return string(',')(stream)

def parenleft(stream):
    return string('(')(stream)

def parenright(stream):
    return string(')')(stream)

def sepby(sep, p):
    def parsesepby(stream):
        if not stream.hasnext():
            return x
        x = p(stream)
        if x is None:
            return None
        c = stream.get_popcount()
        rest = many(sequence([sep, p]))(stream)
        if rest is None:
            if stream.undo(c):
                return [x]
            else:
                return None
        result = [x]
        for y, z in rest:
            result.append(y)
            result.append(z)
        return result
    return parsesepby

def sepbyignore(sep, p):
    q = sepby(sep, p)
    def parsesepbyignore(stream):
        x = q(stream)
        if x is None:
            return None
        return x[0::2]
    return parsesepbyignore

def identifier(stream):
    if stream.hasnext():
        x = stream.peek()
        if x.isalnum() or x == '*' or x.startswith('"'):
            return stream.pop()

def predicate(stream):
    p = identifier(stream)
    if p is None:
        return None
    x = parenleft(stream)
    if x is None:
        return None
    args = sepbyignore(comma, identifier)(stream)
    if args is None:
        return None
    x = parenright(stream)
    if x is None:
        return None
    return Predicate(p, args)

def conjunction(stream):
    return sepbyignore(string('&&'), predicate)(stream)

def relational_calculus(stream):
    x = sepbyignore(string('||'), conjunction)(stream)
    if x is None:
        return None
    if not eof(stream):
        return None
    return x

class Schema:
    def __init__(self, tables):
        self.tables = tables

    def getheader(self, tablename):
        return self.tables.get(tablename)

def makesqlconj(schema, wants, conj):
    froms = []
    bound = []
    preds = dict()
    for p in conj:
        if p.p not in schema:
            raise Exception('No such table:', p.p)
        if len(p.args) != len(schema[p.p]):
            raise Exception('Wrong number of arguments: {}'.format(p))
    for i, p in enumerate(conj):
        pname = '{}{}'.format(p.p, i)
        froms.append((p.p, pname))
        for j, v in enumerate(p.args):
            colname = schema[p.p][j]
            coords = pname, colname
            if v == '*':
                continue
            if v.startswith('"') or v.isdigit():
                bound.append((pname, colname, v))
            if v not in preds:
                preds[v] = set()
            preds[v].add(coords)
    for v in wants:
        if v not in preds:
            raise Exception('variable %s not bound in conjunction %s' % (v,preds))
    result = 'SELECT DISTINCT'
    xs = []
    for v in wants:
        p = next(iter(preds[v]))
        xs.append('\n\t%s.%s AS %s' % (p[0], p[1], v))
    result += ','.join(xs)
    result += '\nFROM'
    result += ','.join('\n\t{} {}'.format(x, y) for x,y in froms)
    result += '\nWHERE 1'
    for t, c, v in bound:
        result += '\n\tAND {}.{} = {}'.format(t, c, v)
    for same in preds.values():
        same = list(same)
        for x in same:
            for y in same[1:]:
                if x != y:
                    result += '\n\tAND {}.{} = {}.{}'.format(x[0],x[1],y[0],y[1])
    result += "\nORDER BY {} ASC".format(', '.join(wants))
    return result

def makesql(schema, wants, rel):
    sqls = [makesqlconj(schema, wants, conj) for conj in rel]
    return '\nUNION\n'.join(sqls)

def lex(query):
    import re
    out = []
    exprs = [r'[a-zA-Z][a-zA-Z0-9]*', r'\*', r'"[^"]*"', r',', r'&&', r'\|\|',r'\(',r'\)']
    while True:
        query = query.strip()
        if not query:
            break
        x = None
        for e in exprs:
            m = re.match(e, query)
            if m is not None:
                x = m.group(0)
                break
        if x is None:
            return None
        query = query[len(x):]
        out.append(x)
    return out

def splitline(line):
    out = []
    w = ''
    escaped = False
    quoted = False
    for c in line:
        if escaped:
            w += c
            escaped = False
        elif c == '\\':
            escaped = True
        elif c == '"':
            quoted = not quoted
        elif quoted or not c.isspace():
            w += c
        elif w:
            out.append(w)
            w = ''
    if quoted or escaped:
        print('Unexpected end of line: ' + line, file=sys.stderr)
        return None
    return out

def joinline(args):
    out = []
    for x in args:
        x = x.replace('\\','\\\\')
        x = x.replace('"', '\\"')
        if len(x.split(None, 1)) > 1:
            x = '"' + x + '"'
        out.append(x)
    return '\t'.join(out)

schema = {}
conn = sqlite3.connect(':memory:')
dodebug = False

def build_db(lines):
    defaultcolnames = list('abcdefghijklmnopqrstuvwxyz')
    for line in lines:
        words = splitline(line)
        if not words or words[0].startswith('#') or words[0].startswith('!'):
            continue
        tblname = words[0]
        values = words[1:]
        if len(values) > 26:
            raise Exception('too many columns: ' + line)
        if len(values) == 0:
            raise Exception('value(s) missing: ' + line)
        if tblname not in schema:
            schema[tblname] = defaultcolnames[:len(values)]
            names = ', '.join(x + ' VARCHAR NOT NULL' for x in schema[tblname])
            sql = 'CREATE TABLE {} ({});'.format(tblname, names)
            debug(sql)
            conn.execute(sql)
        if len(values) != len(schema[tblname]):
            raise Exception('wrong number of values: ' + line)
        sql = 'INSERT INTO {} VALUES ({})'.format(tblname, ', '.join('?'*len(values)))
        conn.execute(sql, values)
    return schema

def debug(*args):
    global dodebug
    if dodebug:
        print(*args)

if __name__ == '__main__':
    args = tuple(sys.argv[1:])

    if args and args[0] == '--debug':
        dodebug = True
        args = args[1:]

    if len(args) != 2:
        print("""\
Usage:

{} [--debug] '<var> [<var>...]' '<DRC query>'  < input.txt

Example:

./relc.py S,SD,L,LD 'student(S,SD) && immatriculated(S, "2016") && lecture(L,LD) && registered(S,L)'  < example.txt""".format(sys.argv[0], sys.argv[0]), file=sys.stderr)
        sys.exit(1)

    wants = args[0].replace(',',' ').split()
    tokens = lex(args[1])
    if tokens is None:
        raise Exception('Failed to lex query')
    calc = relational_calculus(LookAhead(tokens))
    if calc is None:
        raise Exception('Failed to parse query')

    debug('query parsed as', calc)
    build_db(sys.stdin)

    debug()
    sql = makesql(schema, wants, calc)
    debug(sql)
    debug()

    for x in conn.execute(sql):
        print(joinline(x))

# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division


# standard library dependencies
import io
import json
from json.encoder import JSONEncoder
from petl.compat import PY2


# internal dependencies
from petl.util.base import data, Table, dicts as _dicts
from petl.io.sources import read_source_from_arg, write_source_from_arg


def fromjson(source, *args, **kwargs):
    """
    Extract data from a JSON file. The file must contain a JSON array as
    the top level object, and each member of the array will be treated as a
    row of data. E.g.::

        >>> import petl as etl
        >>> data = '''
        ... [{"foo": "a", "bar": 1},
        ... {"foo": "b", "bar": 2},
        ... {"foo": "c", "bar": 2}]
        ... '''
        >>> with open('example.json', 'w') as f:
        ...     f.write(data)
        ...
        74
        >>> table1 = etl.fromjson('example.json')
        >>> table1
        +-----+-----+
        | bar | foo |
        +=====+=====+
        |   1 | 'a' |
        +-----+-----+
        |   2 | 'b' |
        +-----+-----+
        |   2 | 'c' |
        +-----+-----+

    If your JSON file does not fit this structure, you will need to parse it
    via :func:`json.load` and select the array to treat as the data, see also
    :func:`petl.io.json.fromdicts`.

    """

    source = read_source_from_arg(source)
    return JsonView(source, *args, **kwargs)


class JsonView(Table):

    def __init__(self, source, *args, **kwargs):
        self.source = source
        self.args = args
        self.kwargs = kwargs
        self.missing = kwargs.pop('missing', None)
        self.header = kwargs.pop('header', None)

    def __iter__(self):
        with self.source.open('rb') as f:
            if not PY2:
                # wrap buffer for text IO
                f = io.TextIOWrapper(f, encoding='utf-8', newline='',
                                     write_through=True)
            try:
                result = json.load(f, *self.args, **self.kwargs)
                if self.header is None:
                    # determine fields
                    hdr = set()
                    for o in result:
                        if hasattr(o, 'keys'):
                            hdr |= set(o.keys())
                    hdr = sorted(hdr)
                else:
                    hdr = self.header
                yield tuple(hdr)
                # output data rows
                for o in result:
                    row = tuple(o[f] if f in o else None for f in hdr)
                    yield row
            finally:
                if not PY2:
                    f.detach()


def fromdicts(dicts, header=None):
    """
    View a sequence of Python :class:`dict` as a table. E.g.::

        >>> import petl as etl
        >>> dicts = [{"foo": "a", "bar": 1},
        ...          {"foo": "b", "bar": 2},
        ...          {"foo": "c", "bar": 2}]
        >>> table1 = etl.fromdicts(dicts)
        >>> table1
        +-----+-----+
        | bar | foo |
        +=====+=====+
        |   1 | 'a' |
        +-----+-----+
        |   2 | 'b' |
        +-----+-----+
        |   2 | 'c' |
        +-----+-----+

    See also :func:`petl.io.json.fromjson`.

    """

    return DictsView(dicts, header=header)


class DictsView(Table):

    def __init__(self, dicts, header=None):
        self.dicts = dicts
        self.header = header

    def __iter__(self):
        result = self.dicts
        if self.header is None:
            # determine fields
            hdr = set()
            for o in result:
                if hasattr(o, 'keys'):
                    hdr |= set(o.keys())
            hdr = sorted(hdr)
        else:
            hdr = self.header
        yield tuple(hdr)
        # output data rows
        for o in result:
            row = tuple(o[f] if f in o else None for f in hdr)
            yield row


def tojson(table, source=None, prefix=None, suffix=None, *args, **kwargs):
    """
    Write a table in JSON format, with rows output as JSON objects. E.g.::

        >>> import petl as etl
        >>> table1 = [['foo', 'bar'],
        ...           ['a', 1],
        ...           ['b', 2],
        ...           ['c', 2]]
        >>> etl.tojson(table1, 'example.json', sort_keys=True)
        >>> # check what it did
        ... print(open('example.json').read())
        [{"bar": 1, "foo": "a"}, {"bar": 2, "foo": "b"}, {"bar": 2, "foo": "c"}]

    Note that this is currently not streaming, all data is loaded into memory
    before being written to the file.

    """

    obj = list(_dicts(table))
    _writejson(source, obj, prefix, suffix, *args, **kwargs)


Table.tojson = tojson


def tojsonarrays(table, source=None, prefix=None, suffix=None,
                 output_header=False, *args, **kwargs):
    """
    Write a table in JSON format, with rows output as JSON arrays. E.g.::

        >>> import petl as etl
        >>> table1 = [['foo', 'bar'],
        ...           ['a', 1],
        ...           ['b', 2],
        ...           ['c', 2]]
        >>> etl.tojsonarrays(table1, 'example.json')
        >>> # check what it did
        ... print(open('example.json').read())
        [["a", 1], ["b", 2], ["c", 2]]

    Note that this is currently not streaming, all data is loaded into memory
    before being written to the file.

    """

    if output_header:
        obj = list(table)
    else:
        obj = list(data(table))
    _writejson(source, obj, prefix, suffix, *args, **kwargs)


Table.tojsonarrays = tojsonarrays


def _writejson(source, obj, prefix, suffix, *args, **kwargs):
    encoder = JSONEncoder(*args, **kwargs)
    source = write_source_from_arg(source)
    with source.open('wb') as f:
        if PY2:
            # write directly to buffer
            _writeobj(encoder, obj, f, prefix, suffix)
        else:
            # wrap buffer for text IO
            f = io.TextIOWrapper(f, encoding='utf-8', newline='',
                                 write_through=True)
            try:
                _writeobj(encoder, obj, f, prefix, suffix)
            finally:
                f.detach()


def _writeobj(encoder, obj, f, prefix, suffix):
    if prefix is not None:
        f.write(prefix)
    for chunk in encoder.iterencode(obj):
        f.write(chunk)
    if suffix is not None:
        f.write(suffix)

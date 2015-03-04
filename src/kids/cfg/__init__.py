# -*- coding: utf-8 -*-


import os
import sys

from kids.cache import cache
from kids.data import mdict, dct

##
## Cfg Managers
##


class Cfg(object):

    def __init__(self, filename):
        self._filename = filename

    @cache
    @property
    def _cfg(self):
        raise NotImplementedError()

    def save(self):
        raise NotImplementedError()


def mkCustomCfg(name, load, save):

    class CustomCfg(Cfg):

        @cache
        @property
        def _cfg(self):
            return load(self._filename)

        def save(self):
            save(self._filename, self._cfg)

    CustomCfg.__name__ = name

    return CustomCfg


## PyCfg

class PyCfg(Cfg):
    """Python file config parser

        >>> import kids.file as kf
        >>> from pprint import pprint as pp

        >>> cfgfile = kf.mk_tmp_file("x = 1 ; b = 2; c = lambda: max(x, b)")

        >>> cfg = PyCfg(cfgfile)
        >>> pp(cfg._cfg)
        {'b': 2, 'c': <function <lambda> at ...>, 'x': 1}

    Checking that callable are still callable::

        >>> cfg._cfg['c']()
        2

    """

    def __init__(self, filename, config=None):
        super(PyCfg, self).__init__(filename)
        self.config = config

    @cache
    @property
    def _cfg(self):
        cfg = {} if self.config is None else self.config.copy()

        try:
            with open(self._filename) as f:
                code = compile(f.read(), self._filename, 'exec')
                exec(code, cfg)
        except SyntaxError as e:
            raise SyntaxError(
                'Syntax error in config file: %s\n'
                'Line %i offset %i\n' % (self._filename, e.lineno, e.offset))

        ## XXXvlab: if we remove this, any closure will fail :(
        #del cfg['__builtins__']
        ## Prefering to copy dict without ``__builtins__``
        return dict((k, v) for k, v in cfg.items()
                    if k != "__builtins__")


## ConfigObjCfg

try:
    import configobj
except ImportError:
    configobj = None


if configobj:

    def loadConfigObj(filename):
        return configobj.ConfigObj(filename)

    def saveConfigObj(_filename, content):
        content.write()

    ConfigObjCfg = mkCustomCfg("ConfigObjCfg", loadConfigObj, saveConfigObj)

else:

    def ConfigObjCfg(_f):
        raise ValueError(
            "You can't use ConfigObjLoader since 'configobj' "
            "is not available on your system.")


## YamlCfg

try:
    import yaml
except ImportError:
    yaml = None


if yaml:

    def loadYaml(filename):
        with open(filename, 'r') as f:
            return yaml.load(f)

    def saveYaml(filename, content):
        with open(filename, 'w') as f:
            f.write(yaml.dump(content, default_flow_style=False))

    YamlCfg = mkCustomCfg("YamlCfg", loadYaml, saveYaml)

else:

    def YamlCfg(_f):
        raise ValueError(
            "You can't use YamlLoader since 'yaml' "
            "is not available on your system.")

_GENERIC_CFG = [PyCfg, ConfigObjCfg, YamlCfg]


def choose_cfg_manager(filename):
    for cm in _GENERIC_CFG:
        try:
            cm(filename)._cfg
            return cm(filename)
        except Exception:
            pass
    raise SyntaxError(
        "No config parser manage to read config file %r."
        % (filename, ))


class Config(dct.AttrDictAbstract):
    """Config file access

    This wraps the given config file and provide way to browse
    its values::

        >>> from pprint import pprint as pp
        >>> import kids.file as kf

    Manipulation API
    ================

    Let's open this config file::

        >>> cfgfile = kf.mk_tmp_file("x = 1 ; b = {'foo': x + 2}")
        >>> cfg = Config(cfgfile)

        >>> cfg
        <Config '...' (2 values)>

    dict interface
    --------------

    This object give a nearly full dict interface for read access::

        >>> sorted(cfg.keys())
        ['b', 'x']

        >>> sorted(cfg.items())
        [('b', <Config ... prefix='b')>),
         ('x', 1)]

        >>> for k in sorted(cfg):
        ...     print(k)
        b
        x

        >>> "c" in cfg
        False
        >>> "x" in cfg
        True

        >>> cfg['b']['foo']
        3
        >>> cfg['x']
        1
        >>> cfg.get('x')
        1
        >>> cfg['z']
        Traceback (most recent call last):
        ...
        MissingKeyError: missing key 'z' in dict.
        >>> cfg.get('z')


    attribute dict interface
    ------------------------

    Access via attribute is working also::

        >>> getattr(cfg, 'b.foo')
        3
        >>> cfg.b.foo
        3

    mdict interface
    ---------------

    Allows you to provide the path in one go in the getitem:

        >>> cfg.get('b.foo')
        3
        >>> cfg['b.foo']
        3

    This can reveal itself as useful when accessing directly some
    values from command line arguments for instance. And it's strong
    enough to allow you escaping"." with slashes, and slashes with ... slashes:
    So basically this dotted access allow you to address any part
    of your file in one go.

        >>> kf.rm(cfgfile)

    Config Parsers
    ==============

    Loading this file with the python config parser::

        >>> cfgfile = kf.mk_tmp_file("x = 1 ; b = {'foo': x + 2}")
        >>> cfg = Config(PyCfg(cfgfile))

    You can then query the file with::

        >>> cfg.x
        1

    Or even more complex structures like dict are traversable via
    attribute access::

        >>> cfg.b.foo
        3

    Please see the read API section for a complete overview of
    what you can do once the config file is loaded.

        >>> kf.rm(cfgfile)

    Yaml
    ----

    You can provide other loaders as yaml::

        >>> cfgfile = kf.mk_tmp_file('''
        ... a:
        ...     b: 1
        ... x: 2''')

        >>> cfg = Config(YamlCfg(cfgfile))
        >>> cfg.a.b
        1
        >>> cfg.x
        2

        >>> kf.rm(cfgfile)


    ConfigObj
    ---------

    Or ConfigObj::

        >>> cfgfile = kf.mk_tmp_file('''
        ... [a]
        ... [[x]]
        ... foo = 1
        ... [b]
        ... bar = 2''')

        >>> cfg = Config(ConfigObjCfg(cfgfile))
        >>> cfg.a.x.foo
        '1'
        >>> cfg.b.bar
        '2'

        >>> kf.rm(cfgfile)


    Writing values back
    ===================

    There's write support to config files::

        >>> cfgfile = kf.mk_tmp_file('''
        ... a:
        ...     b: 1
        ... x: 2''')
        >>> cfg = Config(cfgfile)

    With full set item support::

        >>> cfg['x'] = 3  ## overwrite on existing value
        >>> cfg['y'] = 9  ## create new direct value

        >>> print(kf.get_contents(cfgfile).strip())
        a:
          b: 1
        x: 3
        y: 9

        >>> cfg['a']['c'] = 2
        >>> print(kf.get_contents(cfgfile).strip())
        a:
          b: 1
          c: 2
        x: 3
        y: 9

    If you need to create new sections, the best is to
    use the dotted notation::

        >>> cfg['k']['u'] = 2
        Traceback (most recent call last):
        ...
        MissingKeyError: missing key 'k' in dict.

    Which seems logical, so you should try::

        >>> cfg['k.u'] = 2
        >>> print(kf.get_contents(cfgfile).strip())
        a:
          b: 1
          c: 2
        k:
          u: 2
        x: 3
        y: 9


    Python
    ------

    Not all the config managerss have writing support. Python config manager
    for instance has only read support, so::

        >>> cfgfile = kf.mk_tmp_file("x = 1 ; b = {'foo': x + 2}")
        >>> cfg = Config(PyCfg(cfgfile))

        >>> cfg.b.bar = 2
        Traceback (most recent call last):
        ...
        NotImplementedError...

        >>> kf.rm(cfgfile)


    ConfigObj
    ---------

    Full read/write support is implemented in ConfigObj config manager.

        >>> cfgfile = kf.mk_tmp_file('''
        ... [a]
        ... [[x]]
        ... foo = 1
        ... [b]
        ... bar = 2''')

        >>> cfg = Config(ConfigObjCfg(cfgfile))

        >>> cfg.a.c = 2
        >>> cfg['a']['x'].foo = 3
        >>> print(kf.get_contents(cfgfile).strip())
        [a]
        c = 2
        [[x]]
        foo = 3
        [b]
        bar = 2

        >>> kf.rm(cfgfile)


    Yaml
    ----

    Full read/write support is implemented in Yaml config manager.

        >>> cfgfile = kf.mk_tmp_file('''
        ... a:
        ...     b: 1
        ... x: 2''')
        >>> cfg = Config(YamlCfg(cfgfile))

        >>> cfg['a.c'] = 2
        >>> cfg['a']['b'] = 3
        >>> print(kf.get_contents(cfgfile).strip())
        a:
          b: 3
          c: 2
        x: 2

        >>> kf.rm(cfgfile)


    Automatic Syntax discovery
    ==========================

    You don't really need to provide a Config manage as it'll be chosen
    accordingly::

    Yaml detection
    --------------

        >>> cfgfile = kf.mk_tmp_file('''
        ... a:
        ...     b: 1
        ... x: 2''')
        >>> cfg = Config(cfgfile)

        >>> del cfg['a']
        >>> print(kf.get_contents(cfgfile).strip())
        x: 2

        >>> kf.rm(cfgfile)

    ConfigObj detection
    -------------------

        >>> cfgfile = kf.mk_tmp_file('''
        ... [a]
        ... [[x]]
        ... foo = 1
        ... [b]
        ... bar = 2''')

        >>> cfg = Config(cfgfile)
        >>> del cfg.a
        >>> print(kf.get_contents(cfgfile).strip())
        [b]
        bar = 2

        >>> kf.rm(cfgfile)


    Python config detection
    -----------------------

        >>> cfgfile = kf.mk_tmp_file("x = 1 ; b = {'foo': x + 2}")
        >>> Config(cfgfile).b.foo
        3

        >>> kf.rm(cfgfile)


    No detection
    ------------

        >>> cfgfile = kf.mk_tmp_file('XXX%%%: !!')
        >>> xx = Config(cfgfile)
        Traceback (most recent call last):
        ...
        SyntaxError: No config parser manage to read config file ...

        >>> kf.rm(cfgfile)

    """

    def __init__(self, config=None, prefix=None, cfg=None):
        self._prefix = prefix if prefix else []
        self._cfg_manager = config if isinstance(config, Cfg) \
                            else choose_cfg_manager(config)
        self._provided_cfg = cfg

    @cache
    @property
    def _cfg(self):
        if self._provided_cfg:
            return self._provided_cfg
        ## this can be overridden at ``init()`` time, by providing a ``cfg``.
        return self._cfg_manager._cfg

    @cache
    @property
    def _tprefix(self):
        return self._mcfg.untokenize(self._prefix)

    @cache
    @property
    def _mcfg(self):
        return mdict.mdict(self._cfg)

    def __getitem__(self, label):
        res = self._mcfg[label]
        if isinstance(res, mdict.mdict):
            return self.__class__(
                self._cfg_manager,
                prefix=self._prefix + [label],
                cfg=res.dct)
        return res

    def __iter__(self):
        return self._cfg.__iter__()

    def __setitem__(self, label, value):
        self._mcfg[label] = value
        self._cfg_manager.save()

    def __delitem__(self, label):
        del self._mcfg[label]
        self._cfg_manager.save()

    def __repr__(self, ):
        return (
            "<%s %r (%s values%s)>"
            % (self.__class__.__name__,
               self._cfg_manager._filename,
               len(self._mcfg.flat),
               (" prefix=%r" % self._tprefix)
               if self._prefix else ""))


def load_files(filenames, config_factory=Config):
    """Loads data from a config file."""
    return dct.MultiDictReader([config_factory(f) for f in filenames])


Null = object()


def load(basename=None, default=Null, config_file=None, local_path=None,
         config_struct=None, config_factory=Config):
    """Load local script configuration."""

    if basename is None:
        ## try to infer the basename of the current executable to
        ## get the various places where it could be stored.
        basename = os.path.basename(sys.argv[0])
        if basename.endswith(".py"):
            basename = basename[:-3]
    if config_struct is None:
        config_struct = [
            ## Typically forced config file location via command line:
            (True, False, lambda: config_file),
            ## Environment variable config file location:
            (True, False, lambda: os.environ.get('%s_CONFIG_FILENAME'
                                                 % basename.upper())),
        ]
        if local_path:
            config_struct.append(
                (False, True, lambda: os.path.expanduser('~/.%s.rc' % b)))
        config_struct.extend([
            ## Standard cascaded paths
            (False, True, lambda: os.path.expanduser('~/.%s.rc' % basename)),
            (False, True, lambda: os.path.expanduser('~/.%s.rc' % basename)),
            (False, True, lambda: '/etc/%s.rc' % basename),
        ])

    filenames = find_files(config_struct, default is Null)
    return load_files(filenames, config_factory=config_factory) \
           if len(filenames) else default


def find_files(research_structure, raise_on_all_missing=True):
    """Returns list of existing filename matching research_structure specs.

    The research structure allows to define a policy to find files in a
    specific order and bail out if some of them matched, or keep looking
    if necessary. Eventually cumulating and returning several matched
    files.

    The struct is a list of 3-uples:

       [(enforce_file_existence, should_cascade, get_filename),
        ...]

    ``get_filename``

        is a callable that takes only one argument, the ``basename``
        which is the base identifier of your application (often the
        name of your executable). Call of this function should return
        an expanded file path to look for or value None. See the usage
        section to see concrete examples.

    ``enforce_file_existence``

        is a boolean, if True, and ``get_filename`` returns a filepath
        then it must exist otherwise an exception will be casted. If False,
        the existence of the file is not important, and next value
        of the struct will be considered silently if not existent.

    ``cascaded``

        is a boolean, if True, then the following 3-uple will be considered
        and may be added to the final returned files. If False, and the
        current ``get_filename`` returned and file and this file exist, then
        this file is considered as the final file, and will be trigger the
        return of the function.

    Usage
    =====

    Here's a few examples. Let's first setup a temporary directory::

        >>> import kids.file as kf
        >>> tmpdir = kf.mk_tmp_dir()

    and make a few files::

        >>> os.chdir(tmpdir)
        >>> kf.touch('foo.rc')
        >>> kf.touch('.foo.rc')

    Basic
    -----

    Here's a typical way to use ``find_files``::

        >>> find_files([(False, False, lambda: 'foo.rc'),
        ...             (False, False, lambda: '.foo.rc')])
        ['foo.rc']

    As the second value (the ``cascaded`` value) is always false, only
    one result can be outputed in the returned list. It'll be the
    first existing file.

    If the first file didn't exist::

        >>> find_files([(False, False, lambda: 'bar.rc'),
        ...             (False, False, lambda: '.foo.rc')])
        ['.foo.rc']

    If none are existing::

        >>> find_files([(False, False, lambda: 'bar.rc'),
        ...             (False, False, lambda: '.bar.rc')])
        Traceback (most recent call last):
        ...
        ValueError: No config file was found in those paths: bar.rc, .bar.rc.

    But you can prevent this by setting ``raise_on_all_missing`` to ``False``::

        >>> find_files([(False, False, lambda: 'bar.rc'),
        ...             (False, False, lambda: '.bar.rc')],
        ...            raise_on_all_missing=False)
        []

    Cascaded
    --------

    In this case, both exists and the cascaded value for the first one is
    True, so both are returned::

        >>> find_files([(False, True, lambda: 'foo.rc'),
        ...             (False, False, lambda: '.foo.rc')])
        ['foo.rc', '.foo.rc']

    Enforce file existence
    ----------------------

    In some case if the 3rd value (the ``get_filename`` callable) returns a
    file path, we want to enforce this file to exist::

        >>> find_files([(True, True, lambda: 'bar.rc'),
        ...             (True, False, lambda: '.foo.rc')])
        Traceback (most recent call last):
        ...
        ValueError: File 'bar.rc' does not exists.

    In the following we ask to ignore this file if not existing::

        >>> find_files([(False, True, lambda: 'bar.rc'),
        ...             (True, False, lambda: '.foo.rc')])
        ['.foo.rc']

    And in this special case the 3rd value callable will return None,
    and this won't trigger any exception, even if enforcing is set::

        >>> find_files([(True, True, lambda: None),
        ...             (True, False, lambda: '.foo.rc')])
        ['.foo.rc']

        >>> kf.rm(tmpdir, recursive=True, force=True)

    """
    filenames = []
    paths_searched = []
    ## config file lookup resolution
    for enforce_file_existence, cascaded, fun in research_structure:
        candidate = fun()
        if candidate:
            if not os.path.exists(candidate):
                if enforce_file_existence:
                    raise ValueError("File %r does not exists." % candidate)
                else:
                    paths_searched.append(candidate)
                    continue  ## filename valued, but file does not exists
            else:
                filenames.append(candidate)
                if not cascaded:
                    break
    if not filenames and raise_on_all_missing:
        raise ValueError("No config file was found in those paths: %s."
                         % ', '.join(paths_searched))
    return filenames


def find_file(research_structure, raise_on_all_missing=True):
    """Returns first existing filename matching research_structure specs.

    The research structure allows to define a policy to find files in a
    specific order and bail out if some of them matched, or keep looking
    if necessary. Eventually cumulating and returning several matched
    files.

    The struct is a list of 3-uples:

       [(enforce_file_existence, get_filename),
        ...]

    ``get_filename``

        is a callable that takes only one argument, the ``basename``
        which is the base identifier of your application (often the
        name of your executable). Call of this function should return
        an expanded file path to look for or value None. See the usage
        section to see concrete examples.

    ``enforce_file_existence``

        is a boolean, if True, and ``get_filename`` returns a filepath
        then it must exist otherwise an exception will be casted. If False,
        the existence of the file is not important, and next value
        of the struct will be considered silently if not existent.

    Usage
    =====

    Here's a few examples. Let's first setup a temporary directory::

        >>> import kids.file as kf
        >>> tmpdir = kf.mk_tmp_dir()

    and make a few files::

        >>> os.chdir(tmpdir)
        >>> kf.touch('foo.rc')
        >>> kf.touch('.foo.rc')

    Basic
    -----

    Here's a typical way to use ``find_file``::

        >>> find_file([(False, lambda: 'foo.rc'),
        ...            (False, lambda: '.foo.rc')])
        'foo.rc'

    As the second value (the ``cascaded`` value) is always false, only
    one result can be outputed in the returned list. It'll be the
    first existing file.

    If the first file didn't exist::

        >>> find_file([(False, lambda: 'bar.rc'),
        ...            (False, lambda: '.foo.rc')])
        '.foo.rc'

    If no file exist::

        >>> find_file([(False, lambda: 'bar.rc'),
        ...            (False, lambda: '.bar.rc')])
        Traceback (most recent call last):
        ...
        ValueError: No config file was found in those paths: bar.rc, .bar.rc.

    But you can prevent this by setting ``raise_on_all_missing`` to ``False``::

        >>> find_file([(False, lambda: 'bar.rc'),
        ...            (False, lambda: '.bar.rc')],
        ...            raise_on_all_missing=False)

    Which then returns 'None'.

    Enforce file existence
    ----------------------

    In some case if the 3rd value (the ``get_filename`` callable) returns a
    file path, we want to enforce this file to exist::

        >>> find_file([(True, lambda: 'bar.rc'),
        ...            (True, lambda: '.foo.rc')])
        Traceback (most recent call last):
        ...
        ValueError: File 'bar.rc' does not exists.

    In the following we ask to ignore this file if not existing::

        >>> find_file([(False, lambda: 'bar.rc'),
        ...            (True, lambda: '.foo.rc')])
        '.foo.rc'

    And in this special case the 2nd value callable will return None,
    and this won't trigger any exception, even if enforcing is set::

        >>> find_file([(True, lambda: None),
        ...            (True, lambda: '.foo.rc')])
        '.foo.rc'

        >>> kf.rm(tmpdir, recursive=True, force=True)

    """

    filenames = find_files(
        [(enforce_file_existence, False, fun)
         for enforce_file_existence, fun in research_structure],
        raise_on_all_missing=raise_on_all_missing)
    if not filenames:
        return None
    return filenames[0]

# -*- coding: utf-8 -*-

import os
import sys


##
## config file functions
##


def load_file(filename, fail_if_not_present=True):
    """Loads data from a config file."""

    config = {}

    if os.path.exists(filename):
        try:
            execfile(filename, config)
        except SyntaxError, e:
            raise SyntaxError(
                'Syntax error in config file: %s\n'
                'Line %i offset %i\n' % (filename, e.lineno, e.offset))
    else:
        if fail_if_not_present:
            raise SyntaxError('%r config file is not found and is required.'
                              % (filename, ))
    return config


def load(basename, default=None):
    config_struct = [
        (True, lambda: os.environ.get('%s_CONFIG_FILENAME' % basename)),
        (False, lambda: os.path.expanduser('~/.%s.rc' % basename)),
        (False, lambda: '/etc/%s.rc' % basename),
        ]
    config_file = find_file(config_struct,
                            raise_on_all_missing=default is None)
    return default if config_file is None else load_file(config_file)


def find_file(research_structure, raise_on_all_missing=True):
    changelogrc = None
    paths_searched = []
    ## config file lookup resolution
    for enforce_file_existence, fun in research_structure:
        candidate = fun()
        if candidate:
            if not os.path.exists(candidate):
                if enforce_file_existence:
                    raise ValueError("File %r does not exists." % candidate)
                else:
                    paths_searched.append(candidate)
                    continue  ## changelogrc valued, but file does not exists
            else:
                changelogrc = candidate
                break
    if not changelogrc:
        if raise_on_all_missing:
            raise ValueError("No config file was found in those paths: %s."
                             % ', '.join(paths_searched))
        else:
            return None
    return changelogrc

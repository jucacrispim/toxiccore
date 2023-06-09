# -*- coding: utf-8 -*-

# Copyright 2015-2019, 2023 Juca Crispim <juca@poraodojuca.net>

# This file is part of toxicbuild.

# toxicbuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# toxicbuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with toxicbuild. If not, see <http://www.gnu.org/licenses/>.

import base64
from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime, timezone, timedelta
import fnmatch
import importlib
import logging
import os
import random
import tempfile
import string
import sys
import time
import warnings

import bcrypt

from .exceptions import ConfigError
from .socks import (read_stream as read_sock_stream,
                    write_stream as write_sock_stream)


DTFORMAT = '%w %m %d %H:%M:%S %Y %z'


_THREAD_EXECUTOR = ThreadPoolExecutor()

WRITE_CHUNK_LEN = 4096
READ_CHUNK_LEN = 1024

logger = logging.getLogger('toxicbuild')


# copy from mongomotor
class MonkeyPatcher:

    def __init__(self):
        self.patched = {}
        # if the original patched object is a dict, indicates if
        # we should merge the original dict with the dict existing
        # when leaving the context manager.
        self._update_original_dict = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for obj, patches in self.patched.items():
            for attr, origobj in patches.items():
                if self._update_original_dict:  # pragma no cover
                    current_obj = getattr(obj, attr)
                    if hasattr(current_obj, 'update'):
                        origobj.update(current_obj)
                setattr(obj, attr, origobj)

    def patch_item(self, obj, attr, newitem, undo=True):
        """Sets ``attr`` in ``obj`` with ``newitem``.
        If not ``undo`` the item will continue patched
        after leaving the context manager"""

        NONE = object()
        olditem = getattr(obj, attr, NONE)
        if undo and olditem is not NONE:  # pragma no branch
            self.patched.setdefault(obj, {}).setdefault(attr, olditem)
        setattr(obj, attr, newitem)


class SourceSuffixesPatcher(MonkeyPatcher):
    """We must to path ``SOURCE_SUFFIXES`` in the python ``importlib`` so
    we can import source code files with extension other than `.py`, in
    this case, namely `.conf`"""

    SOURCE_SUFFIXES = ['.py', '.conf']

    def patch_source_suffixes(self):
        """Patches the ``SOURCE_SUFFIXES`` constant in the module
        :mod:`importlib._bootstrap_external`."""

        self.patch_item(importlib._bootstrap_external, 'SOURCE_SUFFIXES',
                        self.SOURCE_SUFFIXES)


# patching it now!
patcher = SourceSuffixesPatcher()
patcher.patch_source_suffixes()


# class SettingsPatcher(MonkeyPatcher):
#     """Patches the settings from pyrocumulus to use the same settings
#     as toxibuild."""

#     def patch_pyro_settings(self, settings):
#         from pyrocumulus import conf as pyroconf
#         self.patch_item(pyroconf, 'settings', settings)


def interpolate_dict_values(to_return, valued, base):
    """Interpolates the values of ``valued`` with values of ``base``.

    :param to_return: A dictionary that will be updated with interpolated
      values.
    :param valued: A dict with values needing interpolation.
    :param base: A dict with the base values to use in interpolation.
    """
    for var, value in valued.items():
        if var in value:
            current = base.get(var, '')
            value = value.replace(var, current)

        to_return[var] = value

    return to_return


def get_envvars(envvars, use_local_envvars=True):
    """Returns environment variables to be used in shell. Does the
    interpolation of values using the current values from the envvar
    and the values passed as parameters. """

    if use_local_envvars:
        newvars = copy.copy(os.environ)
    else:
        newvars = {}
    newvars = interpolate_dict_values(newvars, envvars, os.environ)
    return newvars


def load_module_from_content(module_content):
    """Loads a module from a string that is the contents of the module.

    :param module_content: A string with the module content.
    """

    # This is a shitty hack. I don't want to  remove python build config
    # but I don't want spend time on it. :P

    with tempfile.NamedTemporaryFile(suffix='.py') as fd:
        fd.write(module_content.encode())
        fd.flush()
        mod = load_module_from_file(fd.name)

    return mod


def load_module_from_file(filename):
    """ Load a module from a source file
    :param filename: full path for file to be loaded.
    """
    fname = filename.rsplit('.', 1)[0]
    fname = fname.rsplit(os.sep, 1)[-1]
    spec = importlib.util.spec_from_file_location(fname, filename)
    module = importlib.util.module_from_spec(spec)
    # source_file = importlib.machinery.SourceFileLoader(fname, filename)
    try:
        # module = source_file.load_module()
        spec.loader.exec_module(module)
    except FileNotFoundError:
        err_msg = 'Config file "%s" does not exist!' % (filename)
        raise FileNotFoundError(err_msg)
    except Exception as e:
        err_msg = 'There is something wrong with your file. '
        err_msg += 'The original exception was:\n{}'.format(e.args[0])
        raise ConfigError(err_msg)

    return module


def set_loglevel(loglevel):
    stdout_handler = logging.StreamHandler(sys.stdout)
    # stderr_handler = logging.StreamHandler(sys.stderr)

    logger.addHandler(stdout_handler)
    # logger.addHandler(stderr_handler)

    loglevel = getattr(logging, loglevel.upper())
    logger.setLevel(loglevel)
    for h in logger.handlers:
        h.setLevel(loglevel)


def log(msg, level='info'):
    log = getattr(logger, level)
    dt = now().strftime('%Y-%m-%d %H:%M:%S')
    lvl = level.upper()
    msg = '[{}] {} - {}'.format(lvl, dt, msg)
    log(msg)


class LoggerMixin:

    """A simple mixin to use log on a class."""

    @classmethod
    def log_cls(cls, msg, level='info'):
        log('[{}] {} '.format(cls.__name__, msg), level)

    def log(self, msg, level='info'):
        """Appends the class name before the log message. """

        type(self).log_cls(msg, level)


def format_timedelta(td):
    """Format a timedelta object to a human-friendly string.

    :param dt: A timedelta object."""

    return str(td).split('.')[0]


def datetime2string(dt, dtformat=DTFORMAT):
    """Transforms a datetime object into a formated string.

    :param dt: The datetime object.
    :param dtformat: The format to use."""

    if dt.utcoffset() is None:
        tz = timezone(timedelta(seconds=0))
        dt = dt.replace(tzinfo=tz)
    return datetime.strftime(dt, dtformat)


def string2datetime(dtstr, dtformat=DTFORMAT):
    """Transforns a string into a datetime object acording to ``dtformat``.

    :param dtstr: The string containing the formated date.
    :param dtformat: The format of the formated date.
    """
    return datetime.strptime(dtstr, dtformat)


def utc2localtime(utcdatetime):
    """Transforms a utc datetime object into a datetime object
    in local time.

    :param utcdatetime: A datetime object"""

    off = time.localtime().tm_gmtoff
    td = timedelta(seconds=off)
    tz = timezone(td)
    local = utcdatetime + td
    localtime = datetime(local.year, local.month, local.day,
                         local.hour, local.minute, local.second,
                         local.microsecond,
                         tzinfo=tz)
    return localtime


def localtime2utc(localdatetime):
    """Transforms a local datetime object into a datetime object
    in utc time.

    :param localdatetime: A datetime object."""
    off = time.localtime().tm_gmtoff
    td = timedelta(seconds=off)
    utc = localdatetime - td
    utctz = timezone(timedelta(seconds=0))
    utctime = datetime(utc.year, utc.month, utc.day,
                       utc.hour, utc.minute, utc.second,
                       utc.microsecond,
                       tzinfo=utctz)
    return utctime


def now():
    """ Returns the localtime with timezone info. """

    off = time.localtime().tm_gmtoff
    tz = timezone(timedelta(seconds=off))
    return datetime.now(tz=tz)


def set_tzinfo(dt, tzoff):
    """Sets a timezone info to a datetime object.

    :param dt: A datetime object.
    :para tzoff: The timezone offset from utc in seconds"""

    tz = timezone(timedelta(seconds=tzoff))
    tztime = datetime(dt.year, dt.month, dt.day,
                      dt.hour, dt.minute, dt.second,
                      dt.microsecond,
                      tzinfo=tz)
    return tztime


# inherit_docs thanks to Raymond Hettinger on stackoverflow
# stackoverflow.com/questions/8100166/inheriting-methods-docstrings-in-python
def inherit_docs(cls):
    """ Inherit docstrings from base classes' methods.
    Can be used as a decorator

    :param cls: Class that will inherit docstrings from its parents.
    """
    for name, func in vars(cls).items():
        if not func.__doc__:
            for parent in cls.__bases__:
                try:
                    parfunc = getattr(parent, name)
                except Exception:
                    continue
                if parfunc and getattr(parfunc, '__doc__', None):
                    func.__doc__ = parfunc.__doc__
                    break
    return cls


def bcrypt_string(src_string, salt=None):
    encoding = sys.getdefaultencoding()
    if not salt:
        salt = bcrypt.gensalt(12)

    if isinstance(salt, str):
        salt = salt.encode(encoding)

    encrypted = bcrypt.hashpw(src_string.encode(encoding), salt)
    return encrypted.decode()


def compare_bcrypt_string(original, encrypted):
    """Compares if a un-encrypted string matches an encrypted one.

    :param original: An un-encrypted string.
    :param encrypted: An bcrypt encrypted string."""

    return bcrypt.checkpw(original.encode(), encrypted.encode())


def create_random_string(length):
    valid_chars = string.ascii_letters + string.digits
    random_str = ''.join([line for i in range(length)
                          for line in random.choice(valid_chars)])
    return random_str


def create_validation_string(secret):
    """Creates a random string that can be used to validate
    against it. The algorithm is as follows:

    Given a secret, a random string is generated, then <secret>-<random-str>
    are encrypted using bcrypt. Finally <encrypted-str>:<random-str>
    are base64 encoded.
    """

    random_str = create_random_string(12)
    enc = bcrypt_string('{}-{}'.format(secret, random_str))
    final = base64.encodebytes(
        '{}:{}'.format(enc, random_str).encode('utf-8')).decode()
    return final


def validate_string(b64_str, secret):
    """Validates a string created with
    :func:`~..utils.create_validation_string`.

    Given a base64 string the validation is as follows:

    First decodes the base64 string in <encrypted-string>:<random-str> then
    bcrypt-compare <secret>-<random-str> with <encrypted-string>
    """

    try:
        real = base64.decodebytes(b64_str.encode()).decode()
        enc, random_sr = real.split(':')
    except Exception as e:
        log('Error validating string: {}'.format(str(e)), level='error')
        return False
    else:
        return compare_bcrypt_string('{}-{}'.format(secret, random_sr), enc)


class changedir(object):

    def __init__(self, path):
        self.old_dir = os.getcwd()
        self.current_dir = path

    def __enter__(self):
        os.chdir(self.current_dir)

    def __exit__(self, *a, **kw):
        os.chdir(self.old_dir)


def match_string(smatch, filters):
    """Checks if a string match agains a list
    of filters containing wildcards.

    :param smatch: String to test against the filters
    :param filters: Filter to match a string."""

    return any([fnmatch.fnmatch(smatch, f) for f in filters])


class MatchKeysDict(dict):
    """A dictionary that returns the values matching the keys using
    :meth:`..utils.match_string`.

    .. code-block:: python

        >>> d = MatchKeysDict()
        >>> d['k*'] = 1
        >>> d['key']
        1
        >>> k['keyboard']
        1
    """

    def __getitem__(self, key):
        for k in self.keys():
            if match_string(key, [k]):
                return super().__getitem__(k)
        return super().__getitem__(key)

    def get(self, key, default=None):
        try:
            r = self[key]
        except KeyError:
            r = default

        return r


async def run_in_thread(fn, *args, **kwargs):
    """Runs a callable in a background thread.

    :param fn: A callable to be executed in a thread.
    :param args: Positional arguments to ``fn``
    :param kwargs: Named arguments to ``fn``

    Usage

    .. code-block:: python

        r = await run_in_thread(call, 1, bla='a')
"""
    f = _THREAD_EXECUTOR.submit(fn, *args, **kwargs)
    return f


async def read_file(filename):
    """Reads the contents of a file asynchronously.

    :param filename: The path of the file."""

    def _read(filename):
        with open(filename) as fd:
            contents = fd.read()
        return contents

    contents = (await run_in_thread(_read, filename)).result()
    return contents


# deprecated stuff

async def exec_cmd(cmd, cwd, timeout=3600, out_fn=None, **envvars):
    """ Executes a shell command. Raises with the command output
    if return code > 0.

    :param cmd: command to run.
    :param cwd: Directory to execute the command.
    :param timeout: How long we should wait some output. Default
      is 3600.
    :param out_fn: A coroutine that receives each line of the step
      output. The coroutine signature must be in the form:
      mycoro(line_index, line).
    :param envvars: Environment variables to be used in the command.

    DEPRECATED: Use :func:`toxiccore.shell.exec_cmd`
    """
    m = "toxiccore.utils.exec_cmd is deprecated. Use toxiccore.shell.exec_cmd"
    warnings.warn(m, DeprecationWarning)
    from .shell import exec_cmd as exec_sh_cmd
    r = await exec_sh_cmd(cmd, cwd, timeout=timeout, out_fn=out_fn, **envvars)
    return r


async def read_stream(reader, timeout=None):  # pragma no cover
    """ Reads the input stream. First reads the bytes until the first "\\n".
    These first bytes are the length of the full message.

    :param reader: An instance of :class:`asyncio.StreamReader`
    :param timeout: Timeout for the operation. If None there is no timeout

    DEPRECATED: Use :func:`toxiccore.socks.read_stream`
    """

    m = "toxiccore.utils.read_string is deprecated. "
    m += "Use toxiccore.socks.read_stream"
    warnings.warn(m, DeprecationWarning)
    r = await read_sock_stream(reader, timeout=timeout)
    return r


async def write_stream(writer, data, timeout=None):  # pragma no cover
    """ Writes ``data`` to output. Encodes data to utf-8 and prepend the
    lenth of the data before sending it.

    :param writer: An instance of asyncio.StreamWriter
    :param data: String data to be sent.
    :param timeout: Timeout for the write operation. If None there is
      no timeout

    DEPRECATED: Use :func:`toxiccore.socks.write_stream`
    """

    m = "toxiccore.utils.write_string is deprecated. "
    m += "Use toxiccore.socks.write_stream"
    warnings.warn(m, DeprecationWarning)
    r = await write_sock_stream(writer, data, timeout=timeout)
    return r


# Sorry, but not willing to test  a daemonizer.

def daemonize(call, cargs, ckwargs, stdout, stderr,
              workdir, pidfile):  # pragma: no cover
    """ Run a callable as a daemon

    :param call: a callable.
    :param cargs: args to ``call``.
    :param ckwargs: kwargs to ``call``.
    :param stdout: daemon's stdout.
    :param stderr: daemon's stderr.
    :param workdir: daemon's workdir
    :param pidfile: pidfile's path
    """
    _create_daemon(stdout, stderr, workdir)
    pid = os.getpid()
    with open(pidfile, 'w') as f:
        f.write(str(pid))

    call(*cargs, **ckwargs)


def _create_daemon(stdout, stderr, workdir):  # pragma: no cover
    _fork_off_and_die()
    os.setsid()
    _fork_off_and_die()
    os.umask(0)
    os.chdir(workdir)
    _redirect_file_descriptors(stdout, stderr)


def _fork_off_and_die():  # pragma: no cover
    pid = os.fork()
    if pid != 0:
        sys.exit(0)


def _redirect_file_descriptors(stdout, stderr):  # pragma: no cover
    for fd in sys.stdout, sys.stderr:
        fd.flush()

    sys.stdout = open(stdout, 'a', 1)
    sys.stderr = open(stderr, 'a', 1)

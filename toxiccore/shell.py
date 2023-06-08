# -*- coding: utf-8 -*-
# Copyright 2023 Juca Crispim <juca@poraodojuca.net>

# This file is part of toxiccore.

# toxiccore is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# toxiccore is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with toxiccore. If not, see <http://www.gnu.org/licenses/>.

import asyncio
from asyncio import ensure_future
from asyncio.exceptions import LimitOverrunError, IncompleteReadError
import os
import subprocess

from .exceptions import ExecCmdError
from .utils import get_envvars, run_in_thread


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
    """

    proc = await _create_cmd_proc(cmd, cwd, **envvars)
    out = []

    line_index = 0
    while proc.returncode is None or not out:
        outline = await asyncio.wait_for(_readline(proc.stdout), timeout)
        outline = outline.decode()
        if out_fn:
            ensure_future(out_fn(line_index, outline))

        line_index += 1
        out.append(outline)

    output = ''.join(out).strip('\n')
    # we must ensure that all process started by our command are
    # dead.
    await _kill_group(proc)
    if int(proc.returncode) > 0:
        raise ExecCmdError(output)

    return output


async def _create_cmd_proc(cmd, cwd, **envvars):
    """Creates a process that will execute a command in a shell.

    :param cmd: command to run.
    :param cwd: Directory to execute the command.
    :param envvars: Environment variables to be used in the command.
    """
    envvars = get_envvars(envvars)

    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd,
        env=envvars, preexec_fn=os.setsid)

    return proc


async def _kill_group(process):
    """Kills all processes of the group which a process belong.

    :param process: A process that belongs to the group you want to kill.
    """

    def fn():
        try:
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, 9)
        except ProcessLookupError:  # pragma no cover
            pass

    await run_in_thread(fn)


async def _try_readline(stream):
    sep = b'\n'
    try:
        r = await stream.readuntil(sep)
    except LimitOverrunError:
        sep = b'\r'
        r = await stream.readuntil(sep)

    return r


async def _readline(stream):
    """Reads a line from the stream buffer. Tries to read a line
    ending in '\n'. If no new line found, try to find '\r'.

    :param stream: The StreamReader to read from.
    """

    # basically taken from asyncio.streams.StreamReader.readline
    lf, cr = b'\n', b'\r'
    seplen = 1
    try:
        line = await _try_readline(stream)
    except IncompleteReadError as e:
        return e.partial
    except LimitOverrunError as e:
        if stream._buffer.startswith(lf, e.consumed) or \
           stream._buffer.startswith(cr, e.consumed):
            del stream._buffer[:e.consumed + seplen]
        else:
            stream._buffer.clear()

        stream._maybe_resume_transport()
        raise ValueError(e.args[0])
    return line

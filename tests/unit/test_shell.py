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
import subprocess
import time
from unittest import TestCase
from unittest.mock import AsyncMock, patch, Mock

from toxiccore import shell
from tests import async_test


class UtilsTest(TestCase):

    @async_test
    async def test_try_readline_lf(self):
        stream = AsyncMock()
        await shell._try_readline(stream)

        assert stream.readuntil.call_args[0][0] == b'\n'

    @async_test
    async def test_try_readline_cr(self):
        stream = AsyncMock()
        stream.readuntil.side_effect = [
            shell.LimitOverrunError('msg', False), '']
        await shell._try_readline(stream)

        assert stream.readuntil.call_args[0][0] == b'\r'

    @patch.object(shell, '_try_readline', AsyncMock(
        side_effect=shell.IncompleteReadError('partial', 'exp')))
    @async_test
    async def test_readline_incomplete(self):
        stream = AsyncMock()
        r = await shell._readline(stream)

        self.assertEqual(r, 'partial')

    @patch.object(shell, '_try_readline', AsyncMock(
        side_effect=shell.LimitOverrunError('msg', 0)))
    @async_test
    async def test_readline_limit_overrun(self):
        stream = AsyncMock()
        stream._buffer = bytearray()
        stream._maybe_resume_transport = Mock()
        stream._buffer.extend(b'\nblerg')
        with self.assertRaises(ValueError):
            await shell._readline(stream)

    @patch.object(shell, '_try_readline', AsyncMock(
        side_effect=shell.LimitOverrunError('msg', 0)))
    @async_test
    async def test_readline_limit_overrun_clear(self):
        stream = AsyncMock()
        stream._buffer = bytearray()
        stream._maybe_resume_transport = Mock()
        await stream.extend(b'blerg')
        with self.assertRaises(ValueError):
            await shell._readline(stream)

    @async_test
    async def test_exec_cmd(self):
        out = await shell.exec_cmd('ls', cwd='.')
        self.assertTrue(out)

    @async_test
    async def test_exec_cmd_with_error(self):
        with self.assertRaises(shell.ExecCmdError):
            # please, don't tell me you have a lsz command on your system.
            await shell.exec_cmd('lsz', cwd='.')

    @async_test
    async def test_exec_cmd_with_timeout(self, *args, **kwargs):
        with self.assertRaises(asyncio.TimeoutError):
            await shell.exec_cmd('sleep 2', cwd='.', timeout=1)

        # wait here to avoid runtime error saying the loop is closed
        # when the process try to send its message to the caller
        time.sleep(1)

    @async_test
    async def test_kill_group(self):
        cmd = 'sleep 55'
        proc = await shell._create_cmd_proc(cmd, cwd='.')
        try:
            f = proc.stdout.readline()
            await asyncio.wait_for(f, 1)
        except asyncio.exceptions.TimeoutError:
            pass

        await shell._kill_group(proc)
        procs = subprocess.check_output(['ps', 'aux']).decode()
        self.assertNotIn(cmd, procs)

    @async_test
    async def test_exec_cmd_with_envvars(self):
        envvars = {'PATH': 'PATH:venv/bin',
                   'MYPROGRAMVAR': 'something'}

        cmd = 'echo $MYPROGRAMVAR'

        returned = await shell.exec_cmd(cmd, cwd='.', **envvars)

        self.assertEqual(returned, 'something')

    @async_test
    async def test_exec_cmd_with_out_fn(self):
        envvars = {'PATH': 'PATH:venv/bin',
                   'MYPROGRAMVAR': 'something'}

        cmd = 'echo $MYPROGRAMVAR'

        out_fn = AsyncMock()
        await shell.exec_cmd(cmd, cwd='.',
                             out_fn=out_fn,
                             **envvars)

        async def wait():
            return

        await wait()
        self.assertTrue(out_fn.called)
        self.assertTrue(isinstance(
            out_fn.call_args[0][1], str), out_fn.call_args)

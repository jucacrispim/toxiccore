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

from unittest import TestCase
from unittest.mock import Mock, MagicMock, AsyncMock

from toxiccore import socks
from tests import async_test


class StreamTest(TestCase):

    def setUp(self):
        super().setUp()
        self.bad_data = b'\n'
        self.good_data = b'17\n{"action": "bla"}'
        giant = {'action': 'bla' * 1000}
        self.giant = str(giant).encode('utf-8')
        self.giant_data = b'3014\n' + self.giant
        self.giant_data_with_more = self.giant_data + self.good_data
        self.data = b'{"action": "bla"}'

    @async_test
    async def test_read_stream_without_data(self):
        reader = Mock()

        async def read(limit):
            return self.bad_data
        reader.read = read

        ret = await socks.read_stream(reader)

        self.assertFalse(ret)

    @async_test
    async def test_read_stream_good_data(self):
        reader = Mock()

        self._rlimit = 0

        async def read(limit):
            part = self.good_data[self._rlimit: limit + self._rlimit]
            self._rlimit += limit
            return part

        reader.read = read

        ret = await socks.read_stream(reader)

        self.assertEqual(ret, self.data)

    @async_test
    async def test_read_stream_with_giant_data(self):
        reader = Mock()

        self._rlimit = 0

        async def read(limit):
            part = self.giant_data[self._rlimit: limit + self._rlimit]
            self._rlimit += limit
            return part

        reader.read = read

        ret = await socks.read_stream(reader)

        self.assertEqual(ret, self.giant)

    @async_test
    async def test_read_stream_with_good_data_in_parts(self):
        reader = Mock()

        self._rlimit = 0

        async def read(limit):
            if limit != 1:
                limit = 10

            part = self.good_data[self._rlimit: limit + self._rlimit]
            self._rlimit += limit
            return part

        reader.read = read
        ret = await socks.read_stream(reader)

        self.assertEqual(ret, self.data)

    @async_test
    async def test_read_stream_with_giant_data_with_more(self):
        reader = Mock()

        self._rlimit = 0

        async def read(limit):
            part = self.giant_data_with_more[
                self._rlimit: limit + self._rlimit]
            self._rlimit += limit
            return part

        reader.read = read

        ret = await socks.read_stream(reader)

        self.assertEqual(ret, self.giant)

    @async_test
    async def test_write_stream(self):
        writer = MagicMock(drain=AsyncMock())
        r = await socks.write_stream(writer, self.data.decode())

        called_arg = writer.write.call_args[0][0]

        self.assertEqual(called_arg, self.good_data)
        self.assertTrue(r)

    @async_test
    async def test_write_stream_no_writer(self):
        writer = None
        r = await socks.write_stream(writer, self.data.decode())
        self.assertFalse(r)

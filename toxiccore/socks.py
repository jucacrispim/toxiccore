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

WRITE_CHUNK_LEN = 4096
READ_CHUNK_LEN = 1024


async def read_stream(reader, timeout=None):
    """ Reads the input stream. First reads the bytes until the first "\\n".
    These first bytes are the length of the full message.

    :param reader: An instance of :class:`asyncio.StreamReader`
    :param timeout: Timeout for the operation. If None there is no timeout
    """

    async def do_read(qbytes):
        r = await asyncio.wait_for(reader.read(qbytes), timeout)
        return r

    data = await do_read(1)
    if not data or data == b'\n':
        raw_data = b''
        raw_data_list = [b'']
    else:
        char = None
        while char != b'\n' and char != b'':
            char = await do_read(1)
            data += char

        len_data = int(data)
        if len_data <= READ_CHUNK_LEN:
            raw_data = await do_read(len_data)
        else:
            raw_data = await do_read(READ_CHUNK_LEN)

        raw_data_len = len(raw_data)
        raw_data_list = [raw_data]
        while raw_data_len < len_data:
            left = len_data - raw_data_len
            next_chunk = left if left < READ_CHUNK_LEN else READ_CHUNK_LEN
            new_data = await do_read(next_chunk)
            raw_data_len += len(new_data)
            raw_data_list.append(new_data)

    return b''.join(raw_data_list)


async def write_stream(writer, data, timeout=None):
    """ Writes ``data`` to output. Encodes data to utf-8 and prepend the
    lenth of the data before sending it.

    :param writer: An instance of asyncio.StreamWriter
    :param data: String data to be sent.
    :param timeout: Timeout for the write operation. If None there is
      no timeout
    """

    if writer is None:
        return False

    data = data.encode('utf-8')
    data = '{}\n'.format(len(data)).encode('utf-8') + data
    init = 0
    chunk = data[:WRITE_CHUNK_LEN]
    while chunk:
        writer.write(chunk)
        await asyncio.wait_for(writer.drain(), timeout)
        init += WRITE_CHUNK_LEN
        chunk = data[init: init + WRITE_CHUNK_LEN]

    return True

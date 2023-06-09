# -*- coding: utf-8 -*-
"""This module implements a simple asynchronous interface for
http requests.

Usage:
``````

.. code-block:: python

    from . import requests
    response = await requests.get('http://google.com/')
    print(response.text)
"""

# Copyright 2016 Juca Crispim <juca@poraodojuca.net>

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

import asyncio
import json
import aiohttp


class Response:
    """Encapsulates a response from a http request"""

    def __init__(self, status, text, headers=None):
        """Constructor for Response.

        :param status: The response status.
        :param text: The response text."""
        self.status = status
        self.text = text
        self.headers = headers or {}

    def json(self):
        """Loads the json in the response text."""

        return json.loads(self.text)


async def _request(method, url, sesskw=None, **kwargs):
    """Performs a http request and returns an instance of
    :class:`..requests.Response`

    :param method: The requrest's method.
    :param url: Request's url.
    :param sesskw: Named arguments passed to aiohttp.ClientSession.
    :param kwargs: Arguments passed to aiohttp.ClientSession.request
        method.
    """

    sesskw = sesskw or {}
    if not sesskw.get('loop'):
        loop = asyncio.get_event_loop()
        sesskw['loop'] = loop
    client = aiohttp.ClientSession(**sesskw)
    try:
        resp = await client.request(method, url, **kwargs)
        status = resp.status
        text = await resp.text()
        headers = resp.headers
        await resp.release()
    finally:
        await client.close()

    return Response(status, text, headers)


async def get(url, **kwargs):
    """Performs a http GET request

    :param url: Request's url.
    :param kwargs: Args passed to :func:`..requests._request`.
    """

    method = 'GET'
    resp = await _request(method, url, **kwargs)
    return resp


async def post(url, **kwargs):
    """Performs a http POST request

    :param url: Request's url.
    :param kwargs: Args passed to :func:`..requests._request`.
    """

    method = 'POST'
    resp = await _request(method, url, **kwargs)
    return resp


async def put(url, **kwargs):
    """Performs a http PUT request

    :param url: Request's url.
    :param kwargs: Args passed to :func:`..requests._request`.
    """

    method = 'PUT'
    resp = await _request(method, url, **kwargs)
    return resp


async def delete(url, **kwargs):
    """Performs a http DELETE request

    :param url: Request's url.
    :param kwargs: Args passed to :func:`..requests._request`.
    """

    method = 'DELETE'
    resp = await _request(method, url, **kwargs)
    return resp

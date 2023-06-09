ToxicBuild Poor's Protocol
==========================

The ToxicBuild Poor's Protocol is a simple protocol used to exchange messages,
using tcp sockets, between the components of ToxicBuild. It is as follows:

The first ``n`` bytes, until the first ``\n`` indicate the length of the
message, the rest of the message is a utf-8 encoded json. This json must
contain 3 keys: ``token``, ``action`` and ``body``.

The ``token`` is obviously for authentication. The ``action`` key says
what you want to do and the ``body`` are params specific for each action.

Toxiccore provides base classes for implementing client/server comunication
using the tpp.


Example
-------

Server
++++++

For the server you just to implement a ``client_connected`` method in
your subclass of :class:`~toxiccore.protocol.BaseToxicProtocol`.
When the request reaches this point the client is already authenticated,
you just need to take care of executing the desired action.

The requested action is available in the ``self.action`` attribute and
the body (with the params for action) are in the ``self.data['body']``
attribute.

To send a response to the client call the ``send_response`` method. It get
two params: ``code`` and ``body``


.. code-block:: python

   from toxiccore.protocol import BaseToxicProtocol

   class MyProtocol(BaseToxicProtocol):

       async def client_connected(self):
           if self.action != "my-action":
	       # code > 0 means something went wrong.
	       await self.send_response(code=1, body={'error': 'invalid action'})
	       return

	   params = self.data['body']
	   # do something
           await fn(**params)
	   # code 0 means everthing ok.
	   await self.send_response(code=0, body={'my-action': 'ok! :)'})


Now you create a server that uses your protocol

.. code-block:: python

   from toxiccore.server import ToxicServer

   class MyServer(ToxicServer):

       PROTOCOL_CLS = MyProtocol

   if __name__ == '__main__':

       host = '0.0.0.0'
       port = 9876
       server = MyServer(host, port)
       server.start()


.. note::

   To use ssl connections you must instantiate your server passing
   ``use_ssl=True`` and the path for your cert and key files.

   .. code-block:: python

      certfile = '/path/to/file.cert'
      keyfile = '/path/to/file.key'
      server = MyServer(host, port, use_ssl=True, certfile=certfile, keyfile=keyfile)


Client
++++++

To have a client to your server, create a subclass of
:class:`~toxiccore.client.BaseToxicClient` and call the
:meth:`~toxiccore.client.request2server` method.

.. code-block:: python

   from toxiccore.client import BaseToxicClient

   class MyClient(BaseToxicClient):

       async def my_action(self):

           action = 'my-action'
	   body = {'a': 'value'}
	   # this token is used to authenticate in the server.
	   token = 'this is secret'
	   # timeout for unresponsive servers, in seconds
	   timeout = 600

	   r = await self.request2server(action, body, token, timeout=timeout)
	   return r


To use the client, use it in an async context manager:

.. code-block:: python

   host = '127.0.0.1'
   port = 9876
   # indicates if the server uses ssl connections
   use_ssl = True
   # indicates if the client should validate the certificate.
   # should be false for self-signed certificates
   validate_cert = False

   async with MyClient(host, port, use_ssl, validate_cert) as client:
       try:
           r = await client.my_action()
       except ToxicClientException as err:
           # this happens when the server returns code > 0
	   print(err)

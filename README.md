SpiNN Test Driver
=================

**Warning: Highly experimental...**

A tool for performing experiments on the SpiNNaker network.  Consists of two
components:

* A SpiNNaker application (`./spinnaker_app/` which generates/consumes traffic
  on the network according to a specification.
* A Python library (`./spinn_test_driver/`) which generates specifications for
  the application and collects the results. See `example.py`.

Depends on the `spinn_route` library.



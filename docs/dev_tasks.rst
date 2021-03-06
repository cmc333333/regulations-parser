===============
Developer Tasks
===============

Building the documentation
==========================
For most tweaks, you will simply need to run the Sphinx documentation
builder again.

.. code-block:: bash

  pip install Sphinx
  cd docs
  make dirhtml

The output will be in ``docs/_build/dirhtml``.

If you are adding new modules, you may need to re-run the skeleton build
script first:

.. code-block:: bash

  pip install Sphinx
  sphinx-apidoc -F -o docs regparser/

Running Tests
=============
As the parser is a complex beast, it has several hundred unit tests to help
catch regressions. To run those tests, make sure you have first added all of
the testing requirements:

.. code-block:: bash

  pip install -r requirements_test.txt

Then, run nose on all of the available unit tests:

.. code-block:: bash

  nosetests

If you'd like a report of test coverage, use the
`nose-cov <https://pypi.python.org/pypi/nose-cov>`_ plugin:

.. code-block:: bash

  nosetests --with-cov --cov-report term-missing --cov regparser

Note also that this library is continuously tested via Travis. Pull requests
should rarely be merged unless Travis gives the green light.


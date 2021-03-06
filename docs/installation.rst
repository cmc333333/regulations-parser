============
Installation
============

Getting the Code and Development Libs
=====================================

Download the source code from GitHub (e.g. ``git clone [URL]``)

Make sure the ``libxml`` libraries are present. On Ubuntu/Debian, install
it via

.. code-block:: bash

  sudo apt-get install libxml2-dev libxslt-dev

Create a virtual environment (optional)
=======================================

.. code-block:: bash

  sudo pip install virtualenvwrapper
  mkvirtualenv parser

Get the required libraries
==========================

.. code-block:: bash

  cd regulations-parser
  pip install -r requirements.txt

Run the parser
==============
Using ``pipeline``
------------------

.. code-block:: bash

  eregs pipeline title part an/output/directory

or

.. code-block:: bash

  eregs pipeline title part https://yourserver/

Example:

.. code-block:: bash

  eregs pipeline 27 447 /output/path

``pipeline`` pulls annual editions of regulations from the 
`Government Printing Office <http://www.gpo.gov/fdsys/browse/collectionCfr.action>`_ and final rules from the 
`Federal Register <https://www.federalregister.gov/>`_ based on the part that
you give it.

When you run ``pipeline``, it:

1. Gets rules that exist for the regulation from the Federal Register API
2. Builds trees from annual editions of the regulation
3. Fills in any missing versions between annual versions by parsing final rules
4. Builds the layers for all these trees
5. Builds the diffs for all these trees, and
6. Writes the results to your output location

If the final parameter begins with ``http://`` or ``https://``, output will be
sent to that API. If it begins with ``git://``, the output will be written as a
git repository to that path. All other values will be treated as a file path;
JSON files will be written in that directory. See :ref:`output` for more.


Settings
--------

All of the settings listed in ``settings.py`` can be overridden in a
``local_settings.py`` file. Current settings include:

* ``META`` - a dictionary of extra info which will be included in the
  "meta" layer. This is free-form, but could be used for copyright
  information, attributions, etc.
* ``CFR_TITLES`` - array of CFR Title names (used in the meta layer); not
  required as those provided are current
* ``DEFAULT_IMAGE_URL`` - string format used in the graphics layer; not
  required as the default should be adequate 
* ``IGNORE_DEFINITIONS_IN`` - a dictionary mapping CFR part numbers to a
  list of terms that should *not* contain definitions. For example, if
  'state' is a defined term, it may be useful to exclude the phrase 'shall
  state'. Terms associated with the constant, ``ALL``, will be ignored in all
  CFR parts parsed.
* ``INCLUDE_DEFINITIONS_IN`` - a dictionary mapping CFR part numbers to a
  list of tuples containing (term, context) for terms that *are
  definitely definitions*. For example, a term that is succeeded by 
  subparagraphs that define it rather than phraseology like "is defined as". 
  Terms associated with the constant, ``ALL``, will  be included in all CFR 
  parts parsed.
* ``OVERRIDES_SOURCES`` - a list of python modules (represented via
  string) which should be consulted when determining image urls. Useful if
  the Federal Register versions aren't pretty. Defaults to a ``regcontent``
  module.
* ``MACRO_SOURCES`` - a list of python modules (represented via strings)
  which should be consulted if replacing chunks of XML in notices. This is
  more or less deprecated by ``LOCAL_XML_PATHS``. Defaults to a ``regcontent``
  module.
* ``REGPATCHES_SOURCES`` - a list of python modules (represented via
  strings) which should be consulted when determining changes to regulations
  made in final rules.  Defaults to a ``regcontent`` module
* ``LOCAL_XML_PATHS`` - a list of paths to search for notices from the
  Federal Register. This directory should match the folder structure of the
  Federal Register. If a notice is present in one of the local paths, that
  file will be used instead of retrieving the file, allowing for local
  edits, etc. to help the parser.

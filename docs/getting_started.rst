Getting started
===============

Install (once per computer)
---------------------------

1. Install **Python 3.9 or newer** from `python.org <https://www.python.org/downloads/>`_.
   On Windows, tick *Add python.exe to PATH* on the first screen of the installer.
2. Open a terminal (Windows: *Start*, type ``cmd``, *Command Prompt*) and go to
   the EMA folder, the one that holds ``README.md``:

   .. code-block:: bat

      cd "C:\Users\<you>\Desktop\EMA"

3. Install the packages EMA needs. This takes a minute or two and needs internet access.

   .. code-block:: bat

      python -m pip install -r requirements.txt

4. Optional: put an EMA icon on the Desktop.

   .. code-block:: bat

      python create_shortcut.py

Start EMA
---------

Double-click the **EMA** icon on the Desktop, or double-click ``EMA.pyw`` in
the EMA folder, or run ``python -m ema`` in a terminal.

The start window lists the five packages under two headings, numbered in
the order you use them:

* **Evoked responses**: 1 ROI Selection, 2 Evoked Analysis Configurator,
  3 Evoked Analysis;
* **Spontaneous events**: 1 Spontaneous Event Configurator, 2 Spontaneous
  Event Analysis, which uses the ROI file of ROI Selection when there is
  one.

Click the one you need. The start window comes back when you close the
package. *Documentation* opens these pages.

.. figure:: screenshots/launcher.png
   :width: 420

   The start window.

:doc:`The workflow <index>` shows which file each package makes and which
it uses, and :doc:`recordings` says how your recordings should be named and
arranged.

Next: :doc:`quick_start`, your first analysis with the defaults.

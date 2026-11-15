Getting started
===============

Install (once per computer)
---------------------------

1. Install **Python 3.9 or newer** from `python.org <https://www.python.org/downloads/>`_.
   On Windows, tick *Add python.exe to PATH* on the first screen of the installer.
2. Open a terminal (Windows: *Start*, type ``cmd``, *Command Prompt*) and go to
   the EMA folder, the one that holds ``README.md``:

   .. code-block:: bat

      cd "C:\Users\<you>\Desktop\EMA\EMA_V3"

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

The start window lists the four packages. Click the one you need. The start
window comes back when you close the package.

.. figure:: screenshots/launcher.png
   :width: 420

   The start window. Packages that are not built yet are greyed out.

What EMA expects
----------------

Recordings
   TIFF movies, one file per trial, grouped in folders. A folder that holds
   at least one TIFF movie is a *recording folder*. In the standard layout
   that is each ``input output`` folder and each ``11p at …`` folder of a
   slice.

File names
   Stimulated trials are named after their current (``200uA.tif``) or
   ``hi1.tif`` … ``hi4.tif``. Unstimulated trials start with ``no``
   (``no1.tif``).

Single images
   TIFF files smaller than 1 MB, such as reference snapshots, are ignored.

EMA never changes your recordings. It only reads them, and it refuses to
save its own files inside the recordings folder.

Frame numbers
-------------

EMA drops the first frame of every TIFF, as every earlier version did. So
*frame 0* in EMA is the second frame of the file. All frame numbers in the
settings and in the plots are counted this way.

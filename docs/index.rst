EMA
===

EMA analyses movies of brain slices recorded with a fluorescent sensor such
as :term:`dLight`, which glows more brightly where dopamine is released.
It measures two things:

* **evoked responses**: the release caused by an electrical stimulus;
* **spontaneous events**: brief, local release without a stimulus, found in
  the unstimulated recordings.

EMA is five packages behind one start window. New to EMA? Read
:doc:`getting_started` and :doc:`recordings` first. Words you do not know
are explained in the :doc:`glossary`.

Workflow
--------

The start window lists the packages in the order you use them.

**Evoked responses**

1. :doc:`ROI Selection <roi_selection/index>` finds the :term:`ROI` and the
   :term:`electrode mask` of every recording folder. You check them and
   :term:`flag` bad recordings. It writes the :term:`ROI file`,
   ``roi_selections.json``, into an output folder.
2. :doc:`Evoked Analysis Configurator <evoked_configurator/index>` makes
   :term:`protocols <protocol>`: which pulses to measure and how. Each is a
   JSON file in the ``protocols`` folder of EMA. Three protocols are built
   in, so you can skip this step.
3. :doc:`Evoked Analysis <evoked_analysis/index>` measures every folder of
   the ROI file with a protocol. It writes ``Evoked per recording.xlsx`` and
   ``Evoked per slice.xlsx`` into an output folder, laid out for
   :term:`Prism`, together with ``evoked_analysis.json``, the
   :term:`kept results`.

**Spontaneous events**

1. :doc:`Spontaneous Event Configurator <spontaneous_configurator/index>`
   makes :term:`detectors <detector>`: how events are found and what is
   measured on them. Each is a JSON file in the ``detectors`` folder of EMA.
   The :term:`Standard detector` is built in, so you can skip this step.
2. :doc:`Spontaneous Event Analysis <spontaneous_analysis/index>` searches
   the unstimulated recordings of every folder under a recordings folder
   with a detector. It uses the ROI file when there is one, for the
   reviewed electrodes, ROI centres and flags. It writes
   ``Spontaneous per event.xlsx`` and ``Spontaneous per slice.xlsx`` into an
   output folder, together with ``spontaneous_analysis.json``.

.. toctree::
   :maxdepth: 2
   :caption: Using EMA

   getting_started
   recordings
   roi_selection/index
   evoked_configurator/index
   evoked_analysis/index
   spontaneous_configurator/index
   spontaneous_analysis/index
   glossary

.. toctree::
   :maxdepth: 1
   :caption: For developers

   development
   extending
   reference

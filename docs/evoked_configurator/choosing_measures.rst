Choosing measures
=================

Not every number that can be computed means what its name suggests. This
page says, measure by measure, what the published work on evoked
dopamine (dLight, GRAB-DA) and glutamate (iGluSnFR) imaging supports at
the resolution of these recordings, 16 µm per pixel and 4.849 ms per frame,
and what it does not. Formulas marked *derived* follow from standard models
rather than from a published measurement. :doc:`measure_reference` gives
the exact definition of every measure.

What 16 µm and 5 ms can and cannot show
---------------------------------------

Three length scales matter, and only the largest is visible:

.. list-table::
   :header-rows: 1
   :widths: 30 25 45

   * - Scale
     - Size
     - Consequence
   * - A release site
     - about 2-3 µm [Beyene2019]_ [Bulumulla2022]_
     - Far below a pixel. A "hot spot" in a map is a patch of many sites.
   * - How far dopamine diffuses in the time of a response
     - 11 µm in 100 ms, 36 µm in 1 s (derived from D = 7.63 × 10⁻⁶ cm²/s
       and a tortuosity of 1.54 [RiceCragg2008]_)
     - Diffusion widens a 300-400 µm footprint by about 1.4 % per second,
       a tenth of a pixel. It cannot be measured, and it does not shape the
       footprint.
   * - The footprint of an electrical stimulus
     - 300-500 µm [Matityahu2023]_
     - Set by which axons the stimulus recruits [Histed2009]_ and by light
       scattered in the slice, not by diffusion.

So EMA does **not** offer a diffusion coefficient, a tortuosity, an uptake
length, or the Michaelis-Menten constants Vmax and Km: none can be
estimated from these movies without a concentration calibration. What can be
measured is how the response decays, and whether it decays at a different
rate in different places.

Decay with distance and a shrinking footprint
---------------------------------------------

A shrinking footprint is a decay that differs with distance
   If the response decays at rate k(r) = 1/τ(r) at distance r from the
   centre, the width λ of a Lorentzian footprint changes at
   d ln λ/dt ≈ −[k(λ) − k(0)] (derived). A footprint shrinks exactly when
   its edge decays faster than its centre. For example, a decay time
   constant 10 % shorter 320 µm from the centre than at the centre shrinks λ
   by about 11 % in 0.4 s. EMA therefore measures the decay of the bands and
   rings (*far-near decay ratio*, *decay-distance slope*) rather than the
   width over time: a width fitted to each fading map is noisy, because the
   fit trades the width against the offset and the noise grows as the
   response fades.

No threshold areas
   An area above a fixed threshold shrinks as the response fades even when
   its shape does not change at all (for a Gaussian footprint at
   2πσ² ÷ τ, derived), so EMA offers no threshold area.

r50 hides most of the change
   For a footprint of the Lorentzian shape, r50 and the tail fraction are
   fixed functions of λ within a given integration radius, and r50 moves by
   only about a quarter as much as λ (derived). Use the width; read r50 and
   the tail fraction as signs that the shape departs from a Lorentzian.

Two things make the centre fade more slowly
   Both depend only on how large the response is at that moment, so both
   make the decay look slower near the centre and the footprint look as if
   it shrinks:

   * **A saturated sensor.** Near the centre the sensor is close to its
     maximum, which flattens the top and widens the apparent footprint (by
     √(1 + c ÷ K) for a concentration c and a sensor affinity K, derived).
     As the response fades the sensor leaves saturation and the footprint
     seems to shrink. A single pulse gives about 0.25-1.4 µM dopamine
     [Garris1994]_ [Phillips2002]_, above the half-maximal concentration of
     dLight1.1 (about 350 nM) and GRAB-DA2m (about 0.1 µM)
     [KleinHerenbrink2022]_.
   * **Saturable uptake.** The transporter clears a smaller share of the
     dopamine per second where the concentration is highest, so the centre
     fades more slowly.

   The test: compare the far-near decay ratio between currents. If it moves
   towards 1 at low currents, where the centre is smaller, the difference is
   a matter of amplitude; if it stays, clearance really is faster away from
   the centre. A transporter blocker removes the uptake effect and a
   low-affinity sensor the saturation effect.

Bleaching and blur
   Bleaching left in the trace makes the small far-band response fade
   sooner, which looks like shrinking; use an unstimulated partner (the
   default). Light scattered from the centre makes the edge look more like
   the centre, so real gradients are measured smaller than they are; blur
   cannot create a change of shape.

Slow sensors and glutamate
   A sensor that unbinds more slowly than dopamine is cleared (several
   GRAB-DA variants, with off-time constants of 0.6 to several seconds
   [Sun2020]_ [Zhuo2024]_) decays at its own rate everywhere, which pulls the
   far-near decay ratio towards 1. iGluSnFR responses decay at the rate the
   sensor itself buffers glutamate [Armbruster2020]_, and in striatal slices
   they decayed alike 500 µm apart [Parsons2016]_: at this scale, footprint
   measures of glutamate are not expected to change over time.

Decay, uptake and release
-------------------------

Decay reads uptake, the peak reads release
   In voltammetry, the decay time constant is the recommended readout of
   uptake and the calibrated peak of release [Yorgason2011]_. With dLight,
   transporter blockers lengthen the decay without changing the peak
   [Salinas2023]_. Fold changes are not comparable between sensors: in the
   same slices cocaine lengthened the GRAB-DA2m decay 4.1-fold and the
   voltammetry decay 2.7-fold [Huang2025]_.

Decays depend on the size of the response
   With saturable uptake, the half-decay time grows with the peak
   concentration (t½ = (Km·ln 2 + peak ÷ 2) ÷ Vmax, derived). Compare decays
   of responses of similar size, or keep the peak as a covariate.

The sensor sets a floor
   Published off-times of the sensors differ about threefold between
   studies (dLight1.1: about 100 ms in tissue [Labouesse2020]_, 340 ms in a
   plate reader [KleinHerenbrink2022]_). With dLight1.x and striatal
   clearance of a few hundred ms the late decay is mostly clearance; with
   GRAB-DA it may be mostly the sensor. A free double exponential cannot say
   which of its two time constants is the sensor and which the clearance,
   because the model is symmetric in them.

Fit windows
   The *Tau* fit of the built-in protocols starts 4 frames after the maximum
   and lasts 412 frames (2 s). Published practice varies; a start at the
   first frame below 80 % of the peak, a window fixed in seconds and an
   offset rule decided in advance are the safest choices. Check that the
   1/e decay agrees with τ.

Area and rise
   In a linear sensor the area under the response does not depend on the
   sensor's speed: it is release × clearance time, so it also grows when
   uptake is blocked. The 10-90 % rise of a step is 0.8 frame (3.9 ms) at
   this frame rate, so rise times are close to the resolution limit, and the
   stimulus, not locked to the frames, adds up to half a frame of jitter.

Trains and recovery
-------------------

Pulses of a 10 Hz train include the decay of the ones before
   The built-in 11P protocol measures each pulse of the train above the
   baseline before the train (P − BL). At 10 Hz the response to the first
   pulse is still decaying during the second: with a decay time constant of
   0.5 s it falls by about 8 % of P1 within P2's window, which can be as
   large as P2 itself (derived). P2/P1 … P10/P1 therefore mix the release of
   each pulse with the decay of the earlier ones. The reference method
   subtracts a whole single-pulse response recorded at the same place
   [Condon2019]_; EMA does not do this yet. Vesicle-pool estimates from
   cumulative release assume depression by depletion, which does not hold
   for dopamine, and are not offered.

The 4 s paired pulse mixes mechanisms
   At 4 s the first response has long decayed, but the interval lies in the
   window of D2 autoreceptor inhibition (0.1-5 s in slices) and well before
   full recovery (beyond 20 s) [Phillips2002]_. A D2 antagonist separates the
   D2 part, but only with dLight: GRAB-DA is built on the D2 receptor and is
   blocked by it [Sun2020]_.

Recovery
   Fit the recovery pulse relative to the first pulse (P11/P1) against the
   delay, with the plateau fixed at full recovery (100 %): with delays up to
   5 s the plateau cannot be fitted, because full recovery takes 10-60 s
   [Kennedy1992]_ [Lebowitz2024]_. Recovery relative to the last pulse of the
   train (P11/P10) divides by a response close to the noise and is
   unstable. The 0.5 s delay may still include autoreceptor inhibition.

Input-output curves
   The top of a curve of dF/F against the current can be the sensor's
   ceiling rather than release's: compare half-max currents rather than
   maxima when the sensor may saturate.

Averaging ratios
   For repeated trials of one condition, the mean of P2 ÷ the mean of P1 is
   unbiased; the mean of the single-trial ratios is biased upwards
   [KimAlger2001]_.

Spatial maps
------------

* The Lorentzian footprint has a published precedent in striatal slices,
  there measured from the electrode rather than from the response centre
  [Matityahu2023]_. Its width trades off against its offset c.
* The centroid offset and the elongation are above 0 and 1 even for a round,
  centred response, because of noise; both are larger for small responses.
  A trend with the current can therefore be an effect of noise.
* Heterogeneity and hot spots describe patches of many release sites; they
  depend on the smoothing and the noise.
* Release latencies differ by a few ms across the footprint. A camera with a
  rolling shutter records image rows at slightly different times, which can
  look like a latency gradient.

Statistics
----------

Slices from one animal are not independent. Analyse the measures with the
animal as the unit and slices within animals (a mixed model or a
hierarchical bootstrap); treating slices as independent can give false
positives in nearly half of tests [Saravanan2020]_ [Aarts2014]_.

Not offered, and why
--------------------

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Measure
     - Why not
   * - Area or radius above a threshold
     - Shrinks with the amplitude alone.
   * - Diffusion coefficient, tortuosity, uptake length
     - Their effects are a tenth of a pixel.
   * - Vmax and Km
     - Need a concentration calibration.
   * - Vesicle pool size, release probability
     - The depletion model behind them does not hold for dopamine.
   * - Double-exponential components named "sensor" and "clearance"
     - The model cannot tell them apart.
   * - Release sites per mm²
     - Sites are about 2 µm across.

Candidates for later, which need more than one recording or a calibration:
pulse amplitudes found by subtracting a single-pulse response (for trains);
per-ring first-moment decay times, whose differences do not depend on a
uniform sensor kernel; a decay time constant corrected for the sensor's
off-time; and a Moffat fit, whose tail index tells a change of shape from a
change of scale. The footprint width over time was tried and dropped: widths
fitted to the fading maps were too noisy to rely on.

References
----------

Links as found by the literature search behind this page.

.. [Aarts2014] Aarts et al. (2014), *Nature Neuroscience*. https://doi.org/10.1038/nn.3648
.. [Armbruster2020] Armbruster et al. (2020), *eLife*. https://doi.org/10.7554/eLife.54441
.. [Beyene2019] Beyene et al. (2019), *Science Advances*. https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6620097/fullTextXML
.. [Bulumulla2022] Bulumulla et al. (2022), *eLife*. https://doi.org/10.7554/eLife.78773
.. [Condon2019] Condon et al. (2019), *Nature Communications*. https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6753151/fullTextXML
.. [Garris1994] Garris et al. (1994), *Journal of Neuroscience*. https://doi.org/10.1523/JNEUROSCI.14-10-06084.1994
.. [Histed2009] Histed et al. (2009), *Neuron*. https://doi.org/10.1016/j.neuron.2009.07.016
.. [Huang2025] Huang et al. (2025), *Science Advances*. https://doi.org/10.1126/sciadv.adx6367
.. [Kennedy1992] Kennedy et al. (1992), *Journal of Neurochemistry*. https://doi.org/10.1111/j.1471-4159.1992.tb09391.x
.. [KimAlger2001] Kim and Alger (2001), *Journal of Neuroscience*. https://doi.org/10.1523/JNEUROSCI.21-24-09608.2001
.. [KleinHerenbrink2022] Klein Herenbrink et al. (2022), *Communications Biology*. https://doi.org/10.1038/s42003-022-03488-5
.. [Labouesse2020] Labouesse et al. (2020), *International Journal of Molecular Sciences*. https://doi.org/10.3390/ijms21218048
.. [Lebowitz2024] Lebowitz et al. (2024). https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10932592/fullTextXML
.. [Matityahu2023] Matityahu et al. (2023), *Nature Communications*. https://doi.org/10.1038/s41467-023-42311-5
.. [Parsons2016] Parsons et al. (2016), *Nature Communications*. https://doi.org/10.1038/ncomms11251
.. [Phillips2002] Phillips et al. (2002), *Synapse*. https://doi.org/10.1002/syn.10049
.. [RiceCragg2008] Rice and Cragg (2008), *Brain Research Reviews*. https://doi.org/10.1016/j.brainresrev.2008.02.004
.. [Salinas2023] Salinas et al. (2023), *Nature Communications*. https://doi.org/10.1038/s41467-023-41581-3
.. [Saravanan2020] Saravanan et al. (2020), *bioRxiv*. https://doi.org/10.1101/819334
.. [Sun2020] Sun et al. (2020), *Nature Methods*. https://doi.org/10.1038/s41592-020-00981-9
.. [Yorgason2011] Yorgason et al. (2011), *Journal of Neuroscience Methods*. https://doi.org/10.1016/j.jneumeth.2011.03.001
.. [Zhuo2024] Zhuo et al. (2024), *Nature Methods*. https://doi.org/10.1038/s41592-023-02100-w

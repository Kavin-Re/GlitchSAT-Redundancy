"""Spot sizes from published laser / EM fault-injection experiments, used to pick the radius range.

SOURCED = number read in the cited document (the document was opened; location given).
ASSUMED = a modelling choice of this folder, not taken from a source.
"""

SOURCES = [
    dict(id="dutertre_fdtc2018",
         label="SOURCED",
         citation="J.-M. Dutertre et al., Laser Fault Injection at the CMOS 28 nm Technology Node: an Analysis of the "
                  "Fault Model, FDTC 2018 (slides, session 1.1)",
         url="https://fdtc.deib.polimi.it/FDTC18/shared/FDTC%202018%20-%20session%201.1.pdf",
         facts=[
             "backside injection; 1030 nm (30 ps pulses) and 1064 nm (ns pulses) (slides 30, 41)",
             "spot size 1 um or 5 um (slide 30)",
             "28 nm D flip-flop about 4.3 um x 1.2 um, about 40 transistors (slide 33)",
             "hardware AES-128, 28 nm, 1.2 V, 100 MHz; 5 um spot, 10 ns, 0.6-1.0 W, step 1 um (slide 42)",
             "26,380 faulted ciphertexts, 19,806 identified single-byte faults (slide 42)",
             "faulted bits per faulted byte: 1: 19,413; 2: 278; 3: 27; 4: 48; 5: 38; 6: 1 (slide 43)",
             "single-bit and bit-set/reset are still practical fault models at 28 nm (slide 45)",
         ],
         derived="392 of 19,805 tabulated single-byte faults (1.98 %) hit 2 to 6 bits (sum of slide 43 rows 2-6; "
                 "the rows sum to 19,805, one less than the 19,806 of slide 42)"),
    dict(id="bartkewitz_tches2022",
         label="SOURCED",
         citation="T. Bartkewitz et al., Beware of Insufficient Redundancy, IACR TCHES 2022(3):438-462 (slides)",
         url="https://iacr.org/submit/files/slides/2022/tches/ches2022/3_57/slides.pdf",
         facts=[
             "ASIC in a 40 nm low-power CMOS technology, backside Nd:YAG laser, spot 5.6 x 5.6 um (slide 9)",
             "\"It is easier to inject multiple bit faults than single bit faults\" (slide 17)",
         ]),
    dict(id="moro_fdtc2013",
         label="SOURCED",
         citation="N. Moro, A. Dehbaoui, K. Heydemann, B. Robisson, E. Encrenaz, Electromagnetic fault injection: "
                  "towards a fault model on a 32-bit microcontroller, FDTC 2013 (arXiv:1402.6421)",
         url="https://arxiv.org/pdf/1402.6421.pdf",
         facts=[
             "EM injection antenna of a few turns with a diameter of 1 mm; target in 130 nm CMOS (ARM Cortex-M3)",
             "probe moved in 200 um steps over a 3 mm square",
         ]),
]

# Radius marks drawn on the plots. A spot DIAMETER d gives radius d / 2.
MARKS = [
    dict(r=0.5, label="1 um laser spot (28 nm)", kind="SOURCED", source="dutertre_fdtc2018"),
    dict(r=2.5, label="5 um laser spot (28 nm)", kind="SOURCED", source="dutertre_fdtc2018"),
    dict(r=2.8, label="5.6 um laser spot (40 nm)", kind="SOURCED", source="bartkewitz_tches2022"),
    dict(r=500.0, label="1 mm EM probe", kind="SOURCED", source="moro_fdtc2013"),
]

ASSUMPTIONS = [
    "the disturbed region is a disc whose radius equals the optical spot radius (the true affected area depends on "
    "pulse energy and on the sensitive area of each cell; it can be smaller or larger than the spot)",
    "every logic cell inside the disc is disturbed with certainty in that cycle (no probability, no partial effect)",
    "the spot sizes above were measured on 28 nm and 40 nm chips; here they are applied unchanged, in micrometres, to "
    "sky130 cells (a sky130 dfxtp_1 is 7.36 x 2.72 um, about 1.6 x 2.3 times the 28 nm flop of the slides)",
    "an EM probe of 1 mm diameter covers the whole 30 um die of these designs, so EM is modelled as r >= cover radius",
]

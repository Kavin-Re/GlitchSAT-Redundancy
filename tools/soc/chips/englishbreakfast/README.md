# OpenTitan English Breakfast (not run)

`top_englishbreakfast` is the reduced OpenTitan top used for FPGA side-channel work (Ibex, AES, a few peripherals).
At the pinned tag (Earlgrey-PROD-M6, commit a78922f14a8cc20c7ee569f322a04626f2ac6127) the repository holds its
description (`hw/top_englishbreakfast/data/top_englishbreakfast.hjson`) but not the generated top-level RTL: the
folder `hw/top_englishbreakfast/rtl/autogen` is produced by `util/topgen.py`, which needs the Python packages
`hjson` and `mako`. They cannot be installed in the build environment (no package index access), so this chip
could not be generated or synthesised there. Nothing is claimed for it.

`cloud/run_opentitan.sh` contains the steps for a machine with package access: install the two packages, run
topgen for English Breakfast, then `TOP=top_englishbreakfast` through the same front end as Earl Grey
(`chips/earlgrey/frontend.sh`). Those steps are written and not run.

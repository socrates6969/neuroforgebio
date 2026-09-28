# Third-party data notice

`mc-rtt-playground.json` is derived from:

O'Doherty, Joseph (2024) MC_RTT: macaque motor cortex spiking activity during self-paced reaching
(Version 0.241017.1444) [Data set]. DANDI archive. https://doi.org/10.48324/dandi.000129/0.241017.1444

Licence: Creative Commons Attribution 4.0 International (CC BY 4.0),
https://creativecommons.org/licenses/by/4.0/

Changes made: spike times and cursor positions of 12 test reaches excerpted from the training file
`sub-Indy_desc-train_behavior+ecephys.nwb` (SHA-256
`2f78db62bd4d68b9bc737444f72bc2dfe475d7390dd7a54848aaf6a6a6ba8da5`); spikes binned and decoded by linear
decoders; positions rounded to 0.1 mm; synthetic noise spikes added and marked as such; summary scores
computed. Pipeline: `tools/playground` (README there). Non-human (macaque) data; no human data.

The original authors do not endorse this demo.

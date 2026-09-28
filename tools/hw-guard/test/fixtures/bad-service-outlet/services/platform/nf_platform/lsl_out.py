import pylsl

info = pylsl.StreamInfo("nf", "EEG", 4, 1000.0, "float32", "nf-1")
outlet = pylsl.StreamOutlet(info)

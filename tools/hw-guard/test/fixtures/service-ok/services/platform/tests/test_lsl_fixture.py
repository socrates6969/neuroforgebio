import pylsl


def test_outlet_fixture() -> None:
    outlet = pylsl.StreamOutlet(pylsl.StreamInfo("t", "EEG", 1, 100.0))
    assert outlet is not None

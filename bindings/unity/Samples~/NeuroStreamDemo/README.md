# NeuroStream demo (sample scene description)

A scene file isn't committed: Unity scenes are YAML and can't be authored or checked without the editor. Here's how to build the scene in about two minutes:

1. **Recording.** Copy a NeuroForge recording (an `nf-signal/1` Zarr root) to
   `Assets/StreamingAssets/NeuroForge/`, so that `Assets/StreamingAssets/NeuroForge/rec-001/` exists.
   The SDK's test fixture works: `cargo run -p neuroforge-c --example make_fixture -- <dir>` writes
   `<dir>/rec-001` (3 channels Fz/Cz/Pz, 250 Hz, 1000 int16 samples; see `bindings/c/tests/fixture/mod.rs`).
2. **Stream object.** Create an empty GameObject named `NeuroStream`, then add **NeuroForge > Neuro Stream**. Set
   *Recording Root* to `NeuroForge`, *Recording Id* to `rec-001`, and turn on *Loop*.
3. **Visual.** Create a Cube, then add `ChannelToScale` (this sample). Drag the `NeuroStream` object into *Stream* and
   set *Channel* to `Cz`. The fixture's values span -1000..999, so keep *Units Per Scale* at 1000.
4. Press Play. The cube grows and shrinks with the mean absolute value of `Cz` per block. The Inspector's debug view shows
   `CurrentSample` advancing at 250 samples per second.

Game logic can also poll `stream.ChannelValue("Cz")` or `stream.LatestValues` each frame, without using the event.

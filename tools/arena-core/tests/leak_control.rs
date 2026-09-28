//! The leak control must be caught, and must not false-positive on a clean fixture.

use arena_core::fixtures;
use arena_core::leak;

#[test]
fn planted_leak_is_flagged() {
    let dataset = fixtures::with_planted_leak(1, 12, 200, 4, 2);
    let checks = leak::check_dataset(&dataset);
    let leaked_channel = dataset.trials[0].n_channels() - 1; // last channel is the leak
    assert!(
        checks[leaked_channel].flagged,
        "planted leak channel (corr={:.4}) was not flagged",
        checks[leaked_channel].abs_correlation
    );
    assert!(leak::any_leak(&checks));
}

#[test]
fn clean_fixture_is_not_flagged() {
    let dataset = fixtures::clean(2, 12, 200, 4, 2);
    let checks = leak::check_dataset(&dataset);
    assert!(
        !leak::any_leak(&checks),
        "clean fixture was flagged: {:?}",
        checks
            .iter()
            .filter(|c| c.flagged)
            .map(|c| (c.channel_index, c.abs_correlation))
            .collect::<Vec<_>>()
    );
}

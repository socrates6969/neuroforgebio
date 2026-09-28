// An outlet in production code is forbidden (inlet-only bridge).
pub fn open() {
    let _outlet = lsl::StreamOutlet::new(&info, 0, 360);
}

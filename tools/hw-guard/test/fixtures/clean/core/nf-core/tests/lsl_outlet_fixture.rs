// Test fixture: an outlet is allowed only under tests/ (SEC-091).
fn fixture() {
    let _outlet = lsl::StreamOutlet::new(&info, 0, 360);
}

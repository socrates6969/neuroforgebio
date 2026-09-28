// Inlet-only LSL bridge (reads samples; never writes to a device).
pub fn resolve_inlet(name: &str) -> String {
    format!("inlet:{name}")
}

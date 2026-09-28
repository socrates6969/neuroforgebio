//! Library surface for `site-rs`'s generator functions, so integration tests (`tests/parity.rs`)
//! can call them directly instead of shelling out to the binary. See PLAN.md.

pub mod content;
pub mod csp_check;
pub mod headers;
pub mod pages;
pub mod robots;
pub mod sitemap;
pub mod theme;

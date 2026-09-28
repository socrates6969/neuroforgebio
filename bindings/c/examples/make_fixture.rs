//! Write the C/C++ test fixture: `cargo run -p neuroforge-c --example make_fixture -- <dir>`.
//! Prints the cached chunk ID. The layout and values are documented in `tests/fixture/mod.rs`.

#[path = "../tests/fixture/mod.rs"]
mod fixture;

fn main() {
    let dir = std::env::args().nth(1).expect("usage: make_fixture <dir>");
    let root = std::path::Path::new(&dir);
    if root.exists() {
        std::fs::remove_dir_all(root).expect("clear fixture dir");
    }
    println!("{}", fixture::write(root));
}

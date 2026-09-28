//! The two build themes (astro.config.mjs: `THEME=clinical|cosmos`).

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Theme {
    Clinical,
    Cosmos,
}

impl Theme {
    pub fn as_str(self) -> &'static str {
        match self {
            Theme::Clinical => "clinical",
            Theme::Cosmos => "cosmos",
        }
    }

    pub fn parse(s: &str) -> Option<Theme> {
        match s {
            "clinical" => Some(Theme::Clinical),
            "cosmos" => Some(Theme::Cosmos),
            _ => None,
        }
    }
}

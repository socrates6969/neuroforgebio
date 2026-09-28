//! API client core (BLUEPRINT §4): request building, bearer-token handling, retries, RFC 9457
//! problem+json errors and the base-URL policy (SEC-030). The byte transport is a trait, so the
//! same rules run over any HTTP stack: the Python binding plugs in `httpx` (TLS 1.3 minimum,
//! verification always on), tests plug in an in-process app.
//!
//! Rules:
//! - Base URL must be `https://`; plain `http://` only for loopback hosts (local development and
//!   tests). There is no switch that turns certificate verification off.
//! - Retries: transport errors and 408/429/500/502/503/504, only for idempotent methods (GET,
//!   HEAD, PUT, DELETE, OPTIONS) or requests carrying an `Idempotency-Key`. Exponential backoff
//!   with full jitter; `Retry-After` (seconds) is honoured up to `max_retry_after`, beyond that
//!   the error is returned instead of waiting.
//! - 401: the token source is asked for a fresh token once, then the request is sent once more.
//! - The token never appears in errors or `Debug` output.

use std::fmt;
use std::sync::Mutex;
use std::time::Duration;

use serde::{Deserialize, Serialize};

pub const RETRY_STATUSES: [u16; 6] = [408, 429, 500, 502, 503, 504];

#[derive(Clone, PartialEq)]
pub struct Request {
    pub method: String,
    pub url: String,
    pub headers: Vec<(String, String)>,
    pub body: Vec<u8>,
}

impl fmt::Debug for Request {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let headers: Vec<(&str, &str)> = self
            .headers
            .iter()
            .map(|(k, v)| {
                if k.eq_ignore_ascii_case("authorization") {
                    (k.as_str(), "<redacted>")
                } else {
                    (k.as_str(), v.as_str())
                }
            })
            .collect();
        f.debug_struct("Request")
            .field("method", &self.method)
            .field("url", &self.url)
            .field("headers", &headers)
            .field("body_len", &self.body.len())
            .finish()
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Response {
    pub status: u16,
    pub headers: Vec<(String, String)>,
    pub body: Vec<u8>,
}

impl Response {
    pub fn header(&self, name: &str) -> Option<&str> {
        self.headers
            .iter()
            .find(|(k, _)| k.eq_ignore_ascii_case(name))
            .map(|(_, v)| v.as_str())
    }
}

/// What kind of transport failure happened; decides whether [`ApiClient::send`] may retry it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TransportErrorKind {
    /// Connection refused/reset, timeout, TLS error and similar: retried for idempotent requests.
    Other,
    /// The response exceeded a size limit. Deterministic, so never retried (a retry would only
    /// multiply the bytes a hostile or broken server can make us read).
    TooLarge,
}

/// Message prefix of a [`TransportErrorKind::TooLarge`] failure (kept in the text for callers that
/// only see the message, e.g. `ApiError::Transport`).
pub const TOO_LARGE: &str = "response too large";

/// A transport-level failure (no HTTP status). Build it with [`TransportError::other`] or
/// [`TransportError::too_large`]; any transport (including the Python and C callback transports)
/// reports an over-size response with `too_large`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransportError {
    pub kind: TransportErrorKind,
    pub message: String,
}

impl TransportError {
    /// A retryable transport failure (connection, timeout, TLS, ...).
    pub fn other(message: impl Into<String>) -> Self {
        Self {
            kind: TransportErrorKind::Other,
            message: message.into(),
        }
    }

    /// The response exceeded a size limit (never retried). The message is `"response too large: <detail>"`.
    pub fn too_large(detail: &str) -> Self {
        Self {
            kind: TransportErrorKind::TooLarge,
            message: format!("{TOO_LARGE}: {detail}"),
        }
    }

    pub fn is_too_large(&self) -> bool {
        self.kind == TransportErrorKind::TooLarge
    }
}

impl fmt::Display for TransportError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for TransportError {}

pub trait HttpTransport {
    fn send(&self, req: &Request) -> Result<Response, TransportError>;
}

/// Where bearer tokens come from (API key, OIDC access token, refreshable session).
pub trait TokenSource: Send + Sync {
    fn token(&self) -> Result<String, String>;
    /// Called once after a 401; return a new token or an error.
    fn refresh(&self) -> Result<String, String> {
        Err("token cannot be refreshed".into())
    }
}

/// A fixed token (API key).
pub struct StaticToken(Mutex<String>);

impl StaticToken {
    pub fn new(token: impl Into<String>) -> Self {
        Self(Mutex::new(token.into()))
    }
}

impl TokenSource for StaticToken {
    fn token(&self) -> Result<String, String> {
        Ok(self.0.lock().expect("token lock").clone())
    }
}

impl fmt::Debug for StaticToken {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("StaticToken(<redacted>)")
    }
}

/// RFC 9457 problem details.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
pub struct Problem {
    #[serde(rename = "type", default)]
    pub type_: Option<String>,
    #[serde(default)]
    pub title: Option<String>,
    #[serde(default)]
    pub status: Option<u16>,
    #[serde(default)]
    pub detail: Option<String>,
    #[serde(default)]
    pub instance: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ApiError {
    Url(String),
    Transport(String),
    Auth(String),
    Http {
        status: u16,
        problem: Option<Box<Problem>>,
        method: String,
        path: String,
    },
    Decode(String),
}

impl fmt::Display for ApiError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Url(m) => write!(f, "invalid API URL: {m}"),
            Self::Transport(m) => write!(f, "transport error: {m}"),
            Self::Auth(m) => write!(f, "authentication: {m}"),
            Self::Http {
                status,
                problem,
                method,
                path,
            } => {
                write!(f, "{method} {path} -> HTTP {status}")?;
                if let Some(p) = problem {
                    if let Some(t) = &p.title {
                        write!(f, " {t}")?;
                    }
                    if let Some(d) = &p.detail {
                        write!(f, ": {d}")?;
                    }
                }
                Ok(())
            }
            Self::Decode(m) => write!(f, "response decoding: {m}"),
        }
    }
}
impl std::error::Error for ApiError {}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct RetryPolicy {
    /// Total attempts including the first one.
    pub max_attempts: u32,
    pub base_delay: Duration,
    pub max_delay: Duration,
    pub max_retry_after: Duration,
}

impl Default for RetryPolicy {
    fn default() -> Self {
        Self {
            max_attempts: 5,
            base_delay: Duration::from_millis(200),
            max_delay: Duration::from_secs(10),
            max_retry_after: Duration::from_secs(60),
        }
    }
}

impl RetryPolicy {
    /// Backoff before retry number `attempt` (1-based), full jitter in `[0, min(max, base*2^(n-1))]`.
    pub fn backoff(&self, attempt: u32) -> Duration {
        let exp = self
            .base_delay
            .saturating_mul(1u32 << (attempt.saturating_sub(1)).min(20));
        let cap = exp.min(self.max_delay);
        let mut r = [0u8; 8];
        let frac = if getrandom::getrandom(&mut r).is_ok() {
            (u64::from_le_bytes(r) >> 11) as f64 / (1u64 << 53) as f64
        } else {
            1.0
        };
        cap.mul_f64(frac)
    }
}

pub fn is_idempotent(method: &str, headers: &[(String, String)]) -> bool {
    matches!(method, "GET" | "HEAD" | "PUT" | "DELETE" | "OPTIONS")
        || headers
            .iter()
            .any(|(k, _)| k.eq_ignore_ascii_case("idempotency-key"))
}

/// Host part of an absolute URL (lower-case, without port or brackets).
fn url_host(url: &str) -> Option<(String, String)> {
    let (scheme, rest) = url.split_once("://")?;
    let authority = rest.split(['/', '?', '#']).next()?;
    let authority = authority.rsplit_once('@').map_or(authority, |(_, h)| h);
    let host = if let Some(stripped) = authority.strip_prefix('[') {
        stripped.split(']').next()?.to_owned()
    } else {
        authority.split(':').next()?.to_owned()
    };
    if host.is_empty() {
        return None;
    }
    Some((scheme.to_ascii_lowercase(), host.to_ascii_lowercase()))
}

pub fn is_loopback_host(host: &str) -> bool {
    host == "localhost"
        || host == "::1"
        || host.split('.').count() == 4
            && host.starts_with("127.")
            && host.split('.').all(|p| p.parse::<u8>().is_ok())
}

/// SEC-030 base-URL policy: https, or http to a loopback host.
pub fn check_base_url(url: &str) -> Result<(), ApiError> {
    let (scheme, host) =
        url_host(url).ok_or_else(|| ApiError::Url("not an absolute URL".into()))?;
    match scheme.as_str() {
        "https" => Ok(()),
        "http" if is_loopback_host(&host) => Ok(()),
        "http" => Err(ApiError::Url(
            "plain http is only allowed for loopback hosts; use https".into(),
        )),
        other => Err(ApiError::Url(format!("unsupported scheme {other}"))),
    }
}

/// Percent-encode a query component (RFC 3986 unreserved characters kept).
pub fn encode_component(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.bytes() {
        if b.is_ascii_alphanumeric() || matches!(b, b'-' | b'.' | b'_' | b'~') {
            out.push(b as char);
        } else {
            out.push_str(&format!("%{b:02X}"));
        }
    }
    out
}

/// Parse `Retry-After` given in seconds (HTTP-dates are ignored: exponential backoff applies).
pub fn retry_after(resp: &Response) -> Option<Duration> {
    resp.header("retry-after")?
        .trim()
        .parse::<u64>()
        .ok()
        .map(Duration::from_secs)
}

pub fn parse_problem(resp: &Response) -> Option<Problem> {
    let ct = resp.header("content-type").unwrap_or("");
    if ct.contains("json") {
        serde_json::from_slice(&resp.body).ok()
    } else {
        None
    }
}

/// The client: base URL + transport + token source + retry policy.
pub struct ApiClient<T: HttpTransport> {
    base: String,
    transport: T,
    tokens: Box<dyn TokenSource>,
    pub policy: RetryPolicy,
    pub user_agent: String,
    sleep: Box<dyn Fn(Duration) + Send + Sync>,
}

impl<T: HttpTransport> ApiClient<T> {
    pub fn new(base: &str, transport: T, tokens: Box<dyn TokenSource>) -> Result<Self, ApiError> {
        check_base_url(base)?;
        Ok(Self {
            base: base.trim_end_matches('/').to_owned(),
            transport,
            tokens,
            policy: RetryPolicy::default(),
            user_agent: format!("nf-core/{}", crate::VERSION),
            sleep: Box::new(std::thread::sleep),
        })
    }

    /// Replace the sleep function (tests, or a caller that must stay responsive).
    pub fn with_sleep(mut self, f: impl Fn(Duration) + Send + Sync + 'static) -> Self {
        self.sleep = Box::new(f);
        self
    }

    pub fn base(&self) -> &str {
        &self.base
    }

    pub fn url(&self, path: &str, query: &[(&str, String)]) -> String {
        let mut u = format!("{}/{}", self.base, path.trim_start_matches('/'));
        for (i, (k, v)) in query.iter().enumerate() {
            u.push(if i == 0 { '?' } else { '&' });
            u.push_str(&encode_component(k));
            u.push('=');
            u.push_str(&encode_component(v));
        }
        u
    }

    /// Send with auth and retries. Non-2xx responses become [`ApiError::Http`].
    pub fn send(
        &self,
        method: &str,
        path: &str,
        query: &[(&str, String)],
        mut headers: Vec<(String, String)>,
        body: Vec<u8>,
    ) -> Result<Response, ApiError> {
        let method = method.to_ascii_uppercase();
        let retryable = is_idempotent(&method, &headers);
        let mut token = self.tokens.token().map_err(ApiError::Auth)?;
        let mut refreshed = false;
        headers.push(("user-agent".into(), self.user_agent.clone()));
        let mut attempt = 0u32;
        loop {
            attempt += 1;
            let mut h = headers.clone();
            h.push(("authorization".into(), format!("Bearer {token}")));
            let req = Request {
                method: method.clone(),
                url: self.url(path, query),
                headers: h,
                body: body.clone(),
            };
            let outcome = self.transport.send(&req);
            let err_delay = match &outcome {
                Err(e) => {
                    // an over-size response is deterministic: never retried
                    if !retryable || e.is_too_large() || attempt >= self.policy.max_attempts {
                        return Err(ApiError::Transport(e.message.clone()));
                    }
                    self.policy.backoff(attempt)
                }
                Ok(r) if r.status == 401 && !refreshed => {
                    refreshed = true;
                    token = self
                        .tokens
                        .refresh()
                        .map_err(|_| self.http_err(r, &method, path))?;
                    attempt -= 1; // the refresh round does not count as a retry
                    continue;
                }
                Ok(r) if (200..300).contains(&r.status) => return Ok(r.clone()),
                Ok(r)
                    if RETRY_STATUSES.contains(&r.status)
                        && retryable
                        && attempt < self.policy.max_attempts =>
                {
                    match retry_after(r) {
                        Some(d) if d > self.policy.max_retry_after => {
                            return Err(self.http_err(r, &method, path));
                        }
                        Some(d) => d,
                        None => self.policy.backoff(attempt),
                    }
                }
                Ok(r) => return Err(self.http_err(r, &method, path)),
            };
            (self.sleep)(err_delay);
        }
    }

    fn http_err(&self, r: &Response, method: &str, path: &str) -> ApiError {
        ApiError::Http {
            status: r.status,
            problem: parse_problem(r).map(Box::new),
            method: method.into(),
            path: path.into(),
        }
    }

    pub fn get_json<R: for<'de> Deserialize<'de>>(
        &self,
        path: &str,
        query: &[(&str, String)],
    ) -> Result<R, ApiError> {
        let r = self.send(
            "GET",
            path,
            query,
            vec![("accept".into(), "application/json".into())],
            vec![],
        )?;
        serde_json::from_slice(&r.body).map_err(|e| ApiError::Decode(e.to_string()))
    }

    pub fn post_json<B: Serialize, R: for<'de> Deserialize<'de>>(
        &self,
        path: &str,
        body: &B,
        idempotency_key: Option<&str>,
    ) -> Result<R, ApiError> {
        let mut h = vec![
            ("accept".to_owned(), "application/json".to_owned()),
            ("content-type".to_owned(), "application/json".to_owned()),
        ];
        if let Some(k) = idempotency_key {
            h.push(("idempotency-key".into(), k.into()));
        }
        let b = serde_json::to_vec(body).map_err(|e| ApiError::Decode(e.to_string()))?;
        let r = self.send("POST", path, &[], h, b)?;
        serde_json::from_slice(&r.body).map_err(|e| ApiError::Decode(e.to_string()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use std::sync::atomic::{AtomicU32, Ordering};

    struct Script {
        replies: Mutex<Vec<Result<Response, TransportError>>>,
        seen: Mutex<Vec<Request>>,
    }
    impl HttpTransport for Arc<Script> {
        fn send(&self, req: &Request) -> Result<Response, TransportError> {
            self.seen.lock().unwrap().push(req.clone());
            self.replies.lock().unwrap().remove(0)
        }
    }
    fn resp(status: u16, headers: &[(&str, &str)], body: &str) -> Result<Response, TransportError> {
        Ok(Response {
            status,
            headers: headers
                .iter()
                .map(|(a, b)| (a.to_string(), b.to_string()))
                .collect(),
            body: body.as_bytes().to_vec(),
        })
    }
    fn client(
        replies: Vec<Result<Response, TransportError>>,
    ) -> (ApiClient<Arc<Script>>, Arc<Script>, Arc<AtomicU32>) {
        let s = Arc::new(Script {
            replies: Mutex::new(replies),
            seen: Mutex::new(vec![]),
        });
        let sleeps = Arc::new(AtomicU32::new(0));
        let sl = sleeps.clone();
        let c = ApiClient::new(
            "https://api.example.test/",
            s.clone(),
            Box::new(StaticToken::new("tok-1")),
        )
        .unwrap()
        .with_sleep(move |_| {
            sl.fetch_add(1, Ordering::SeqCst);
        });
        (c, s, sleeps)
    }

    #[test]
    fn url_policy() {
        assert!(check_base_url("https://api.example.test").is_ok());
        assert!(check_base_url("http://127.0.0.1:8000").is_ok());
        assert!(check_base_url("http://localhost/v1").is_ok());
        assert!(check_base_url("http://[::1]:9/").is_ok());
        assert!(check_base_url("http://api.example.test").is_err());
        assert!(check_base_url("http://127.0.0.1.evil.test").is_err());
        assert!(check_base_url("http://user@127.0.0.1.evil.test/").is_err());
        assert!(check_base_url("ftp://x").is_err());
        assert!(check_base_url("api.example.test").is_err());
    }

    #[test]
    fn retries_get_on_503_and_transport_errors() {
        let (c, s, sleeps) = client(vec![
            Err(TransportError::other("reset")),
            resp(503, &[], ""),
            resp(
                200,
                &[("content-type", "application/json")],
                r#"{"ok":true}"#,
            ),
        ]);
        let v: serde_json::Value = c.get_json("/v1/health", &[("a b", "x&y".into())]).unwrap();
        assert_eq!(v["ok"], true);
        assert_eq!(sleeps.load(Ordering::SeqCst), 2);
        let seen = s.seen.lock().unwrap();
        assert_eq!(
            seen[0].url,
            "https://api.example.test/v1/health?a%20b=x%26y"
        );
        assert!(
            seen[0]
                .headers
                .contains(&("authorization".into(), "Bearer tok-1".into()))
        );
        assert!(!format!("{:?}", seen[0]).contains("tok-1"));
    }

    #[test]
    fn post_without_idempotency_key_is_not_retried() {
        let (c, s, _) = client(vec![resp(503, &[], ""), resp(200, &[], "{}")]);
        let e = c
            .post_json::<_, serde_json::Value>("/v1/runs", &serde_json::json!({}), None)
            .unwrap_err();
        assert!(matches!(e, ApiError::Http { status: 503, .. }));
        assert_eq!(s.seen.lock().unwrap().len(), 1);
        let (c, s, _) = client(vec![resp(503, &[], ""), resp(200, &[], "{}")]);
        c.post_json::<_, serde_json::Value>("/v1/runs", &serde_json::json!({}), Some("k1"))
            .unwrap();
        assert_eq!(s.seen.lock().unwrap().len(), 2);
    }

    #[test]
    fn retry_after_cap_and_problem_json() {
        let (c, s, _) = client(vec![resp(
            429,
            &[
                ("retry-after", "3600"),
                ("content-type", "application/problem+json"),
            ],
            r#"{"type":"about:blank","title":"Too Many Requests","status":429,"detail":"slow down"}"#,
        )]);
        let e = c.get_json::<serde_json::Value>("/v1/x", &[]).unwrap_err();
        match e {
            ApiError::Http {
                status: 429,
                problem: Some(p),
                ..
            } => assert_eq!(p.detail.as_deref(), Some("slow down")),
            other => panic!("{other:?}"),
        }
        assert_eq!(s.seen.lock().unwrap().len(), 1);
    }

    #[test]
    fn too_large_is_not_retried() {
        let (c, s, sleeps) = client(vec![
            Err(TransportError::too_large("body above 64 MiB")),
            resp(200, &[], "{}"),
        ]);
        let e = c.get_json::<serde_json::Value>("/v1/x", &[]).unwrap_err();
        match e {
            ApiError::Transport(m) => assert!(m.starts_with(TOO_LARGE), "{m}"),
            other => panic!("{other:?}"),
        }
        assert_eq!(s.seen.lock().unwrap().len(), 1, "exactly one attempt");
        assert_eq!(sleeps.load(Ordering::SeqCst), 0);
        let tl = TransportError::too_large("x");
        assert_eq!(tl.kind, TransportErrorKind::TooLarge);
        assert!(tl.is_too_large());
        assert_eq!(tl.to_string(), "response too large: x");
        // the kind decides, not the text: a plain error whose message merely starts with the
        // prefix is still retryable
        assert!(!TransportError::other(format!("{TOO_LARGE} (quoted by a proxy)")).is_too_large());
    }

    #[test]
    fn plain_transport_errors_still_retry_to_max_attempts() {
        let (c, s, _) = client(
            (0..5)
                .map(|_| Err(TransportError::other("connection reset")))
                .collect(),
        );
        assert!(matches!(
            c.get_json::<serde_json::Value>("/v1/x", &[]),
            Err(ApiError::Transport(_))
        ));
        assert_eq!(s.seen.lock().unwrap().len(), 5);
    }

    #[test]
    fn gives_up_after_max_attempts() {
        let (c, s, _) = client((0..5).map(|_| resp(502, &[], "")).collect());
        assert!(c.get_json::<serde_json::Value>("/v1/x", &[]).is_err());
        assert_eq!(s.seen.lock().unwrap().len(), 5);
    }

    struct Refreshing(AtomicU32);
    impl TokenSource for Refreshing {
        fn token(&self) -> Result<String, String> {
            Ok("old".into())
        }
        fn refresh(&self) -> Result<String, String> {
            self.0.fetch_add(1, Ordering::SeqCst);
            Ok("new".into())
        }
    }

    #[test]
    fn refreshes_once_on_401() {
        let s = Arc::new(Script {
            replies: Mutex::new(vec![resp(401, &[], ""), resp(401, &[], "")]),
            seen: Mutex::new(vec![]),
        });
        let c = ApiClient::new(
            "https://a.test",
            s.clone(),
            Box::new(Refreshing(AtomicU32::new(0))),
        )
        .unwrap();
        let e = c.get_json::<serde_json::Value>("/v1/x", &[]).unwrap_err();
        assert!(matches!(e, ApiError::Http { status: 401, .. }));
        let seen = s.seen.lock().unwrap();
        assert_eq!(seen.len(), 2);
        assert!(
            seen[1]
                .headers
                .contains(&("authorization".into(), "Bearer new".into()))
        );
    }

    #[test]
    fn backoff_is_bounded() {
        let p = RetryPolicy::default();
        for n in 1..40 {
            assert!(p.backoff(n) <= p.max_delay);
        }
    }
}

//! Platform API client core: bearer-token auth with one refresh on 401, retries with backoff for
//! idempotent requests, problem+json errors and the SEC-030 base-URL policy. The HTTP stack and
//! the token store belong to the caller (C callbacks), as in the Python binding.
//!
//! Thread safety: an `nf_api_client` may be used from several threads when its callbacks are
//! thread-safe; each request runs its callbacks on the calling thread.

use std::ffi::{CString, c_char, c_void};

use nf_core::http::{
    self, ApiClient, ApiError, HttpTransport, Request, Response, TokenSource, TransportError,
};

use crate::streaming::nf_reply;
use crate::{
    Error, NF_ERR_AUTH, NF_ERR_HTTP, NF_ERR_INVALID_ARG, NF_ERR_TRANSPORT, Result, cstr,
    free_handle, guard, guard_value, handle, into_handle, nf_status, opt_cstr, out, slice,
};

/// One header or query pair (NUL-terminated UTF-8).
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct nf_header {
    pub name: *const c_char,
    pub value: *const c_char,
}

/// A request handed to the caller's HTTP transport. Valid only during the callback.
#[repr(C)]
#[derive(Debug)]
pub struct nf_http_request {
    pub method: *const c_char,
    pub url: *const c_char,
    pub headers: *const nf_header,
    pub n_headers: usize,
    pub body: *const u8,
    pub body_len: usize,
    pub timeout_s: f64,
}

/// Fixed cap on one HTTP response: header names and values plus body together (64 MiB). Over it
/// the request fails (CABI-M1 case 12). A transport that wants a lower limit (the engine default
/// transports use 16 MiB) enforces it on its own side.
pub const NF_MAX_RESPONSE_BYTES: usize = 64 << 20;

/// Most response headers one reply may carry (`nf_http_reply_add_header`).
pub const NF_MAX_RESPONSE_HEADERS: usize = 256;

/// Most bytes of header names plus values one reply may carry (256 KiB).
pub const NF_MAX_RESPONSE_HEADER_BYTES: usize = 256 << 10;

/// Response slot handed to the caller's HTTP transport. Opaque.
pub struct nf_http_reply {
    status: u16,
    headers: Vec<(String, String)>,
    header_bytes: usize,
    body: Vec<u8>,
    /// A cap was exceeded; the request fails whatever the callback returns.
    overflow: bool,
}

impl nf_http_reply {
    /// Mark the reply as over a limit and drop what it holds.
    fn refuse(&mut self, what: String) -> crate::Result<()> {
        self.overflow = true;
        // replace rather than clear, so the memory is released at once (nfb-security)
        self.headers = Vec::new();
        self.header_bytes = 0;
        self.body = Vec::new();
        Err(Error::invalid(what))
    }
}

/// Perform one HTTP exchange. Return 0 after filling `reply` (status, headers, body) for any
/// HTTP status, or non-zero for a transport failure (connection, TLS, timeout), with an
/// optional UTF-8 message set via `nf_http_reply_set_body`.
pub type nf_http_send_fn = Option<
    unsafe extern "C" fn(
        user: *mut c_void,
        request: *const nf_http_request,
        reply: *mut nf_http_reply,
    ) -> i32,
>;

/// Return a bearer token (`refresh` false) or a new one after a 401 (`refresh` true): set it with
/// `nf_reply_set` and return 0, or return non-zero on failure.
pub type nf_token_fn =
    Option<unsafe extern "C" fn(user: *mut c_void, refresh: bool, reply: *mut nf_reply) -> i32>;

/// The caller's HTTP stack.
/// Transport requirements (SEC-030, CABI-M1); a conforming transport MUST:
/// 1. use TLS 1.3 only and refuse lower versions (plain http only to a loopback host);
/// 2. verify the certificate chain and hostname on every connection (no accept-all handler);
/// 3. never follow redirects (hand the 3xx back through the reply), and never send the
///    `authorization` header to any host other than the request URL's;
/// 4. enforce `timeout_s` as the whole-request deadline;
/// 5. never log, cache or persist `authorization`, request headers or bodies;
/// 6. stop reading once the response passes `NF_MAX_RESPONSE_BYTES` or the header limits (the
///    `nf_http_reply_*` setters then fail, and so does the request).
///
/// Thread contract: `send` runs on the thread that called
/// `nf_api_client_request`, and may run concurrently from every thread that shares the client, so
/// `send` and `user` must be thread-safe if the client is shared. It must not unwind, throw or
/// longjmp.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct nf_http_transport {
    pub user: *mut c_void,
    pub send: nf_http_send_fn,
}

/// The caller's token store (API key, OIDC session, ...). Thread contract as for
/// `nf_http_transport`: `token` may be called concurrently from every thread that shares the client
/// (including a refresh on one thread while another reads), so it and `user` must be thread-safe.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct nf_token_source {
    pub user: *mut c_void,
    pub token: nf_token_fn,
}

/// Set the HTTP status of the reply.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_http_reply_set_status(
    reply: *mut nf_http_reply,
    status: u16,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        unsafe { out(reply, "reply")? }.status = status;
        Ok(())
    })
}

/// Append one response header (copied). At most `NF_MAX_RESPONSE_HEADERS` headers and
/// `NF_MAX_RESPONSE_HEADER_BYTES` of names plus values, and headers plus body together within
/// `NF_MAX_RESPONSE_BYTES` whichever is set first: beyond that this returns
/// `NF_ERR_INVALID_ARG` and the request fails as a transport error whatever the callback returns.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_http_reply_add_header(
    reply: *mut nf_http_reply,
    name: *const c_char,
    value: *const c_char,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (r, n, v) = unsafe {
            (
                out(reply, "reply")?,
                cstr(name, "name")?,
                cstr(value, "value")?,
            )
        };
        let bytes = r
            .header_bytes
            .saturating_add(n.len())
            .saturating_add(v.len());
        // headers and body share NF_MAX_RESPONSE_BYTES in either order (nfb-security)
        if r.overflow
            || r.headers.len() >= NF_MAX_RESPONSE_HEADERS
            || bytes > NF_MAX_RESPONSE_HEADER_BYTES
            || bytes.saturating_add(r.body.len()) > NF_MAX_RESPONSE_BYTES
        {
            return r.refuse(format!(
                "response headers exceed NF_MAX_RESPONSE_HEADERS ({NF_MAX_RESPONSE_HEADERS}) or \
                 NF_MAX_RESPONSE_HEADER_BYTES ({NF_MAX_RESPONSE_HEADER_BYTES})"
            ));
        }
        r.header_bytes = bytes;
        r.headers.push((n.to_owned(), v.to_owned()));
        Ok(())
    })
}

/// Set the response body (copied), or the error message when the callback fails. The body may not
/// make headers plus body exceed `NF_MAX_RESPONSE_BYTES`: above it this returns
/// `NF_ERR_INVALID_ARG` and the request fails as a transport error whatever the callback returns.
/// Setting the body again replaces it.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_http_reply_set_body(
    reply: *mut nf_http_reply,
    data: *const u8,
    len: usize,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (r, d) = unsafe { (out(reply, "reply")?, slice(data, len, "data")?) };
        // checked before any copy: an oversize body is never allocated (nfb-security)
        if r.overflow || d.len() > NF_MAX_RESPONSE_BYTES.saturating_sub(r.header_bytes) {
            return r.refuse(format!(
                "response of {} body bytes exceeds NF_MAX_RESPONSE_BYTES ({NF_MAX_RESPONSE_BYTES})",
                d.len()
            ));
        }
        r.body = d.to_vec();
        Ok(())
    })
}

struct CHttp {
    table: nf_http_transport,
    timeout_s: f64,
}

fn cstring(s: &str, what: &str) -> std::result::Result<CString, TransportError> {
    CString::new(s).map_err(|_| TransportError::other(format!("{what} contains NUL")))
}

impl HttpTransport for CHttp {
    fn send(&self, req: &Request) -> std::result::Result<Response, TransportError> {
        let f = self
            .table
            .send
            .ok_or_else(|| TransportError::other("transport callback send is NULL"))?;
        let method = cstring(&req.method, "method")?;
        let url = cstring(&req.url, "url")?;
        let owned: Vec<(CString, CString)> = req
            .headers
            .iter()
            .map(|(k, v)| Ok((cstring(k, "header name")?, cstring(v, "header value")?)))
            .collect::<std::result::Result<_, TransportError>>()?;
        let headers: Vec<nf_header> = owned
            .iter()
            .map(|(k, v)| nf_header {
                name: k.as_ptr(),
                value: v.as_ptr(),
            })
            .collect();
        let creq = nf_http_request {
            method: method.as_ptr(),
            url: url.as_ptr(),
            headers: headers.as_ptr(),
            n_headers: headers.len(),
            body: req.body.as_ptr(),
            body_len: req.body.len(),
            timeout_s: self.timeout_s,
        };
        let mut reply = nf_http_reply {
            status: 0,
            headers: Vec::new(),
            header_bytes: 0,
            body: Vec::new(),
            overflow: false,
        };
        // SAFETY: the caller's callback; every pointer outlives the call.
        let code = unsafe { f(self.table.user, &creq, &mut reply) };
        if reply.overflow {
            // deterministic, so nf-core does not retry it
            return Err(TransportError::too_large(&format!(
                "exceeds NF_MAX_RESPONSE_BYTES ({NF_MAX_RESPONSE_BYTES}) or the header limits"
            )));
        }
        if code != 0 {
            let m = String::from_utf8_lossy(&reply.body).into_owned();
            return Err(TransportError::other(if m.is_empty() {
                format!("transport failed with code {code}")
            } else {
                m
            }));
        }
        if !(100..=599).contains(&reply.status) {
            return Err(TransportError::other(format!(
                "transport returned HTTP status {}",
                reply.status
            )));
        }
        Ok(Response {
            status: reply.status,
            headers: reply.headers,
            body: reply.body,
        })
    }
}

struct CTokens(nf_token_source);

// SAFETY: TokenSource needs Send + Sync. The callback and `user` belong to the caller, who
// promises (header) that they are thread-safe if the client is shared between threads.
unsafe impl Send for CTokens {}
unsafe impl Sync for CTokens {}

impl CTokens {
    fn get(&self, refresh: bool) -> std::result::Result<String, String> {
        let f = self.0.token.ok_or("token callback is NULL")?;
        let mut reply = nf_reply::new();
        // SAFETY: the caller's callback.
        let code = unsafe { f(self.0.user, refresh, &mut reply) };
        if reply.overflow {
            return Err("token reply exceeds NF_MAX_REPLY_BYTES".to_owned());
        }
        let text = String::from_utf8(reply.data).map_err(|_| "token is not UTF-8".to_owned())?;
        if code == 0 {
            Ok(text)
        } else if text.is_empty() {
            Err(format!("token callback failed with code {code}"))
        } else {
            Err(text)
        }
    }
}

impl TokenSource for CTokens {
    fn token(&self) -> std::result::Result<String, String> {
        self.get(false)
    }
    fn refresh(&self) -> std::result::Result<String, String> {
        self.get(true)
    }
}

fn api_err(e: ApiError) -> Error {
    match &e {
        ApiError::Http { problem, .. } => Error {
            code: NF_ERR_HTTP,
            msg: e.to_string(),
            detail: problem.as_ref().and_then(|p| serde_json::to_string(p).ok()),
        },
        ApiError::Url(_) => Error::new(NF_ERR_INVALID_ARG, e.to_string()),
        ApiError::Auth(_) => Error::new(NF_ERR_AUTH, e.to_string()),
        ApiError::Transport(_) | ApiError::Decode(_) => Error::new(NF_ERR_TRANSPORT, e.to_string()),
    }
}

/// An API client bound to one base URL. Opaque; free with `nf_api_client_free`.
pub struct nf_api_client {
    client: ApiClient<CHttp>,
}

/// A 2xx response. Opaque; free with `nf_http_response_free`.
pub struct nf_http_response {
    status: u16,
    headers: Vec<(CString, CString)>,
    body: Vec<u8>,
}

/// Check a base URL against the SEC-030 policy (https, or http to a loopback host):
/// `NF_OK` or `NF_ERR_INVALID_ARG`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_check_base_url(url: *const c_char) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let u = unsafe { cstr(url, "url")? };
        http::check_base_url(u).map_err(api_err)
    })
}

/// A client for `base_url` (checked with `nf_check_base_url`). `timeout_s` is passed to every
/// transport call, `max_attempts` bounds retries (at least 1), `user_agent` may be NULL. The
/// transport and token tables are copied; their `user` pointers must stay valid until
/// `nf_api_client_free`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_api_client_new(
    base_url: *const c_char,
    transport: *const nf_http_transport,
    tokens: *const nf_token_source,
    timeout_s: f64,
    max_attempts: u32,
    user_agent: *const c_char,
    out_client: *mut *mut nf_api_client,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (u, t, k, ua, o) = unsafe {
            (
                cstr(base_url, "base_url")?,
                handle(transport, "transport")?,
                handle(tokens, "tokens")?,
                opt_cstr(user_agent, "user_agent")?,
                out(out_client, "out_client")?,
            )
        };
        if !(timeout_s.is_finite() && timeout_s > 0.0) {
            return Err(Error::invalid("timeout_s must be positive"));
        }
        let http = CHttp {
            table: *t,
            timeout_s,
        };
        let mut c = ApiClient::new(u, http, Box::new(CTokens(*k))).map_err(api_err)?;
        c.policy.max_attempts = max_attempts.max(1);
        if let Some(ua) = ua {
            c.user_agent = ua.to_owned();
        }
        *o = into_handle(nf_api_client { client: c });
        Ok(())
    })
}

/// Free a client (NULL is a no-op).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_api_client_free(client: *mut nf_api_client) {
    // SAFETY: header contract.
    unsafe { free_handle(client) }
}

unsafe fn pairs(p: *const nf_header, n: usize, what: &str) -> Result<Vec<(String, String)>> {
    // SAFETY: header contract.
    unsafe { slice(p, n, what) }?
        .iter()
        .map(|h| {
            // SAFETY: header contract for each pair.
            let (k, v) = unsafe { (cstr(h.name, what)?, cstr(h.value, what)?) };
            Ok((k.to_owned(), v.to_owned()))
        })
        .collect()
}

/// Send `method path?query` with auth and retries. `query` and `headers` are arrays of pairs
/// (may be NULL when their count is 0); `body` may be NULL when `body_len` is 0. A 2xx answer
/// yields `*out_response`; any other status is `NF_ERR_HTTP` with the problem+json in
/// `nf_last_error_detail()`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_api_client_request(
    client: *const nf_api_client,
    method: *const c_char,
    path: *const c_char,
    query: *const nf_header,
    n_query: usize,
    headers: *const nf_header,
    n_headers: usize,
    body: *const u8,
    body_len: usize,
    out_response: *mut *mut nf_http_response,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (c, m, p, q, h, b, o) = unsafe {
            (
                handle(client, "client")?,
                cstr(method, "method")?,
                cstr(path, "path")?,
                pairs(query, n_query, "query")?,
                pairs(headers, n_headers, "headers")?,
                slice(body, body_len, "body")?,
                out(out_response, "out_response")?,
            )
        };
        let q: Vec<(&str, String)> = q.iter().map(|(k, v)| (k.as_str(), v.clone())).collect();
        let r = c.client.send(m, p, &q, h, b.to_vec()).map_err(api_err)?;
        let headers = r
            .headers
            .into_iter()
            .map(|(k, v)| {
                Ok((
                    CString::new(k).map_err(|_| Error::new(NF_ERR_TRANSPORT, "header has NUL"))?,
                    CString::new(v).map_err(|_| Error::new(NF_ERR_TRANSPORT, "header has NUL"))?,
                ))
            })
            .collect::<Result<Vec<_>>>()?;
        *o = into_handle(nf_http_response {
            status: r.status,
            headers,
            body: r.body,
        });
        Ok(())
    })
}

/// Free a response (NULL is a no-op).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_http_response_free(response: *mut nf_http_response) {
    // SAFETY: header contract.
    unsafe { free_handle(response) }
}

/// HTTP status (0 for NULL).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_http_response_status(response: *const nf_http_response) -> u16 {
    // SAFETY: header contract.
    guard_value(0, || Ok(unsafe { handle(response, "response") }?.status))
}

/// Number of response headers (0 for NULL).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_http_response_header_count(response: *const nf_http_response) -> usize {
    // SAFETY: header contract.
    guard_value(0, || {
        Ok(unsafe { handle(response, "response") }?.headers.len())
    })
}

/// Header `index`: `*out_name` and `*out_value` point into the response (valid until it is
/// freed).
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_http_response_header(
    response: *const nf_http_response,
    index: usize,
    out_name: *mut *const c_char,
    out_value: *mut *const c_char,
) -> nf_status {
    guard(|| {
        // SAFETY: header contract.
        let (r, n, v) = unsafe {
            (
                handle(response, "response")?,
                out(out_name, "out_name")?,
                out(out_value, "out_value")?,
            )
        };
        let (k, val): &(CString, CString) = r
            .headers
            .get(index)
            .ok_or_else(|| Error::invalid(format!("no header {index}")))?;
        *n = k.as_ptr();
        *v = val.as_ptr();
        Ok(())
    })
}

/// Response body, owned by the response; `*out_len` receives its length. NULL for NULL.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn nf_http_response_body(
    response: *const nf_http_response,
    out_len: *mut usize,
) -> *const u8 {
    guard_value(std::ptr::null(), || {
        // SAFETY: header contract.
        let r = unsafe { handle(response, "response") }?;
        // SAFETY: NULL or writable.
        if let Some(l) = unsafe { crate::opt_out(out_len, "out_len") }? {
            *l = r.body.len();
        }
        Ok(r.body.as_ptr())
    })
}

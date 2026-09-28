// nf_winhttp_transport.hpp: header-only HTTPS transport for C++ hosts on Windows, written to the
// CABI-M1 transport contract (docs/hive/CABI-M1-PLAN.md). Plugs into neuroforge::ApiClient
// (bindings/cpp/neuroforge.hpp) as its HttpSend. Uses only WinHTTP, which ships with Windows.
//
// Contract, and how it is met:
//  1. TLS 1.3 only: WINHTTP_OPTION_SECURE_PROTOCOLS = TLS1_3, no fallback to TLS 1.2. Schannel
//     supports TLS 1.3 from Windows 11 and Windows Server 2022; every Windows 10 version lists it
//     as "Not supported" (Microsoft Learn, "Protocols in TLS/SSL (Schannel SSP)", 2025-03-20).
//     There the constructor throws if WinHTTP rejects the option, and otherwise every connection
//     fails its handshake: the transport fails closed either way.
//  2. Certificate chain and hostname are verified by WinHTTP against the Windows trust store (no
//     ignore flags), with revocation checking ON (WINHTTP_ENABLE_SSL_REVOCATION) and failing closed:
//     revoked and "revocation unknown/offline" both fail the request. This header has
//     NO way to trust another CA or certificate. The test-only CA hook lives in
//     unshipped test-only header under ../tests/; defining NF_TRANSPORT_TESTING against this
//     header is a compile error.
//  3. Redirects are never followed (WINHTTP_OPTION_REDIRECT_POLICY_NEVER on the session and the
//     request, plus WINHTTP_DISABLE_REDIRECTS): a 3xx is returned to the library as the response.
//  4. timeout_s is the whole-request deadline: a threadpool-timer watchdog closes the request handle
//     at the deadline, which cancels whatever WinHTTP call is blocked; each phase also gets only the
//     time left. Measured bound: deadline + < 0.25 s (conformance case 4).
//  5. Nothing is logged; error texts name the failing WinHTTP step and error code only, never a URL
//     query, header or body.
//  6. No proxy (WINHTTP_ACCESS_TYPE_NO_PROXY): behind a mandatory corporate proxy every request
//     fails closed, which is intended. No cookies, no automatic authentication.
//  7. Plain http is refused unless the host is loopback (127.0.0.1, ::1, localhost); CR/LF in
//     request headers and credentials in the URL are refused before any network use.
//  8. Response headers are capped (default 64 KiB) and the body is capped (default 16 MiB, below
//     the library's fixed 64 MiB ceiling of ABI 1.2.1); larger responses are aborted, not buffered.
//
// Approved by nfb-security as a conformant Windows C++ transport for CABI-M1 cases 1-4, 6-9, 11, 12
// (review of cb0fd54). NOT a default transport: cases 10 (gRPC) and 13 (other platforms) are open.
#ifndef NF_WINHTTP_TRANSPORT_HPP
#define NF_WINHTTP_TRANSPORT_HPP

#ifdef NF_TRANSPORT_TESTING
#error "NF_TRANSPORT_TESTING is not supported by the shipped transport; the test-only hook lives in the unshipped tests/ header"
#endif

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <wincrypt.h>
#include <winhttp.h>

#include <atomic>
#include <cctype>
#include <chrono>
#include <cstdint>
#include <iterator>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "neuroforge.hpp"

#pragma comment(lib, "winhttp.lib")
#pragma comment(lib, "crypt32.lib")

#ifndef WINHTTP_FLAG_SECURE_PROTOCOL_TLS1_3
#define WINHTTP_FLAG_SECURE_PROTOCOL_TLS1_3 0x00002000
#endif

namespace nf {
namespace transport {

struct WinHttpOptions {
    size_t max_response_bytes = 16u << 20;  // body cap (nfb-security case 12)
    size_t max_header_bytes = 64u << 10;    // raw response header cap
    std::wstring user_agent = L"neuroforge-winhttp/1";
};

// A transport failure. what() never contains a header, body, token or URL query.
class TransportError : public std::runtime_error {
public:
    TransportError(const char *step, DWORD code)
        : std::runtime_error(std::string("winhttp: ") + step + " failed (error " + std::to_string(code) + ")"), code_(code) {}
    explicit TransportError(const std::string &what) : std::runtime_error("winhttp: " + what), code_(0) {}
    DWORD code() const noexcept { return code_; }

private:
    DWORD code_;
};

namespace detail {

struct HandleCloser {
    void operator()(HINTERNET h) const noexcept {
        if (h) WinHttpCloseHandle(h);
    }
};
using Handle = std::unique_ptr<void, HandleCloser>;

// Shared by the request thread, the deadline watchdog and (test builds) the pinning callback: the
// request handle is closed exactly once, by whoever flips `closed` first.
struct RequestState {
    HINTERNET request = nullptr;
    std::atomic<bool> closed{false};
    std::atomic<bool> deadline_fired{false};
    bool close_once() noexcept {
        if (closed.exchange(true)) return false;
        WinHttpCloseHandle(request);
        return true;
    }
};

// Declared, never defined here. Only the unshipped test-only header under ../tests/ defines it; the
// release conformance test asserts it is incomplete in a release translation unit.
struct TestAccess;

inline std::wstring widen(const std::string &s) {
    if (s.empty()) return {};
    int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(), static_cast<int>(s.size()), nullptr, 0);
    if (n <= 0) throw TransportError("invalid UTF-8 in request");
    std::wstring w(static_cast<size_t>(n), L'\0');
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(), static_cast<int>(s.size()), w.data(), n);
    return w;
}

inline std::string narrow(const wchar_t *p, size_t len) {
    if (len == 0) return {};
    int n = WideCharToMultiByte(CP_UTF8, 0, p, static_cast<int>(len), nullptr, 0, nullptr, nullptr);
    std::string s(static_cast<size_t>(n > 0 ? n : 0), '\0');
    if (n > 0) WideCharToMultiByte(CP_UTF8, 0, p, static_cast<int>(len), s.data(), n, nullptr, nullptr);
    return s;
}

inline bool has_crlf(const std::string &s) { return s.find_first_of("\r\n") != std::string::npos; }

inline bool is_loopback(const std::wstring &host) {
    return host == L"127.0.0.1" || host == L"::1" || host == L"[::1]" || _wcsicmp(host.c_str(), L"localhost") == 0;
}

// Closes the request handle at the deadline (threadpool timer). The destructor cancels the timer
// and waits for a running callback, so the state outlives every use.
class Watchdog {
public:
    Watchdog(RequestState &st, int ms) : st_(st) {
        timer_ = CreateThreadpoolTimer(&Watchdog::fire, &st_, nullptr);
        if (!timer_) throw TransportError("CreateThreadpoolTimer", GetLastError());
        ULARGE_INTEGER due;
        due.QuadPart = static_cast<ULONGLONG>(-(static_cast<LONGLONG>(ms) * 10000));  // relative, 100 ns units
        FILETIME ft{due.LowPart, due.HighPart};
        SetThreadpoolTimer(timer_, &ft, 0, 0);
    }
    Watchdog(const Watchdog &) = delete;
    Watchdog &operator=(const Watchdog &) = delete;
    ~Watchdog() {
        SetThreadpoolTimer(timer_, nullptr, 0, 0);
        WaitForThreadpoolTimerCallbacks(timer_, TRUE);
        CloseThreadpoolTimer(timer_);
    }

private:
    static void CALLBACK fire(PTP_CALLBACK_INSTANCE, PVOID ctx, PTP_TIMER) {
        auto *st = static_cast<RequestState *>(ctx);
        st->deadline_fired = true;
        st->close_once();  // cancels the blocked WinHTTP call
    }
    RequestState &st_;
    PTP_TIMER timer_ = nullptr;
};

}  // namespace detail

class WinHttpTransport {
public:
    explicit WinHttpTransport(WinHttpOptions opt = {}) : opt_(std::move(opt)) {
        session_.reset(WinHttpOpen(opt_.user_agent.c_str(), WINHTTP_ACCESS_TYPE_NO_PROXY, WINHTTP_NO_PROXY_NAME,
                                   WINHTTP_NO_PROXY_BYPASS, 0));
        if (!session_) throw TransportError("WinHttpOpen", GetLastError());
        DWORD protocols = WINHTTP_FLAG_SECURE_PROTOCOL_TLS1_3;
        if (!WinHttpSetOption(session_.get(), WINHTTP_OPTION_SECURE_PROTOCOLS, &protocols, sizeof(protocols)))
            throw TransportError("TLS 1.3 is not available on this Windows (no fallback to TLS 1.2)");
        DWORD policy = WINHTTP_OPTION_REDIRECT_POLICY_NEVER;
        if (!WinHttpSetOption(session_.get(), WINHTTP_OPTION_REDIRECT_POLICY, &policy, sizeof(policy)))
            throw TransportError("WinHttpSetOption(REDIRECT_POLICY)", GetLastError());
    }
    WinHttpTransport(const WinHttpTransport &) = delete;
    WinHttpTransport &operator=(const WinHttpTransport &) = delete;

    // For neuroforge::ApiClient: the returned function keeps a reference to this transport, which
    // must outlive the client.
    neuroforge::HttpSend as_http_send() {
        return [this](const neuroforge::HttpRequest &r) { return send(r); };
    }

    // One exchange. Returns the response for ANY HTTP status (3xx included); throws TransportError
    // for connection, TLS, policy, size or deadline failures.
    neuroforge::HttpResponse send(const neuroforge::HttpRequest &req) const { return send_impl(req, nullptr, nullptr); }

    // Result of one gRPC call: code 0 with the single response message, or a gRPC status code
    // (https://grpc.github.io/grpc/core/md_doc_statuscodes.html) with a message. The message never
    // contains the authorization value, a request body or a URL query.
    struct GrpcResult {
        int code = 0;
        std::string bytes;
    };

    // One gRPC call (unary or client-streaming: `messages` are sent in order in one HTTP/2 request)
    // under exactly the same policy as send(): TLS 1.3 only, revocation on, no redirects/proxy,
    // whole-call deadline, size caps. HTTP/2 is REQUIRED (the call fails if the server does not
    // negotiate it); grpc-status/grpc-message come from the trailers (or headers, "trailers-only").
    // Transport failures map to UNAVAILABLE (14), the deadline to DEADLINE_EXCEEDED (4).
    GrpcResult grpc_call(const std::string &origin, const std::string &method_path, const std::vector<std::string> &messages,
                         const std::string &authorization, double timeout_s) const {
        return grpc_impl(origin, method_path, messages, authorization, timeout_s, nullptr, nullptr);
    }

private:
    friend struct detail::TestAccess;
    // Test builds only (the unshipped test-only header): called after the request handle exists and
    // before it is sent; returns false to reject. Release code always passes nullptr.
    using BeforeSend = bool (*)(void *ctx, detail::RequestState &st);

    // HTTP/2 mode for gRPC: require h2, cap the body, collect the grpc-* trailers.
    struct Http2Mode {
        size_t max_body = 1u << 20;  // NF_MAX_REPLY_BYTES of ABI 1.2.1: ingest replies are tiny
        std::string grpc_status, grpc_message;
        bool has_status = false;
    };

    static constexpr int kGrpcDeadlineExceeded = 4, kGrpcInternal = 13, kGrpcUnavailable = 14, kGrpcUnknown = 2;

    GrpcResult grpc_impl(const std::string &origin, const std::string &method_path, const std::vector<std::string> &messages,
                         const std::string &authorization, double timeout_s, BeforeSend before_send, void *ctx) const {
        if (origin.rfind("https://", 0) != 0) return {kGrpcUnavailable, "winhttp: gRPC requires an https origin"};
        if (method_path.empty() || method_path[0] != '/') return {kGrpcInternal, "winhttp: malformed gRPC method path"};
        neuroforge::HttpRequest req;
        req.method = "POST";
        req.url = origin + method_path;
        req.timeout_s = timeout_s > 0 ? timeout_s : 30.0;
        const long long ms = static_cast<long long>(req.timeout_s * 1000.0 + 0.999);
        req.headers = {{"content-type", "application/grpc"},
                       {"te", "trailers"},
                       {"grpc-timeout", std::to_string(ms > 99999999 ? 99999999 : ms) + "m"},
                       {"authorization", authorization}};
        for (const std::string &m : messages) {  // length-prefixed messages, uncompressed
            if (m.size() > 0xffffffffu) return {kGrpcInternal, "winhttp: gRPC message too large"};
            const uint32_t n = static_cast<uint32_t>(m.size());
            req.body.push_back('\0');
            for (int s = 24; s >= 0; s -= 8) req.body.push_back(static_cast<char>((n >> s) & 0xff));
            req.body += m;
        }
        Http2Mode mode;
        neuroforge::HttpResponse r;
        try {
            r = send_impl(req, before_send, ctx, &mode);
        } catch (const TransportError &e) {
            const bool deadline = std::string(e.what()).find("deadline") != std::string::npos;
            return {deadline ? kGrpcDeadlineExceeded : kGrpcUnavailable, e.what()};
        }
        if (r.status != 200) {  // gRPC's HTTP-to-status mapping
            const int code = r.status == 401 ? 16 : r.status == 403 ? 7 : r.status == 404 ? 12 : r.status == 400 ? kGrpcInternal
                           : (r.status == 429 || r.status == 502 || r.status == 503 || r.status == 504) ? kGrpcUnavailable
                                                                                                     : kGrpcUnknown;
            return {code, "winhttp: gRPC call answered with HTTP " + std::to_string(r.status)};
        }
        std::string ctype;
        for (const auto &h : r.headers) {
            std::string name = h.first;
            for (char &ch : name) ch = static_cast<char>(tolower(static_cast<unsigned char>(ch)));
            if (name == "content-type") ctype = h.second;
            if (!mode.has_status && name == "grpc-status") {  // trailers-only response
                mode.grpc_status = h.second;
                mode.has_status = true;
            } else if (name == "grpc-message" && mode.grpc_message.empty()) {
                mode.grpc_message = h.second;
            }
        }
        if (ctype.rfind("application/grpc", 0) != 0) return {kGrpcInternal, "winhttp: not a gRPC response"};
        if (!mode.has_status) return {kGrpcInternal, "winhttp: gRPC response without grpc-status"};
        int code = 0;
        for (char ch : mode.grpc_status) {
            if (ch < '0' || ch > '9' || code > 99) return {kGrpcInternal, "winhttp: malformed grpc-status"};
            code = code * 10 + (ch - '0');
        }
        if (code != 0) return {code, percent_decode(mode.grpc_message)};
        // Exactly one uncompressed length-prefixed message.
        const std::string &b = r.body;
        if (b.size() < 5 || b[0] != '\0') return {kGrpcInternal, "winhttp: malformed or compressed gRPC response"};
        uint32_t n = 0;
        for (int i = 1; i <= 4; i++) n = (n << 8) | static_cast<unsigned char>(b[static_cast<size_t>(i)]);
        if (b.size() != 5u + n) return {kGrpcInternal, "winhttp: gRPC response is not exactly one message"};
        return {0, b.substr(5)};
    }

    // grpc-message is server-controlled and ends up in error text (and consumers' logs): after
    // percent-decoding, every C0 control character and DEL becomes a space, so a hostile or buggy
    // server cannot inject lines (nfb-security hardening, case 10 review). Capped at 1024 bytes.
    static std::string percent_decode(const std::string &s) {
        std::string out;
        for (size_t i = 0; i < s.size() && out.size() < 1024; i++) {
            char ch = s[i];
            if (ch == '%' && i + 2 < s.size() && isxdigit(static_cast<unsigned char>(s[i + 1])) &&
                isxdigit(static_cast<unsigned char>(s[i + 2]))) {
                ch = static_cast<char>(std::stoi(s.substr(i + 1, 2), nullptr, 16));
                i += 2;
            }
            const unsigned char u = static_cast<unsigned char>(ch);
            out += (u < 0x20 || u == 0x7f) ? ' ' : ch;
        }
        return out;
    }

    neuroforge::HttpResponse send_impl(const neuroforge::HttpRequest &req, BeforeSend before_send, void *ctx,
                                       Http2Mode *h2 = nullptr) const {
        using clock = std::chrono::steady_clock;
        const auto deadline = clock::now() + std::chrono::duration_cast<clock::duration>(
                                                 std::chrono::duration<double>(req.timeout_s > 0 ? req.timeout_s : 30.0));
        auto remaining_ms = [&]() -> int {
            auto left = std::chrono::duration_cast<std::chrono::milliseconds>(deadline - clock::now()).count();
            if (left <= 0) throw TransportError("request deadline (timeout_s) exceeded");
            return static_cast<int>(left > 0x7fffffff ? 0x7fffffff : left);
        };

        // ---- URL and policy checks (before any network activity)
        std::wstring wurl = detail::widen(req.url);
        URL_COMPONENTS uc{};
        uc.dwStructSize = sizeof(uc);
        wchar_t host[256] = {}, path[2048] = {}, extra[2048] = {};
        uc.lpszHostName = host;
        uc.dwHostNameLength = static_cast<DWORD>(std::size(host));
        uc.lpszUrlPath = path;
        uc.dwUrlPathLength = static_cast<DWORD>(std::size(path));
        uc.lpszExtraInfo = extra;
        uc.dwExtraInfoLength = static_cast<DWORD>(std::size(extra));
        if (!WinHttpCrackUrl(wurl.c_str(), static_cast<DWORD>(wurl.size()), 0, &uc)) throw TransportError("malformed URL");
        const bool https = uc.nScheme == INTERNET_SCHEME_HTTPS;
        if (!https && !(uc.nScheme == INTERNET_SCHEME_HTTP && detail::is_loopback(host)))
            throw TransportError("plain http is only allowed to a loopback host");
        if (uc.dwUserNameLength || uc.dwPasswordLength) throw TransportError("credentials in the URL are not allowed");
        for (const auto &h : req.headers)
            if (detail::has_crlf(h.first) || detail::has_crlf(h.second)) throw TransportError("CR/LF in a request header");

        // ---- connection and request handles
        detail::Handle connect(WinHttpConnect(session_.get(), host, uc.nPort, 0));
        if (!connect) throw TransportError("WinHttpConnect", GetLastError());
        std::wstring object = std::wstring(path) + extra;
        std::wstring method = detail::widen(req.method);
        detail::RequestState st;
        st.request = WinHttpOpenRequest(connect.get(), method.c_str(), object.c_str(), nullptr, WINHTTP_NO_REFERER,
                                        WINHTTP_DEFAULT_ACCEPT_TYPES, https ? WINHTTP_FLAG_SECURE : 0);
        if (!st.request) throw TransportError("WinHttpOpenRequest", GetLastError());
        // Closes the handle on every exit path unless the watchdog or the test hook already did.
        struct Closer {
            detail::RequestState &st;
            ~Closer() { st.close_once(); }
        } closer{st};
        HINTERNET hr = st.request;

        DWORD disable = WINHTTP_DISABLE_COOKIES | WINHTTP_DISABLE_REDIRECTS | WINHTTP_DISABLE_AUTHENTICATION;
        if (!WinHttpSetOption(hr, WINHTTP_OPTION_DISABLE_FEATURE, &disable, sizeof(disable)))
            throw TransportError("WinHttpSetOption(DISABLE_FEATURE)", GetLastError());
        DWORD policy = WINHTTP_OPTION_REDIRECT_POLICY_NEVER;
        if (!WinHttpSetOption(hr, WINHTTP_OPTION_REDIRECT_POLICY, &policy, sizeof(policy)))
            throw TransportError("WinHttpSetOption(REDIRECT_POLICY)", GetLastError());
        // Revocation checking ON (nfb-security, review of b976337). A revoked certificate is a hard
        // failure, and so is "revocation unknown/offline": the shipped path never sets any of
        // WinHTTP's ignore-revocation-failure or ignore-offline-revocation options (E2 guard T3 checks).
        // Our API and ingest edge staple OCSP, so Schannel rarely has to reach the CA (SEC-030).
        DWORD enable = WINHTTP_ENABLE_SSL_REVOCATION;
        if (https && !WinHttpSetOption(hr, WINHTTP_OPTION_ENABLE_FEATURE, &enable, sizeof(enable)))
            throw TransportError("WinHttpSetOption(ENABLE_SSL_REVOCATION)", GetLastError());
        DWORD maxhdr = static_cast<DWORD>(opt_.max_header_bytes);
        if (!WinHttpSetOption(hr, WINHTTP_OPTION_MAX_RESPONSE_HEADER_SIZE, &maxhdr, sizeof(maxhdr)))
            throw TransportError("WinHttpSetOption(MAX_RESPONSE_HEADER_SIZE)", GetLastError());
        if (h2) {
            if (!https) throw TransportError("gRPC requires https (HTTP/2 over TLS)");
            DWORD proto = WINHTTP_PROTOCOL_FLAG_HTTP2;
            if (!WinHttpSetOption(hr, WINHTTP_OPTION_ENABLE_HTTP_PROTOCOL, &proto, sizeof(proto)))
                throw TransportError("WinHttpSetOption(ENABLE_HTTP_PROTOCOL)", GetLastError());
        }
        if (before_send && !before_send(ctx, st)) throw TransportError("request rejected before sending");

        // The watchdog is destroyed (timer cancelled, callback drained) before `closer` runs.
        detail::Watchdog watchdog(st, remaining_ms());
        auto fail = [&](const char *step) -> TransportError {
            DWORD err = GetLastError();
            if (st.deadline_fired) return TransportError("request deadline (timeout_s) exceeded");
            return TransportError(step, err);
        };

        // ---- headers + body; each phase also gets only the time that is left
        std::wstring headers;
        for (const auto &h : req.headers) headers += detail::widen(h.first) + L": " + detail::widen(h.second) + L"\r\n";
        set_timeouts(hr, remaining_ms());
        if (req.body.size() > 0xffffffffu) throw TransportError("request body too large");
        const DWORD blen = static_cast<DWORD>(req.body.size());
        if (!WinHttpSendRequest(hr, headers.empty() ? WINHTTP_NO_ADDITIONAL_HEADERS : headers.c_str(),
                                headers.empty() ? 0 : static_cast<DWORD>(-1L),
                                blen ? const_cast<char *>(req.body.data()) : WINHTTP_NO_REQUEST_DATA, blen, blen, 0)) {
            if (st.closed && !st.deadline_fired) throw TransportError("request rejected before sending");
            throw fail("WinHttpSendRequest");
        }
        if (st.closed && !st.deadline_fired) throw TransportError("request rejected before sending");
        set_timeouts(hr, remaining_ms());
        if (!WinHttpReceiveResponse(hr, nullptr)) throw fail("WinHttpReceiveResponse");
        if (h2) {
            DWORD used = 0, ulen = sizeof(used);
            if (!WinHttpQueryOption(hr, WINHTTP_OPTION_HTTP_PROTOCOL_USED, &used, &ulen))
                throw fail("WinHttpQueryOption(HTTP_PROTOCOL_USED)");
            if (!(used & WINHTTP_PROTOCOL_FLAG_HTTP2)) throw TransportError("the server did not negotiate HTTP/2 (required for gRPC)");
        }

        // ---- status + headers (size-checked before allocation)
        neuroforge::HttpResponse out;
        DWORD status = 0, slen = sizeof(status);
        if (!WinHttpQueryHeaders(hr, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER, WINHTTP_HEADER_NAME_BY_INDEX,
                                 &status, &slen, WINHTTP_NO_HEADER_INDEX))
            throw fail("WinHttpQueryHeaders(STATUS_CODE)");
        out.status = static_cast<uint16_t>(status);
        DWORD hbytes = 0;
        WinHttpQueryHeaders(hr, WINHTTP_QUERY_RAW_HEADERS_CRLF, WINHTTP_HEADER_NAME_BY_INDEX, WINHTTP_NO_OUTPUT_BUFFER,
                            &hbytes, WINHTTP_NO_HEADER_INDEX);
        if (GetLastError() != ERROR_INSUFFICIENT_BUFFER) throw fail("WinHttpQueryHeaders(size)");
        if (hbytes / sizeof(wchar_t) > opt_.max_header_bytes) throw TransportError("response headers exceed the size cap");
        std::wstring raw(hbytes / sizeof(wchar_t), L'\0');
        if (!WinHttpQueryHeaders(hr, WINHTTP_QUERY_RAW_HEADERS_CRLF, WINHTTP_HEADER_NAME_BY_INDEX, raw.data(), &hbytes,
                                 WINHTTP_NO_HEADER_INDEX))
            throw fail("WinHttpQueryHeaders(RAW)");
        raw.resize(hbytes / sizeof(wchar_t));
        parse_headers(raw, out.headers);

        // ---- body, capped, read under the deadline
        const size_t max_body = h2 ? h2->max_body : opt_.max_response_bytes;
        for (;;) {
            set_timeouts(hr, remaining_ms());
            DWORD avail = 0;
            if (!WinHttpQueryDataAvailable(hr, &avail)) throw fail("WinHttpQueryDataAvailable");
            if (avail == 0) break;
            if (out.body.size() + avail > max_body) throw TransportError("response body exceeds the size cap");
            size_t at = out.body.size();
            out.body.resize(at + avail);
            DWORD got = 0;
            if (!WinHttpReadData(hr, &out.body[at], avail, &got)) throw fail("WinHttpReadData");
            out.body.resize(at + got);
        }
        if (h2) {  // trailers are readable once the body is fully read
            h2->has_status = query_trailer(hr, L"grpc-status", h2->grpc_status, opt_.max_header_bytes);
            query_trailer(hr, L"grpc-message", h2->grpc_message, opt_.max_header_bytes);
        }
        if (st.deadline_fired) throw TransportError("request deadline (timeout_s) exceeded");
        return out;
    }

    // One response trailer by name; false if absent. Size-checked before allocation.
    static bool query_trailer(HINTERNET h, const wchar_t *name, std::string &value, size_t max_bytes) {
        DWORD bytes = 0;
        const DWORD level = WINHTTP_QUERY_CUSTOM | WINHTTP_QUERY_FLAG_TRAILERS;
        if (WinHttpQueryHeaders(h, level, name, WINHTTP_NO_OUTPUT_BUFFER, &bytes, WINHTTP_NO_HEADER_INDEX)) return false;
        const DWORD err = GetLastError();
        if (err == ERROR_WINHTTP_HEADER_NOT_FOUND) return false;
        if (err != ERROR_INSUFFICIENT_BUFFER) throw TransportError("WinHttpQueryHeaders(trailer size)", err);
        if (bytes / sizeof(wchar_t) > max_bytes) throw TransportError("response trailers exceed the size cap");
        std::wstring w(bytes / sizeof(wchar_t), L'\0');
        if (!WinHttpQueryHeaders(h, level, name, w.data(), &bytes, WINHTTP_NO_HEADER_INDEX))
            throw TransportError("WinHttpQueryHeaders(trailer)", GetLastError());
        w.resize(bytes / sizeof(wchar_t));
        value = detail::narrow(w.data(), w.size());
        return true;
    }

    // WinHttpSetTimeouts covers resolve/connect/send/receive, but waiting for the response headers
    // has its own timeout (WINHTTP_OPTION_RECEIVE_RESPONSE_TIMEOUT, default 90 s): set both.
    static void set_timeouts(HINTERNET h, int ms) {
        if (!WinHttpSetTimeouts(h, ms, ms, ms, ms)) throw TransportError("WinHttpSetTimeouts", GetLastError());
        DWORD rr = static_cast<DWORD>(ms);
        if (!WinHttpSetOption(h, WINHTTP_OPTION_RECEIVE_RESPONSE_TIMEOUT, &rr, sizeof(rr)))
            throw TransportError("WinHttpSetOption(RECEIVE_RESPONSE_TIMEOUT)", GetLastError());
    }

    static void parse_headers(const std::wstring &raw, std::vector<std::pair<std::string, std::string>> &out) {
        size_t pos = raw.find(L"\r\n");  // skip the status line
        while (pos != std::wstring::npos) {
            size_t start = pos + 2, end = raw.find(L"\r\n", start);
            if (end == std::wstring::npos || end == start) break;
            size_t colon = raw.find(L':', start);
            if (colon != std::wstring::npos && colon < end) {
                size_t v = colon + 1;
                while (v < end && raw[v] == L' ') v++;
                out.emplace_back(detail::narrow(raw.data() + start, colon - start), detail::narrow(raw.data() + v, end - v));
            }
            pos = end;
        }
    }

    WinHttpOptions opt_;
    detail::Handle session_;
};

// The ingest transport for neuroforge::Sender (nf_ingest_transport, CABI-M1 case 10): the three
// IngestService calls as gRPC over this WinHTTP transport, carrying the NFDevice token in the
// authorization metadata. `origin` is the ingest edge, e.g. "https://ingest.example:443" (https only).
// The transport must outlive this object.
class WinHttpIngestTransport : public neuroforge::IngestTransport {
public:
    WinHttpIngestTransport(const WinHttpTransport &t, std::string origin) : t_(t), origin_(std::move(origin)) {
        if (origin_.rfind("https://", 0) != 0) throw TransportError("the ingest origin must be https");
        while (!origin_.empty() && origin_.back() == '/') origin_.pop_back();
    }

    neuroforge::RpcResult get_stream_state(const std::string &request, const std::string &authorization, double timeout_s) override {
        return call("/neuroforge.ingest.v1.IngestService/GetStreamState", {request}, authorization, timeout_s);
    }
    neuroforge::RpcResult stream_chunks(const std::vector<std::string> &chunks, const std::string &authorization,
                                        double timeout_s) override {
        return call("/neuroforge.ingest.v1.IngestService/StreamChunks", chunks, authorization, timeout_s);
    }
    neuroforge::RpcResult finish_stream(const std::string &request, const std::string &authorization, double timeout_s) override {
        return call("/neuroforge.ingest.v1.IngestService/FinishStream", {request}, authorization, timeout_s);
    }

protected:
    virtual WinHttpTransport::GrpcResult invoke(const std::string &method_path, const std::vector<std::string> &messages,
                                                const std::string &authorization, double timeout_s) {
        return t_.grpc_call(origin_, method_path, messages, authorization, timeout_s);
    }
    const WinHttpTransport &transport() const { return t_; }
    const std::string &origin() const { return origin_; }

private:
    neuroforge::RpcResult call(const char *path, const std::vector<std::string> &messages, const std::string &authorization,
                               double timeout_s) {
        WinHttpTransport::GrpcResult r = invoke(path, messages, authorization, timeout_s);
        return {r.code, std::move(r.bytes)};
    }
    const WinHttpTransport &t_;
    std::string origin_;
};

}  // namespace transport
}  // namespace nf

#endif  // NF_WINHTTP_TRANSPORT_HPP

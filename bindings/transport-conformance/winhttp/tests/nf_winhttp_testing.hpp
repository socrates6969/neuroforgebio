// nf_winhttp_testing.hpp: TEST-ONLY trust hook for the WinHTTP transport. NOT SHIPPED: it lives under
// tests/ and no SDK package includes it (nfb-security review of cb0fd54, condition 1).
//
// Trusts exactly one test CA (PEM) instead of the Windows store, for the local conformance server:
//  - WinHTTP is told to accept an unknown ROOT only (SECURITY_FLAG_IGNORE_UNKNOWN_CA); it still
//    enforces the hostname and the validity dates. Revocation is enabled by the shipped send path;
//    because Windows cannot complete revocation under an untrusted root, this hook by default
//    tolerates "revocation unknown/offline" (see Revocation below). Revoked-vs-good is CI-only;
//  - in the WINHTTP_CALLBACK_STATUS_SENDING_REQUEST callback (after the TLS handshake, before any
//    request byte, and so before the Authorization header, is sent) the server chain is verified
//    against the pinned CA alone (exclusive-root chain engine + CERT_CHAIN_POLICY_SSL); on failure the
//    request handle is closed there, which aborts the send.
#ifndef NF_WINHTTP_TESTING_HPP
#define NF_WINHTTP_TESTING_HPP

#include <fstream>
#include <iterator>
#include <string>
#include <vector>

#include "nf_winhttp_transport.hpp"

namespace nf {
namespace transport {

namespace testing {

// How the TEST path treats revocation (the shipped path always enforces it):
//  - Enforce: leave WinHTTP's revocation result alone. With this untrusted test root Windows cannot
//    complete revocation, so every request fails with CERT_REV_FAILED: used for the one local
//    check that proves revocation is requested and fails closed.
//  - TolerateUnknownForTesting: set WINHTTP_OPTION_IGNORE_CERT_REVOCATION_OFFLINE on the request so
//    the rest of the suite can run under the untrusted test root. In this mode the hook's OWN pin
//    check does the revocation work (chain against the pinned root with
//    CERT_CHAIN_REVOCATION_CHECK_CHAIN_EXCLUDE_ROOT, CRL fetch allowed) and refuses revoked, unknown
//    and offline alike. That tests the fixtures and the test path; WinHTTP's OWN revoked-vs-good
//    decision under a trusted root is CI-only (ephemeral runner).
enum class Revocation { Enforce, TolerateUnknownForTesting };

class PinnedCa {
public:
    explicit PinnedCa(const std::string &pem_path, Revocation rev = Revocation::TolerateUnknownForTesting) : rev_(rev) {
        std::ifstream in(pem_path, std::ios::binary);
        std::string pem((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
        if (pem.empty()) throw TransportError("test CA: cannot read PEM file");
        store_ = CertOpenStore(CERT_STORE_PROV_MEMORY, 0, 0, 0, nullptr);
        if (!store_) throw TransportError("CertOpenStore", GetLastError());
        // A bundle of one or more PEM certificates (the conformance server uses two test CAs).
        const std::string end = "-----END CERTIFICATE-----";
        size_t at = 0, added = 0;
        for (size_t e; (e = pem.find(end, at)) != std::string::npos; at = e + end.size()) {
            const std::string one = pem.substr(at, e + end.size() - at);
            DWORD der_len = 0;
            if (!CryptStringToBinaryA(one.data(), static_cast<DWORD>(one.size()), CRYPT_STRING_BASE64HEADER, nullptr, &der_len,
                                      nullptr, nullptr))
                continue;
            std::vector<BYTE> der(der_len);
            CryptStringToBinaryA(one.data(), static_cast<DWORD>(one.size()), CRYPT_STRING_BASE64HEADER, der.data(), &der_len,
                                 nullptr, nullptr);
            if (!CertAddEncodedCertificateToStore(store_, X509_ASN_ENCODING, der.data(), der_len, CERT_STORE_ADD_ALWAYS, nullptr)) {
                CertCloseStore(store_, 0);
                throw TransportError("test CA: CertAddEncodedCertificateToStore", GetLastError());
            }
            added++;
        }
        if (added == 0) {
            CertCloseStore(store_, 0);
            throw TransportError("test CA: no PEM certificate in the file");
        }
    }
    PinnedCa(const PinnedCa &) = delete;
    PinnedCa &operator=(const PinnedCa &) = delete;
    ~PinnedCa() { CertCloseStore(store_, 0); }

    // Whether the server certificate of request handle `h` chains to the pinned CA alone.
    bool verifies(HINTERNET h) const {
        PCCERT_CONTEXT cert = nullptr;
        DWORD len = sizeof(cert);
        if (!WinHttpQueryOption(h, WINHTTP_OPTION_SERVER_CERT_CONTEXT, &cert, &len) || !cert) return false;
        CERT_CHAIN_ENGINE_CONFIG cfg{};
        cfg.cbSize = sizeof(cfg);
        cfg.hExclusiveRoot = store_;
        HCERTCHAINENGINE engine = nullptr;
        bool ok = false;
        if (CertCreateCertificateChainEngine(&cfg, &engine)) {
            CERT_CHAIN_PARA para{};
            para.cbSize = sizeof(para);
            PCCERT_CHAIN_CONTEXT chain = nullptr;
            // Revocation over the whole chain except the (pinned) root, with URL retrieval allowed
            // (nfb-security revocation ruling, condition 3).
            if (CertGetCertificateChain(engine, cert, nullptr, cert->hCertStore, &para,
                                        CERT_CHAIN_REVOCATION_CHECK_CHAIN_EXCLUDE_ROOT, nullptr, &chain)) {
                const DWORD err = chain->TrustStatus.dwErrorStatus;
                last_chain_error() = err;
                // Fail closed in the test path too: revoked, unknown and offline all refuse.
                const bool revocation_bad =
                    (err & (CERT_TRUST_IS_REVOKED | CERT_TRUST_REVOCATION_STATUS_UNKNOWN | CERT_TRUST_IS_OFFLINE_REVOCATION)) != 0;
                CERT_CHAIN_POLICY_PARA policy{};
                policy.cbSize = sizeof(policy);
                CERT_CHAIN_POLICY_STATUS st{};
                st.cbSize = sizeof(st);
                ok = !revocation_bad && CertVerifyCertificateChainPolicy(CERT_CHAIN_POLICY_SSL, chain, &policy, &st) &&
                     st.dwError == 0 && err == CERT_TRUST_NO_ERROR;
                CertFreeCertificateChain(chain);
            }
            CertFreeCertificateChainEngine(engine);
        }
        CertFreeCertificateContext(cert);
        return ok;
    }

    Revocation revocation() const { return rev_; }

    // TrustStatus.dwErrorStatus of the last pinned chain check on this thread (diagnostics).
    static DWORD &last_chain_error() {
        thread_local DWORD e = 0;
        return e;
    }

private:
    HCERTSTORE store_ = nullptr;
    Revocation rev_;
};

}  // namespace testing

namespace detail {

// The one definition of TestAccess (declared, not defined, in the shipped header).
struct TestAccess {
    struct Ctx {
        const testing::PinnedCa *pin;
        RequestState *st;
        DWORD secure_failure_flags = 0;  // WINHTTP_CALLBACK_STATUS_FLAG_* from a SECURE_FAILURE callback
    };

    // Flags of the last secure failure on this thread's pinned request (diagnostics for tests).
    static DWORD &last_secure_failure() {
        thread_local DWORD flags = 0;
        return flags;
    }

    static neuroforge::HttpResponse send(const WinHttpTransport &t, const neuroforge::HttpRequest &req,
                                         const testing::PinnedCa &pin) {
        Ctx ctx{&pin, nullptr};
        last_secure_failure() = 0;
        struct Save {
            Ctx &c;
            ~Save() { last_secure_failure() = c.secure_failure_flags; }
        } save{ctx};
        return t.send_impl(req, &TestAccess::arm, &ctx);
    }

    static WinHttpTransport::GrpcResult grpc(const WinHttpTransport &t, const std::string &origin, const std::string &path,
                                             const std::vector<std::string> &messages, const std::string &authorization,
                                             double timeout_s, const testing::PinnedCa &pin) {
        Ctx ctx{&pin, nullptr};
        last_secure_failure() = 0;
        struct Save {
            Ctx &c;
            ~Save() { last_secure_failure() = c.secure_failure_flags; }
        } save{ctx};
        return t.grpc_impl(origin, path, messages, authorization, timeout_s, &TestAccess::arm, &ctx);
    }

private:
    // Runs after the request handle exists, before WinHttpSendRequest.
    static bool arm(void *vctx, RequestState &st) {
        auto *ctx = static_cast<Ctx *>(vctx);
        ctx->st = &st;
        if (!(st.request && ctx->pin)) return false;
        DWORD flags = SECURITY_FLAG_IGNORE_UNKNOWN_CA;  // root only; hostname and dates stay enforced
        if (!WinHttpSetOption(st.request, WINHTTP_OPTION_SECURITY_FLAGS, &flags, sizeof(flags))) return false;
        if (ctx->pin->revocation() == testing::Revocation::TolerateUnknownForTesting) {
            BOOL tolerate = TRUE;
            if (!WinHttpSetOption(st.request, WINHTTP_OPTION_IGNORE_CERT_REVOCATION_OFFLINE, &tolerate, sizeof(tolerate)))
                return false;
        }
        DWORD_PTR value = reinterpret_cast<DWORD_PTR>(ctx);
        if (!WinHttpSetOption(st.request, WINHTTP_OPTION_CONTEXT_VALUE, &value, sizeof(value))) return false;
        return WinHttpSetStatusCallback(st.request, &TestAccess::on_status,
                                        WINHTTP_CALLBACK_FLAG_SEND_REQUEST | WINHTTP_CALLBACK_FLAG_SECURE_FAILURE,
                                        0) != WINHTTP_INVALID_STATUS_CALLBACK;
    }

    static void CALLBACK on_status(HINTERNET h, DWORD_PTR context, DWORD status, LPVOID info, DWORD info_len) {
        if (!context) return;
        auto *ctx = reinterpret_cast<Ctx *>(context);
        if (status == WINHTTP_CALLBACK_STATUS_SECURE_FAILURE) {
            if (info && info_len >= sizeof(DWORD)) ctx->secure_failure_flags |= *static_cast<DWORD *>(info);
            return;
        }
        if (status != WINHTTP_CALLBACK_STATUS_SENDING_REQUEST) return;
        if (!ctx->pin->verifies(h)) ctx->st->close_once();  // aborts the send before any byte leaves
    }
};

}  // namespace detail

namespace testing {

// HttpSend for neuroforge::ApiClient that trusts only `pin` (which must outlive the client).
inline neuroforge::HttpSend pinned_http_send(const WinHttpTransport &t, const PinnedCa &pin) {
    return [&t, &pin](const neuroforge::HttpRequest &r) { return detail::TestAccess::send(t, r, pin); };
}

// The shipped WinHttpIngestTransport, but trusting only `pin` (test CA).
class PinnedIngestTransport : public WinHttpIngestTransport {
public:
    PinnedIngestTransport(const WinHttpTransport &t, const PinnedCa &pin, std::string origin)
        : WinHttpIngestTransport(t, std::move(origin)), pin_(pin) {}

protected:
    WinHttpTransport::GrpcResult invoke(const std::string &method_path, const std::vector<std::string> &messages,
                                        const std::string &authorization, double timeout_s) override {
        return detail::TestAccess::grpc(transport(), origin(), method_path, messages, authorization, timeout_s, pin_);
    }

private:
    const PinnedCa &pin_;
};

}  // namespace testing
}  // namespace transport
}  // namespace nf

#endif  // NF_WINHTTP_TESTING_HPP

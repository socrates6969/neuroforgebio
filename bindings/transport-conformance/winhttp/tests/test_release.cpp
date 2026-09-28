// Release-build checks (nfb-security case 9 and review condition 1): this translation unit sees only
// the SHIPPED header, exactly as a customer build does.
//  - compile time: WinHttpTransport has no public way to trust a custom CA, and the test-access type
//    is declared but never defined (the unshipped tests/nf_winhttp_testing.hpp is the only definition);
//    `#define NF_TRANSPORT_TESTING` against the shipped header is a hard #error (checked by
//    run-msvc.cmd, which expects that compile to FAIL);
//  - run time: the release transport trusts only the Windows store, so the local test-CA server is
//    refused and no request reaches it.
#include "nf_winhttp_transport.hpp"

#include <type_traits>

#include "conformance_common.hpp"

template <class T, class = void>
struct has_testing_pin : std::false_type {};
template <class T>
struct has_testing_pin<T, std::void_t<decltype(&T::testing_pin_ca_pem)>> : std::true_type {};

template <class T, class = void>
struct is_complete : std::false_type {};
template <class T>
struct is_complete<T, std::void_t<decltype(sizeof(T))>> : std::true_type {};

static_assert(!has_testing_pin<nf::transport::WinHttpTransport>::value, "no public test-CA hook in the shipped header");
static_assert(!is_complete<nf::transport::detail::TestAccess>::value,
              "the test-access type must not be defined by the shipped header (nfb-security condition 1)");

int main() {
    conf::Config c = conf::load();
    CHECK(!has_testing_pin<nf::transport::WinHttpTransport>::value, "9 shipped header: no public test-CA hook");
    CHECK(!is_complete<nf::transport::detail::TestAccess>::value, "9 shipped header: test access undefined");

    nf::transport::WinHttpTransport t;
    const std::string secret = "NFTEST-RELEASE-SECRET";
    bool refused = false;
    std::string text;
    try {
        neuroforge::ApiClient client(c.origin("good"), t.as_http_send(), [&](bool) { return secret; }, 5.0, 1, "nf-conformance");
        client.request("GET", "/release-probe");
    } catch (const neuroforge::Error &e) {
        refused = e.status() == NF_ERR_TRANSPORT;
        text = std::string(e.what()) + e.message() + e.detail();
    }
    CHECK(refused, "9 release transport refuses the test-CA server (Windows trust store only)");
    CHECK(conf::events_for(c, "good", "/release-probe") == 0, "9 no request reached the untrusted server");
    CHECK(text.find(secret) == std::string::npos, "11 no token in the release error text");
    return conf::finish("test_release");
}

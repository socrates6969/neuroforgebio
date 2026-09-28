// Shared helpers for the WinHTTP conformance tests: reading conformance.json (written by
// run_conformance.py) and the server's event log, and a tiny CHECK framework.
#ifndef NF_CONFORMANCE_COMMON_HPP
#define NF_CONFORMANCE_COMMON_HPP

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <sstream>
#include <string>

namespace conf {

inline int g_checks = 0, g_failures = 0;

#define CHECK(cond, what)                                                                          \
    do {                                                                                           \
        conf::g_checks++;                                                                          \
        bool ok_ = (cond);                                                                         \
        if (!ok_) conf::g_failures++;                                                              \
        std::printf("%s %s\n", ok_ ? "PASS" : "FAIL", what);                                       \
        std::fflush(stdout);                                                                       \
    } while (0)

inline std::string read_all(const std::string &path) {
    std::ifstream in(path, std::ios::binary);
    return std::string(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
}

// conformance.json is flat enough (json.dumps(indent=2)) to read `"key": value` directly.
inline std::string raw_value(const std::string &json, const std::string &key) {
    std::string pat = "\"" + key + "\":";
    size_t k = json.find(pat);
    if (k == std::string::npos) {
        std::fprintf(stderr, "conformance.json: missing %s\n", key.c_str());
        std::exit(3);
    }
    size_t b = k + pat.size();
    while (json[b] == ' ') b++;
    size_t e = b;
    if (json[b] == '"') {
        e = b + 1;
        std::string out;
        while (json[e] != '"') {
            if (json[e] == '\\') e++;  // Windows paths arrive as \\ escapes
            out += json[e++];
        }
        return out;
    }
    while (e < json.size() && json[e] != ',' && json[e] != '\n' && json[e] != '}') e++;
    return json.substr(b, e - b);
}

struct Config {
    std::string json, host, ca_cert, events;
    int port(const std::string &name) const { return std::atoi(raw_value(json, name).c_str()); }
    std::string origin(const std::string &name) const { return "https://" + host + ":" + std::to_string(port(name)); }
};

inline Config load() {
    const char *p = std::getenv("NF_CONFORMANCE");
    if (!p) {
        std::fprintf(stderr, "NF_CONFORMANCE not set: run under bindings/transport-conformance/run_conformance.py\n");
        std::exit(3);
    }
    Config c;
    c.json = read_all(p);
    c.host = raw_value(c.json, "host");
    c.ca_cert = raw_value(c.json, "ca_cert");
    c.events = raw_value(c.json, "events");
    return c;
}

// Number of logged requests matching listener (and path, if given).
inline int events_for(const Config &c, const std::string &listener, const std::string &path = "") {
    std::istringstream in(read_all(c.events));
    std::string line;
    int n = 0;
    while (std::getline(in, line)) {
        if (line.find("\"listener\": \"" + listener + "\"") == std::string::npos) continue;
        if (!path.empty() && line.find("\"path\": \"" + path + "\"") == std::string::npos) continue;
        n++;
    }
    return n;
}

inline int finish(const char *name) {
    std::printf("%s: %d checks, %d failures\n", name, g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}

}  // namespace conf

#endif  // NF_CONFORMANCE_COMMON_HPP

// Must NOT compile (run-msvc.cmd expects cl to fail): defining NF_TRANSPORT_TESTING against the
// shipped header is an #error, so no consumer can switch a test hook on in a customer build.
#define NF_TRANSPORT_TESTING 1
#include "nf_winhttp_transport.hpp"

int main() { return 0; }

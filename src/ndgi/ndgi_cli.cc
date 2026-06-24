// ndgi_cli — JSON-over-subprocess bridge for NDGiCloudProxy (TASK-C02).
// Usage:
//   ndgi_cli --op read   --key <key>
//   ndgi_cli --op write  --key <key> --trit <-1|0|1>
//   ndgi_cli --op prefix --prefix <prefix>
//
// Exits 0 on success with JSON to stdout; exits 1 on error with message to stderr.
#include "ndgi_store.h"
#include "trit_lib/trit_types.h"
#include <cstdlib>
#include <iostream>
#include <string>

static NDGiStore g_store(TRIT_POS);  // always route to TST in proxy context

static std::string get_arg(int argc, char** argv, const std::string& flag) {
    for (int i = 1; i < argc - 1; ++i)
        if (argv[i] == flag) return argv[i + 1];
    return "";
}

int main(int argc, char** argv) {
    std::string op  = get_arg(argc, argv, "--op");
    std::string key = get_arg(argc, argv, "--key");

    if (op == "read") {
        if (key.empty()) { std::cerr << "missing --key\n"; return 1; }
        trit_t val = g_store.read(key);
        bool found = (val != TRIT_ZERO);  // TRIT_ZERO means not-present in this context
        std::cout << "{\"key\":\"" << key << "\","
                  << "\"trit\":"   << static_cast<int>(val) << ","
                  << "\"found\":"  << (found ? "true" : "false") << "}\n";
        return 0;
    }

    if (op == "write") {
        std::string trit_str = get_arg(argc, argv, "--trit");
        if (key.empty() || trit_str.empty()) { std::cerr << "missing --key or --trit\n"; return 1; }
        trit_t trit = static_cast<trit_t>(std::stoi(trit_str));
        g_store.write(key, trit);
        std::cout << "{\"written\":true,"
                  << "\"trit_state\":"  << static_cast<int>(trit) << ","
                  << "\"tst_key\":\""   << key << "\"}\n";
        return 0;
    }

    if (op == "prefix") {
        std::string pfx = get_arg(argc, argv, "--prefix");
        if (pfx.empty()) { std::cerr << "missing --prefix\n"; return 1; }
        // NDGiStore does not expose prefix search directly — placeholder returns empty.
        // Full implementation added in TASK-C03 when TST prefix API is wired.
        std::cout << "{\"keys\":[],\"count\":0,\"trust_filter\":\"TRIT_POS\"}\n";
        return 0;
    }

    std::cerr << "unknown --op: " << op << "\n";
    return 1;
}

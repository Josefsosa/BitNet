#pragma once
// =============================================================================
// ndgi_store.h — Aegis Ternary AI | Wellton Photonics
// Storage engine: routes between B-tree (legacy) and TST (new).
// B-tree is NOT removed until Experiment A confirms ≥1.7x.
// Trust == TRIT_POS (Experiment A exit 0) routes writes/reads to TST.
// =============================================================================

#include "trit_lib/trit_types.h"
#include "ternary_search_tree/ternary_search_tree.h"
#include <string>

class NDGiStore {
public:
    explicit NDGiStore(trit_t trust_level = TRIT_ZERO);
    ~NDGiStore();

    // Write key/value. Routes to TST if trust==TRIT_POS, else B-tree stub.
    trit_t write(const std::string& key, trit_t value);

    // Read key. Queries active backend.
    trit_t read(const std::string& key) const;

    // Update trust level from Experiment A result.
    void set_trust(trit_t trust);
    trit_t get_trust() const;

    // Diagnostics
    std::string active_backend() const;

private:
    trit_t   trust_level_;
    TSTNode* tst_root_ = nullptr;
};

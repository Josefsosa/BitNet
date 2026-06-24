// =============================================================================
// ndgi_store.cc — Aegis Ternary AI | Wellton Photonics
// B-tree→TST migration router. Trust gate enforces Experiment A result.
// =============================================================================

#include "ndgi_store.h"

NDGiStore::NDGiStore(trit_t trust_level) : trust_level_(trust_level) {}

NDGiStore::~NDGiStore() { tst_free(tst_root_); }

trit_t NDGiStore::write(const std::string& key, trit_t value) {
    if (trust_level_ == TRIT_POS)
        return tst_insert(&tst_root_, key, value);
    return TRIT_NEG;  // B-tree path not yet implemented
}

trit_t NDGiStore::read(const std::string& key) const {
    if (trust_level_ == TRIT_POS)
        return tst_search(tst_root_, key);
    return TRIT_ZERO;  // B-tree path not yet implemented
}

void NDGiStore::set_trust(trit_t trust) { trust_level_ = trust; }
trit_t NDGiStore::get_trust() const { return trust_level_; }

std::string NDGiStore::active_backend() const {
    if (trust_level_ == TRIT_POS)  return "TST";
    if (trust_level_ == TRIT_NEG)  return "BTREE_FAILED";
    return "BTREE_PENDING";
}

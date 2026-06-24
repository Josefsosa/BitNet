#pragma once
// =============================================================================
// ndgi_graph.h — Aegis Ternary AI | Wellton Photonics
// NDGi: Neural Dynamic Graph Intelligence node/edge declarations.
// =============================================================================

#include "trit_lib/trit_types.h"
#include <cstddef>
#include <cstdint>
#include <array>
#include <vector>
#include <unordered_map>

constexpr size_t NDGI_EMBEDDING_DIM = 128;

// ---------------------------------------------------------------------------
// Graph node — a single knowledge vertex
// ---------------------------------------------------------------------------
struct GraphNode {
    uint64_t                            id         = 0;
    trit_t                              trit_state = TRIT_ZERO;
    std::array<float, NDGI_EMBEDDING_DIM> embedding = {};
    uint64_t                            timestamp  = 0;
};

// ---------------------------------------------------------------------------
// Graph edge — a directed weighted connection
// ---------------------------------------------------------------------------
struct GraphEdge {
    uint64_t src       = 0;
    uint64_t dst       = 0;
    trit_t   weight    = TRIT_ZERO;
    uint64_t timestamp = 0;
};

// ---------------------------------------------------------------------------
// NDGi Graph — in-memory dynamic graph
// ---------------------------------------------------------------------------
class NDGiGraph {
public:
    // Add node. Returns TRIT_POS on success, TRIT_NEG if id already exists.
    trit_t add_node(const GraphNode& node);

    // Add edge. Returns TRIT_NEG if src or dst does not exist (orphan guard).
    trit_t add_edge(const GraphEdge& edge);

    // Retrieve node by id. Returns nullptr if not found.
    const GraphNode* get_node(uint64_t id) const;

    // Breadth-first traversal from start_id, max_depth hops.
    std::vector<uint64_t> traverse(uint64_t start_id, int max_depth) const;

    // Diagnostics
    size_t node_count() const;
    size_t edge_count() const;
    bool   has_orphans() const;

private:
    std::unordered_map<uint64_t, GraphNode>             nodes_;
    std::unordered_map<uint64_t, std::vector<GraphEdge>> edges_;
};

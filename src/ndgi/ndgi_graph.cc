// =============================================================================
// ndgi_graph.cc — Aegis Ternary AI | Wellton Photonics
// Phase 1C implementation: node/edge management + BFS traversal.
// =============================================================================

#include "ndgi_graph.h"
#include <queue>
#include <unordered_set>

trit_t NDGiGraph::add_node(const GraphNode& node) {
    if (nodes_.count(node.id)) return TRIT_NEG;  // duplicate id
    nodes_[node.id] = node;
    return TRIT_POS;
}

trit_t NDGiGraph::add_edge(const GraphEdge& edge) {
    if (!get_node(edge.src) || !get_node(edge.dst)) return TRIT_NEG;
    edges_[edge.src].push_back(edge);
    return TRIT_POS;
}

const GraphNode* NDGiGraph::get_node(uint64_t id) const {
    auto it = nodes_.find(id);
    return it == nodes_.end() ? nullptr : &it->second;
}

std::vector<uint64_t> NDGiGraph::traverse(uint64_t start_id, int max_depth) const {
    std::vector<uint64_t> visited;
    if (!get_node(start_id)) return visited;

    std::queue<std::pair<uint64_t, int>> q;
    std::unordered_set<uint64_t>         seen;
    q.push({start_id, 0});
    seen.insert(start_id);

    while (!q.empty()) {
        auto [id, depth] = q.front(); q.pop();
        visited.push_back(id);
        if (depth >= max_depth) continue;
        auto it = edges_.find(id);
        if (it == edges_.end()) continue;
        for (const auto& e : it->second) {
            if (!seen.count(e.dst)) {
                seen.insert(e.dst);
                q.push({e.dst, depth + 1});
            }
        }
    }
    return visited;
}

size_t NDGiGraph::node_count() const { return nodes_.size(); }
size_t NDGiGraph::edge_count()  const { return edges_.size(); }

bool NDGiGraph::has_orphans() const {
    for (const auto& [src, edge_list] : edges_) {
        for (const auto& e : edge_list) {
            if (!get_node(e.src) || !get_node(e.dst)) return true;
        }
    }
    return false;
}

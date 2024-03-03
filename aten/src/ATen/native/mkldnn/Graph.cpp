#include <ATen/native/mkldnn/Graph.h>

#if AT_ONEDNN_GRAPH_ENABLED()

namespace at {
namespace native {
namespace onednn_graph {

// Thread local data-structures are required if multiple thread-pools
// of a PyTorch process would be used for inference.
thread_local std::unordered_map<int64_t, dnnl::graph::partition> partition_map_;
// Compiled partition (fused kernel) cache
// Adopted from
// https://github.com/lamerman/cpp-lru-cache/blob/master/include/lrucache.hpp

thread_local std::list<key_value_pair_t> cache_items_list_;
thread_local std::unordered_map<std::vector<int64_t>, list_iterator_t>
    fused_kernel_cache_map_;
thread_local size_t capacity_ = 75000;

void insert_in_fused_kernel_cache(std::vector<int64_t>& map_key, cp_entry& cp) {
  cache_items_list_.push_front(key_value_pair_t(map_key, std::move(cp)));
  fused_kernel_cache_map_[map_key] = cache_items_list_.begin();
  if (fused_kernel_cache_map_.size() > capacity_) {
    auto last = cache_items_list_.end();
    last--;
    fused_kernel_cache_map_.erase(last->first);
    cache_items_list_.pop_back();
  }
}

void change_pos_in_list(list_iterator_t& kvpair) {
  cache_items_list_.splice(
      cache_items_list_.begin(), cache_items_list_, kvpair);
}

std::unordered_map<std::vector<int64_t>, list_iterator_t>::iterator cache_lookup(
    std::vector<int64_t>& map_key) {
  return fused_kernel_cache_map_.find(map_key);
}

std::unordered_map<std::vector<int64_t>, list_iterator_t>::iterator cache_end() {
  return fused_kernel_cache_map_.end();
}

std::unordered_map<int64_t, dnnl::graph::partition>::iterator
partition_map_lookup(int64_t patternID) {
  return partition_map_.find(patternID);
}

std::unordered_map<int64_t, dnnl::graph::partition>::iterator
partition_map_end() {
  return partition_map_.end();
}

void insert_in_partition_cache(int64_t patternID, partition& p) {
  partition_map_[patternID] = std::move(p);
}

// Compile a partition
compiled_partition compile_partition(
    const partition& partition,
    const std::vector<logical_tensor>& inputs,
    const std::vector<logical_tensor>& outputs) {
  compiled_partition compilation;
  compilation =
      partition.compile(inputs, outputs, onednn_graph::Engine::getEngine());
  return compilation;
}

} // end namespace onednn_graph
} // end namespace native
} // end namespace at

#endif

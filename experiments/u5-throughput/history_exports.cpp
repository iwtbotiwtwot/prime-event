// Append to the unchanged native planner in the isolated GPU prototype.
extern "C" uint64_t history_range_count(Plan* p) {
    uint64_t total=0;for(const auto& ranges:p->ranges)total+=ranges.size();return total;
}
extern "C" void history_ranges(Plan* p,uint64_t* out) {
    for(uint64_t j=0;j<p->ranges.size();j++)for(const auto& range:p->ranges[j]) {
        *out++=p->ids[j];*out++=range.q;*out++=range.lo;*out++=range.hi;
    }
}

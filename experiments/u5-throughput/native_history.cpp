// Actual-event feedback only. Private output masks make parallel OR race-free.
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <vector>
#include <omp.h>
struct Range { uint64_t q,lo,hi; };
struct Plan { uint64_t first,count; std::vector<uint64_t> ids; std::vector<std::vector<Range>> ranges; };
static double timings[5];
extern "C" {
void history_timings(double* out){std::copy(timings,timings+5,out);}
void* history_plan(uint64_t first,uint64_t count,uint64_t records) {
 double started=omp_get_wtime();
 auto p=new Plan{first,count,{},{}};
 std::vector<std::vector<Range>> grouped(records);
 uint64_t end=first+count-1;
 for(uint64_t q=2;q<=end/(count+1);q++) {
  uint64_t lo=std::max(count+1,(first+q-1)/q),hi=std::min(first-1,end/q);
  if(lo>hi)continue;
  for(uint64_t j=(lo-2)/count;j<=(hi-2)/count;j++) {
   if(j>=records){delete p;return nullptr;}
   grouped[j].push_back({q,std::max(lo,2+j*count),std::min(hi,1+(j+1)*count)});
  }
 }
 // Include chunk zero for the small-period returns.
 for(uint64_t j=0;j<records;j++)if(j==0 || !grouped[j].empty()) {
  p->ids.push_back(j);p->ranges.push_back(std::move(grouped[j]));
 }
 timings[0]=omp_get_wtime()-started;return p;
}
uint64_t history_size(Plan* p){return p->ids.size();}
void history_ids(Plan* p,uint64_t* out){std::copy(p->ids.begin(),p->ids.end(),out);}
void history_free(Plan* p){delete p;}
int history_apply(Plan* p,const uint64_t* const* arrays,const uint64_t* sizes,
 const uint64_t* ranks,uint8_t* banks,int threads) {
 if(p->ids.empty() || p->ids[0]!=0 || threads<1)return 1;
 uint64_t first=p->first,count=p->count,end=first+count-1;
 double started=omp_get_wtime();
 // Small returns: disjoint destination intervals, just as in mark_parallel.
 #pragma omp parallel for num_threads(threads) schedule(static)
 for(uint64_t block=0;block<(count+524287)/524288;block++) {
  uint64_t begin=first+block*524288,last=std::min(end,begin+524287);
  for(uint64_t i=0;i<sizes[0];i++) {
   uint64_t period=arrays[0][i];if(period>std::min(count,first-1))break;
   if(period<2)continue;
   uint64_t q=std::max(uint64_t(2),(begin+period-1)/period);
   for(uint64_t n=q*period;n<=last;n+=period)banks[n-first]|=uint8_t(1<<((ranks[0]+i)%2));
  }
 }
 timings[1]=omp_get_wtime()-started;started=omp_get_wtime();
 static thread_local std::vector<uint8_t> scratch;
 scratch.resize(uint64_t(threads)*count);
 uint8_t* scratch_data=scratch.data();
 timings[2]=omp_get_wtime()-started;started=omp_get_wtime();
 #pragma omp parallel num_threads(threads)
 {
  uint8_t* local=scratch_data+uint64_t(omp_get_thread_num())*count;
  int active_threads=omp_get_num_threads();
  std::memset(local,0,count);
  #pragma omp for schedule(dynamic,1)
  for(uint64_t j=0;j<p->ids.size();j++) {
   auto a=arrays[j];
   for(auto r:p->ranges[j]) {
    auto b=std::lower_bound(a,a+sizes[j],r.lo),e=std::upper_bound(b,a+sizes[j],r.hi);
    for(auto v=b;v!=e;++v)local[r.q*(*v)-first]|=uint8_t(1<<((ranks[j]+(v-a))%2));
   }
  }
  #pragma omp single
  {timings[3]=omp_get_wtime()-started;started=omp_get_wtime();}
  #pragma omp for schedule(static)
  for(uint64_t block=0;block<(count+4095)/4096;block++) {
   uint64_t begin=block*4096,last=std::min(count,begin+4096);
   for(int t=0;t<active_threads;t++) {
    const uint8_t* src=scratch_data+uint64_t(t)*count;
    for(uint64_t i=begin;i<last;i++)banks[i]|=src[i];
   }
  }
 }
 timings[4]=omp_get_wtime()-started;return 0;
}
}

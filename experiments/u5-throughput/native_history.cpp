// Actual-event feedback only; each task writes to a private bank mask.
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <vector>
#include <omp.h>
#ifndef DIRECT_RECORDS
#define DIRECT_RECORDS 4
#endif
#ifndef REUSE_BOUNDS
#define REUSE_BOUNDS 1
#endif
struct Range { uint64_t q,lo,hi; };
struct Task { uint64_t record,begin,end; bool direct; };
struct Plan { uint64_t first,count; std::vector<uint64_t> ids; std::vector<std::vector<Range>> ranges; std::vector<Task> tasks; };
static double timings[5];

// Within one record, ascending multipliers give nonincreasing period bounds.
// Search backward from the previous bound with a logarithmic bracket, so both
// dense and sparse arbitrary event histories retain exact lower/upper bounds.
template<bool Upper>
static const uint32_t* retreat(const uint32_t* a,const uint32_t* previous,uint32_t key) {
 auto before=[key](uint32_t value){return Upper?value<=key:value<key;};
 if(previous==a || before(previous[-1]))return previous;
 const uint64_t position=previous-a;uint64_t distance=1;
 while(distance<position && !before(previous[-int64_t(distance)]))
  distance=distance>position/2?position:distance*2;
 const uint32_t* begin=previous-distance;
 return Upper?std::upper_bound(begin,previous,key):std::lower_bound(begin,previous,key);
}
extern "C" {
void history_timings(double* out){std::copy(timings,timings+5,out);}
void* history_plan(uint64_t first,uint64_t count,uint64_t records) {
 double started=omp_get_wtime();
 auto p=new Plan{first,count,{},{},{}};
 std::vector<std::vector<Range>> grouped(records);
 const uint64_t end=first+count-1;
 // The oldest fixed prefix is scanned directly, once per event. Enumerate
 // multiplier ranges only for later chunks; no oracle enters this choice.
 const uint64_t direct_records=DIRECT_RECORDS;
 const uint64_t minimum_period=direct_records?2+direct_records*count:count+1;
 for(uint64_t j=0;j<direct_records && 2+j*count<=end/2;j++)
  if(j>=records){delete p;return nullptr;}
 for(uint64_t q=2;q<=end/minimum_period;q++) {
  uint64_t lo=std::max(minimum_period,(first+q-1)/q),hi=std::min(first-1,end/q);
  if(lo>hi)continue;
  for(uint64_t j=(lo-2)/count;j<=(hi-2)/count;j++) {
   if(j>=records){delete p;return nullptr;}
   grouped[j].push_back({q,std::max(lo,2+j*count),std::min(hi,1+(j+1)*count)});
  }
 }
 for(uint64_t j=0;j<records;j++) {
  // A freshly emitted chunk is read only once its first possible return can
  // reach this window. Preserve the pipeline's early durability dependency.
  const bool direct=j<direct_records && 2+j*count<=end/2;
  if(j==0 || direct || !grouped[j].empty()) {
   if(j>=records){delete p;return nullptr;}
   p->ids.push_back(j);p->ranges.push_back(std::move(grouped[j]));
  }
 }
 for(uint64_t j=0;j<p->ranges.size();j++)
  for(uint64_t begin=0;begin<p->ranges[j].size();begin+=128)
   p->tasks.push_back({j,begin,std::min<uint64_t>(begin+128,p->ranges[j].size()),false});
 timings[0]=omp_get_wtime()-started;return p;
}
uint64_t history_size(Plan* p){return p->ids.size();}
void history_ids(Plan* p,uint64_t* out){std::copy(p->ids.begin(),p->ids.end(),out);}
void history_free(Plan* p){delete p;}
int history_apply_offsets(Plan* p,const uint32_t* const* arrays,const uint64_t* sizes,
 const uint64_t* ranks,uint8_t* banks,int threads) {
 if(p->ids.empty() || p->ids[0]!=0 || threads<1)return 1;
 const uint64_t first=p->first,count=p->count,end=first+count-1;
 double started=omp_get_wtime();
 const uint64_t limit=std::min(count,first-1),cutoff=std::min<uint64_t>(4096,limit),origin0=2;
 const uint64_t tiny=cutoff>=origin0?std::upper_bound(arrays[0],arrays[0]+sizes[0],uint32_t(cutoff-origin0))-arrays[0]:0;
 const uint64_t medium=limit>=origin0?std::upper_bound(arrays[0],arrays[0]+sizes[0],uint32_t(limit-origin0))-arrays[0]:0;
 #pragma omp parallel for num_threads(threads) schedule(static)
 for(int block=0;block<threads;block++) {
  uint64_t begin=first+count*block/threads,last=first+count*(block+1)/threads-1;
  if(begin>last)continue;
  for(uint64_t i=0;i<tiny;i++) {
   const uint64_t period=origin0+arrays[0][i];if(period<2)continue;
   const uint64_t q=std::max<uint64_t>(2,(begin+period-1)/period);
   for(uint64_t n=q*period;n<=last;n+=period)banks[n-first]|=uint8_t(1<<((ranks[0]+i)%2));
  }
 }
 timings[1]=omp_get_wtime()-started;started=omp_get_wtime();
 auto work=p->tasks;
 for(uint64_t j=0;j<p->ids.size();j++)if(p->ids[j]<DIRECT_RECORDS) {
  const uint64_t begin=j==0?medium:0;
  for(uint64_t b=begin;b<sizes[j];b+=16384)
   work.push_back({j,b,std::min<uint64_t>(b+16384,sizes[j]),true});
 }
 static thread_local std::vector<uint8_t> scratch;
 scratch.resize(uint64_t(threads)*count);uint8_t* scratch_data=scratch.data();
 timings[2]=omp_get_wtime()-started;started=omp_get_wtime();
 #pragma omp parallel num_threads(threads)
 {
  uint8_t* local=scratch_data+uint64_t(omp_get_thread_num())*count;
  const int active_threads=omp_get_num_threads();std::memset(local,0,count);
  #pragma omp for schedule(dynamic,128)
  for(uint64_t i=tiny;i<medium;i++) {
   const uint64_t period=origin0+arrays[0][i];if(period<2)continue;
   const uint64_t q=std::max<uint64_t>(2,(first+period-1)/period);
   const uint8_t bit=uint8_t(1<<((ranks[0]+i)%2));
   for(uint64_t n=q*period;n<=end;n+=period)local[n-first]|=bit;
  }
  #pragma omp for schedule(dynamic,1)
  for(uint64_t ti=0;ti<work.size();ti++) {
   const auto task=work[ti];const uint64_t j=task.record;const auto a=arrays[j];
   const uint64_t origin=2+p->ids[j]*count;
   if(task.direct) {
    for(uint64_t i=task.begin;i<task.end;i++) {
     const uint64_t period=origin+a[i];
     if(period<=count)continue;
     const uint64_t q=std::max<uint64_t>(2,(first+period-1)/period),n=q*period;
     if(n<=end)local[n-first]|=uint8_t(1<<((ranks[j]+i)%2));
    }
   } else {
    const uint32_t *b=nullptr,*e=nullptr;
    for(uint64_t ri=task.begin;ri<task.end;ri++) {
     const auto r=p->ranges[j][ri];
     const uint32_t lo=uint32_t(r.lo-origin),hi=uint32_t(r.hi-origin);
     if(REUSE_BOUNDS && b) {
      b=retreat<false>(a,b,lo);e=retreat<true>(a,e,hi);
     } else {
      b=std::lower_bound(a,a+sizes[j],lo);e=std::upper_bound(b,a+sizes[j],hi);
     }
     for(auto v=b;v!=e;++v)local[r.q*(origin+*v)-first]|=uint8_t(1<<((ranks[j]+(v-a))%2));
    }
   }
  }
  #pragma omp single
  {timings[3]=omp_get_wtime()-started;started=omp_get_wtime();}
  #pragma omp for schedule(static)
  for(uint64_t block=0;block<(count+4095)/4096;block++) {
   const uint64_t begin=block*4096,last=std::min(count,begin+4096);
   for(int t=0;t<active_threads;t++) {
    const uint8_t* src=scratch_data+uint64_t(t)*count;
    for(uint64_t i=begin;i<last;i++)banks[i]|=src[i];
   }
  }
 }
 timings[4]=omp_get_wtime()-started;return 0;
}
}

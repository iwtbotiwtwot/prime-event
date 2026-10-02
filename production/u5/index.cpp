#include <algorithm>
#include <cstdint>
extern "C" int mark_ranges(uint64_t first,uint64_t count,const uint64_t* a,uint64_t size,uint64_t rank,const uint64_t* ranges,uint64_t nr,uint8_t* banks){
 for(uint64_t i=0;i<nr;i++){
  uint64_t q=ranges[3*i],lo=ranges[3*i+1],hi=ranges[3*i+2];
  auto b=std::lower_bound(a,a+size,lo),e=std::upper_bound(b,a+size,hi);
  for(auto p=b;p!=e;++p){uint64_t n=q*(*p);if(n<first||n-first>=count||q<2)return 1;banks[n-first]|=uint8_t(1<<((rank+(p-a))%2));}
 }
 return 0;
}

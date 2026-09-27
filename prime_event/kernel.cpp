#include <cstdint>
#include <limits>
extern "C" int mark_periods(uint64_t first,uint64_t count,const uint64_t* periods,
 uint64_t size,uint64_t first_rank,uint8_t* banks){
 const uint64_t end=first+count-1;
 for(uint64_t i=0;i<size;i++){
  const uint64_t p=periods[i];if(p<2)return 1;if(p>end/2)break;
  uint64_t q=first/p+(first%p!=0);if(q<2)q=2;
  if(q>end/p)continue;uint64_t z=q*p;const uint8_t bank=uint8_t(1<<((first_rank+i)%2));
  while(z<=end){banks[z-first]|=bank;if(end-z<p)break;z+=p;}
 }
 return 0;
}
extern "C" int advance_segment(uint64_t first,uint64_t count,const double* cdf,
 const double* base,const double* extra,uint8_t* banks,uint8_t* emit,
 uint8_t* prefix,uint64_t prefix_count,uint64_t* status){
 int state=int(status[0]);uint64_t events=status[1],hash=status[2];const uint64_t end=first+count-1;
 auto sample=[](const double* p,double u){int lo=0,hi=128;while(lo<hi){int m=(lo+hi)/2;if(p[m]<=u)lo=m+1;else hi=m;}return lo;};
 for(uint64_t k=0;k<count;k++){
  const uint64_t n=first+k;const unsigned bits=banks[k];if(bits>3)return 2;
  const double* table=cdf+(((n-2)%35*4+bits)*128*128);bool accept=true;
  for(int j=0;j<3;j++){
   const double u=j<2?extra[k*2+j]:base[k];state=sample(table+state*128,u);if(state>=128)return 1;
   if(k<prefix_count)prefix[k*3+j]=uint8_t(state);
   hash=(hash^uint64_t(state))*1099511628211ULL;if(state&1)accept=false;
  }
  if(accept){emit[k]=1;const uint8_t bank=uint8_t(1<<(events%2));events++;
   if(n<=end/2){uint64_t z=2*n;while(z<=end){banks[z-first]|=bank;if(end-z<n)break;z+=n;}}
  }
 }
 status[0]=state;status[1]=events;status[2]=hash;return 0;
}

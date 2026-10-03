// Exact speculative transitions: never replace an ambiguous state-dependent draw.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>
#include <omp.h>
static int sample(const double* p,double u) {
 int lo=0,hi=128;while(lo<hi){int m=(lo+hi)/2;if(p[m]<=u)lo=m+1;else hi=m;}return lo;
}
extern "C" {
void grade(uint64_t first,uint64_t count,const uint8_t* emit,const uint8_t* truth,
 uint64_t* events,uint64_t* errors,uint64_t* totals) {
 uint64_t ne=0,nw=0,fp=0,fn=0;
 for(uint64_t k=0;k<count;k++) {
  if(emit[k])events[ne++]=first+k;
  if(bool(emit[k])!=bool(truth[k])){errors[nw++]=k;if(truth[k])fn++;else fp++;}
 }
 totals[0]=ne;totals[1]=nw;totals[2]=fp;totals[3]=fn;
}
int mark_parallel(uint64_t first,uint64_t count,const uint64_t* periods,
 uint64_t size,uint64_t rank,uint8_t* banks,int threads) {
 for(uint64_t i=0;i<size;i++)if(periods[i]<2)return 1;
 #pragma omp parallel for num_threads(threads) schedule(static)
 for(uint64_t block=0;block<(count+524287)/524288;block++) {
  uint64_t begin=first+block*524288,end=std::min(first+count-1,begin+524287);
  for(uint64_t i=0;i<size;i++) {
   uint64_t p=periods[i];if(p>end/2)break;
   uint64_t q=std::max(uint64_t(2),(begin+p-1)/p);
   for(uint64_t n=q*p;n<=end;n+=p)banks[n-first]|=uint8_t(1<<((rank+i)%2));
  }
 }
 return 0;
}
void propose(uint64_t first,uint64_t count,const double* row,const double* low,
 const double* high,const uint16_t* lut,const double* base,const double* extra,
 const uint8_t* banks,uint32_t* out,int threads) {
 #pragma omp parallel for num_threads(threads) schedule(static)
 for(uint64_t k=0;k<count;k++) {
  int t=((first+k-2)%35)*4+banks[k];uint32_t word=uint32_t(banks[k])<<24;
  for(int j=0;j<3;j++) {
   double u=j<2?extra[2*k+j]:base[k];int bin=int(u*4096);
   int lo=lut[t*4097+bin],hi=lut[t*4097+bin+1];
   while(lo<hi){int m=(lo+hi)/2;if(row[t*128+m]<=u)lo=m+1;else hi=m;}
   int s=lo;bool certain=s<128 && u<low[t*128+s] && (s==0 || u>=high[t*128+s-1]);
   word|=uint32_t(certain?s:128)<<(8*j);
  }
  out[k]=word;
 }
}
int consume(uint64_t first,uint64_t count,const double* cdf,const double* base,
 const double* extra,uint8_t* banks,uint8_t* emit,uint8_t* prefix,uint64_t prefix_count,
 uint64_t* status,const uint32_t* proposals,uint64_t* counters) {
 int state=status[0];uint64_t events=status[1],hash=status[2],fallback=0,changed=0,end=first+count-1;
 for(uint64_t k=0;k<count;k++) {
  unsigned bits=banks[k];if(bits>3)return 2;
  uint32_t word=proposals[k];bool changed_bank=(word>>24)!=bits;changed+=changed_bank;
  bool accept=true;
  if(!changed_bank && !(word&0x00808080) && k>=prefix_count) {
   unsigned s0=word&127,s1=(word>>8)&127,s2=(word>>16)&127;
   hash=(hash^s0)*1099511628211ULL;
   hash=(hash^s1)*1099511628211ULL;
   hash=(hash^s2)*1099511628211ULL;
   state=s2;accept=!((s0|s1|s2)&1);
  } else {
  for(int j=0;j<3;j++) {
   int s=(word>>(8*j))&255;
   if(changed_bank || s==128) {
    const double* table=cdf+(((first+k-2)%35*4+bits)*128*128);
    s=sample(table+state*128,j<2?extra[2*k+j]:base[k]);fallback++;
   }
   if(s>=128)return 1;state=s;
   if(k<prefix_count)prefix[3*k+j]=state;
   hash=(hash^uint64_t(state))*1099511628211ULL;if(state&1)accept=false;
  }
  }
  emit[k]=accept;
  if(accept) {
   uint8_t bank=1<<(events%2);events++;
   if(first+k<=end/2)for(uint64_t z=2*(first+k);z<=end;z+=first+k)banks[z-first]|=bank;
  }
 }
 status[0]=state;status[1]=events;status[2]=hash;counters[0]+=fallback;counters[1]+=changed;return 0;
}
void sieve(uint64_t first,uint64_t count,uint8_t* out,int threads) {
 uint64_t end=first+count-1,lim=std::sqrt((long double)end);
 while((lim+1)<=end/(lim+1))lim++;while(lim>end/lim)lim--;
 std::vector<uint8_t> small(lim+1,1);std::vector<uint64_t> primes;
 for(uint64_t p=2;p<=lim;p++)if(small[p]){primes.push_back(p);if(p<=lim/p)for(uint64_t n=p*p;n<=lim;n+=p)small[n]=0;}
 #pragma omp parallel for num_threads(threads) schedule(static)
 for(uint64_t block=0;block<(count+262143)/262144;block++) {
  uint64_t lo=block*262144,hi=std::min(count,lo+262144),begin=first+lo,finish=first+hi-1;
  std::fill(out+lo,out+hi,1);
  for(uint64_t p:primes){if(p>finish/p)break;uint64_t n=std::max(p*p,((begin+p-1)/p)*p);for(;n<=finish;n+=p)out[n-first]=0;}
  for(uint64_t n=begin;n<2 && n<=finish;n++)out[n-first]=0;
 }
}
}

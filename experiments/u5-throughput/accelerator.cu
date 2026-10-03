#include <cuda_runtime.h>
#include <cstdint>
static double *drow,*dlow,*dhigh,*dbase,*dextra;
static uint16_t* dlut;static uint8_t* dbanks;static uint32_t* dout;
static uint64_t capacity=0;
#define CHECK(x) do {cudaError_t e=(x);if(e!=cudaSuccess)return int(e);}while(0)
__global__ void proposals(uint64_t first,uint64_t count,const double* row,const double* low,
 const double* high,const uint16_t* lut,const double* base,const double* extra,
 const uint8_t* banks,uint32_t* out) {
 uint64_t k=uint64_t(blockIdx.x)*blockDim.x+threadIdx.x;if(k>=count)return;
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
extern "C" int gpu_init(const double* row,const double* low,const double* high,const uint16_t* lut) {
 const size_t n=140*128*sizeof(double),l=140*4097*sizeof(uint16_t);
 CHECK(cudaMalloc(&drow,n));CHECK(cudaMalloc(&dlow,n));CHECK(cudaMalloc(&dhigh,n));CHECK(cudaMalloc(&dlut,l));
 CHECK(cudaMemcpy(drow,row,n,cudaMemcpyHostToDevice));CHECK(cudaMemcpy(dlow,low,n,cudaMemcpyHostToDevice));
 CHECK(cudaMemcpy(dhigh,high,n,cudaMemcpyHostToDevice));CHECK(cudaMemcpy(dlut,lut,l,cudaMemcpyHostToDevice));return 0;
}
extern "C" int gpu_propose(uint64_t first,uint64_t count,const double* base,const double* extra,const uint8_t* banks,uint32_t* out) {
 if(count>capacity) {
  if(capacity){CHECK(cudaFree(dbase));CHECK(cudaFree(dextra));CHECK(cudaFree(dbanks));CHECK(cudaFree(dout));}
  CHECK(cudaMalloc(&dbase,count*8));CHECK(cudaMalloc(&dextra,count*16));CHECK(cudaMalloc(&dbanks,count));CHECK(cudaMalloc(&dout,count*4));capacity=count;
 }
 CHECK(cudaMemcpy(dbase,base,count*8,cudaMemcpyHostToDevice));CHECK(cudaMemcpy(dextra,extra,count*16,cudaMemcpyHostToDevice));
 CHECK(cudaMemcpy(dbanks,banks,count,cudaMemcpyHostToDevice));
 proposals<<<(count+255)/256,256>>>(first,count,drow,dlow,dhigh,dlut,dbase,dextra,dbanks,dout);
 CHECK(cudaGetLastError());CHECK(cudaMemcpy(out,dout,count*4,cudaMemcpyDeviceToHost));return 0;
}

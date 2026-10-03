// Bank masks from cached, authenticated actual events. No prime oracle.
#include <cuda_runtime.h>
#include <algorithm>
#include <cstdint>
#include <vector>
#define CHECK(x) do {cudaError_t e=(x);if(e!=cudaSuccess)return int(e);}while(0)
struct Record {uint32_t* offsets;uint64_t size,rank,origin;};
struct Range {uint64_t record,q,lo,hi;};
static int device=1;
static std::vector<Record> records;
static Record* device_records=nullptr;
static uint32_t* banks=nullptr;
static uint64_t bank_capacity=0,range_capacity=0;
static Range* device_ranges=nullptr;

__device__ void mark(uint32_t* banks,uint64_t offset,unsigned bit) {
    atomicOr(banks+offset/4,bit<<((offset%4)*8));
}
__global__ void tiny_periods(uint64_t first,uint64_t count,Record record,uint32_t* banks){
    uint64_t index=blockIdx.x;
    uint64_t period=record.origin+record.offsets[index];
    if(period<2)return;
    uint64_t begin=first+uint64_t(blockIdx.y)*65536;
    uint64_t last=min(first+count-1,begin+65535);
    uint64_t q=max(uint64_t(2),(begin+period-1)/period)+threadIdx.x;
    unsigned bit=1u<<((record.rank+index)%2);
    for(uint64_t n=q*period;n<=last;n+=uint64_t(blockDim.x)*period)mark(banks,n-first,bit);
}
__global__ void direct_periods(uint64_t first,uint64_t count,Record record,uint32_t* banks){
    uint64_t index=uint64_t(blockIdx.x)*blockDim.x+threadIdx.x;
    if(index>=record.size)return;
    uint64_t period=record.origin+record.offsets[index];if(period<=4096)return;
    uint64_t q=max(uint64_t(2),(first+period-1)/period);
    uint64_t last=first+count-1;
    unsigned bit=1u<<((record.rank+index)%2);
    for(uint64_t n=q*period;n<=last;n+=period)mark(banks,n-first,bit);
}
__global__ void multiplier_ranges(uint64_t first,uint64_t count,const Record* records,
                                   const Range* ranges,uint64_t size,uint32_t* banks){
    uint64_t index=uint64_t(blockIdx.x)*(blockDim.x/32)+threadIdx.x/32;
    if(index>=size)return;
    Range range=ranges[index];Record record=records[range.record];
    unsigned begin=0,end=0,lane=threadIdx.x%32;
    if(lane==0){
        uint32_t lo=uint32_t(range.lo-record.origin),hi=uint32_t(range.hi-record.origin);
        unsigned left=0,right=unsigned(record.size);
        while(left<right){unsigned mid=(left+right)/2;if(record.offsets[mid]<lo)left=mid+1;else right=mid;}
        begin=left;right=unsigned(record.size);
        while(left<right){unsigned mid=(left+right)/2;if(record.offsets[mid]<=hi)left=mid+1;else right=mid;}
        end=left;
    }
    begin=__shfl_sync(0xffffffff,begin,0);end=__shfl_sync(0xffffffff,end,0);
    for(uint64_t k=uint64_t(begin)+lane;k<end;k+=32){
        uint64_t n=range.q*(record.origin+record.offsets[k]);
        if(n>=first && n-first<count)mark(banks,n-first,1u<<((record.rank+k)%2));
    }
}
static int record_capacity(uint64_t id){
    if(id<records.size())return 0;
    uint64_t size=std::max<uint64_t>(id+1,std::max<uint64_t>(4096,records.size()*2));
    records.resize(size,Record{nullptr,0,0,0});
    Record* replacement;CHECK(cudaMalloc(&replacement,size*sizeof(Record)));
    CHECK(cudaMemcpy(replacement,records.data(),size*sizeof(Record),cudaMemcpyHostToDevice));
    if(device_records)CHECK(cudaFree(device_records));device_records=replacement;return 0;
}
extern "C" int gh_init(int index,uint64_t record_count){
    device=index;CHECK(cudaSetDevice(device));return record_capacity(record_count);
}
extern "C" int gh_put(uint64_t id,const uint32_t* offsets,uint64_t size,uint64_t rank,uint64_t origin){
    CHECK(cudaSetDevice(device));int error=record_capacity(id);if(error)return error;
    if(records[id].offsets)CHECK(cudaFree(records[id].offsets));
    Record record{nullptr,size,rank,origin};
    if(size){CHECK(cudaMalloc(&record.offsets,size*4));CHECK(cudaMemcpy(record.offsets,offsets,size*4,cudaMemcpyHostToDevice));}
    records[id]=record;CHECK(cudaMemcpy(device_records+id,&record,sizeof(record),cudaMemcpyHostToDevice));return 0;
}
extern "C" int gh_drop(uint64_t id){
    CHECK(cudaSetDevice(device));if(id>=records.size())return -1;
    if(records[id].offsets)CHECK(cudaFree(records[id].offsets));
    records[id]=Record{nullptr,0,0,0};
    CHECK(cudaMemcpy(device_records+id,&records[id],sizeof(Record),cudaMemcpyHostToDevice));return 0;
}
extern "C" int gh_apply(uint64_t first,uint64_t count,const Range* ranges,uint64_t size,
                         uint64_t tiny_count,uint8_t* host_banks){
    CHECK(cudaSetDevice(device));
    if(count>bank_capacity){if(banks)CHECK(cudaFree(banks));CHECK(cudaMalloc(&banks,((count+3)/4)*4));bank_capacity=count;}
    if(size>range_capacity){if(device_ranges)CHECK(cudaFree(device_ranges));CHECK(cudaMalloc(&device_ranges,size*sizeof(Range)));range_capacity=size;}
    CHECK(cudaMemset(banks,0,((count+3)/4)*4));
    if(size)CHECK(cudaMemcpy(device_ranges,ranges,size*sizeof(Range),cudaMemcpyHostToDevice));
    if(tiny_count){
        tiny_periods<<<dim3(unsigned(tiny_count),unsigned((count+65535)/65536)),256>>>(first,count,records[0],banks);
        CHECK(cudaGetLastError());
    }
    for(uint64_t j=0;j<4 && j<records.size();j++)if(records[j].size){
        direct_periods<<<(records[j].size+255)/256,256>>>(first,count,records[j],banks);
        CHECK(cudaGetLastError());
    }
    if(size){multiplier_ranges<<<(size+3)/4,128>>>(first,count,device_records,device_ranges,size,banks);CHECK(cudaGetLastError());}
    CHECK(cudaMemcpy(host_banks,banks,count,cudaMemcpyDeviceToHost));return 0;
}
extern "C" int gh_close(){
    CHECK(cudaSetDevice(device));
    for(const auto& record:records)if(record.offsets)CHECK(cudaFree(record.offsets));
    records.clear();if(device_records)CHECK(cudaFree(device_records));device_records=nullptr;
    if(banks)CHECK(cudaFree(banks));banks=nullptr;bank_capacity=0;
    if(device_ranges)CHECK(cudaFree(device_ranges));device_ranges=nullptr;range_capacity=0;return 0;
}

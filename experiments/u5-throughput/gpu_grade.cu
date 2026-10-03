// Isolated exact event compaction and error grading; oracle never creates events.
#include <cuda_runtime.h>
#include <cub/cub.cuh>
#include <algorithm>
#include <cstdint>
#include <cstring>

#define CHECK(x) do {cudaError_t e=(x);if(e!=cudaSuccess)return int(e);}while(0)
static int device=2;
static uint64_t capacity=0;
static uint8_t *de,*dt,*dw,*he,*ht;
static uint64_t *dev_events,*dev_errors,*totals,*host_events,*host_errors,*host_totals;
static int* selected;
static void* temporary=nullptr;
static size_t temporary_bytes=0;
static cudaStream_t stream;

__global__ void mismatches(uint64_t count,const uint8_t* emit,const uint8_t* truth,
                           uint8_t* wrong,uint64_t* sums) {
    __shared__ unsigned fp[256],fn[256];
    uint64_t k=uint64_t(blockIdx.x)*blockDim.x+threadIdx.x;
    bool a=k<count && emit[k],b=k<count && truth[k];
    if(k<count)wrong[k]=a!=b;
    fp[threadIdx.x]=a&&!b;fn[threadIdx.x]=!a&&b;
    __syncthreads();
    for(int stride=128;stride;stride/=2){
        if(threadIdx.x<stride){fp[threadIdx.x]+=fp[threadIdx.x+stride];fn[threadIdx.x]+=fn[threadIdx.x+stride];}
        __syncthreads();
    }
    if(threadIdx.x==0){
        if(fp[0])atomicAdd(reinterpret_cast<unsigned long long*>(sums+2),fp[0]);
        if(fn[0])atomicAdd(reinterpret_cast<unsigned long long*>(sums+3),fn[0]);
    }
}
__global__ void publish_counts(const int* selected,uint64_t* totals){
    totals[0]=selected[0];totals[1]=selected[1];
}
extern "C" int gg_init(int index){
    device=index;CHECK(cudaSetDevice(device));
    CHECK(cudaStreamCreateWithFlags(&stream,cudaStreamNonBlocking));return 0;
}
static int reserve(uint64_t count){
    if(count<=capacity)return 0;
    if(capacity){
        CHECK(cudaFree(de));CHECK(cudaFree(dt));CHECK(cudaFree(dw));
        CHECK(cudaFree(dev_events));CHECK(cudaFree(dev_errors));CHECK(cudaFree(totals));
        CHECK(cudaFree(selected));CHECK(cudaFree(temporary));
        CHECK(cudaFreeHost(he));CHECK(cudaFreeHost(ht));
        CHECK(cudaFreeHost(host_events));CHECK(cudaFreeHost(host_errors));CHECK(cudaFreeHost(host_totals));
    }
    CHECK(cudaMalloc(&de,count));CHECK(cudaMalloc(&dt,count));CHECK(cudaMalloc(&dw,count));
    CHECK(cudaMalloc(&dev_events,count*8));CHECK(cudaMalloc(&dev_errors,count*8));
    CHECK(cudaMalloc(&totals,32));CHECK(cudaMalloc(&selected,2*sizeof(int)));
    CHECK(cudaMallocHost(&he,count));CHECK(cudaMallocHost(&ht,count));
    CHECK(cudaMallocHost(&host_events,count*8));CHECK(cudaMallocHost(&host_errors,count*8));
    CHECK(cudaMallocHost(&host_totals,32));
    temporary_bytes=0;
    CHECK(cub::DeviceSelect::Flagged(nullptr,temporary_bytes,
        cub::CountingInputIterator<uint64_t>(0),de,dev_events,selected,int(count),stream));
    CHECK(cudaMalloc(&temporary,temporary_bytes));capacity=count;return 0;
}
extern "C" int gg_grade(uint64_t first,uint64_t count,const uint8_t* emit,const uint8_t* truth,
                         uint64_t* events,uint64_t* errors,uint64_t* out_totals){
    CHECK(cudaSetDevice(device));
    if(!count){std::fill(out_totals,out_totals+4,0);return 0;}
    if(count>uint64_t(INT32_MAX))return -1;
    int error=reserve(count);if(error)return error;
    std::memcpy(he,emit,count);std::memcpy(ht,truth,count);
    CHECK(cudaMemcpyAsync(de,he,count,cudaMemcpyHostToDevice,stream));
    CHECK(cudaMemcpyAsync(dt,ht,count,cudaMemcpyHostToDevice,stream));
    CHECK(cudaMemsetAsync(totals,0,32,stream));
    mismatches<<<(count+255)/256,256,0,stream>>>(count,de,dt,dw,totals);
    CHECK(cudaGetLastError());
    CHECK(cub::DeviceSelect::Flagged(temporary,temporary_bytes,
        cub::CountingInputIterator<uint64_t>(first),de,dev_events,selected,int(count),stream));
    CHECK(cub::DeviceSelect::Flagged(temporary,temporary_bytes,
        cub::CountingInputIterator<uint64_t>(0),dw,dev_errors,selected+1,int(count),stream));
    publish_counts<<<1,1,0,stream>>>(selected,totals);CHECK(cudaGetLastError());
    CHECK(cudaMemcpyAsync(host_totals,totals,32,cudaMemcpyDeviceToHost,stream));
    CHECK(cudaStreamSynchronize(stream));
    if(host_totals[0])CHECK(cudaMemcpyAsync(host_events,dev_events,host_totals[0]*8,cudaMemcpyDeviceToHost,stream));
    if(host_totals[1])CHECK(cudaMemcpyAsync(host_errors,dev_errors,host_totals[1]*8,cudaMemcpyDeviceToHost,stream));
    CHECK(cudaStreamSynchronize(stream));
    std::memcpy(out_totals,host_totals,32);
    std::memcpy(events,host_events,host_totals[0]*8);std::memcpy(errors,host_errors,host_totals[1]*8);
    return 0;
}
extern "C" int gg_close(){
    CHECK(cudaSetDevice(device));
    if(capacity){
        CHECK(cudaFree(de));CHECK(cudaFree(dt));CHECK(cudaFree(dw));
        CHECK(cudaFree(dev_events));CHECK(cudaFree(dev_errors));CHECK(cudaFree(totals));
        CHECK(cudaFree(selected));CHECK(cudaFree(temporary));
        CHECK(cudaFreeHost(he));CHECK(cudaFreeHost(ht));
        CHECK(cudaFreeHost(host_events));CHECK(cudaFreeHost(host_errors));CHECK(cudaFreeHost(host_totals));capacity=0;
    }
    CHECK(cudaStreamDestroy(stream));return 0;
}

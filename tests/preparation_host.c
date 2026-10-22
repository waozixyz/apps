#define _DEFAULT_SOURCE
#include "ziran_host.h"
#include <assert.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <pthread.h>
#include <time.h>
#include <unistd.h>
#endif
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

static atomic_bool blocked;
static atomic_bool started;
static atomic_int opens;
static atomic_int live;
static atomic_int frame_opens;
#ifdef _WIN32
static DWORD frame_thread;
#else
static pthread_t frame_thread;
#endif

static bool FrameThread(void)
{
#ifdef _WIN32
    return frame_thread == GetCurrentThreadId();
#else
    return pthread_equal(frame_thread, pthread_self());
#endif
}

void PreparationTestBegin(void)
{
#ifdef _WIN32
    frame_thread = GetCurrentThreadId();
#else
    frame_thread = pthread_self();
#endif
}

void PreparationTestBlock(bool enabled)
{
    if (enabled) atomic_store(&started, false);
    atomic_store(&blocked, enabled);
}

bool PreparationTestStarted(void)
{
    return atomic_load(&started);
}

int32_t PreparationTestOpens(void)
{
    return atomic_load(&opens);
}

int32_t PreparationTestLive(void)
{
    return atomic_load(&live);
}

int32_t PreparationTestFrameOpens(void)
{
    return atomic_load(&frame_opens);
}

void PreparationTestYield(void)
{
#ifdef _WIN32
    Sleep(1);
#else
    usleep(1000);
#endif
}

double PreparationTestNow(void)
{
#ifdef _WIN32
    LARGE_INTEGER now, frequency;
    assert(QueryPerformanceCounter(&now) && QueryPerformanceFrequency(&frequency));
    return (double)now.QuadPart / (double)frequency.QuadPart;
#else
    struct timespec now;
    assert(clock_gettime(CLOCK_MONOTONIC, &now) == 0);
    return (double)now.tv_sec + (double)now.tv_nsec / 1e9;
#endif
}

void PreparationTestTiming(double synchronous, double activation)
{
    printf("{\"synchronous_start_ms\":%.3f,\"prepared_activation_ms\":%.3f}\n",
           synchronous * 1000.0, activation * 1000.0);
}

void PreparationTestLocatorTiming(double synchronous, double maximum_poll)
{
    printf("{\"synchronous_locator_ms\":%.3f,\"maximum_locator_poll_ms\":%.3f}\n",
           synchronous * 1000.0, maximum_poll * 1000.0);
}

Bundle *__real_BundleOpenBytes(const unsigned char *bytes, size_t count);
Bundle *__wrap_BundleOpenBytes(const unsigned char *bytes, size_t count)
{
    atomic_fetch_add(&opens, 1);
    if (FrameThread()) atomic_fetch_add(&frame_opens, 1);
    if (atomic_load(&blocked)) {
        atomic_store(&started, true);
        while (atomic_load(&blocked)) PreparationTestYield();
    }
    Bundle *bundle = __real_BundleOpenBytes(bytes, count);
    if (bundle) atomic_fetch_add(&live, 1);
    return bundle;
}

void __real_BundleClose(Bundle *bundle);
void __wrap_BundleClose(Bundle *bundle)
{
    if (bundle) atomic_fetch_sub(&live, 1);
    __real_BundleClose(bundle);
}

BundleInstance *__real_BundleInstantiate(const Bundle *bundle,
    const HostBinding *bindings, size_t count);
BundleInstance *__wrap_BundleInstantiate(const Bundle *bundle,
    const HostBinding *bindings, size_t count)
{
    assert(FrameThread());
    return __real_BundleInstantiate(bundle, bindings, count);
}

int __real_BundleInstanceRun(BundleInstance *instance, int64_t *answer, int *has_answer);
int __wrap_BundleInstanceRun(BundleInstance *instance, int64_t *answer, int *has_answer)
{
    assert(FrameThread());
    return __real_BundleInstanceRun(instance, answer, has_answer);
}

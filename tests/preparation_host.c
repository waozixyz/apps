#define _DEFAULT_SOURCE
#include "ziran_host.h"
#include <assert.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

static atomic_bool blocked;
static atomic_bool started;
static atomic_int opens;
static atomic_int live;
static atomic_int frame_opens;
static pthread_t frame_thread;

void PreparationTestBegin(void)
{
    frame_thread = pthread_self();
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
    usleep(1000);
}

double PreparationTestNow(void)
{
    struct timespec now;
    assert(clock_gettime(CLOCK_MONOTONIC, &now) == 0);
    return (double)now.tv_sec + (double)now.tv_nsec / 1e9;
}

void PreparationTestTiming(double synchronous, double activation)
{
    printf("{\"synchronous_start_ms\":%.3f,\"prepared_activation_ms\":%.3f}\n",
           synchronous * 1000.0, activation * 1000.0);
}

Bundle *__real_BundleOpenBytes(const unsigned char *bytes, size_t count);
Bundle *__wrap_BundleOpenBytes(const unsigned char *bytes, size_t count)
{
    atomic_fetch_add(&opens, 1);
    if (pthread_equal(frame_thread, pthread_self())) atomic_fetch_add(&frame_opens, 1);
    if (atomic_load(&blocked)) {
        atomic_store(&started, true);
        while (atomic_load(&blocked)) usleep(1000);
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
    assert(pthread_equal(frame_thread, pthread_self()));
    return __real_BundleInstantiate(bundle, bindings, count);
}

int __real_BundleInstanceRun(BundleInstance *instance, int64_t *answer, int *has_answer);
int __wrap_BundleInstanceRun(BundleInstance *instance, int64_t *answer, int *has_answer)
{
    assert(pthread_equal(frame_thread, pthread_self()));
    return __real_BundleInstanceRun(instance, answer, has_answer);
}

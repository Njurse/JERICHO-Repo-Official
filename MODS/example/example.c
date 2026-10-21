#include "jericho.h"

static int ExampleOnFrame(void* userdata, void* args)
{
    static int n = 0;
    JERICHO_CONTEXT* ctx = (JERICHO_CONTEXT*)userdata;
    if ((++n % 60) == 0)
        ctx->jer_log(ctx, "[example] frame %d", n);
    return JER_RESULT_CONTINUE;
}

JER_MODULE_ENTRY(jer_module_example_entry)(JERICHO_CONTEXT* ctx)
{
    ctx->jer_register_module(ctx, "example", "Example Module", "0.1.0",
        "Njurse", "Minimal official example.", "", JERICHO_SDK_VERSION);
    ctx->jer_register_hook(ctx, JER_EVENT_FRAME, ExampleOnFrame, ctx, 0);
}

import asyncio
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


async def aemit_run_event(run_id: str, data: dict):
    """
    纯异步：在 async 上下文内调用。
    """
    channel_layer = get_channel_layer()
    # group_send 本身是 coroutine，必须 await
    await channel_layer.group_send(
        f"run_{run_id}",
        {"type": "run_event", "data": data}
    )


def emit_run_event(run_id: str, data: dict):
    try:
        asyncio.get_running_loop()
        # 如果能拿到 loop，说明处在 async 上下文内，直接提示误用
        raise RuntimeError("emit_run_event() called inside async context; use await aemit_run_event() instead.")
    except RuntimeError:
        # 没有事件循环 -> 同步场景，正常走 async_to_sync
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"run_{run_id}",
            {"type": "run_event", "data": data}
        )

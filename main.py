from __future__ import annotations

import asyncio
import logging

from config import load_settings


async def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger("velofetch").info(
        "Configuration loaded. WZGram client/handlers are the next porting step."
    )
    # Keep the entry point intentionally small. The WZGram adapter will be
    # connected here after its exact API is ported from the original bridge.
    _ = settings
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

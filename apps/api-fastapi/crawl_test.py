import asyncio

from services.sync_service import run_portal_sync


async def main() -> None:
    print("[All Blue Sync Engine] Manual CLI invocation for remaxrd.")
    result = await run_portal_sync("remaxrd")
    print(f"[All Blue Sync Engine] Completed: {result}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Sync Engine] Execution lifecycle aborted by user.")
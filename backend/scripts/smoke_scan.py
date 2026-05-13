import asyncio

from services import scanner


async def test() -> None:
    try:
        # Kungsgatan 1, Stockholm
        res = await scanner.scan_address("Kungsgatan 1, Stockholm")
        print(f"Result: {res}")
    except Exception:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())

import asyncio

from services import geocode


async def test() -> None:
    try:
        res = await geocode.geocode("Kungsgatan 1, Stockholm")
        print(f"Result: {res}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())

import asyncio
from storage.database import async_session, init_db
from sqlalchemy import text

async def main():
    await init_db()
    async with async_session() as session:
        await session.execute(
            text("UPDATE llm_provider_configs SET base_url = :url WHERE name = 'vansrouter'"),
            {"url": "http://172.19.0.2:20128/v1"}
        )
        await session.commit()
        result = await session.execute(text('SELECT name, base_url FROM llm_provider_configs'))
        for row in result:
            print(f"Name={row[0]} URL={row[1]}")

asyncio.run(main())

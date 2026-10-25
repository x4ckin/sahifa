from httpx import ASGITransport, AsyncClient

from sahifa.db import init_db
from sahifa.main import build


async def test_runtime_wires_api_and_bot(settings):
    rt = build(settings)
    await init_db(rt.engine)
    async with AsyncClient(transport=ASGITransport(app=rt.app), base_url="https://api.test") as c:
        assert (await c.get("/api/public/m/nothing")).status_code == 404
        assert (await c.get("/api/me")).status_code == 401
    assert {r.name for r in rt.dp.sub_routers} == {"start", "payments", "review", "admin"}
    await rt.bot.session.close()
    await rt.engine.dispose()

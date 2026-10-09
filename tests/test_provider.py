import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from app.provider import FootballAPI, ProviderError


def run(coro):
    return asyncio.run(coro)


def test_cache_prevents_repeat_requests_and_secret_is_header(settings,store):
    received=[]
    def handle(request):
        received.append(request)
        return httpx.Response(200,json={"response":[],"errors":[],"paging":{"total":1}})
    async def scenario():
        client=httpx.AsyncClient(base_url="https://v3.football.api-sports.io",headers={"x-apisports-key":settings.api_football_key},transport=httpx.MockTransport(handle))
        provider=FootballAPI(settings,store,client)
        await provider.get('/fixtures',{"date":"2026-01-01"})
        await provider.get('/fixtures',{"date":"2026-01-01"})
        await provider.close()
    run(scenario())
    assert len(received)==1
    assert received[0].headers["x-apisports-key"]=="test-only-key"
    assert "test-only-key" not in str(received[0].url)
    assert store.quota(datetime.now(timezone.utc).date().isoformat())==1


@pytest.mark.parametrize('status,payload',[(401,{}),(403,{}),(429,{}),(500,{}),(200,{"response":[],"errors":{"plan":"private secret"}}),(200,{"response":{},"errors":[]})])
def test_api_errors_safe(settings,store,status,payload):
    async def scenario():
        async with httpx.AsyncClient(base_url="https://test.invalid",transport=httpx.MockTransport(lambda req:httpx.Response(status,json=payload))) as client:
            provider=FootballAPI(settings,store,client)
            with pytest.raises(ProviderError) as error:
                await provider.get('/fixtures',{})
            assert 'private secret' not in str(error.value)
    run(scenario())


def test_daily_quota_persists_across_provider_instances(settings,store):
    settings.max_requests_per_day=1
    async def scenario():
        async with httpx.AsyncClient(base_url="https://test.invalid",transport=httpx.MockTransport(lambda req:httpx.Response(200,json={"response":[],"errors":[]}))) as client:
            await FootballAPI(settings,store,client).get('/fixtures',{"date":"one"})
            with pytest.raises(ProviderError,match="diário"):
                await FootballAPI(settings,store,client).get('/fixtures',{"date":"two"})
    run(scenario())


def test_refresh_budget_and_pagination(settings,store):
    settings.max_requests_per_refresh=2
    pages=[]
    def handle(request):
        page=int(request.url.params['page']); pages.append(page)
        return httpx.Response(200,json={"response":[{"page":page}],"errors":[],"paging":{"total":2}})
    async def scenario():
        async with httpx.AsyncClient(base_url="https://test.invalid",transport=httpx.MockTransport(handle)) as client:
            provider=FootballAPI(settings,store,client)
            result=await provider.odds(42)
            assert result['response']==[{"page":1},{"page":2}]
            with pytest.raises(ProviderError,match="atualização"):
                await provider.get('/fixtures',{})
    run(scenario()); assert pages==[1,2]


def test_no_key_no_outbound_request(settings,store):
    settings.api_football_key=''
    async def scenario():
        async with httpx.AsyncClient(base_url="https://test.invalid",transport=httpx.MockTransport(lambda req:pytest.fail('Request without key'))) as client:
            with pytest.raises(ProviderError,match="Configure"):
                await FootballAPI(settings,store,client).get('/fixtures',{})
    run(scenario())

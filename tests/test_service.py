import asyncio
from datetime import datetime, timedelta, timezone

from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.main import create_app
from app.provider import ProviderError
from app.service import AnalysisService
from conftest import make_fixture


class FakeProvider:
    def __init__(self,fixture,history,fail=False):
        self.fixture,self.history,self.fail=fixture,history,fail
        self.calls=[]
    def reset_budget(self): pass
    async def get(self,endpoint,params,ttl=0):
        self.calls.append((endpoint,params))
        if self.fail: raise ProviderError('Teste de indisponibilidade')
        rows=self.history if 'season' in params else [self.fixture]
        return {"response":rows,"fetched_at":datetime.now(timezone.utc).isoformat()}


def test_auto_discovery_and_analysis(settings,store,fixture,history):
    provider=FakeProvider(fixture,history)
    service=AnalysisService(settings,store,provider)
    assert asyncio.run(service.refresh())["status"]=="success"
    snapshot=service.dashboard()
    assert len(snapshot["fixtures"])==1
    assert snapshot["fixtures"][0]["analysis"]["probabilities"] is not None
    assert provider.calls[0][1]['date']==datetime.now().astimezone(ZoneInfo(settings.timezone)).date().isoformat()
    assert 'fixture' not in provider.calls[0][1]
    assert snapshot['updated_at']


def test_failed_refresh_keeps_prior_snapshot(settings,store,fixture,history):
    provider=FakeProvider(fixture,history)
    service=AnalysisService(settings,store,provider)
    asyncio.run(service.refresh());previous=service.dashboard()['updated_at']
    provider.fail=True
    assert asyncio.run(service.refresh())['status']=='error'
    assert service.dashboard()['updated_at']==previous
    assert len(service.dashboard()['fixtures'])==1


def test_started_and_stale_odds_cannot_be_eligible(settings,store,fixture,history):
    service=AnalysisService(settings,store,FakeProvider(fixture,history))
    asyncio.run(service.refresh())
    snap=store.get('snapshot')
    snap['fixtures'][0]['kickoff']=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
    snap['fixtures'][0]['opportunities']=[{'updated_at':datetime.now(timezone.utc).isoformat(),'classification':'vantagem na sensibilidade'}]
    store.set('snapshot',snap)
    assert not service.dashboard()['fixtures'][0]['opportunities'][0]['eligible']
    snap['fixtures'][0]['kickoff']=fixture['fixture']['date']
    snap['fixtures'][0]['opportunities'][0]['updated_at']=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
    store.set('snapshot',snap)
    assert not service.dashboard()['fixtures'][0]['opportunities'][0]['eligible']


def test_missing_key_dashboard_no_fiction_and_no_secret(settings,store,fixture,history):
    settings.api_football_key=''
    service=AnalysisService(settings,store,FakeProvider(fixture,history))
    asyncio.run(service.refresh())
    app=create_app(settings,service,start_scheduler=False)
    with TestClient(app) as client:
        response=client.get('/api/dashboard')
        assert response.status_code==200
        assert response.json()['fixtures']==[]
        assert not response.json()['configured']
        assert 'api_football_key' not in response.text
        assert client.get('/health').json()['status']=='ok'
        assert client.get('/').status_code==200
        assert client.get('/static/app.js').status_code==200
        assert client.get('/static/style.css').status_code==200
        assert client.post('/api/refresh').status_code==403
        assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']


def test_refresh_authentication(settings,store,fixture,history):
    settings.admin_token='test-admin'
    service=AnalysisService(settings,store,FakeProvider(fixture,history))
    with TestClient(create_app(settings,service,start_scheduler=False)) as client:
        assert client.post('/api/refresh').status_code==401
        assert client.post('/api/refresh',headers={'Authorization':'Bearer wrong'}).status_code==401
        assert client.post('/api/refresh',headers={'Authorization':'Bearer test-admin'}).json()['status']=='success'


def test_scheduling_removes_live_and_finished_and_limits_matches(settings,store,fixture,history):
    settings.max_fixtures=1
    class Provider(FakeProvider):
        async def get(self,endpoint,params,ttl=0):
            payload=await super().get(endpoint,params,ttl)
            if 'season' not in params:
                payload['response']=[make_fixture(7,status='1H'),make_fixture(8,status='FT'),fixture,make_fixture(12,kickoff=datetime.now(timezone.utc)+timedelta(days=2))]
            return payload
    service=AnalysisService(settings,store,Provider(fixture,history))
    asyncio.run(service.refresh())
    snapshot=service.dashboard()
    assert snapshot['discovered']==2
    assert len(snapshot['fixtures'])==1
    assert snapshot['warnings']


def test_preferred_house_id_filters_without_substituting_prices(settings,store,fixture,history):
    settings.enable_odds=True
    settings.preferred_bookmaker_id=42
    class Provider(FakeProvider):
        async def odds(self,fixture_id):
            return {'fetched_at':datetime.now(timezone.utc).isoformat(),'response':[{
                'update':datetime.now(timezone.utc).isoformat(),
                'bookmakers':[{'id':identifier,'name':f'Casa sintética {identifier}','bets':[{
                    'name':'Match Winner','values':[{'value':'Home','odd':'2.10'},{'value':'Draw','odd':'3.5'},{'value':'Away','odd':'3.6'}]
                }]} for identifier in (7,42)]
            }]}
    service=AnalysisService(settings,store,Provider(fixture,history))
    asyncio.run(service.refresh())
    rows=service.dashboard()['fixtures'][0]['opportunities']
    assert rows and all(row['bookmaker_id']==42 for row in rows)
    settings.preferred_bookmaker_id=99
    asyncio.run(service.refresh())
    assert service.dashboard()['fixtures'][0]['opportunities']==[]


def test_optional_features_off_do_not_call_endpoints(settings,store,fixture,history):
    provider=FakeProvider(fixture,history)
    service=AnalysisService(settings,store,provider)
    asyncio.run(service.refresh())
    assert all(endpoint=='/fixtures' for endpoint,params in provider.calls)


def test_snapshot_staleness_suppresses_opportunities(settings,store,fixture,history):
    service=AnalysisService(settings,store,FakeProvider(fixture,history))
    asyncio.run(service.refresh())
    snap=store.get('snapshot')
    snap['updated_at']=(datetime.now(timezone.utc)-timedelta(hours=3)).isoformat()
    snap['fixtures'][0]['opportunities']=[{'updated_at':datetime.now(timezone.utc).isoformat(),'classification':'vantagem na sensibilidade'}]
    store.set('snapshot',snap)
    snapshot=service.dashboard()
    assert snapshot['stale']
    assert not snapshot['fixtures'][0]['opportunities'][0]['eligible']

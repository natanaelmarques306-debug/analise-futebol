import asyncio
import json
from datetime import datetime, timezone

import httpx

from app.config import Settings
from app.storage import Store


class ProviderError(Exception):
    pass


class FootballAPI:
    """API-Football v3 direta. Chave exclusivamente no servidor; sem scraping."""
    def __init__(self, settings: Settings, store: Store, client: httpx.AsyncClient | None = None):
        self.settings, self.store = settings, store
        self.client = client or httpx.AsyncClient(
            base_url="https://v3.football.api-sports.io",
            headers={"x-apisports-key": settings.api_football_key},
            timeout=25.0,
        )
        self.requests = 0

    def reset_budget(self):
        self.requests = 0

    async def get(self, endpoint: str, params: dict, ttl: int = 1800) -> dict:
        if not self.settings.api_football_key:
            raise ProviderError("Configure API_FOOTBALL_KEY no servidor para consultar dados reais.")
        key = endpoint + json.dumps(params, sort_keys=True)
        cached = self.store.cache_get(key, ttl)
        if cached is not None:
            return cached
        if self.requests >= self.settings.max_requests_per_refresh:
            raise ProviderError("Limite de consultas desta atualização atingido; reduza ligas ou partidas.")
        day = datetime.now(timezone.utc).date().isoformat()
        if not self.store.reserve_request(day, self.settings.max_requests_per_day):
            raise ProviderError("Limite diário local de consultas atingido. Aguarde o próximo dia UTC.")
        self.requests += 1
        # Sem retry cego: cada tentativa também consome a cota do fornecedor.
        await asyncio.sleep(0.25)
        try:
            response = await self.client.get(endpoint, params=params)
            if response.status_code in (401, 403):
                raise ProviderError("API recusou acesso: verifique a chave e as permissões do plano.")
            if response.status_code == 429:
                raise ProviderError("Cota ou limite de frequência da API atingido.")
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("Falha de comunicação com a API esportiva. Tente na próxima atualização.") from exc
        if not isinstance(payload, dict) or payload.get("errors"):
            raise ProviderError("API retornou erro: confira plano, temporada, filtros e cota no painel API-Sports.")
        if not isinstance(payload.get("response"), list):
            raise ProviderError("Resposta da API esportiva em formato inesperado.")
        result = {"response": payload["response"], "paging": payload.get("paging", {}),
                  "fetched_at": datetime.now(timezone.utc).isoformat(), "source": "API-Football v3"}
        self.store.cache_set(key, result)
        return result

    async def odds(self, fixture_id: int) -> dict:
        rows = []
        fetched_at = None
        for page in range(1, 11):
            payload = await self.get("/odds", {"fixture": fixture_id, "page": page}, ttl=300)
            rows.extend(payload["response"])
            fetched_at = payload["fetched_at"]
            total = payload["paging"].get("total", 1)
            if page >= total:
                return {"response": rows, "fetched_at": fetched_at}
        raise ProviderError("Odds excederam 10 páginas: comparação omitida para evitar cobertura incompleta.")

    async def close(self):
        await self.client.aclose()

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import Settings
from app.model import analyze, parse_time, summarize_detailed
from app.odds import compare_odds
from app.provider import FootballAPI, ProviderError
from app.storage import Store


class AnalysisService:
    def __init__(self, settings: Settings, store: Store, provider: FootballAPI):
        self.settings, self.store, self.provider = settings, store, provider
        self.lock = asyncio.Lock()

    def dashboard(self) -> dict:
        snapshot = self.store.get("snapshot", {"fixtures": [], "updated_at": None, "warnings": []})
        attempted = self.store.get("attempt", {})
        now = datetime.now(timezone.utc)
        snapshot["configured"] = bool(self.settings.api_football_key)
        snapshot["timezone"] = self.settings.timezone
        snapshot["refresh_minutes"] = self.settings.refresh_minutes
        snapshot["refreshing"] = self.lock.locked()
        snapshot["last_attempt"] = attempted
        snapshot["stale"] = not snapshot["updated_at"] or (now-parse_time(snapshot["updated_at"])).total_seconds() > self.settings.refresh_minutes*120
        # Odds ficam inelegíveis mesmo se o cache global ainda estiver visível.
        for fixture in snapshot["fixtures"]:
            fixture["started"] = parse_time(fixture["kickoff"]) <= now
            for row in fixture.get("opportunities", []):
                row["stale"] = fixture["started"] or snapshot["stale"] or (now-parse_time(row["updated_at"])).total_seconds() > self.settings.odds_max_age_minutes*60
                row["eligible"] = not row["stale"] and row["classification"] == "vantagem na sensibilidade"
        snapshot["quota"] = {"used": self.store.quota(now.date().isoformat()), "limit": self.settings.max_requests_per_day,
                              "reset_timezone": "UTC"}
        snapshot["integration"] = {"source": "API-Football v3", "leagues": self.settings.leagues,
                                   "odds": self.settings.enable_odds, "injuries": self.settings.enable_injuries,
                                   "detailed_stats": self.settings.enable_detailed_stats,
                                   "preferred_bookmaker_name": self.settings.preferred_bookmaker_name,
                                   "preferred_bookmaker_id": self.settings.preferred_bookmaker_id}
        return snapshot

    async def refresh(self) -> dict:
        if self.lock.locked():
            return {"status": "already_running"}
        async with self.lock:
            self.provider.reset_budget()
            attempted_at = datetime.now(timezone.utc).isoformat()
            if not self.settings.api_football_key:
                attempt = {"at": attempted_at, "status": "configuration_required", "message": "Configure API_FOOTBALL_KEY no servidor."}
                self.store.set("attempt", attempt)
                return attempt
            try:
                await self._refresh(attempted_at)
            except (ProviderError, KeyError, ValueError, TypeError) as exc:
                message = str(exc) if isinstance(exc, ProviderError) else "Dados recebidos em formato inesperado; atualização interrompida."
                attempt = {"at": attempted_at, "status": "error", "message": message}
                self.store.set("attempt", attempt)
                return attempt
            return self.store.get("attempt")

    async def _refresh(self, attempted_at: str):
        now = datetime.now(timezone.utc)
        local_date = now.astimezone(ZoneInfo(self.settings.timezone)).date()
        warnings, scheduled = [], []
        # Sem cadastro de partidas: descoberta por data, em cada liga configurada.
        for offset in range(self.settings.days_ahead + 1):
            date = (local_date+timedelta(days=offset)).isoformat()
            for league in self.settings.leagues:
                payload = await self.provider.get("/fixtures", {"date": date, "league": league, "timezone": self.settings.timezone}, ttl=900 if offset == 0 else 21600)
                scheduled.extend(dict(r, fixture_fetched_at=payload["fetched_at"]) for r in payload["response"] if r["fixture"]["status"]["short"] == "NS"
                                 and parse_time(r["fixture"]["date"]) > now)
        scheduled = sorted({r["fixture"]["id"]: r for r in scheduled}.values(), key=lambda r: r["fixture"]["date"])
        discovered = len(scheduled)
        if discovered > self.settings.max_fixtures:
            warnings.append(f"{discovered} partidas encontradas; analisando as {self.settings.max_fixtures} mais próximas para respeitar a cota.")
        output = []
        for row in scheduled[:self.settings.max_fixtures]:
            item = {"id": row["fixture"]["id"], "kickoff": row["fixture"]["date"], "status": row["fixture"]["status"]["short"],
                    "league": {"id": row["league"]["id"], "name": row["league"]["name"], "country": row["league"].get("country"), "season": row["league"]["season"]},
                    "home": {"id": row["teams"]["home"]["id"], "name": row["teams"]["home"]["name"]},
                    "away": {"id": row["teams"]["away"]["id"], "name": row["teams"]["away"]["name"]},
                    "fixture_fetched_at": row.get("fixture_fetched_at"),
                    "venue": row["fixture"].get("venue", {}).get("name"), "source": "API-Football v3",
                    "analysis": None, "opportunities": [], "warnings": [], "injuries": None,
                    "detailed_stats": None, "odds_fetched_at": None, "analyzed_at": datetime.now(timezone.utc).isoformat()}
            try:
                history = await self.provider.get("/fixtures", {"league": row["league"]["id"], "season": row["league"]["season"], "status": "FT"}, ttl=21600)
                item["history_fetched_at"] = history["fetched_at"]
                item["analysis"] = analyze(row, history["response"])
            except (ProviderError, KeyError, ValueError, TypeError) as exc:
                item["warnings"].append(str(exc) if isinstance(exc, ProviderError) else "Histórico inválido; análise omitida.")
            if self.settings.enable_injuries:
                try:
                    injuries = await self.provider.get("/injuries", {"fixture": item["id"]}, ttl=3600)
                    item["injuries"] = {"players": [{"team": x.get("team", {}).get("name"), "player": x.get("player", {}).get("name"),
                                                         "reason": x.get("player", {}).get("reason"), "type": x.get("player", {}).get("type")}
                                                        for x in injuries["response"]], "fetched_at": injuries["fetched_at"]}
                    if not injuries["response"]:
                        item["warnings"].append("API não informou desfalques; resposta vazia não confirma elenco completo.")
                except ProviderError as exc:
                    item["warnings"].append(str(exc))
            if self.settings.enable_detailed_stats and item["analysis"]:
                item["detailed_stats"] = {}
                for side in ("home", "away"):
                    payloads = []
                    for match in item["analysis"][f"{side}_recent"]["fixture_ids"][:5]:
                        try:
                            payloads.append(await self.provider.get("/fixtures/statistics", {"fixture": match}, ttl=604800))
                        except ProviderError as exc:
                            item["warnings"].append(str(exc)); break
                    item["detailed_stats"][side] = summarize_detailed(payloads, item[side]["id"])
            if self.settings.enable_odds:
                try:
                    odds = await self.provider.odds(item["id"])
                    item["odds_fetched_at"] = odds["fetched_at"]
                    item["opportunities"] = compare_odds(odds, item["analysis"] or {}, self.settings.odds_max_age_minutes)
                    if self.settings.preferred_bookmaker_id:
                        item["opportunities"] = [q for q in item["opportunities"] if q["bookmaker_id"] == self.settings.preferred_bookmaker_id]
                    if not item["opportunities"]:
                        item["warnings"].append("Sem comparação: odds recentes de mercados suportados ou amostra estatística indisponíveis.")
                except ProviderError as exc:
                    item["warnings"].append(str(exc))
            output.append(item)
        snapshot = {"fixtures": output, "updated_at": datetime.now(timezone.utc).isoformat(), "warnings": warnings,
                    "discovered": discovered, "window_start": local_date.isoformat(),
                    "window_end": (local_date+timedelta(days=self.settings.days_ahead)).isoformat()}
        self.store.set("snapshot", snapshot)
        partial = any(x["warnings"] or x["analysis"] is None for x in output)
        self.store.set("attempt", {"at": attempted_at, "status": "partial" if partial else "success",
                                   "message": "Atualização concluída com avisos." if partial else "Atualização concluída."})

    async def run(self):
        while True:
            try:
                await self.refresh()
            except Exception:
                # Não imprime respostas, chaves nem URLs autenticadas.
                self.store.set("attempt", {"at": datetime.now(timezone.utc).isoformat(), "status": "error",
                                           "message": "Falha interna na atualização. Consulte os logs operacionais do servidor."})
            await asyncio.sleep(self.settings.refresh_minutes*60)

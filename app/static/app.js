'use strict';
const $ = id => document.getElementById(id);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const pct = value => Number.isFinite(value) ? `${(value * 100).toLocaleString('pt-BR', {maximumFractionDigits:1})}%` : '—';
const num = value => Number.isFinite(value) ? value.toLocaleString('pt-BR', {maximumFractionDigits:2, minimumFractionDigits:2}) : '—';
let data = null, disconnected = false;
const date = (value, options={}) => value ? new Date(value).toLocaleString('pt-BR', {timeZone:data?.timezone || 'America/Sao_Paulo', ...options}) : '—';
const dateKey = value => new Intl.DateTimeFormat('sv-SE', {timeZone:data.timezone, year:'numeric', month:'2-digit', day:'2-digit'}).format(new Date(value));
const eligible = row => !disconnected && !data?.stale && row.eligible && !row.stale;
function bestFor(game) {
  return game.opportunities.find(row => eligible(row) && (!$('market').value || row.market === $('market').value) && (!$('bookmaker').value || row.bookmaker === $('bookmaker').value));
}
function options(id, rows) {
  const select = $(id), selected = select.value;
  select.querySelectorAll('option:not(:first-child)').forEach(option => option.remove());
  rows.forEach(([value, label]) => {const option = document.createElement('option'); option.value=value; option.textContent=label; select.append(option);});
  if ([...select.options].some(option => option.value === selected)) select.value=selected;
}
function summary() {
  $('count').textContent = data.fixtures.length;
  $('analyzed').textContent = data.fixtures.filter(game=>game.analysis?.probabilities).length;
  $('opportunities').textContent = data.fixtures.reduce((n, game)=>n+game.opportunities.filter(eligible).length, 0);
  $('quota').textContent = `${data.quota.used} / ${data.quota.limit}`;
  $('window').textContent = data.window_start ? `${data.window_start.split('-').reverse().join('/')} a ${data.window_end.split('-').reverse().join('/')}` : 'Janela configurada no servidor';
  $('updated').textContent = `Última atualização: ${date(data.updated_at, {dateStyle:'short',timeStyle:'short'})} · ${data.timezone}`;
  $('connection').textContent = !data.configured ? 'Integração aguardando chave' : data.refreshing ? 'Atualização em andamento' : data.last_attempt.status === 'error' ? 'Falha na última atualização' : data.stale ? 'Dados aguardando atualização' : 'Servidor conectado · atualização automática';
  const messages = [];
  if (!data.configured) messages.push('<strong>Conecte sua API para começar</strong>Configure <code>API_FOOTBALL_KEY</code> no arquivo .env do servidor e reinicie a aplicação. Nenhuma partida, estatística ou cotação será preenchida artificialmente.');
  else {
    if (data.last_attempt.status === 'error') messages.push(`<strong>Atualização indisponível</strong>${escapeHTML(data.last_attempt.message)} Os dados anteriores, se existentes, continuam identificados pelo horário de coleta.`);
    if (data.stale) messages.push('Os dados estão desatualizados ou aguardando a primeira coleta. Comparações antigas não são elegíveis.');
    if (!data.integration.odds) messages.push('Odds desativadas. Para comparar preços, configure ENABLE_ODDS=true somente com acesso autorizado pelo fornecedor.');
    data.warnings.forEach(w=>messages.push(escapeHTML(w)));
    const target=data.integration.preferred_bookmaker_name;
    if (target && !data.integration.preferred_bookmaker_id) messages.push(`Casa de interesse: ${escapeHTML(target)}. Cobertura não confirmada; as odds disponíveis podem ser de outras casas. Configure o ID do fornecedor apenas após confirmar a correspondência.`);
    else if (target) messages.push(`Casa de interesse: ${escapeHTML(target)}. Comparações limitadas ao ID ${data.integration.preferred_bookmaker_id} configurado no fornecedor.`);
  }
  $('notice').classList.toggle('visible', messages.length>0);
  $('notice').innerHTML = messages.join('<br>');
}
function recentHTML(analysis, side, name, detailed) {
  const recent=analysis?.[`${side}_recent`];
  if (!recent) return '';
  let stats='';
  if (detailed) stats=Object.entries(detailed).map(([key,row])=>`<p>${{corners:'Escanteios',yellow_cards:'Cartões amarelos',red_cards:'Cartões vermelhos'}[key]}: ${num(row.mean)} por jogo · ${row.sample} jogos informados</p>`).join('');
  return `<div><h3>${escapeHTML(name)}</h3><div class="form">${recent.form.map(v=>`<span class="${escapeHTML(v)}">${escapeHTML(v)}</span>`).join('')}</div><p>Mais recente à esquerda · ${recent.sample} jogos da temporada</p><p>Gols marcados: ${num(recent.goals_for)} · sofridos: ${num(recent.goals_against)} por jogo</p>${stats}</div>`;
}
function card(game) {
  const a=game.analysis, p=a?.probabilities, best=bestFor(game), confidence=a?.confidence || 'insuficiente';
  let chart = `<div class="reason">${escapeHTML(a?.reason || 'Análise indisponível: histórico real ainda não foi obtido.')}</div>`;
  if (p) {
    const h=p.home*100, d=p.draw*100, away=p.away*100;
    chart=`<div class="probability-section"><div><div class="micro-heading">RESULTADO · 90 MINUTOS</div><svg class="prob-chart" viewBox="0 0 100 4" preserveAspectRatio="none" role="img" aria-label="Casa ${pct(p.home)}, empate ${pct(p.draw)}, visitante ${pct(p.away)}"><rect class="home-bar" x="0" y="0" width="${h}" height="4"/><rect class="draw-bar" x="${h}" y="0" width="${d}" height="4"/><rect class="away-bar" x="${h+d}" y="0" width="${away}" height="4"/></svg><div class="prob-legend"><span>Casa<strong>${pct(p.home)}</strong></span><span>Empate<strong>${pct(p.draw)}</strong></span><span>Visitante<strong>${pct(p.away)}</strong></span></div></div><div><div class="micro-heading">MERCADOS DE GOLS</div><div class="goals-row"><span>Mais de 2,5 gols</span><strong>${pct(p['over_2.5'])}</strong></div><div class="goals-row"><span>Menos de 2,5 gols</span><strong>${pct(p['under_2.5'])}</strong></div><div class="goals-row"><span>Ambas marcam</span><strong>${pct(p.btts_yes)}</strong></div></div></div>`;
  }
  const oddsHTML=best ? `<div class="best"><div><div class="micro-heading">VANTAGEM NA SENSIBILIDADE · ESTIMATIVA</div><h3>${escapeHTML(best.label)} · odd ${num(best.odd)}</h3><p>${escapeHTML(best.bookmaker)} · atualizada ${date(best.updated_at,{timeStyle:'short',dateStyle:'short'})}</p></div><div class="best-number">+${pct(best.expected_value)}<small>EV por unidade · cenário menor ${pct(best.sensitivity_ev)}</small></div></div>` : `<div class="no-odds">${game.started ? 'Partida iniciada: comparações de pré-jogo inelegíveis.' : game.opportunities.length ? 'Nenhuma vantagem elegível com os filtros e a atualização atuais.' : 'Sem odds comparáveis disponíveis. A ausência de preço impede calcular vantagem.'}</div>`;
  const quotes=game.opportunities.filter(row=>(!$('market').value || row.market===$('market').value) && (!$('bookmaker').value || row.bookmaker===$('bookmaker').value));
  const table=quotes.length ? `<div class="table-wrap"><table><caption>Comparação de odds · maior vantagem conservadora primeiro</caption><thead><tr><th>Mercado / casa</th><th>Prob.</th><th>Odd</th><th>Justa</th><th>EV</th><th>EV menor*</th><th>Status</th><th>Prob. sem margem</th><th>Atualização</th></tr></thead><tbody>${quotes.map(row=>`<tr><td>${escapeHTML(row.label)}<br>${escapeHTML(row.bookmaker)}</td><td>${pct(row.probability)}</td><td>${num(row.odd)}</td><td>${num(row.fair_odd)}</td><td class="${row.expected_value>0?'positive':'negative'}">${pct(row.expected_value)}</td><td>${pct(row.sensitivity_ev)}</td><td>${row.stale||disconnected?'Inelegível / desatualizada':escapeHTML(row.classification)}</td><td>${pct(row.no_vig_probability)}</td><td>${date(row.updated_at,{dateStyle:'short',timeStyle:'short'})}</td></tr>`).join('')}</tbody></table></div><p>* Menor EV com taxas de gols variando ±15%; não é intervalo estatístico. Odds podem mudar antes da aposta.</p>` : '';
  const h2h=a?.h2h?.length ? `<h3>Confrontos diretos nesta liga e temporada</h3>${a.h2h.map(r=>`<p>${date(r.date,{dateStyle:'short'})} · ${escapeHTML(r.home)} ${num(r.goals.home)} × ${num(r.goals.away)} ${escapeHTML(r.away)}</p>`).join('')}` : '<p>Confrontos diretos: sem jogos informados nesta liga e temporada.</p>';
  const injuries=game.injuries ? `<h3>Desfalques informados pelo fornecedor</h3>${game.injuries.players.length ? game.injuries.players.map(r=>`<p>${escapeHTML(r.team)} · ${escapeHTML(r.player)} · ${escapeHTML(r.type)} / ${escapeHTML(r.reason)}</p>`).join('') : '<p>Não informados; não confirma ausência de desfalques.</p>'}` : '<p>Desfalques: integração desativada ou dados indisponíveis.</p>';
  const samples=a ? `<p>Amostra: ${a.sample.league} jogos da liga · casa no mando: ${a.sample.home_venue} · visitante fora: ${a.sample.away_venue}.</p>` : '';
  return `<article class="game"><div class="game-top"><span class="league-name">${escapeHTML(game.league.name)} · ${escapeHTML(game.league.country)} · ${escapeHTML(game.league.season)}</span><span class="coverage ${confidence}">Cobertura ${confidence}</span></div><div class="game-content"><div class="match"><div><div class="teams">${escapeHTML(game.home.name)}<span class="versus">×</span>${escapeHTML(game.away.name)}</div><div class="venue">${escapeHTML(game.venue || 'Estádio não informado')}${game.started?' · partida iniciada':''}</div></div><div class="kickoff">${date(game.kickoff,{hour:'2-digit',minute:'2-digit'})}<small>${date(game.kickoff,{day:'2-digit',month:'short'})}</small></div></div>${chart}${oddsHTML}</div><details class="detail"><summary>Estatísticas, preços e fontes</summary><div class="detail-body"><div class="context-grid">${recentHTML(a,'home',game.home.name,game.detailed_stats?.home)}${recentHTML(a,'away',game.away.name,game.detailed_stats?.away)}</div>${!game.detailed_stats?'<p>Escanteios e cartões: integração detalhada desativada ou dados indisponíveis.</p>':''}${h2h}${injuries}${samples}${a?.rates?`<p>Gols esperados pelo modelo: casa ${num(a.rates.home)} · visitante ${num(a.rates.away)}.</p>`:''}${table}<ul>${(a?.limitations || []).map(text=>`<li>${escapeHTML(text)}</li>`).join('')}</ul><div class="warning-list">${game.warnings.map(text=>`<p>${escapeHTML(text)}</p>`).join('')}</div><div class="metadata">Fonte: ${escapeHTML(game.source)} · Modelo: ${escapeHTML(a?.model_version || 'indisponível')}<br>Agenda coletada: ${date(game.fixture_fetched_at,{dateStyle:'short',timeStyle:'short'})}<br>Histórico coletado: ${date(game.history_fetched_at,{dateStyle:'short',timeStyle:'short'})} · análise calculada: ${date(game.analyzed_at,{dateStyle:'short',timeStyle:'short'})}</div></div></details></article>`;
}
function render() {
  if (!data) return;
  const search=$('search').value.toLocaleLowerCase('pt-BR');
  let games=data.fixtures.filter(game => `${game.home.name} ${game.away.name} ${game.league.name}`.toLocaleLowerCase('pt-BR').includes(search)
    && (!$('league').value || String(game.league.id)===$('league').value)
    && (!$('date').value || dateKey(game.kickoff)===$('date').value)
    && (!$('confidence').value || (game.analysis?.confidence || 'insuficiente')===$('confidence').value)
    && (!$('only-value').checked || bestFor(game)));
  games.sort((a,b)=>$('sort').value==='value' ? (bestFor(b)?.sensitivity_ev ?? -Infinity)-(bestFor(a)?.sensitivity_ev ?? -Infinity) || a.kickoff.localeCompare(b.kickoff) : a.kickoff.localeCompare(b.kickoff));
  $('visible-count').textContent=`(${games.length})`;
  if (games.length) $('games').innerHTML=games.map(card).join('');
  else {
    const title=!data.configured?'Seu painel está pronto para receber dados':data.refreshing?'Buscando jogos e estatísticas':data.fixtures.length?'Nenhum jogo corresponde aos filtros':'Nenhuma partida disponível nesta janela';
    const message=!data.configured?'Adicione sua chave API-Football no servidor. Jogos serão encontrados automaticamente por data e campeonato, sem cadastro manual.':data.refreshing?'A primeira coleta pode levar alguns minutos, conforme o número de consultas.':data.fixtures.length?'Ajuste os filtros para explorar as partidas coletadas.':'Confira a janela de datas, as ligas configuradas, os avisos da integração e a cobertura do seu plano.';
    $('games').innerHTML=`<div class="empty"><div class="empty-icon">${data.configured?'◷':'∑'}</div><h3>${title}</h3><p>${message}</p></div>`;
  }
}
async function load() {
  $('reload').disabled=true;
  try {
    const response=await fetch('/api/dashboard',{cache:'no-store',signal:AbortSignal.timeout(15000)});
    if (!response.ok) throw new Error('dashboard');
    data=await response.json(); disconnected=false;
    options('league',[...new Map(data.fixtures.map(game=>[game.league.id,[String(game.league.id),game.league.name]])).values()]);
    options('bookmaker',[...new Set(data.fixtures.flatMap(game=>game.opportunities.map(row=>row.bookmaker)))].sort().map(value=>[value,value]));
    options('date',[...new Set(data.fixtures.map(game=>dateKey(game.kickoff)))].sort().map(value=>[value,value.split('-').reverse().join('/')]));
    summary(); render();
  } catch {
    disconnected=true;
    $('connection').textContent='Sem conexão com o servidor';
    $('notice').classList.add('visible');
    $('notice').textContent='Não foi possível consultar o servidor. Verifique a conexão e recarregue. Dados anteriores, se visíveis, não permitem identificar vantagens atuais.';
    if (data) { $('opportunities').textContent='—'; render(); }
    else $('games').innerHTML='<div class="empty"><div class="empty-icon">!</div><h3>Servidor indisponível</h3><p>Tente recarregar o painel quando a conexão estiver disponível.</p></div>';
  } finally {$('reload').disabled=false;}
}
['search','league','date','confidence','market','bookmaker','only-value','sort'].forEach(id=>$(id).addEventListener(id==='search'?'input':'change',render));
$('clear').addEventListener('click',()=>{['search','league','date','confidence','market','bookmaker'].forEach(id=>$(id).value='');$('only-value').checked=false;$('sort').value='time';render();});
$('reload').addEventListener('click',load);
load();setInterval(load,60000);

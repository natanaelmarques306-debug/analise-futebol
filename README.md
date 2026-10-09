# Análise Futebol

Aplicação web responsiva em português com processamento estatístico em **Python/FastAPI**, integração direta com **API-Football v3 (API-Sports)**, persistência SQLite e atualização automática. O repositório não contém partidas, odds ou estatísticas de demonstração para produção. Sem uma chave válida, o painel funciona e informa que a integração precisa ser configurada.

## Executar

Requer Python 3.11+ e acesso de saída HTTPS a `v3.football.api-sports.io`.

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e '.[dev]'
cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
# Edite .env com a chave e as configurações do seu plano.
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Abra **http://localhost:8000**. No celular conectado à mesma rede, acesse `http://IP_DO_COMPUTADOR:8000` e permita a porta 8000 no firewall local. Para acesso pela internet, publique com HTTPS; veja [Publicação](docs/publicacao.md).

O agendador inicia uma coleta ao iniciar o servidor e repete a cada `REFRESH_MINUTES`. Não é necessário manter o navegador aberto. A página consulta o estado do servidor a cada 60 segundos; **Recarregar painel** apenas consulta o cache e não consome consultas esportivas. A primeira coleta pode levar alguns minutos. Use um único processo/worker e uma única réplica, pois o agendador está embutido no servidor.

## Credenciais e cobertura

1. Crie uma conta em [API-Football](https://www.api-football.com/) e obtenha uma **chave direta API-Sports** no dashboard. Uma chave RapidAPI não é compatível com este adaptador.
2. Coloque `API_FOOTBALL_KEY` no `.env` local ou nos secrets da hospedagem. **Não coloque a chave no navegador, no Git, em capturas de tela ou em mensagens públicas.**
3. Escolha ligas em `LEAGUE_IDS`, separadas por vírgula. O padrão `71` corresponde à Série A brasileira. Confirme IDs, temporadas e cobertura no endpoint `/leagues` do fornecedor. Nenhuma partida precisa ser cadastrada.
4. O plano precisa permitir jogos **da temporada atual e de datas futuras** e histórico suficiente da mesma temporada. Planos gratuitos podem limitar temporadas, endpoints e acesso por `date`/`last`/`next`; uma chave gratuita pode não permitir os jogos do dia. Confira as condições vigentes no fornecedor.
5. `ENABLE_ODDS=true`, `ENABLE_INJURIES=true` e `ENABLE_DETAILED_STATS=true` são opcionais e devem ser ativados apenas se o plano autorizar esses endpoints e a liga tiver cobertura. Não é necessária credencial de uma casa de apostas: as odds são fornecidas pela API autorizada. As odds podem não existir para uma partida/mercado.

**Não houve validação de uma coleta real sem credenciais.** Os testes da integração usam respostas sintéticas isoladas em `tests/`; essas respostas nunca são instaladas no banco do aplicativo. O sistema faz chamadas reais quando configurado. Não há fallback para dados inventados.

### Configuração

| Variável | Padrão | Uso |
| --- | --- | --- |
| `API_FOOTBALL_KEY` | vazia | Credencial do servidor |
| `LEAGUE_IDS` | `71` | Campeonatos a descobrir automaticamente |
| `TIMEZONE` | `America/Sao_Paulo` | Datas da agenda e horários do painel |
| `DAYS_AHEAD` | `3` | Hoje mais os próximos 3 dias (0–7) |
| `REFRESH_MINUTES` | `30` | Intervalo de coleta, mínimo 5 |
| `DATABASE_PATH` | `data/football.sqlite3` | Cache, estado e cota persistentes |
| `MAX_REQUESTS_PER_DAY` | `90` | Limite local por dia UTC; não substitui a cota real |
| `MAX_REQUESTS_PER_REFRESH` | `35` | Teto de chamadas de uma coleta |
| `MAX_FIXTURES` | `12` | Analisa as partidas futuras mais próximas; avisa sobre excedentes |
| `ENABLE_ODDS` | `false` | Endpoint de odds autorizado |
| `ENABLE_INJURIES` | `false` | Desfalques disponíveis na API |
| `ENABLE_DETAILED_STATS` | `false` | Escanteios/cartões dos últimos 5 jogos de cada equipe |
| `ODDS_MAX_AGE_MINUTES` | `60` | Idade máxima da atualização informada pelo fornecedor |
| `PREFERRED_BOOKMAKER_NAME` | `83bets` | Casa de interesse; não confirma cobertura |
| `PREFERRED_BOOKMAKER_ID` | vazio | ID verificado na API; se informado, só compara essa casa |
| `ADMIN_TOKEN` | vazia | Token opcional para atualização manual protegida |

O custo básico é uma consulta de agenda por **liga × dia**, com TTL de 15 minutos para hoje e 6 horas para os próximos dias, mais uma consulta de histórico por liga/temporada com TTL de 6 horas. Detalhes podem exigir até 10 consultas adicionais por partida (cache de 7 dias), desfalques uma consulta (TTL 1 hora), e odds uma ou mais páginas (TTL 5 minutos). Consultas repetidas ao painel não atingem o fornecedor. Com muitas ligas/detalhes, ajuste cota, intervalo e número de partidas ao plano. Sem cota, análises ausentes ficam identificadas e são tentadas novamente nas próximas coletas. O limite diário é persistente e compartilhado com o processo; outras aplicações usando a mesma chave podem consumir a cota real fora deste contador.

## Casa de interesse: 83bets

A casa indicada pelo usuário é [83bets](https://83bets.bet/). **Não há confirmação de que a API-Football ofereça suas odds.** O sistema não acessa a conta da casa, não captura suas páginas e não realiza apostas. As odds exibidas sempre identificam a casa retornada pelo fornecedor.

Confirme a cobertura em `/odds/bookmakers` e em `/odds?fixture=...` no fornecedor, incluindo a correspondência comercial/domínio da casa. Se houver um ID confirmado, configure `PREFERRED_BOOKMAKER_ID`; o servidor limitará as comparações a esse ID. Sem ID, as odds são de todas as casas disponíveis e podem ser filtradas no painel. Não atribua à 83bets a cotação de outra casa. Se ela não estiver coberta, será necessária uma integração oficial autorizada adicional; esta versão não substitui preços ausentes por números inventados.

## Funcionalidades

- Descoberta automática por data e liga, sem cadastro manual; somente pré-jogo `NS` futuro.
- Histórico concluído `FT`, excluindo prorrogação, jogos incompletos, outras temporadas/ligas e dados posteriores ao início da partida analisada.
- Forma recente, gols a favor/contra, mando e confrontos diretos na mesma liga/temporada.
- Escanteios, cartões e desfalques reais como contexto opcional; campo não informado continua ausente (não vira zero).
- Probabilidades de 1X2, acima/abaixo de 1,5/2,5/3,5 gols, ambas marcam e dupla chance.
- Comparação de odds em mercados reconhecidos, odd justa, valor esperado e margem de grupos completos da mesma casa.
- Ranking por valor esperado conservador, cobertura da amostra e filtros. Partidas iniciadas e odds antigas ficam inelegíveis.
- Histórico de coleta, avisos sobre erros e cache persistente. Falha na descoberta preserva o snapshot anterior com a indicação da falha; coleta parcial marca os dados indisponíveis.

## Modelo e limites

Leia [Metodologia](docs/metodologia.md). É uma **primeira versão estatística**, não um modelo de aprendizado treinado ou um serviço de lucro garantido. Confiança é cobertura da amostra, não taxa de acerto. Não há backtest de calibração nesta versão. Desfalques, cartões, escanteios e H2H são contexto, sem ajustes numéricos arbitrários no modelo de gols. Probabilidades de cartões, escanteios, handicaps e mercados com devolução não estão implementadas. Dados não disponíveis não são estimados como se fossem reais.

## Testes

```bash
pytest -q
# Opcional, se Node estiver instalado:
node --check app/static/app.js
```

Teste opcional de navegador (servidor rodando **sem chave**, com Playwright/Chromium):

```bash
npm ci
npx playwright install chromium
npm run test:browser
# Chromium já instalado: CHROMIUM_PATH=/usr/bin/chromium npm run test:browser
```

Os cenários com jogos sintéticos são interceptados apenas no navegador de teste e não alteram o banco nem a API do servidor.

Os testes verificam identidades matemáticas, ausência de vazamento temporal, dados insuficientes, EV, margem, odds antigas/inválidas, paginação, cache, cota persistente, descoberta automática, falhas de atualização e autenticação. CI executa em Python 3.11 e 3.12. Para validação com credencial real, siga [Operação e verificação](docs/operacao.md).

## API da aplicação

- `GET /health`: saúde do servidor e indicação de chave configurada (não valida o plano).
- `GET /api/dashboard`: snapshot, fontes, horários, avisos, probabilidades e oportunidades.
- `POST /api/refresh`: coleta manual; exige `Authorization: Bearer <ADMIN_TOKEN>`. Desativada sem token. Não coloque o token no frontend. Não há autenticação nos endpoints de leitura; se os dados forem privados, use controle de acesso no proxy.

Documentação local de endpoints: `/docs`. Especificação OpenAPI para clientes de API: `/openapi.json`. Os recursos do painel e da documentação são locais, sem dependência de CDN.

## Estrutura

```text
app/config.py          configuração e validação
app/provider.py        cliente API-Football, cache e limites
app/storage.py         persistência SQLite
app/model.py           processamento estatístico Poisson
app/odds.py            normalização de mercados e cálculo de valor
app/service.py         descoberta, análise e agendador
app/main.py            API e servidor do painel
app/static/            HTML/CSS/JavaScript responsivos, sem CDN
tests/                dados sintéticos somente para testes
docs/                 metodologia, operação e publicação
```

## Aparência e validação

Capturas do aplicativo real executando **sem credenciais**, sem dados fictícios de produção: [computador](docs/imagens/painel-desktop.png) e [celular](docs/imagens/painel-celular.png). A coleta precisa ser configurada para preencher partidas e análises. Veja também o [registro de verificação](docs/verificacao.md).

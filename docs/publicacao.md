# Publicar com Python e disco persistente

Esta aplicação precisa de um servidor Python sempre ativo. Hospedagem puramente estática não executa a coleta. Nenhuma publicação remota é feita automaticamente por este repositório.

## Render (Web Service)

1. Conecte o repositório `analise-futebol` e a branch com a aplicação.
2. Crie um Web Service Python. Build: `pip install .`.
3. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`.
4. Adicione `API_FOOTBALL_KEY` como variável secreta, `LEAGUE_IDS` e opções do plano.
5. Adicione disco persistente em `/var/data` e `DATABASE_PATH=/var/data/football.sqlite3`.
6. Use uma instância/réplica sempre ativa. Planos que suspendem o processo não garantem atualizações periódicas. O disco persistente pode exigir plano pago.
7. Configure health check `/health`; confirme a coleta em `/api/dashboard`, não apenas o health check.
8. Use a URL HTTPS gerenciada e, se necessário, autenticação de leitura num proxy/serviço de acesso antes da aplicação.

O repositório contém `render.yaml` com disco e uma instância para facilitar a configuração. Revise os custos vigentes antes de criar o serviço. `API_FOOTBALL_KEY` fica pendente para você preencher. O blueprint usa a branch padrão selecionada no provedor; escolha a branch correta ou faça merge da implementação.

## VPS com Docker Compose

Requer Docker com plugin Compose e proxy reverso HTTPS disponível. A imagem roda sem root. O volume nomeado preserva cache e cota entre reinícios.

```bash
cp .env.example .env
# Configure chave, ligas, limites e integrações autorizadas.
docker compose up -d --build
docker compose logs --tail=100
curl http://127.0.0.1:8000/health
```

Por padrão Compose publica **somente em 127.0.0.1**. Configure Nginx/Caddy/Traefik para encaminhar seu domínio HTTPS a `127.0.0.1:8000`. Não exponha o token administrativo em scripts públicos. Se quiser acesso LAN direto, altere o bind para um endereço da rede privada conscientemente.

Não aumente workers/réplicas: cada processo iniciaria seu próprio agendador. Para escalar, extraia a coleta para um único worker e use banco/filas compartilhados antes de multiplicar servidores.

## Operação

- Libere saída TLS para `v3.football.api-sports.io`; mantenha validação de certificados.
- Guarde `.env` fora do controle de versão e proteja o acesso à hospedagem.
- A leitura do painel é pública por padrão. Para uso privado, configure controle de acesso no proxy.
- Garanta que sua licença permite exibir/redistribuir estatísticas e odds antes de tornar o painel público.
- Faça backup do volume SQLite com a API de backup do SQLite ou com o serviço parado; não copie apenas o `.sqlite3` ativo ignorando o WAL.
- Reinicie o processo após alterar configuração. Sem persistência, a cota local será reiniciada e não refletirá consultas já consumidas no fornecedor.
- Verifique snapshots, avisos e consumo no fornecedor. `/health` verifica o processo, não credenciais/cobertura esportiva.

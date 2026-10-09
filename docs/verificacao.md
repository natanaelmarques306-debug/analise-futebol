# Registro de verificação

Verificação local realizada em 09/10/2026.

- **Python 3.12:** 42 testes passaram. Uma advertência de depreciação interna Starlette/AnyIO, sem falha de teste.
- **Navegador Chromium com Playwright:** painel sem chave, tamanho de computador (1440 px) e celular (390 px), ausência de rolagem horizontal, documentação local, escape de nomes externos, filtros por mercado/casa, busca e inelegibilidade de odds vencidas.
- **JavaScript:** validação sintática com `node --check`.
- **Pacote Python:** wheel construída, com os quatro recursos estáticos do painel e documentação local incluídos.
- **Docker Compose:** configuração validada com `.env` sem credenciais.
- **Imagem Docker:** build concluído; teste de execução verificou usuário sem root, SQLite gravável, startup do agendador, `/health`, `/api/dashboard`, painel, JavaScript e documentação.
- **Git:** `.env`, banco, ambientes virtuais, arquivos temporários e artefatos de build excluídos do versionamento.

Os dados com partidas usados nos testes são **sintéticos e isolados**, incluindo interceptação exclusiva do navegador. Nenhum jogo fictício foi carregado no banco do servidor ou usado como dado real. As capturas em `docs/imagens/` mostram o aplicativo sem chave e sem partidas.

**Não verificado nesta sessão:** coleta esportiva real, cobertura/identidade da 83bets no fornecedor, calibração histórica do modelo, publicação em hospedagem remota ou acesso real por um aparelho celular. Essas validações dependem, respectivamente, de credenciais/plano autorizado, identificação do bookmaker, backtest temporal, uma conta de hospedagem e acesso de rede ao servidor. O teste responsivo usa navegador em viewport móvel.

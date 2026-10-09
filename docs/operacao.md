# Verificação de uma coleta real

Sem a credencial e a licença do fornecedor não é possível comprovar dados atuais. Não há fixtures de demonstração em produção.

1. Configure `API_FOOTBALL_KEY`, uma liga com jogos futuros, temporada atual e histórico disponível. Mantenha as opções avançadas desligadas na primeira coleta.
2. Inicie o servidor com um worker. Espere a primeira coleta e abra `/api/dashboard`.
3. Confira `configured=true`, `last_attempt.status`, `updated_at`, `warnings` e `quota`. `configured=true` significa chave preenchida, não autorização confirmada.
4. Compare ao menos uma partida e seu início com o painel/API do fornecedor. Confira a janela de datas em `TIMEZONE` e a liga configurada.
5. Confira `analysis.sample` e `history_fetched_at`. Sem amostra mínima, `probabilities=null` é o comportamento correto.
6. Se autorizado, ative `ENABLE_ODDS=true` e reinicie. Compare bookmaker, linha, preço e `updated_at` com o fornecedor. Uma lista vazia pode indicar falta de odds recentes, mercado não suportado, plano sem acesso ou histórico insuficiente; veja os avisos.
7. Ative detalhes/desfalques somente com cota suficiente. Verifique a contagem de observações por indicador; campos ausentes permanecem ausentes.
8. Confirme uma segunda atualização automática pelo timestamp. Fechar o navegador não deve interromper a coleta.

## Diagnóstico

| Sintoma | Verificação |
| --- | --- |
| Chave configurada, erro de acesso | Chave direta API-Sports, licença e endpoints liberados no plano |
| Nenhum jogo | Liga, período, jogos somente `NS` futuros, cobertura e datas permitidas pelo plano |
| Sem probabilidades | Ao menos 40 partidas `FT` da liga e 5 de cada equipe no respectivo mando na mesma temporada |
| Sem odds | Opção ativada, plano autorizado, timestamp recente e mercados reconhecidos |
| Cota excedida | Limites locais e limite real no dashboard API-Sports; outras aplicações podem consumir a mesma chave |
| Informações parciais | Reduza ligas/partidas, desative detalhes, aumente intervalo ou contrate capacidade apropriada |
| Dados envelhecem | Processo suspenso, agendador parado, chave inválida, rede ou cota indisponível |
| Erro de rede neste ambiente gerenciado | Credencial e domínio esportivo precisam estar autorizados na configuração de rede do ambiente |

## Coleta manual opcional

Configure um token administrativo forte no servidor. `POST /api/refresh` exige cabeçalho `Authorization: Bearer <token>`. Use um cliente de API com o token armazenado de forma segura, sem colocá-lo em histórico de shell, URL ou frontend. A coleta automática é suficiente para uso normal. Uma coleta já em execução retorna `already_running`.

## Dados persistidos

SQLite contém cache de respostas esportivas, snapshot do painel, estado da última tentativa e contador diário UTC. Não armazena a chave ou token administrativo. Retenção não é limitada nesta primeira versão; monitore crescimento do volume. Cache de histórico e estatísticas pode ser limpo em manutenção programada, mantendo o contador de cota do dia. Atualização de dados históricos exige aguardar o TTL ou invalidar o cache com o servidor parado.

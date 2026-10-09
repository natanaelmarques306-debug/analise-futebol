# Metodologia da versão 0.1

## Proveniência e amostra

Todas as entradas de produção vêm da API-Football v3. O snapshot mantém fonte, início do jogo, horário de coleta do histórico, cálculo e atualização das odds. `updated_at` do dashboard é a conclusão da coleta do snapshot, não significa que cada estatística foi recolhida naquele instante: os endpoints têm TTLs diferentes. A atualização das odds usada para elegibilidade é a indicada pelo fornecedor, não o horário em que foi consultada.

A descoberta usa a data no fuso configurado e ligas escolhidas. Para cada partida, o histórico é filtrado pela mesma liga/temporada, status `FT`, gols numéricos válidos e data **anterior ao início**. Partidas com prorrogação (`AET`/`PEN`) ficam fora para evitar mistura com mercados de 90 minutos. Os 10 jogos mais recentes de cada equipe são contexto; o modelo usa no máximo 10 da equipe mandante **em casa** e 10 da visitante **fora**.

Exige pelo menos 40 jogos da liga e 5 de cada equipe no respectivo mando. Início de temporada, promoção, cobertura limitada e ligas curtas podem deixar o modelo indisponível. O sistema não mistura temporadas para preencher essas lacunas.

## Taxas de gols

1. Calcule médias de gols da liga em casa (`B_h`) e fora (`B_a`).
2. Para os jogos recentes no mando, atribua peso `w_i = 0.5 ** (i/5)`, com `i=0` no mais recente: meia-vida de 5 jogos.
3. Regularize cada taxa: `R = (sum(w_i*gols_i) + 3*B) / (sum(w_i)+3)`. Os 3 jogos equivalentes de regularização são uma escolha inicial de modelagem, explicitada e ainda não calibrada.
4. `lambda_h = R_mandante_marca_em_casa * R_visitante_sofre_fora / B_h`.
5. `lambda_a = R_visitante_marca_fora * R_mandante_sofre_em_casa / B_a`.
6. A matriz de placares usa Poisson independente: `P(H=i,A=j) = Pois(i;lambda_h)*Pois(j;lambda_a)`.

A distribuição usa 0 a 40 gols e normaliza a massa numérica; taxas acima de 15 são recusadas. Esses limites são salvaguardas numéricas, não valores esportivos. O modelo considera independência dos gols, não aplica correção Dixon–Coles, não ajusta força individual dos adversários, xG, lesões, descanso, viagens, mudanças de elenco, escalações ou campo neutro. O mando é o informado na partida pela API. Competições/campos neutros exigem cautela ou exclusão da liga configurada.

Vitória, empate, derrota, totais de gols e ambas marcam vêm da soma das células correspondentes. Dupla chance soma resultados compatíveis. Mercados se referem aos 90 minutos mais acréscimos, sem prorrogação.

## Escanteios, cartões, desfalques e H2H

Detalhes opcionais: média dos valores efetivamente informados nos últimos 5 jogos da equipe nessa liga/temporada. Cada indicador tem sua própria contagem de observações. `null` é ausência de informação e não zero. Vermelhos e amarelos são categorias separadas do fornecedor; não há inferência sobre cartões decorrentes de segundo amarelo.

Desfalques vêm de `/injuries?fixture=...`; uma lista vazia **não prova elenco completo**. Não há impacto numérico arbitrário atribuído a jogadores. H2H é limitado à temporada atual e serve como contexto, sem peso adicional para evitar dupla contagem do histórico.

Não calculamos probabilidades de escanteios, cartões ou handicaps nesta versão. Isso exige distribuições específicas, mais dados e validação.

## Odds e vantagem

O adaptador reconhece apenas nomes exatos dos mercados pré-jogo API-Football: `Match Winner`, `Goals Over/Under` nas linhas 1.5/2.5/3.5, `Both Teams Score`, `Double Chance`. Outras linhas/mercados são ignorados. Quotes precisam ser decimais finitas e maiores que 1. Os valores e a disponibilidade não são completados artificialmente.

Para `p` estimado e odd decimal `o`:

- Probabilidade implícita: `q=1/o`.
- Odd justa: `1/p`.
- Valor esperado por unidade: `EV=p*o-1`.
- Em grupo **completo e exclusivo**, na mesma casa/mercado/linha: margem `sum(q)-1` e probabilidade sem margem `q/sum(q)`.

Dupla chance tem resultados sobrepostos e **não** recebe normalização de margem. Essa probabilidade sem margem descreve o preço da casa, não é a estimativa independente do modelo. Não há custos, taxas, limites de aposta ou mudanças de preço incluídos. Não tratamos mercados com devolução ou liquidação parcial com a fórmula simplificada.

Odds sem timestamp, vencidas ou com timestamp mais de 5 minutos no futuro ficam fora da comparação. As páginas do endpoint são percorridas até o total, limitado a 10; erro/cota/paginação incompleta omite a comparação dessa partida. Após o início do jogo, a comparação de pré-jogo fica inelegível. Um snapshot vencido também fica inelegível; odds podem vencer antes do snapshot.

## Sensibilidade e confiança

Variamos cada `lambda` por fatores `0.85`, `1.0`, `1.15`, totalizando 9 cenários, e guardamos a menor probabilidade de cada mercado. `EV_menor = p_menor*o-1`. **Não é intervalo de confiança estatístico nem garantia de cobertura.** A variação de ±15% é uma análise inicial de sensibilidade, ainda não calibrada.

Cobertura **moderada**: ao menos 100 jogos da liga e 8 de cada equipe no mando; **baixa**: atende ao mínimo, mas não a esses limiares; **insuficiente**: sem probabilidades. Não oferecemos cobertura alta enquanto não houver validação.

- **Vantagem na sensibilidade**: EV menor positivo e cobertura moderada.
- **Vantagem frágil**: EV central positivo, mas falha em um desses critérios.
- **Sem vantagem**: EV central não positivo.

Ordenamos primeiro as vantagens na sensibilidade, depois o EV menor e o EV central. No painel, partidas são ordenadas por início ou pela melhor vantagem elegível no mercado filtrado. Não há recomendação de valor de aposta ou lucro garantido.

## Próxima validação necessária

Antes de usar estimativas para decisões monetárias, faça avaliação temporal fora da amostra com previsões produzidas usando somente dados conhecidos em cada data, odds arquivadas no instante da previsão, Brier score, log loss, curva de calibração e segmentação por liga/mercado. O histórico atual da API pode conter revisões posteriores; recriar previsões passadas sem snapshots não estabelece performance histórica fiel. Desempenho passado tampouco garante retorno futuro.

# Dataset: B2B SaaS Marketing Attribution — Brasil

## Visão Geral

Dataset sintético multi-tabela para análise de atribuição de marketing em
contexto B2B SaaS brasileiro. Simula 18 meses de dados de uma empresa de
CRM/ERP integrations vendendo para o mercado mid-market (50–500 funcionários).

**Gerado em:** 2026-05-20 16:06
**Período:** 2023-01-01 → 2024-06-30

## Volumes

| Tabela | Registros |
|---|---|
| accounts | 2,000 |
| leads | 7,962 |
| opportunities | 1,410 |
| ga4_sessions | 150,000 |
| touchpoints | 6,363 |
| channel_spend | 553 |
| content_assets | 21 |

## Decisões Metodológicas

### Geração Baseada em Processo (SCM Simplificado)
Dados gerados simulando o processo causal real do funil B2B:
`sessão → lead → MQL → oportunidade → fechamento`.
Cada etapa é condicional ao canal, indústria e porte da empresa.

### Cópula Gaussiana para Correlações
Variáveis contínuas correlacionadas foram geradas via decomposição de Cholesky,
preservando a estrutura de correlação especificada. Não há colunas
estatisticamente independentes que pareçam relacionadas.

### Ground Truth Causal
O campo `true_marginal_contribution` em `touchpoints` representa a contribuição
marginal REAL calculada pelo modelo generativo. Use para avaliar quão próximo
cada modelo heurístico (last-click, time-decay, etc.) chega da verdade causal.

### Heterogeneidade de Subpopulações
P(conversão) = f(canal, indústria, porte). Uma empresa de Agronegócio grande
que veio pelo LinkedIn tem P(won) diferente de uma startup de Tecnologia
pelo mesmo canal.

## Data Dictionary

### accounts.csv
| Campo | Tipo | Descrição |
|---|---|---|
| account_id | string | PK: ACC-NNNNN |
| company_name | string | Razão social sintética |
| email_domain | string | Domínio para matching com leads |
| industry | string | Setor (nullable — ~5% missing) |
| state | string | UF brasileira |
| size_class | string | pequena / media / grande (nullable — ~4% missing) |
| n_employees | int | Número de funcionários (50–500) |
| created_date | date | Data de entrada no CRM |

### leads.csv
| Campo | Tipo | Descrição |
|---|---|---|
| lead_id | string | PK: LEAD-NNNNNN |
| account_id | string | FK → accounts |
| email | string | Email de contato |
| first_touch_channel | string | Canal do primeiro contato |
| first_touch_session_id | string | FK → ga4_sessions |
| utm_source / utm_medium | string | Parâmetros UTM do first touch |
| campaign | string | Nome da campanha (com inconsistências intencionais) |
| landing_page | string | URL da página de conversão |
| lead_score | int | Score 1–100 (correlacionado com engagement) |
| lead_date | date | Data de criação do lead |
| is_mql | int | 0/1 — Marketing Qualified Lead |

### opportunities.csv
| Campo | Tipo | Descrição |
|---|---|---|
| opp_id | string | PK: OPP-NNNNN |
| lead_id | string | FK → leads |
| account_id | string | FK → accounts |
| first_touch_channel | string | Canal de aquisição original |
| stage | string | Closed Won / Closed Lost / Em Andamento |
| amount_brl | float | ACV em BRL |
| created_date | date | Data de criação da opp |
| close_date | date | Data de fechamento (nullable) |
| is_won | int | 0/1 |
| win_probability_hist | float | P(won) histórico do modelo generativo |
| stage_*_dt | date | Timestamps de entrada em cada estágio (série temporal) |

### ga4_sessions.csv
| Campo | Tipo | Descrição |
|---|---|---|
| session_id | string | PK: SES-NNNNNNNN |
| user_pseudo_id | string | ID anônimo do usuário |
| session_datetime | datetime | Timestamp com viés horário comercial |
| channel | string | Canal de aquisição |
| campaign | string | Nome da campanha |
| landing_page | string | Primeira URL da sessão |
| device_category | string | desktop / mobile / tablet |
| engagement_time_sec | int | Tempo de engajamento (correlacionado com events) |
| events_per_session | int | Número de eventos GA4 |
| is_bounce | int | 0/1 — sessão de uma única página |
| lead_id | string | FK → leads (nullable — ~15% anônimo) |

### touchpoints.csv
| Campo | Tipo | Descrição |
|---|---|---|
| touchpoint_id | string | PK: TP-NNNNNNN |
| opp_id | string | FK → opportunities |
| lead_id | string | FK → leads |
| touch_sequence | int | Posição na jornada (1 = first touch) |
| total_touches_in_journey | int | Total de touchpoints desta opp |
| touch_date | date | Data do touchpoint |
| days_before_opp_creation | int | Distância temporal até a criação da opp |
| channel | string | Canal deste touchpoint específico |
| touch_type | string | impression / click / form_fill / demo_request / sales_call / etc |
| engagement_score | int | Score 1–100 (correlacionado com touch_type) |
| is_first_touch | int | 0/1 |
| is_last_touch | int | 0/1 |
| **true_marginal_contribution** | float | **GROUND TRUTH: contribuição causal real (soma = 1 por opp)** |
| attributed_revenue_brl | float | Receita atribuída pelo ground truth |

### channel_spend.csv
| Campo | Tipo | Descrição |
|---|---|---|
| spend_id | string | PK |
| week_start / week_end | date | Período semanal |
| channel | string | Canal |
| spend_brl | float | Investimento em BRL |
| impressions | int | Impressões totais |
| clicks | int | Cliques totais |

## Análises Suportadas

1. **Last-Touch Attribution** — receita por canal final antes da opp
2. **First-Touch Attribution** — receita por canal de aquisição
3. **Linear Attribution** — crédito igual a todos os touchpoints
4. **Time-Decay Attribution** — decaimento exponencial (half-life configurável)
5. **Position-Based** — 40% first + 40% last + 20% middle
6. **Engagement-Weighted** — crédito proporcional ao engagement_score
7. **Ground Truth Comparison** — avaliar heurísticos contra true_marginal_contribution
8. **ROAS / CPQL / CPO** — via JOIN com channel_spend
9. **Cohort Analysis** — por mês de aquisição do lead
10. **Pipeline Velocity** — via stage_history timestamps em opportunities
11. **Survival Analysis** — via close_date + stage transitions
12. **Content Attribution** — via content_asset_id em touchpoints

## Limitações Conhecidas

- Sem dados pós-venda (renovações, expansão de ACV) — fora do escopo
- Autocorrelação setorial simplificada (não é um processo de Hawkes completo)
- Cross-device tracking não modelado explicitamente
- Walled gardens (Meta, Google) têm dados completos — na realidade haveria
  data gaps por limitações de pixel/cookie

## Como Usar

```python
import pandas as pd
import sqlite3

# Via CSV
accounts = pd.read_csv('accounts.csv')
touchpoints = pd.read_csv('touchpoints.csv')

# Via SQLite (recomendado para análises multi-tabela)
conn = sqlite3.connect('b2b_attribution.db')
df = pd.read_sql('''
    SELECT t.channel, SUM(t.attributed_revenue_brl) as ground_truth_revenue,
           COUNT(DISTINCT t.opp_id) as opps
    FROM touchpoints t
    JOIN opportunities o ON t.opp_id = o.opp_id
    WHERE o.is_won = 1
    GROUP BY t.channel
    ORDER BY ground_truth_revenue DESC
''', conn)
```

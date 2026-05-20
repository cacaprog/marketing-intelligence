"""
=============================================================================
GERADOR DE DATASET SINTÉTICO — ATRIBUIÇÃO DE MARKETING B2B SaaS (Brasil)
=============================================================================

PROPÓSITO
---------
Gera um conjunto de dados sintético multi-tabela para análise de atribuição
de marketing em contexto B2B SaaS brasileiro. O dataset simula o ciclo
completo: sessões web → leads → oportunidades → receita, com touchpoints
rastreados para múltiplos modelos de atribuição.

DECISÕES METODOLÓGICAS
----------------------
1. GERAÇÃO BASEADA EM PROCESSO (Nível 3 — SCM simplificado)
   Cada entidade é gerada como consequência causal da anterior, respeitando
   a estrutura temporal do funil. Não há sampling marginal independente.
   P(conversão) é sempre condicional ao contexto do canal + empresa.

2. CÓPULA GAUSSIANA para correlações intra-entidade
   Variáveis contínuas correlacionadas (engagement_time × events_per_session,
   lead_score × opp_amount) são geradas via scipy.stats multivariada,
   preservando a estrutura de correlação especificada.

3. GROUND TRUTH CAUSAL
   Cada touchpoint recebe um `true_marginal_contribution` calculado ANTES
   da observação, baseado no modelo generativo (não nos dados observados).
   Isso permite avaliar qual modelo heurístico de atribuição mais se aproxima
   da verdade causal.

4. HETEROGENEIDADE DE SUBPOPULAÇÕES
   P(conversão) é calculado como interação: canal × indústria × porte.
   Uma empresa de Agronegócio grande que veio por LinkedIn tem perfil
   diferente de uma startup de Tecnologia pelo mesmo canal.

5. AUTOCORRELAÇÃO SETORIAL SIMPLIFICADA
   Setor com deals fechados recentemente tem leve boost na P(lead → opp),
   simulando efeito de referência/word-of-mouth B2B.

OUTPUTS
-------
Cada dimensão é um arquivo CSV separado + SQLite com todas as tabelas:
  - accounts.csv          → empresas (CRM)
  - leads.csv             → contatos / first touch (CRM + GA4 bridge)
  - opportunities.csv     → oportunidades com histórico de estágio
  - ga4_sessions.csv      → sessões web (Analytics)
  - touchpoints.csv       → spine da atribuição (multi-touch)
  - channel_spend.csv     → investimento semanal por canal (para ROAS)
  - content_assets.csv    → ativos de conteúdo linkados a touchpoints
  - b2b_attribution.db    → SQLite com todas as tabelas e índices

VOLUMES
-------
  ~2.000 accounts / ~8.000 leads / ~1.200 opportunities
  ~150.000 ga4_sessions / ~25.000 touchpoints / ~18 meses de dados

=============================================================================
"""

import sqlite3
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker
from scipy.stats import norm

warnings.filterwarnings("ignore")

# Seed para reprodutibilidade
RNG = np.random.default_rng(42)
fake = Faker("pt_BR")
Faker.seed(42)

# =============================================================================
# MÓDULO 1 — CONFIGURAÇÃO CENTRAL
# =============================================================================
# Centralizar parâmetros aqui permite ajustar o dataset sem tocar na lógica.

CONFIG = {
    # Janela temporal: 18 meses
    "date_start": datetime(2023, 1, 1),
    "date_end": datetime(2024, 6, 30),

    # Volumes alvo
    "n_accounts": 2_000,
    "n_sessions_target": 150_000,

    # Funil global (taxas BASE — serão moduladas por canal e subpopulação)
    "funnel": {
        "visitor_to_lead":    0.025,   # 2.5% das sessões geram lead
        "lead_to_mql":        0.30,    # 30% dos leads qualificam
        "mql_to_opp":         0.40,    # 40% dos MQLs viram oportunidades
        "opp_to_closed_won":  0.22,    # 22% das opps fecham ganhas
    },

    # ACV (Annual Contract Value) em BRL por segmento de porte
    "acv_by_size": {
        "pequena":  (24_000,  48_000),   # R$ 2K–4K/mês
        "media":    (48_000, 120_000),   # R$ 4K–10K/mês
        "grande":   (120_000, 180_000),  # R$ 10K–15K/mês
    },

    # Distribuição de estados brasileiros (peso por PIB/concentração)
    "states": {
        "SP": 0.40, "RJ": 0.15, "MG": 0.12, "RS": 0.08,
        "PR": 0.07, "SC": 0.04, "BA": 0.03, "GO": 0.03,
        "PE": 0.03, "CE": 0.02, "DF": 0.02, "outros": 0.01,
    },

    # Indústrias e distribuição
    "industries": {
        "Varejo":        0.22,
        "Tecnologia":    0.18,
        "Serviços":      0.16,
        "Indústria":     0.13,
        "Financeiro":    0.10,
        "Saúde":         0.08,
        "Agronegócio":   0.07,
        "Educação":      0.06,
    },

    # Porte das empresas (50–500 funcionários = mid-market brasileiro)
    "company_sizes": {
        "pequena": (50, 150, 0.45),    # (min, max, peso)
        "media":   (151, 350, 0.40),
        "grande":  (351, 500, 0.15),
    },

    # Fator de sazonalidade por semana do ano (índice relativo ao volume médio)
    # 1.0 = volume normal; valores < 1.0 = período de queda
    "seasonality_notes": {
        "carnaval": "semanas 6-7 (fev)",
        "ferias_julho": "semanas 27-30",
        "black_friday": "semana 47 (nov)",
        "recesso_fim_ano": "semanas 51-2 do ano seguinte",
    },
}

# =============================================================================
# MÓDULO 2 — DEFINIÇÃO DOS CANAIS
# =============================================================================
# Cada canal tem um perfil estatístico completo que modula o funil.
# Esta é a implementação da "channel bias table" do design.
#
# Campos:
#   weight         → participação no mix de aquisição (soma ≠ 1; normalizado depois)
#   lead_to_opp    → multiplicador sobre a taxa base de MQL→Opp
#   win_rate       → multiplicador sobre a taxa base de Opp→Closed Won
#   deal_size_mult → multiplicador sobre o ACV médio do segmento
#   time_to_close  → (média_dias, std_dias) do ciclo de vendas
#   cpc_range      → (min, max) custo por clique em BRL (para spend sintético)
#   utm_source     → valor padrão de UTM source
#   utm_medium     → valor padrão de UTM medium

CHANNELS = {
    "organic_search": {
        "weight": 0.28, "lead_to_opp": 1.0, "win_rate": 1.2,
        "deal_size_mult": 1.0, "time_to_close": (55, 12),
        "cpc_range": (0, 0),        # orgânico — sem custo por clique
        "utm_source": "google", "utm_medium": "organic",
    },
    "paid_search": {
        "weight": 0.22, "lead_to_opp": 1.3, "win_rate": 0.95,
        "deal_size_mult": 0.90, "time_to_close": (42, 10),
        "cpc_range": (3.50, 18.00),
        "utm_source": "google", "utm_medium": "cpc",
    },
    "linkedin_ads": {
        "weight": 0.10, "lead_to_opp": 1.6, "win_rate": 1.35,
        "deal_size_mult": 1.40, "time_to_close": (68, 15),
        "cpc_range": (12.00, 45.00),
        "utm_source": "linkedin", "utm_medium": "paid_social",
    },
    "meta_ads": {
        "weight": 0.20, "lead_to_opp": 0.55, "win_rate": 0.60,
        "deal_size_mult": 0.75, "time_to_close": (35, 8),
        "cpc_range": (1.20, 6.00),
        "utm_source": "facebook", "utm_medium": "paid_social",
    },
    "email_marketing": {
        "weight": 0.08, "lead_to_opp": 0.90, "win_rate": 1.05,
        "deal_size_mult": 1.05, "time_to_close": (50, 11),
        "cpc_range": (0.10, 0.80),  # custo por envio
        "utm_source": "email", "utm_medium": "email",
    },
    "webinar_evento": {
        "weight": 0.04, "lead_to_opp": 2.20, "win_rate": 1.70,
        "deal_size_mult": 1.50, "time_to_close": (72, 18),
        "cpc_range": (15.00, 60.00),  # custo por participante
        "utm_source": "webinar", "utm_medium": "evento",
    },
    "direct": {
        "weight": 0.08, "lead_to_opp": 1.4, "win_rate": 1.30,
        "deal_size_mult": 1.20, "time_to_close": (38, 9),
        "cpc_range": (0, 0),
        "utm_source": "(direct)", "utm_medium": "(none)",
    },
}

# Normaliza os pesos para somarem 1
_total_weight = sum(c["weight"] for c in CHANNELS.values())
for c in CHANNELS.values():
    c["weight"] /= _total_weight

CHANNEL_NAMES = list(CHANNELS.keys())
CHANNEL_WEIGHTS = [CHANNELS[c]["weight"] for c in CHANNEL_NAMES]

# =============================================================================
# MÓDULO 3 — MOTOR DE SAZONALIDADE
# =============================================================================

def get_seasonality_factor(date: datetime) -> float:
    """
    Retorna um multiplicador de volume para uma data específica.

    Implementa quatro padrões sazonais do mercado B2B brasileiro:
    - Queda em Carnaval (semanas 6-7)
    - Queda em Férias de Julho (semanas 27-30)
    - Pico em Black Friday (semana 47)
    - Queda no Recesso de fim/início de ano (semanas 51-2)

    B2B apresenta queda de ~65% em fins de semana; isso é tratado
    separadamente no gerador de sessões.
    """
    week = date.isocalendar().week
    month = date.month
    day_of_week = date.weekday()  # 0=seg, 6=dom

    # Fim de semana: redução drástica em B2B
    if day_of_week >= 5:
        weekend_factor = 0.15
    else:
        weekend_factor = 1.0

    # Sazonalidade anual
    if week in (6, 7):               # Carnaval
        seasonal = 0.35
    elif week in (27, 28, 29, 30):   # Férias de julho
        seasonal = 0.60
    elif week == 47:                  # Black Friday B2B
        seasonal = 1.45
    elif week >= 51 or week <= 2:    # Recesso fim/início de ano
        seasonal = 0.20
    elif month in (3, 9):            # Picos de orçamento Q1/Q3
        seasonal = 1.15
    else:
        seasonal = 1.0

    return weekend_factor * seasonal


def get_business_hour_weight(hour: int) -> float:
    """Peso para hora do dia em contexto B2B (horário de Brasília)."""
    if 9 <= hour <= 11:   return 1.4   # pico manhã
    elif 14 <= hour <= 16: return 1.3   # pico tarde
    elif 8 <= hour <= 18:  return 0.8   # horário comercial normal
    elif 7 <= hour <= 20:  return 0.2   # fora do horário mas plausível
    else:                  return 0.02  # madrugada — quase zero


def random_business_datetime(start: datetime, end: datetime) -> datetime:
    """Gera timestamp aleatório com viés para horário comercial brasileiro."""
    days_range = max(1, (end - start).days)
    date = start + timedelta(days=int(RNG.integers(0, days_range)))
    
    # Hora com distribuição bimodal (pico manhã + tarde)
    hours = list(range(24))
    weights = [get_business_hour_weight(h) for h in hours]
    weights = np.array(weights) / sum(weights)
    hour = RNG.choice(hours, p=weights)
    minute = int(RNG.integers(0, 60))
    
    return date.replace(hour=hour, minute=minute)

# =============================================================================
# MÓDULO 4 — UTILITÁRIOS DE CORRELAÇÃO (CÓPULA GAUSSIANA)
# =============================================================================

def correlated_samples(n: int, means: list, stds: list, corr_matrix: np.ndarray) -> np.ndarray:
    """
    Gera amostras multivariadas com estrutura de correlação especificada.

    Usa a decomposição de Cholesky da matriz de correlação para transformar
    samples normais independentes em amostras correlacionadas.
    Equivalente a uma cópula gaussiana com marginais normais.

    Args:
        n:           número de amostras
        means:       média de cada variável
        stds:        desvio padrão de cada variável
        corr_matrix: matriz de correlação (deve ser positiva semi-definida)

    Returns:
        Array (n, k) com amostras correlacionadas
    """
    k = len(means)
    # Cholesky decompõe R em L tal que L @ L.T = R
    L = np.linalg.cholesky(corr_matrix)
    # Gera normais independentes e transforma
    z = RNG.standard_normal((n, k))
    correlated = z @ L.T
    # Escala para médias e desvios desejados
    result = correlated * np.array(stds) + np.array(means)
    return result


def industry_size_multiplier(industry: str, size_class: str) -> float:
    """
    Retorna um multiplicador de P(conversão) baseado na combinação
    indústria × porte. Implementa a heterogeneidade de subpopulações.

    Justificativa: uma empresa de Tecnologia pequena tem comportamento
    de compra diferente de uma empresa de Agronegócio grande — mesmo
    que o canal de aquisição seja o mesmo.
    """
    # Matriz de multipliers [indústria][porte]
    matrix = {
        "Tecnologia":  {"pequena": 1.20, "media": 1.15, "grande": 1.10},
        "Financeiro":  {"pequena": 0.90, "media": 1.25, "grande": 1.40},
        "Varejo":      {"pequena": 1.10, "media": 1.00, "grande": 0.85},
        "Indústria":   {"pequena": 0.85, "media": 1.05, "grande": 1.20},
        "Serviços":    {"pequena": 1.00, "media": 1.00, "grande": 1.00},
        "Saúde":       {"pequena": 0.95, "media": 1.10, "grande": 1.15},
        "Agronegócio": {"pequena": 0.80, "media": 0.95, "grande": 1.35},
        "Educação":    {"pequena": 0.90, "media": 1.00, "grande": 0.95},
    }
    return matrix.get(industry, {}).get(size_class, 1.0)

# =============================================================================
# MÓDULO 5 — GERADOR DE CONTEÚDO / LANDING PAGES
# =============================================================================

CONTENT_ASSETS = {
    "blog": [
        ("/blog/gestao-vendas-b2b", "Blog: Gestão de Vendas B2B"),
        ("/blog/crm-para-industria", "Blog: CRM para Indústria"),
        ("/blog/integracao-erp-sistemas", "Blog: Integração ERP"),
        ("/blog/automacao-marketing-b2b", "Blog: Automação Marketing"),
        ("/blog/churn-saas-brasil", "Blog: Churn em SaaS"),
        ("/blog/funil-vendas-complexas", "Blog: Funil de Vendas Complexas"),
        ("/blog/leads-qualificados-b2b", "Blog: Leads Qualificados"),
    ],
    "ebook": [
        ("/ebook/crm-para-varejo", "Ebook: CRM para Varejo"),
        ("/ebook/gestao-pipeline-vendas", "Ebook: Gestão de Pipeline"),
        ("/ebook/roi-tecnologia-empresas", "Ebook: ROI em Tecnologia"),
        ("/ebook/integracao-sistemas-guia", "Ebook: Guia de Integração"),
    ],
    "webinar": [
        ("/webinar/integracao-erp-ao-vivo", "Webinar: Integração ERP ao Vivo"),
        ("/webinar/crm-para-gestores", "Webinar: CRM para Gestores"),
        ("/webinar/automacao-vendas-demo", "Webinar: Demo Automação de Vendas"),
    ],
    "landing_page": [
        ("/lp/demo-gratis", "LP: Demo Grátis"),
        ("/lp/trial-30-dias", "LP: Trial 30 Dias"),
        ("/lp/comparativo-erp", "LP: Comparativo ERP"),
        ("/lp/roi-calculator", "LP: Calculadora ROI"),
    ],
    "produto": [
        ("/produto/crm-integracao", "Produto: CRM Integration"),
        ("/produto/erp-connector", "Produto: ERP Connector"),
        ("/produto/api-marketplace", "Produto: API Marketplace"),
    ],
}

# Mapeamento canal → tipos de conteúdo mais prováveis
CHANNEL_CONTENT_AFFINITY = {
    "organic_search": ["blog", "produto"],
    "paid_search":    ["landing_page", "produto"],
    "linkedin_ads":   ["ebook", "webinar", "landing_page"],
    "meta_ads":       ["ebook", "landing_page"],
    "email_marketing":["ebook", "webinar", "blog"],
    "webinar_evento": ["webinar", "landing_page"],
    "direct":         ["produto", "landing_page"],
}

def get_landing_page(channel: str) -> tuple:
    """Retorna (url, nome) do ativo de conteúdo mais provável para o canal."""
    content_types = CHANNEL_CONTENT_AFFINITY.get(channel, ["blog"])
    # 70% chance de usar tipo afim, 30% qualquer tipo
    if RNG.random() < 0.70:
        content_type = RNG.choice(content_types)
    else:
        content_type = RNG.choice(list(CONTENT_ASSETS.keys()))
    assets = CONTENT_ASSETS[content_type]
    idx = int(RNG.integers(0, len(assets)))
    return assets[idx]  # (url, nome)


# Nomes de campanhas com typos intencionais (para mostrar data cleaning)
CAMPAIGN_TEMPLATES = {
    "paid_search": [
        "google_brand_keywords_{year}",
        "google_branded_{year}",          # variação intencional
        "pesquisa_concorrentes_q{q}_{year}",
        "integracao_erp_pesquisa_{year}",
        "crm-b2b-keywords-{year}",        # hífen vs underscore
    ],
    "linkedin_ads": [
        "linkedin_prospecao_q{q}_{year}",
        "linkedin_prospeccao_q{q}_{year}", # erro ortográfico intencional
        "linkedin_decisores_ti_{year}",
        "linkedin_gestores_{year}",
        "lkd_awareness_{year}",            # abreviação
    ],
    "meta_ads": [
        "meta_awareness_{year}",
        "facebook_retargeting_{year}",     # inconsistência meta vs facebook
        "ig_gestores_b2b_q{q}",
        "fb-leads-varejo-{year}",
    ],
    "email_marketing": [
        "email_nurture_leads_{year}",
        "newsletter_mensal_{month}_{year}",
        "email_reengajamento_q{q}_{year}",
        "campanha_email_{month}-{year}",   # formato diferente
    ],
    "webinar_evento": [
        "webinar_integracao_erp_{year}",
        "evento_crm_gestores_q{q}",
        "black_friday_2023",               # typos de BF
        "bf-23",                           # abreviação inconsistente
        "campanha_natal_{year}",
        "campanha-natal-{year}",
    ],
    "organic_search": ["(not set)", "(none)", ""],
    "direct":         ["(not set)", "(direct)", ""],
    "paid_search_brand": ["google_brand_{year}"],
}


def get_campaign_name(channel: str, date: datetime) -> str:
    """Gera nome de campanha com realismo (incluindo inconsistências)."""
    templates = CAMPAIGN_TEMPLATES.get(channel, ["sem_campanha"])
    template = RNG.choice(templates)
    quarter = (date.month - 1) // 3 + 1
    return (template
            .replace("{year}", str(date.year))
            .replace("{q}", str(quarter))
            .replace("{month}", f"{date.month:02d}"))

# =============================================================================
# MÓDULO 6 — BUILDERS DE ENTIDADES
# =============================================================================

def build_accounts(n: int) -> pd.DataFrame:
    """
    Constrói a tabela de accounts (empresas).

    Cada account representa uma empresa-alvo no mercado mid-market brasileiro.
    A distribuição de estados reflete a concentração econômica real.
    Missing data intencional: ~5% de industry e company_size ausentes.
    """
    print(f"  → Gerando {n} accounts...")

    states = list(CONFIG["states"].keys())
    state_weights = list(CONFIG["states"].values())

    industries = list(CONFIG["industries"].keys())
    industry_weights = list(CONFIG["industries"].values())

    size_classes = list(CONFIG["company_sizes"].keys())
    size_weights = [CONFIG["company_sizes"][s][2] for s in size_classes]

    records = []
    for i in range(n):
        industry = RNG.choice(industries, p=industry_weights / np.array(industry_weights).sum())
        size_class = RNG.choice(size_classes, p=size_weights / np.array(size_weights).sum())
        size_min, size_max, _ = CONFIG["company_sizes"][size_class]
        n_employees = int(RNG.integers(size_min, size_max + 1))
        state = RNG.choice(states, p=state_weights / np.array(state_weights).sum())
        created = CONFIG["date_start"] + timedelta(
            days=int(RNG.integers(0, (CONFIG["date_end"] - CONFIG["date_start"]).days))
        )

        # Missing data intencional (~5%)
        industry_val = None if RNG.random() < 0.05 else industry
        size_val = None if RNG.random() < 0.04 else size_class

        domain_suffix = RNG.choice(["com.br", "com.br", "com.br", "net.br", "org.br"])
        company_slug = fake.company().lower().replace(" ", "").replace(",", "")[:12]

        records.append({
            "account_id":   f"ACC-{i+1:05d}",
            "company_name": fake.company(),
            "email_domain": f"{company_slug}.{domain_suffix}",
            "industry":     industry_val,
            "state":        state,
            "size_class":   size_val,
            "n_employees":  n_employees,
            "created_date": created.date(),
            # Metadado interno — usado pelos outros builders, dropado no export final
            "_industry_raw":  industry,
            "_size_class_raw": size_class,
        })

    return pd.DataFrame(records)


def build_channel_spend(date_start: datetime, date_end: datetime) -> pd.DataFrame:
    """
    Constrói a tabela de investimento semanal por canal.

    Granularidade: semana × canal.
    Permite cálculo de ROAS, CPQL e CPO por canal.

    Budget base mensal (BRL) por canal — escalado com sazonalidade.
    Orgânico e direto têm custo zero (não são paid media).
    """
    print("  → Gerando channel_spend...")

    monthly_budgets = {
        "paid_search":    18_000,
        "linkedin_ads":   12_000,
        "meta_ads":        8_000,
        "email_marketing": 1_500,
        "webinar_evento":  4_000,
        "organic_search":      0,
        "direct":              0,
    }

    records = []
    current = date_start
    week_id = 1

    while current <= date_end:
        week_end = current + timedelta(days=6)
        season = get_seasonality_factor(current + timedelta(days=2))  # meio da semana

        for channel, monthly_budget in monthly_budgets.items():
            if monthly_budget == 0:
                spend = 0.0
                impressions = 0
                clicks = 0
            else:
                # Budget semanal base + variação aleatória ±20%
                weekly_base = monthly_budget / 4.33
                noise = RNG.uniform(0.80, 1.20)
                seasonal_adj = max(0.3, season)  # não vai a zero mesmo no recesso
                spend = round(weekly_base * noise * seasonal_adj, 2)

                # Impressions e clicks baseados no CPC range do canal
                cpc_min, cpc_max = CHANNELS[channel]["cpc_range"]
                if cpc_max > 0:
                    avg_cpc = RNG.uniform(cpc_min, cpc_max)
                    clicks = max(1, int(spend / avg_cpc))
                    ctr = RNG.uniform(0.008, 0.045)  # 0.8%–4.5% CTR
                    impressions = int(clicks / ctr)
                else:
                    clicks = 0
                    impressions = 0

            records.append({
                "spend_id":    f"SPD-{week_id:04d}-{channel[:6].upper()}",
                "week_start":  current.date(),
                "week_end":    week_end.date(),
                "channel":     channel,
                "spend_brl":   spend,
                "impressions": impressions,
                "clicks":      clicks,
                "week_number": week_id,
            })

        current += timedelta(days=7)
        week_id += 1

    return pd.DataFrame(records)


def build_content_assets() -> pd.DataFrame:
    """
    Constrói a tabela de ativos de conteúdo.
    Cada ativo tem métricas de performance agregadas.
    """
    print("  → Gerando content_assets...")
    records = []
    asset_id = 1
    for content_type, assets in CONTENT_ASSETS.items():
        for url, name in assets:
            records.append({
                "asset_id":       f"AST-{asset_id:04d}",
                "asset_type":     content_type,
                "asset_name":     name,
                "url_path":       url,
                "publish_date":   (CONFIG["date_start"] + timedelta(
                    days=int(RNG.integers(0, 60)))).date(),
                "topic_cluster":  _infer_topic(url),
            })
            asset_id += 1
    return pd.DataFrame(records)


def _infer_topic(url: str) -> str:
    if "erp" in url or "integracao" in url: return "ERP & Integração"
    if "crm" in url:                        return "CRM"
    if "vendas" in url or "pipeline" in url: return "Gestão de Vendas"
    if "automacao" in url:                  return "Automação"
    if "demo" in url or "trial" in url:     return "Conversão"
    if "roi" in url or "calculator" in url: return "ROI & Valor"
    return "Geral"


def build_ga4_sessions(accounts: pd.DataFrame, n_target: int) -> pd.DataFrame:
    """
    Constrói sessões GA4 com viés temporal, sazonalidade e estrutura de
    engajamento correlacionada.

    Correlações implementadas via cópula gaussiana:
    - engagement_time_sec ↔ events_per_session: r ≈ 0.62
    - session_depth ↔ bounce_prob: r ≈ -0.55 (mais páginas = menos bounce)

    ~15% das sessões não resolvem para lead_id (tráfego anônimo).
    """
    print(f"  → Gerando ~{n_target:,} sessões GA4...")

    date_start = CONFIG["date_start"]
    date_end = CONFIG["date_end"]

    # Gera distribuição de datas com sazonalidade
    # Gera pool de datas candidatas e amostra proporcionalmente
    all_dates = [date_start + timedelta(days=d)
                 for d in range((date_end - date_start).days + 1)]
    date_weights = np.array([get_seasonality_factor(d) for d in all_dates])
    date_weights = date_weights / date_weights.sum()

    chosen_dates = RNG.choice(all_dates, size=n_target, p=date_weights)

    channels_arr = RNG.choice(CHANNEL_NAMES, size=n_target, p=CHANNEL_WEIGHTS)

    # Métricas correlacionadas via cópula gaussiana
    # [engagement_time_sec, events_per_session]
    corr_engagement = np.array([
        [1.00, 0.62],
        [0.62, 1.00],
    ])
    engagement_raw = correlated_samples(
        n_target,
        means=[180, 6.5],     # 3 min médios, 6.5 eventos por sessão
        stds=[120, 3.5],
        corr_matrix=corr_engagement
    )
    engagement_times = np.clip(engagement_raw[:, 0], 5, 900).astype(int)
    events_per_session = np.clip(engagement_raw[:, 1], 1, 30).astype(int)

    # Device distribution
    devices = RNG.choice(
        ["desktop", "mobile", "tablet"],
        size=n_target,
        p=[0.58, 0.36, 0.06]
    )

    # Vetorizado: gera horas e minutos em batch
    n_unique_users = int(n_target * 0.65)
    user_ids_arr = np.array([f"user_{i:07d}" for i in range(n_unique_users)])
    user_idx = RNG.integers(0, n_unique_users, size=n_target)

    hours_arr = np.array(list(range(24)))
    hour_weights = np.array([get_business_hour_weight(h) for h in hours_arr])
    hour_weights = hour_weights / hour_weights.sum()
    chosen_hours = RNG.choice(hours_arr, size=n_target, p=hour_weights)
    chosen_minutes = RNG.integers(0, 60, size=n_target)

    # Landing pages e campaigns por canal (vetorizado por canal único)
    lp_map = {ch: get_landing_page(ch)[0] for ch in CHANNEL_NAMES}
    utm_source_map  = {ch: CHANNELS[ch]["utm_source"] for ch in CHANNEL_NAMES}
    utm_medium_map  = {ch: CHANNELS[ch]["utm_medium"] for ch in CHANNEL_NAMES}

    bounce_probs = np.clip(0.8 - events_per_session / 30, 0.05, 0.95)
    is_bounce_arr = (RNG.random(n_target) < bounce_probs).astype(int)

    # Monta datetime strings sem loop
    dates_str = [d.strftime("%Y-%m-%d") for d in chosen_dates]
    datetimes_str = [
        f"{dates_str[i]}T{chosen_hours[i]:02d}:{chosen_minutes[i]:02d}:00"
        for i in range(n_target)
    ]

    df = pd.DataFrame({
        "session_id":          [f"SES-{i+1:08d}" for i in range(n_target)],
        "user_pseudo_id":      user_ids_arr[user_idx],
        "session_date":        dates_str,
        "session_datetime":    datetimes_str,
        "channel":             channels_arr,
        "utm_source":          [utm_source_map[c] for c in channels_arr],
        "utm_medium":          [utm_medium_map[c] for c in channels_arr],
        "campaign":            [get_campaign_name(channels_arr[i], chosen_dates[i]) for i in range(n_target)],
        "landing_page":        [lp_map[c] for c in channels_arr],
        "device_category":     devices,
        "engagement_time_sec": engagement_times,
        "events_per_session":  events_per_session,
        "is_bounce":           is_bounce_arr,
        "lead_id":             None,
    })

    df = df.sort_values("session_datetime").reset_index(drop=True)
    return df


def build_leads(accounts: pd.DataFrame, sessions: pd.DataFrame) -> pd.DataFrame:
    """
    Constrói leads a partir de sessões GA4, respeitando o funil probabilístico.

    Cada lead:
    1. Está associado a uma account (empresa) — via email_domain
    2. Tem uma sessão de first-touch
    3. Recebe um lead_score correlacionado com o potencial de conversão
    4. Tem lead_score ↔ future_opp_amount correlacionados (r ≈ 0.4)

    A taxa de conversão de sessão → lead é modulada por:
    - Canal (channel bias)
    - Sazonalidade da data
    - Tipo de landing page (LPs de conversão têm CVR maior)
    """
    print("  → Gerando leads a partir de sessões...")

    base_rate = CONFIG["funnel"]["visitor_to_lead"]
    lp_boost = {"/lp/demo-gratis": 2.5, "/lp/trial-30-dias": 2.2,
                "/lp/roi-calculator": 1.8, "/lp/comparativo-erp": 1.6,
                "/ebook/": 1.4, "/webinar/": 1.5}

    # Seleciona sessões candidatas a gerar lead
    lead_sessions = []
    for _, sess in sessions.iterrows():
        # Calcula taxa de conversão desta sessão
        channel_factor = CHANNELS[sess["channel"]]["lead_to_opp"] * 0.6 + 0.4
        lp = sess["landing_page"]
        lp_factor = 1.0
        for pattern, boost in lp_boost.items():
            if pattern in lp:
                lp_factor = boost
                break

        cvr = base_rate * channel_factor * lp_factor
        if RNG.random() < cvr:
            lead_sessions.append(sess)

    print(f"    → {len(lead_sessions):,} sessões converteram em lead")

    # Distribui leads entre accounts
    accounts_list = accounts.to_dict("records")

    # Correlação lead_score ↔ engajamento da sessão
    lead_records = []
    for i, sess in enumerate(lead_sessions):
        account = RNG.choice(accounts_list)

        # Lead score correlacionado com engajamento da sessão
        engagement_norm = sess["engagement_time_sec"] / 900
        base_score = engagement_norm * 60 + RNG.uniform(10, 40)
        lead_score = int(np.clip(base_score, 1, 100))

        lead_date = datetime.fromisoformat(sess["session_datetime"])
        conv_opp_date = None  # preenchido se virar MQL→Opp

        lead_records.append({
            "lead_id":                    f"LEAD-{i+1:06d}",
            "account_id":                 account["account_id"],
            "email":                      f"contato{i}@{account['email_domain']}",
            "first_touch_channel":        sess["channel"],
            "first_touch_session_id":     sess["session_id"],
            "utm_source":                 sess["utm_source"],
            "utm_medium":                 sess["utm_medium"],
            "campaign":                   sess["campaign"],
            "landing_page":               sess["landing_page"],
            "lead_score":                 lead_score,
            "lead_date":                  lead_date.date(),
            "is_mql":                     0,   # preenchido depois
            "converted_to_opp_date":      None,
            "_account_industry":          account["_industry_raw"],
            "_account_size_class":        account["_size_class_raw"],
            "_account_n_employees":       account["n_employees"],
        })

    leads_df = pd.DataFrame(lead_records)

    # Atualiza sessions com lead_id (85% resolução)
    lead_session_ids = [s["session_id"] for s in lead_sessions]
    session_to_lead = {
        sess["first_touch_session_id"]: sess["lead_id"]
        for _, sess in leads_df.iterrows()
    }
    # Marca 15% como anônimos (não resolvidos)
    anonymous_mask = RNG.random(len(sessions)) < 0.15
    sessions.loc[sessions["session_id"].isin(lead_session_ids) & ~anonymous_mask,
                 "lead_id"] = sessions.loc[
                     sessions["session_id"].isin(lead_session_ids) & ~anonymous_mask,
                     "session_id"].map(session_to_lead)

    return leads_df


def build_opportunities(leads: pd.DataFrame,
                        accounts: pd.DataFrame,
                        sector_closed_tracker: dict = None) -> pd.DataFrame:
    """
    Constrói oportunidades a partir de leads, com histórico de estágios.

    Inovações em relação ao design original:
    1. STAGE HISTORY: cada oportunidade tem timestamps por estágio,
       permitindo survival analysis e velocidade de pipeline por canal.
    2. AUTOCORRELAÇÃO SETORIAL: P(opp→won) recebe boost leve se o setor
       teve deals fechados nos 60 dias anteriores (word-of-mouth B2B).
    3. HETEROGENEIDADE canal × indústria × porte via industry_size_multiplier.

    Missing data: ~3% de opportunities com stage_history incompleto
    (simula falha no CRM de registrar datas de mudança de estágio).
    """
    print("  → Gerando opportunities com stage history...")

    if sector_closed_tracker is None:
        sector_closed_tracker = {}

    base_mql = CONFIG["funnel"]["lead_to_mql"]
    base_opp = CONFIG["funnel"]["mql_to_opp"]
    base_won = CONFIG["funnel"]["opp_to_closed_won"]

    STAGES = ["Prospecting", "Qualification", "Proposal", "Negotiation",
              "Closed Won", "Closed Lost"]

    opp_records = []
    opp_id = 1

    accounts_dict = accounts.set_index("account_id").to_dict("index")

    for _, lead in leads.iterrows():
        channel = lead["first_touch_channel"]
        ch = CHANNELS[channel]
        industry = lead["_account_industry"]
        size_class = lead["_account_size_class"]
        lead_date = datetime.combine(lead["lead_date"], datetime.min.time())

        # Multiplicador de subpopulação
        sub_mult = industry_size_multiplier(industry, size_class)

        # MQL?
        mql_prob = base_mql * (ch["lead_to_opp"] * 0.5 + 0.5) * sub_mult
        if RNG.random() > mql_prob:
            continue

        # Opp?
        opp_prob = base_opp * ch["lead_to_opp"] * sub_mult
        if RNG.random() > opp_prob:
            continue

        # Datas de criação da opp
        days_to_opp = int(RNG.integers(3, 21))
        opp_create_date = lead_date + timedelta(days=days_to_opp)
        if opp_create_date > CONFIG["date_end"]:
            continue

        # Deal amount — correlacionado com lead_score e porte
        size_class_clean = size_class if size_class else "media"
        acv_min, acv_max = CONFIG["acv_by_size"].get(size_class_clean, (48_000, 120_000))
        score_norm = lead["lead_score"] / 100
        base_amount = acv_min + (acv_max - acv_min) * score_norm
        amount = round(base_amount * ch["deal_size_mult"] * RNG.uniform(0.85, 1.15), -2)

        # Win probability — autocorrelação setorial
        sector_boost = 1.0
        if industry in sector_closed_tracker:
            days_since_last = (opp_create_date - sector_closed_tracker[industry]).days
            if 0 < days_since_last < 60:
                sector_boost = 1.12  # +12% se houve deal no setor nos últimos 60 dias

        win_prob = base_won * ch["win_rate"] * sub_mult * sector_boost
        win_prob = min(win_prob, 0.75)  # cap realista

        # Fechamento
        mean_days, std_days = ch["time_to_close"]
        days_to_close = max(14, int(RNG.normal(mean_days, std_days)))
        close_date = opp_create_date + timedelta(days=days_to_close)
        if close_date > CONFIG["date_end"] + timedelta(days=90):
            stage = "Em Andamento"
            won = False
        else:
            won = RNG.random() < win_prob
            stage = "Closed Won" if won else "Closed Lost"

        # Stage history — série temporal de estágios
        # Simula timestamps de entrada em cada estágio
        stage_history = _generate_stage_history(
            opp_create_date, close_date, stage, STAGES
        )

        # Missing data intencional no stage_history (~3%)
        if RNG.random() < 0.03:
            stage_history = {k: None for k in stage_history}

        if won and stage == "Closed Won":
            sector_closed_tracker[industry] = close_date

        opp_records.append({
            "opp_id":               f"OPP-{opp_id:05d}",
            "lead_id":              lead["lead_id"],
            "account_id":           lead["account_id"],
            "first_touch_channel":  channel,
            "stage":                stage,
            "amount_brl":           amount,
            "created_date":         opp_create_date.date(),
            "close_date":           close_date.date() if close_date <= CONFIG["date_end"] + timedelta(days=90) else None,
            "is_won":               int(won),
            "win_probability_hist": round(win_prob, 3),
            # Stage history como colunas separadas (mais fácil para SQL)
            "stage_prospecting_dt":   stage_history.get("Prospecting"),
            "stage_qualification_dt": stage_history.get("Qualification"),
            "stage_proposal_dt":      stage_history.get("Proposal"),
            "stage_negotiation_dt":   stage_history.get("Negotiation"),
            "stage_closed_dt":        stage_history.get("Closed"),
        })
        opp_id += 1

    print(f"    → {len(opp_records):,} opportunities geradas")
    won_count = sum(1 for r in opp_records if r["is_won"])
    print(f"    → {won_count:,} Closed Won ({won_count/max(len(opp_records),1)*100:.1f}%)")
    return pd.DataFrame(opp_records)


def _generate_stage_history(opp_start: datetime, close_date: datetime,
                             final_stage: str, stages: list) -> dict:
    """Gera timestamps realistas de progressão por estágio."""
    total_days = max(1, (close_date - opp_start).days)
    # Distribui os estágios ativos no tempo total
    active_stages = ["Prospecting", "Qualification", "Proposal", "Negotiation"]
    # Proporção de tempo em cada estágio (variável)
    splits = RNG.dirichlet(np.ones(4)) * total_days
    history = {}
    current = opp_start
    for i, stage in enumerate(active_stages):
        history[stage] = current.date()
        current += timedelta(days=int(splits[i]))
    history["Closed"] = close_date.date()
    return history


def build_touchpoints(leads: pd.DataFrame, opps: pd.DataFrame,
                      sessions: pd.DataFrame,
                      content_assets: pd.DataFrame) -> pd.DataFrame:
    """
    Constrói a spine de atribuição multi-touch.

    Para cada oportunidade, gera N touchpoints representando a jornada
    completa desde a primeira sessão até o fechamento.

    GROUND TRUTH CAUSAL:
    O campo `true_marginal_contribution` é calculado ANTES da observação,
    baseado no modelo generativo. A lógica:
    - Cada touchpoint recebe um "peso causal" baseado no canal e posição
    - O peso causal é normalizado pela opp e representa a contribuição
      marginal real que o SCM atribuiria a cada touchpoint
    - Isso permite comparar modelos heurísticos (last-click, time-decay)
      contra o ground truth

    O engagement_score é gerado correlacionado com o tipo de touchpoint:
    - Demo requests e sales calls têm scores altos
    - Impressões e email_opens têm scores baixos
    """
    print("  → Gerando touchpoints (spine de atribuição)...")

    TOUCH_TYPES = {
        # touch_type: (base_engagement, base_causal_weight)
        "impression":     (10, 0.05),
        "click":          (25, 0.15),
        "content_view":   (35, 0.20),
        "form_fill":      (65, 0.55),
        "demo_request":   (85, 0.80),
        "email_open":     (15, 0.10),
        "sales_call":     (90, 0.90),
        "proposal_sent":  (75, 0.70),
    }

    # Sequência típica de touchpoints por canal
    CHANNEL_JOURNEY = {
        "organic_search":  ["impression", "click", "content_view", "form_fill"],
        "paid_search":     ["click", "landing_page_view", "form_fill", "demo_request"],
        "linkedin_ads":    ["impression", "click", "content_view", "demo_request", "sales_call"],
        "meta_ads":        ["impression", "click", "form_fill"],
        "email_marketing": ["email_open", "click", "content_view", "form_fill"],
        "webinar_evento":  ["impression", "click", "form_fill", "demo_request", "sales_call"],
        "direct":          ["click", "form_fill", "demo_request", "sales_call"],
    }

    opps_dict = opps.set_index("opp_id").to_dict("index")
    leads_dict = leads.set_index("lead_id").to_dict("index")
    content_ids = content_assets["asset_id"].tolist()
    content_urls = dict(zip(content_assets["url_path"], content_assets["asset_id"]))

    records = []
    touch_id = 1

    for opp_id, opp in opps_dict.items():
        lead_id = opp["lead_id"]
        if lead_id not in leads_dict:
            continue

        lead = leads_dict[lead_id]
        channel = opp["first_touch_channel"]

        opp_create = datetime.combine(
            opp["created_date"] if isinstance(opp["created_date"], type(datetime.today().date()))
            else datetime.strptime(str(opp["created_date"]), "%Y-%m-%d").date(),
            datetime.min.time()
        )

        # Número de touchpoints: varia por canal (LinkedIn e webinar têm mais)
        n_touches_by_channel = {
            "organic_search": (2, 6), "paid_search": (2, 5),
            "linkedin_ads": (4, 9), "meta_ads": (2, 4),
            "email_marketing": (3, 7), "webinar_evento": (3, 8),
            "direct": (2, 5),
        }
        n_min, n_max = n_touches_by_channel.get(channel, (2, 5))
        n_touches = int(RNG.integers(n_min, n_max + 1))

        # Touchpoints adicionais de outros canais (cross-channel journey)
        journey_channels = [channel]
        if n_touches > 3 and RNG.random() < 0.45:
            # Adiciona touchpoint de canal auxiliar
            aux_channel = RNG.choice([c for c in CHANNEL_NAMES if c != channel])
            journey_channels.append(aux_channel)

        # Distribui touchpoints no tempo (antes da criação da opp)
        lookback_days = 45  # janela de lookback
        touch_dates = sorted([
            opp_create - timedelta(days=int(RNG.integers(0, lookback_days)))
            for _ in range(n_touches)
        ])

        # Causal weights — ground truth
        # Posição: primeiro e último têm peso maior (position-based baseline)
        raw_weights = []
        touch_types_seq = []

        journey_templates = CHANNEL_JOURNEY.get(channel, ["click", "form_fill"])
        for j in range(n_touches):
            # Tipo de touchpoint baseado na posição na jornada
            if j < len(journey_templates):
                t_type = journey_templates[j]
            else:
                t_type = RNG.choice(list(TOUCH_TYPES.keys()))

            if t_type not in TOUCH_TYPES:
                t_type = "click"

            touch_types_seq.append(t_type)
            _, base_causal = TOUCH_TYPES[t_type]

            # Boost por posição: primeiro (+30%) e último (+50%)
            pos_mult = 1.0
            if j == 0:              pos_mult = 1.30
            elif j == n_touches - 1: pos_mult = 1.50

            # Time decay: touchpoints mais recentes têm peso maior
            days_before = (opp_create - touch_dates[j]).days
            decay = np.exp(-days_before / 14)  # half-life 14 dias

            raw_weights.append(base_causal * pos_mult * decay)

        # Normaliza para que a soma = 1 (representa 100% do crédito da opp)
        total_w = sum(raw_weights) or 1
        norm_weights = [w / total_w for w in raw_weights]

        for j in range(n_touches):
            t_type = touch_types_seq[j]
            t_channel = journey_channels[min(j, len(journey_channels) - 1)]
            base_eng, _ = TOUCH_TYPES.get(t_type, (30, 0.2))
            engagement = int(np.clip(base_eng + RNG.normal(0, 10), 1, 100))

            lp_url, _ = get_landing_page(t_channel)
            asset_id = content_urls.get(lp_url)

            records.append({
                "touchpoint_id":              f"TP-{touch_id:07d}",
                "opp_id":                     opp_id,
                "lead_id":                    lead_id,
                "touch_sequence":             j + 1,
                "total_touches_in_journey":   n_touches,
                "touch_date":                 touch_dates[j].date(),
                "days_before_opp_creation":   (opp_create - touch_dates[j]).days,
                "channel":                    t_channel,
                "campaign":                   get_campaign_name(t_channel, touch_dates[j]),
                "touch_type":                 t_type,
                "landing_page":               lp_url,
                "content_asset_id":           asset_id,
                "engagement_score":           engagement,
                "is_first_touch":             int(j == 0),
                "is_last_touch":              int(j == n_touches - 1),
                # GROUND TRUTH CAUSAL — calculado pelo SCM antes da observação
                "true_marginal_contribution": round(norm_weights[j], 6),
                # Revenue atribuído (para facilitar análises downstream)
                "attributed_revenue_brl":     round(opp["amount_brl"] * norm_weights[j], 2),
            })
            touch_id += 1

    print(f"    → {len(records):,} touchpoints gerados")
    return pd.DataFrame(records)

# =============================================================================
# MÓDULO 7 — LIMPEZA E EXPORT
# =============================================================================

def clean_for_export(accounts: pd.DataFrame, leads: pd.DataFrame) -> tuple:
    """Remove colunas internas (prefixo _) usadas apenas durante a geração."""
    internal_cols_acc = [c for c in accounts.columns if c.startswith("_")]
    internal_cols_leads = [c for c in leads.columns if c.startswith("_")]
    return (accounts.drop(columns=internal_cols_acc),
            leads.drop(columns=internal_cols_leads))


def export_to_sqlite(dfs: dict, db_path: Path):
    """
    Exporta todos os DataFrames para um SQLite com índices para performance.
    Índices criados nas foreign keys e colunas de alta cardinalidade.
    """
    print(f"  → Exportando SQLite: {db_path}")
    conn = sqlite3.connect(db_path)

    for table_name, df in dfs.items():
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        print(f"    → {table_name}: {len(df):,} rows")

    # Índices para performance em JOINs e filtros
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_leads_account ON leads(account_id)",
        "CREATE INDEX IF NOT EXISTS idx_leads_channel ON leads(first_touch_channel)",
        "CREATE INDEX IF NOT EXISTS idx_opps_lead ON opportunities(lead_id)",
        "CREATE INDEX IF NOT EXISTS idx_opps_account ON opportunities(account_id)",
        "CREATE INDEX IF NOT EXISTS idx_opps_is_won ON opportunities(is_won)",
        "CREATE INDEX IF NOT EXISTS idx_tp_opp ON touchpoints(opp_id)",
        "CREATE INDEX IF NOT EXISTS idx_tp_lead ON touchpoints(lead_id)",
        "CREATE INDEX IF NOT EXISTS idx_tp_channel ON touchpoints(channel)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_channel ON ga4_sessions(channel)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_lead ON ga4_sessions(lead_id)",
        "CREATE INDEX IF NOT EXISTS idx_spend_channel ON channel_spend(channel)",
        "CREATE INDEX IF NOT EXISTS idx_spend_week ON channel_spend(week_start)",
    ]
    cursor = conn.cursor()
    for idx_sql in indices:
        cursor.execute(idx_sql)
    conn.commit()
    conn.close()
    print(f"    → {len(indices)} índices criados")


def write_readme(output_dir: Path, stats: dict):
    """Gera README.md com data dictionary e estatísticas do dataset."""
    readme = f"""# Dataset: B2B SaaS Marketing Attribution — Brasil

## Visão Geral

Dataset sintético multi-tabela para análise de atribuição de marketing em
contexto B2B SaaS brasileiro. Simula 18 meses de dados de uma empresa de
CRM/ERP integrations vendendo para o mercado mid-market (50–500 funcionários).

**Gerado em:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Período:** {CONFIG['date_start'].date()} → {CONFIG['date_end'].date()}

## Volumes

| Tabela | Registros |
|---|---|
| accounts | {stats.get('accounts', 0):,} |
| leads | {stats.get('leads', 0):,} |
| opportunities | {stats.get('opportunities', 0):,} |
| ga4_sessions | {stats.get('ga4_sessions', 0):,} |
| touchpoints | {stats.get('touchpoints', 0):,} |
| channel_spend | {stats.get('channel_spend', 0):,} |
| content_assets | {stats.get('content_assets', 0):,} |

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
"""
    with open(output_dir / "README.md", "w", encoding="utf-8") as f:
        f.write(readme)
    print("  → README.md gerado")


# =============================================================================
# MÓDULO 8 — ORQUESTRADOR PRINCIPAL
# =============================================================================

def main():
    print("=" * 65)
    print("GERADOR DE DATASET SINTÉTICO — B2B SAAS ATTRIBUTION (Brasil)")
    print("=" * 65)

    output_dir = Path("/mnt/user-data/outputs/b2b_attribution_dataset")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. ACCOUNTS
    print("\n[1/7] Accounts...")
    accounts = build_accounts(CONFIG["n_accounts"])

    # 2. CHANNEL SPEND
    print("\n[2/7] Channel Spend...")
    channel_spend = build_channel_spend(CONFIG["date_start"], CONFIG["date_end"])

    # 3. CONTENT ASSETS
    print("\n[3/7] Content Assets...")
    content_assets = build_content_assets()

    # 4. GA4 SESSIONS
    print("\n[4/7] GA4 Sessions...")
    sessions = build_ga4_sessions(accounts, CONFIG["n_sessions_target"])

    # 5. LEADS
    print("\n[5/7] Leads...")
    leads = build_leads(accounts, sessions)

    # 6. OPPORTUNITIES
    print("\n[6/7] Opportunities...")
    sector_tracker = {}
    opportunities = build_opportunities(leads, accounts, sector_tracker)

    # 7. TOUCHPOINTS
    print("\n[7/7] Touchpoints...")
    touchpoints = build_touchpoints(leads, opportunities, sessions, content_assets)

    # Limpeza
    print("\n[→] Limpando colunas internas...")
    accounts_clean, leads_clean = clean_for_export(accounts, leads)

    # Export CSVs
    print("\n[→] Exportando CSVs...")
    dfs = {
        "accounts":      accounts_clean,
        "leads":         leads_clean,
        "opportunities": opportunities,
        "ga4_sessions":  sessions,
        "touchpoints":   touchpoints,
        "channel_spend": channel_spend,
        "content_assets": content_assets,
    }

    stats = {}
    for name, df in dfs.items():
        path = output_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        stats[name] = len(df)
        size_kb = path.stat().st_size / 1024
        print(f"  → {name}.csv: {len(df):,} rows ({size_kb:.0f} KB)")

    # Export SQLite
    print("\n[→] Exportando SQLite...")
    export_to_sqlite(dfs, output_dir / "b2b_attribution.db")

    # README
    print("\n[→] Gerando README...")
    write_readme(output_dir, stats)

    # Sumário final
    print("\n" + "=" * 65)
    print("SUMÁRIO DO DATASET GERADO")
    print("=" * 65)
    total_revenue = opportunities[opportunities["is_won"] == 1]["amount_brl"].sum()
    won_opps = opportunities["is_won"].sum()
    total_opps = len(opportunities)
    print(f"  Accounts:       {stats['accounts']:>8,}")
    print(f"  Leads:          {stats['leads']:>8,}")
    print(f"  Opportunities:  {stats['opportunities']:>8,} ({won_opps:,} won = {won_opps/max(total_opps,1)*100:.1f}%)")
    print(f"  GA4 Sessions:   {stats['ga4_sessions']:>8,}")
    print(f"  Touchpoints:    {stats['touchpoints']:>8,}")
    print(f"  Channel Spend:  {stats['channel_spend']:>8,} registros semanais")
    print(f"  Receita Total (Won): R$ {total_revenue:,.0f}")
    print(f"\n  Output: {output_dir}")
    print("=" * 65)


if __name__ == "__main__":
    main()

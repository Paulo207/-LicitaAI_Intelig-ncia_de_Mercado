# ============================================================
# config.py — LicitaAI Streamlit · PE&CR Soluções Ltda
# CNPJ: 13.441.865/0001-35
# ============================================================

import os
from pathlib import Path

# ── Carrega .env manualmente ─────────────────────────────────
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _linha in _env_path.read_text(encoding="utf-8").splitlines():
        _linha = _linha.strip()
        if _linha and not _linha.startswith("#") and "=" in _linha:
            _chave, _valor = _linha.split("=", 1)
            os.environ.setdefault(_chave.strip(), _valor.strip())

# ── Credenciais ──────────────────────────────────────────────
TOKEN_TELEGRAM     = os.environ.get("TOKEN_TELEGRAM", "")
CHAT_ID            = os.environ.get("CHAT_ID", "7197692719")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# ── IA Config ────────────────────────────────────────────────
MODEL_IA = "z-ai/glm-4.5-air:free"
# Modelo reserva caso o principal esteja fora do ar
MODEL_IA_FALLBACK = "meta-llama/llama-3.1-8b-instruct:free"

# ── Filtros de CNAE Híbridos ─────────────────────────────────

# 🌍 ÂMBITO FEDERAL (Nacional) — Saúde e Assistência Social
CNAES_FEDERAL = {
    "8610-1/01-02 · Hospitalar":        ["hospitalar", "unidade de saúde", "pronto-socorro", "urgência e emergência"],
    "8630-5/02-03 · Amb. Médica":        ["exames complementares", "atividade médica", "consultas médicas", "ambulatório"],
    "8660-7/00 · Gestão de Saúde":      ["apoio à gestão de saúde", "gerenciamento de saúde", "administração hospitalar"],
    "8711-5/01-03 · Geriátrico/Def.":   ["geriátrica", "convalescentes", "deficientes físicos", "imunodeprimidos"],
    "8720-4/01-99 · Psicossocial":      ["psicossocial", "caps", "distúrbios psíquicos", "dependência química", "mental"],
    "8800-6/00 · Assistência Social":   ["assistência social", "serviço social", "atendimento social", "acolhimento"],
}

# 🏢 ÂMBITO REGIONAL (GO + DF) — Infraestrutura e Serviços Prediais
CNAES_REGIONAL = {
    "8129-0/00 · Limpeza":              ["limpeza", "higienização", "conservação predial", "asseio"],
    "8111-7/00 · Facilities":           ["serviços combinados", "manutenção predial", "facilities", "apoio a edifícios"],
    "8130-3/00 · Paisagismo":           ["paisagismo", "jardinagem", "áreas verdes", "poda", "gramado"],
    "4321-5/00 · Elétrica":             ["instalação elétrica", "manutenção elétrica", "serviços elétricos"],
    "4322-3/02 · Ar-condicionado":      ["ar condicionado", "refrigeração", "climatização", "hvac", "split"],
    "8122-2/00 · Controle de Pragas":   ["controle de pragas", "dedetização", "desinsetização", "desratização"],
    "4213-8/00 · Urbanização":          ["urbanização", "calçadas", "praças", "pavimentação"],
    "4211-1/01 · Construção":           ["construção", "obra civil", "edificação", "reforma", "pintura predial"],
    "3811-4/00 · Resíduos":             ["coleta de resíduos", "gestão de resíduos", "limpeza urbana"],
}

# ── Blacklist de Produtos (Purificação de Resultados) ────────
# Se o objeto contiver qualquer destes termos, o edital é descartado para manter foco em SERVIÇOS
BLACKLIST_PRODUTOS = [
    "aquisição", "compra de", "fornecimento de material", "fornecimento de materiais", 
    "entrega de materiais", "fornecimento de equipamentos", "compra de peças", 
    "fornecimento de gêneros", "fornecimento de produtos", "compra de mobiliário",
    "aquisição de veículos", "entrega imediata de produtos", "material médico-hospitalar",
    "medicamentos", "insumos"
]

UFS_REGIONAL   = ["GO", "DF"]
MODALIDADES    = {6: "Pregão Eletrônico", 7: "Dispensa Eletrônica", 1: "Concorrência"}
VALOR_MINIMO   = 5_000

# ── Arquivo de deduplicação ──────────────────────────────────
ENVIADOS_JSON  = Path(__file__).parent / "enviados.json"

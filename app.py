"""
LicitaAI — Monitor de Licitações · PE&CR Soluções Ltda
Streamlit · API pública PNCP · sem autenticação · sem custo

Melhorias implementadas:
  ✅ Credenciais lidas do .env (nunca expostas no código)
  ✅ Deduplicação: editais já enviados ao Telegram não são reenviados
  ✅ Cache com @st.cache_data para evitar re-requests desnecessários
  ✅ Rate-limit robusto com retry automático (backoff exponencial)
  ✅ Filtro adicional por município
  ✅ Alerta visual quando CHAT_ID não está configurado
  ✅ Contador de novos × já enviados na interface
"""

import pypdf
import streamlit as st
import requests
import time
import json
import os
import re
import datetime
from pathlib import Path
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    TOKEN_TELEGRAM, CHAT_ID, CNAES_FEDERAL, CNAES_REGIONAL,
    UFS_REGIONAL, BLACKLIST_PRODUTOS, MODALIDADES, 
    VALOR_MINIMO, ENVIADOS_JSON, OPENROUTER_API_KEY, MODEL_IA, MODEL_IA_FALLBACK,
)

# ── Configuração da página ──────────────────────────────────
st.set_page_config(
    page_title="LicitaAI · PE&CR",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS personalizado ────────────────────────────────────────
st.markdown("""
<style>
  /* Cabeçalho verde institucional — estilo Compras.gov.br */
  .header-bar {
    background: linear-gradient(135deg, #1a5c2a 0%, #2e7d46 100%);
    color: white;
    padding: 14px 22px;
    border-radius: 8px;
    margin-bottom: 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 2px 8px rgba(0,0,0,.15);
  }
  .header-bar h1 { margin:0; font-size:20px; font-weight:700; }
  .header-bar .cnpj { font-size:12px; opacity:.85; margin-top:3px; }

  /* Card de edital — estilo lista do Compras.gov */
  .edital-card {
    background: #fff;
    border: 1px solid #d0d7de;
    border-left: 5px solid #1a5c2a;
    border-radius: 6px;
    padding: 16px 18px;
    margin-bottom: 14px;
    font-family: 'Segoe UI', sans-serif;
    transition: box-shadow .2s;
  }
  .edital-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,.10); }
  .edital-card.urgente { border-left-color: #c0392b; }
  .edital-card.atencao { border-left-color: #e67e22; }
  .edital-card.ja-enviado { opacity: .75; }

  .edital-numero {
    font-size: 13px;
    font-weight: 700;
    color: #1a5c2a;
    margin-bottom: 4px;
  }
  .edital-orgao {
    font-size: 14px;
    font-weight: 700;
    color: #1a1a1a;
    margin-bottom: 6px;
  }
  .edital-objeto {
    font-size: 13px;
    color: #333;
    line-height: 1.5;
    margin-bottom: 10px;
  }
  .edital-meta {
    display: flex;
    gap: 18px;
    flex-wrap: wrap;
    font-size: 12px;
    color: #555;
    border-top: 1px solid #eee;
    padding-top: 8px;
    margin-top: 8px;
  }
  .edital-meta span strong { color: #1a1a1a; }

  .badge {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
  }
  .badge-verde   { background:#d4edda; color:#155724; }
  .badge-amarelo { background:#fff3cd; color:#856404; }
  .badge-vermelho{ background:#f8d7da; color:#721c24; }
  .badge-cinza   { background:#e2e3e5; color:#383d41; }
  .badge-azul    { background:#cce5ff; color:#004085; }

  .btn-download {
    display: inline-block;
    background: #1a5c2a;
    color: white !important;
    padding: 5px 14px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
    text-decoration: none;
    margin-right: 6px;
    transition: background .2s;
  }
  .btn-download:hover { background: #145222; }
  .btn-pncp {
    display: inline-block;
    background: #fff;
    color: #1a5c2a !important;
    border: 1px solid #1a5c2a;
    padding: 5px 14px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
    text-decoration: none;
    transition: background .2s;
  }
  .btn-pncp:hover { background: #f0f8f2; }

  /* Métricas */
  .metric-row {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 10px;
    margin-bottom: 20px;
  }
  .metric-box {
    background: #fff;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 12px 16px;
    text-align: center;
    box-shadow: 0 1px 4px rgba(0,0,0,.05);
  }
  .metric-box .val { font-size: 26px; font-weight: 700; color: #1a5c2a; }
  .metric-box .lbl { font-size: 11px; color: #666; margin-top: 2px; }

  /* Alerta de configuração */
  .config-alert {
    background: #fff3cd;
    border: 1px solid #ffc107;
    border-left: 5px solid #ffc107;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 16px;
    font-size: 13px;
    color: #856404;
  }

  /* Badge de IA */
  .badge-ia {
    background: #f3e5f5;
    color: #6a1b9a;
    border: 1px solid #ce93d8;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
  }
  .insight-box {
    background: #fdf5ff;
    border: 1px dashed #ce93d8;
    color: #4a148c;
    padding: 10px 14px;
    border-radius: 6px;
    margin-top: 10px;
    font-size: 13px;
    line-height: 1.5;
  }

  /* Oculta menu e footer padrão do Streamlit */
  #MainMenu, footer { visibility: hidden; }
  .block-container { padding-top: 1rem !important; }
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# DEDUPLICAÇÃO — persistência de IDs já enviados
# ════════════════════════════════════════════════════════════

def _carregar_enviados() -> set:
    """Carrega conjunto de IDs de editais já enviados ao Telegram."""
    if ENVIADOS_JSON.exists():
        try:
            return set(json.loads(ENVIADOS_JSON.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()

def _salvar_enviados(ids: set):
    """Persiste o conjunto de IDs enviados no disco."""
    ENVIADOS_JSON.write_text(
        json.dumps(sorted(ids), indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

def limpar_html(texto: str) -> str:
    """Remove tags HTML residuais e escapa chaves {} que quebram f-strings."""
    if not texto: return ""
    # Remove tags como <div>, <p>, <br>, etc.
    clean = re.compile('<.*?>')
    texto = re.sub(clean, '', texto)
    # Escapa chaves para não quebrar f-strings do Streamlit/HTML
    return texto.replace("{", "[").replace("}", "]")

@st.cache_data(ttl=3600)
def buscar_arquivos_pncp(cnpj: str, ano: str, seq: str) -> list[dict]:
    """Busca a lista de arquivos de uma contratação no PNCP."""
    url = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []

# ════════════════════════════════════════════════════════════
# FUNÇÕES — API PNCP
# ════════════════════════════════════════════════════════════
PNCP_BASE = "https://pncp.gov.br/api/consulta/v1"
HEADERS   = {"Accept": "application/json", "User-Agent": "LicitaAI-PECR/1.0"}

def _data_str(dias_atras: int) -> tuple[str, str]:
    hoje   = datetime.date.today()
    inicio = hoje - datetime.timedelta(days=dias_atras)
    return inicio.strftime("%Y%m%d"), hoje.strftime("%Y%m%d")

def _dias_restantes(enc: str | None) -> int | None:
    if not enc:
        return None
    try:
        fim   = datetime.datetime.fromisoformat(enc.replace("Z", "+00:00"))
        agora = datetime.datetime.now(datetime.timezone.utc)
        return max(0, (fim - agora).days)
    except Exception:
        return None

def _fmt_data(s: str | None) -> str:
    if not s:
        return "—"
    try:
        dt = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return s[:10]

def _fmt_valor(v) -> str:
    if not v or v == 0:
        return "Não informado"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _link_edital(e: dict) -> str:
    link = e.get("linkSistemaOrigem") or ""
    if link:
        return link
    pncp = e.get("numeroControlePNCP") or ""
    return f"https://pncp.gov.br/app/editais/{pncp}" if pncp else "https://pncp.gov.br/app/editais"

def _get_com_retry(url: str, tentativas: int = 3) -> list[dict]:
    """GET com retry e backoff exponencial para tolerar rate-limit da API."""
    for tentativa in range(tentativas):
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            if r.status_code == 404:
                return []
            if r.status_code == 429:
                espera = 2 ** tentativa
                time.sleep(espera)
                continue
            r.raise_for_status()
            data = r.json()
            return data.get("data") or (data if isinstance(data, list) else [])
        except requests.exceptions.Timeout:
            if tentativa < tentativas - 1:
                time.sleep(1)
        except Exception:
            break
    return []

# ════════════════════════════════════════════════════════════
# FUNÇÕES — ANALISTA DE PDF (IA)
# ════════════════════════════════════════════════════════════

def extrair_texto_pdf(pdf_file) -> str:
    """Extrai texto de um arquivo PDF carregado via Streamlit com indicador de progresso."""
    try:
        reader = pypdf.PdfReader(pdf_file)
        texto_completo = ""
        total_pags = len(reader.pages)
        # Limitamos a 50 páginas para evitar estourar o contexto da IA free
        num_paginas = min(total_pags, 50)
        
        prog_extracao = st.progress(0, text=f"⏳ Iniciando leitura de {num_paginas} páginas...")
        
        for i in range(num_paginas):
            page = reader.pages[i]
            texto_completo += f"\n--- PÁGINA {i+1} ---\n" + (page.extract_text() or "")
            pct = int(((i + 1) / num_paginas) * 100)
            prog_extracao.progress(pct, text=f"📂 Lendo página {i+1} de {num_paginas}...")
            
        prog_extracao.empty()
        
        # SANEAMENTO: Remove caracteres nulos e de controle que quebram o JSON da API
        texto_completo = texto_completo.replace("\x00", "").replace("\r", " ")
        # Remove espaços excessivos e normaliza quebras
        texto_completo = re.sub(r'\n{3,}', '\n\n', texto_completo)
        
        return texto_completo.strip()
    except Exception as e:
        return f"Erro ao ler PDF: {str(e)}"

def obter_pergunta_ia(pergunta: str, contexto: str, historico: list) -> str:
    """Envia pergunta sobre o PDF para a API OpenRouter com memória."""
    if not OPENROUTER_API_KEY:
        return "⚠️ Erro: OPENROUTER_API_KEY não configurada."

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://licitaai.local",
        "X-Title": "LicitaAI Analyst"
    }

    # Contexto do sistema com o conteúdo do edital
    system_prompt = f"""
    Você é o Analista Master de Licitações da PE&CR Soluções. 
    Seu objetivo é analisar o edital abaixo e responder perguntas de forma técnica, estratégica e precisa.
    Foque em prazos, valores, exigências técnicas (CNAE/Atestados) e riscos.
    
    CONTEÚDO DO EDITAL:
    {contexto[:35000]} # Limite de segurança de caracteres (reduzido para evitar 400 Bad Request)
    """
    
    messages = [{"role": "system", "content": system_prompt}]
    # Adiciona histórico (memória)
    for msg in historico[-6:]: # Mantém as últimas 6 mensagens para contexto solar
        messages.append(msg)
    # Adiciona pergunta atual
    messages.append({"role": "user", "content": pergunta})

    # TENTATIVA 1: Modelo Principal
    try:
        r = requests.post(url, headers=headers, json={
            "model": MODEL_IA,
            "messages": messages,
            "temperature": 0.5
        }, timeout=45)
        
        # Se falhar (400, 404, 429), partimos para o Fallback
        if r.status_code in [400, 404, 429]:
            r = requests.post(url, headers=headers, json={
                "model": MODEL_IA_FALLBACK,
                "messages": messages,
                "temperature": 0.5
            }, timeout=45)
        
        if r.status_code != 200:
            return f"❌ Erro crítico em todos os modelos (HTTP {r.status_code}): {r.text}"
            
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Erro na consulta à IA: {str(e)}"

@st.cache_data(ttl=3600, show_spinner=False)
def obter_insight_ia(objeto: str, cnae: str) -> dict:
    """Consulta OpenRouter para analisar a viabilidade e estratégia do edital."""
    if not OPENROUTER_API_KEY:
        return {}

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://licitaai.streamlit.app",
        "X-Title": "LicitaAI",
        "Content-Type": "application/json"
    }

    prompt = f"""
    Você é um consultor sênior de licitações da PE&CR Soluções. 
    Analise o edital abaixo e forneça uma resposta em JSON.
    
    OBJETO: {objeto}
    SETOR: {cnae}
    
    Responda EXCLUSIVAMENTE no formato JSON:
    {{
      "resumo": "Uma frase curta e direta sobre o que deve ser feito.",
      "score_fit": 85, // nota de 0 a 100 de compatibilidade
      "dica": "Sugestão técnica ou estratégia para vencer esse certame."
    }}
    """

    # TENTATIVA 1: Modelo Principal
    try:
        r = requests.post(url, headers=headers, json={
            "model": MODEL_IA,
            "messages": [{"role": "user", "content": prompt}]
        }, timeout=20)
        
        # Fallback se necessário
        if r.status_code in [400, 404, 429]:
            r = requests.post(url, headers=headers, json={
                "model": MODEL_IA_FALLBACK,
                "messages": [{"role": "user", "content": prompt}]
            }, timeout=20)
            
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"]
        # Limpa possível markdown da resposta
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        return json.loads(raw)
    except Exception:
        return {}

def render_ia_section(e: dict):
    """Renderiza a caixa de insight de IA na interface."""
    objeto = e.get("objetoCompra") or ""
    cnae   = e.get("_cnae") or ""
    
    with st.expander("✨ Ver Insight Estratégico (IA)", expanded=False):
        with st.spinner("Analisando edital com IA..."):
            insight = obter_insight_ia(objeto, cnae)
            
        if not insight:
            st.info("Não foi possível gerar um insight para este edital no momento.")
            return

        st.markdown(f"""
        <div class="insight-box">
          <b>🎯 Resumo Estratégico:</b><br>{insight.get('resumo', '—')}<br><br>
          <b>📊 Compatibilidade (PE&CR Fit):</b> {insight.get('score_fit', 0)}%<br>
          <b>💡 Dica de Ouro:</b> {insight.get('dica', '—')}
        </div>
        """, unsafe_allow_html=True)

@st.cache_data(ttl=300, show_spinner=False)
def buscar_pagina(di: str, df: str, uf: str, mod: int, pagina: int, termo: str = "") -> list[dict]:
    """Busca uma página na API PNCP com suporte a filtro de termo."""
    url = (f"{PNCP_BASE}/contratacoes/publicacao"
           f"?dataInicial={di}&dataFinal={df}"
           f"&codigoModalidadeContratacao={mod}"
           f"&pagina={pagina}&tamanhoPagina=50")
    if uf:
        url += f"&uf={uf}"
    if termo:
        url += f"&termo={requests.utils.quote(termo)}"
    
    return _get_com_retry(url)

def _processar_edital(e: dict, radar: str, valor_min: float, municipio_filtro: str, termo_manual: str = "") -> dict | None:
    """Aplica filtros locais a um edital individual."""
    obj = (e.get("objetoCompra") or "").lower()

    if any(term in obj for term in BLACKLIST_PRODUTOS):
        return None

    if any(b in obj for b in ["software", "licença microsoft", "tecnologia da informação"]):
        return None

    val = e.get("valorTotalEstimado") or 0
    if val > 0 and val < valor_min:
        return None

    dias_r = _dias_restantes(e.get("dataEncerramentoProposta"))
    if dias_r is not None and dias_r <= 0:
        return None

    municipio_e = ((e.get("unidadeOrgao") or {}).get("municipioNome") or "").lower()
    if municipio_filtro and municipio_filtro.lower() not in municipio_e:
        return None

    match_cnae = None
    if termo_manual:
        match_cnae = "🔍 Explorador Manual"
    else:
        if radar == "FEDERAL":
            for cnae_label, pal in CNAES_FEDERAL.items():
                if any(p.lower() in obj for p in pal):
                    match_cnae = cnae_label
                    break
        else:
            for cnae_label, pal in CNAES_REGIONAL.items():
                if any(p.lower() in obj for p in pal):
                    match_cnae = cnae_label
                    break
            if not match_cnae:
                for cnae_label, pal in CNAES_FEDERAL.items():
                    if any(p.lower() in obj for p in pal):
                        match_cnae = cnae_label
                        break

    if not match_cnae:
        return None

    e["_radar"]        = radar
    e["_cnae"]         = match_cnae
    e["_dias"]         = dias_r
    e["_link"]         = _link_edital(e)
    e["_valor_fmt"]    = _fmt_valor(val)
    e["_abertura_fmt"] = _fmt_data(e.get("dataAberturaProposta"))
    e["_encerra_fmt"]  = _fmt_data(e.get("dataEncerramentoProposta"))
    e["_orgao"]        = ((e.get("orgaoEntidade") or {}).get("nomeFantasia")
                          or (e.get("orgaoEntidade") or {}).get("razaoSocial")
                          or "Órgão não identificado")
    e["_uf"]           = (e.get("unidadeOrgao") or {}).get("ufSigla") or ""
    e["_municipio"]    = (e.get("unidadeOrgao") or {}).get("municipioNome") or ""
    e["_modalidade"]   = e.get("modalidadeNome") or MODALIDADES.get(e.get("codigoModalidadeContratacao"), "—")
    e["_pncp_num"]     = e.get("numeroControlePNCP") or "—"
    
    return e

@st.cache_data(ttl=300, show_spinner=False)
def varrer(dias: int, mods: tuple, valor_min: float, municipio_filtro: str, 
           modo: str = "RADAR", uf_manual: str = "", termo_manual: str = "") -> list[dict]:
    """Varre PNCP em modo paralelo suportando Radar ou Explorador Manual."""
    di, df = _data_str(dias)
    tarefas = []
    
    if modo == "RADAR":
        for mod in mods:
            for pg in [1, 2]:
                tarefas.append(("FEDERAL", "", mod, pg, ""))
        for uf in UFS_REGIONAL:
            for mod in mods:
                for pg in [1, 2]:
                    tarefas.append(("REGIONAL", uf, mod, pg, ""))
    else:
        radar_lbl = "EXPLORADOR"
        ufs = [uf_manual] if uf_manual else [""]
        for uf in ufs:
            for mod in mods:
                for pg in [1, 2, 3]:
                    tarefas.append((radar_lbl, uf, mod, pg, termo_manual))

    resultados_filtrados = {}
    progress_text = f"Varrendo PNCP ({modo})..."
    prog_bar = st.progress(0, text=progress_text)
    
    total_t = len(tarefas)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(buscar_pagina, di, df, uf, mod, pg, termo): (radar, uf, mod, pg, termo) 
                   for radar, uf, mod, pg, termo in tarefas}
        
        for i, future in enumerate(as_completed(futures)):
            radar, uf, mod, pg, termo = futures[future]
            try:
                items = future.result()
                if items:
                    for e in items:
                        processado = _processar_edital(e, radar, valor_min, municipio_filtro, termo_manual)
                        if processado:
                            chave = processado["_pncp_num"]
                            if chave not in resultados_filtrados or radar == "REGIONAL":
                                resultados_filtrados[chave] = processado
                
                pct = int((i + 1) / total_t * 100)
                prog_bar.progress(pct, text=f"Radar {modo} - {uf or 'BR'} {pg}... {pct}%")
            except Exception:
                continue

    prog_bar.empty()
    res = list(resultados_filtrados.values())
    res.sort(key=lambda x: (x.get("_dias") or 9999))
    return res

# ════════════════════════════════════════════════════════════
# FUNÇÕES — TELEGRAM
# ════════════════════════════════════════════════════════════
def _telegram_post(texto: str) -> bool:
    if not TOKEN_TELEGRAM or not CHAT_ID or CHAT_ID == "SEU_CHAT_ID_AQUI":
        return False
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id":    CHAT_ID,
            "text":       texto,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }, timeout=15)
        return r.status_code == 200
    except Exception:
        return False

def enviar_edital_telegram(e: dict) -> bool:
    dias = e.get("_dias")
    urgencia = "🚨" if (dias is not None and dias <= 2) else ("⚠️" if (dias is not None and dias <= 5) else "🟢")
    dias_txt = f"{dias} dia(s)" if dias is not None else "verificar"
    radar_tipo = e.get("_radar", "SISTEMA")

    texto = (
        f"{urgencia} *NOVO EDITAL ({radar_tipo})*\n\n"
        f"🏢 *Órgão:* {e['_orgao']} · {e['_uf']}\n"
        f"📋 *Modalidade:* {e['_modalidade']}\n\n"
        f"📄 *Objeto:*\n{(e.get('objetoCompra') or '')[:350]}\n\n"
        f"💰 *Valor:* {e['_valor_fmt']}\n"
        f"📌 *CNAE:* `{e['_cnae'].split('·')[0].strip()}`\n"
        f"⏳ *Prazo:* {e['_encerra_fmt']} ({dias_txt} restantes)\n"
        f"🔢 *PNCP:* `{e['_pncp_num']}`\n\n"
        f"👉 [ACESSAR EDITAL]({e['_link']})"
    )
    return _telegram_post(texto)

def enviar_resumo_telegram(total: int, novos: int, ja_enviados: int):
    emoji = "✅" if novos > 0 else "ℹ️"
    texto = (
        f"{emoji} *Varredura LicitaAI — PE&CR*\n\n"
        f"*{total}* edital(is) encontrado(s)\n"
        f"*{novos}* novo(s) enviado(s) agora\n"
        f"*{ja_enviados}* já notificado(s) anteriormente\n"
        f"_Brasília · {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}_"
    )
    _telegram_post(texto)

# ════════════════════════════════════════════════════════════
# INTERFACE STREAMLIT
# ════════════════════════════════════════════════════════════

# ── Alerta de configuração ────────────────────────────────────
chat_id_ok = CHAT_ID and CHAT_ID != "SEU_CHAT_ID_AQUI"
token_ok   = bool(TOKEN_TELEGRAM)

if not token_ok or not chat_id_ok:
    avisos = []
    if not token_ok:
        avisos.append("TOKEN_TELEGRAM não definido no arquivo <b>.env</b>")
    if not chat_id_ok:
        avisos.append(
            "CHAT_ID não configurado → execute <code>python obter_chat_id.py</code> "
            "e preencha o valor no <b>.env</b>"
        )
    st.markdown(
        "<div class='config-alert'>⚠️ <b>Configuração pendente:</b><br>" +
        "<br>".join(f"• {a}" for a in avisos) + "</div>",
        unsafe_allow_html=True
    )

# ── Cabeçalho ───────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
  <div>
    <h1>🏛️ LicitaAI — Inteligência de Mercado</h1>
    <div class="cnpj">PE&CR Soluções Ltda · CNPJ 13.441.865/0001-35 · Monitor Híbrido (Fed + Reg)</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar — Modo de Busca ────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏹 Modo de Operação")
    modo_op = st.radio(
        "Selecione o motor de busca:",
        options=["📡 Radar Inteligente", "🔍 Explorador Manual"],
        help="Radar: Pesquisa automática setores configurados. Explorador: Busca livre por termo e estado."
    )
    st.markdown("---")

    st.markdown("### ⚙️ Filtros Gerais")
    dias = st.selectbox(
        "Período (publicação)",
        options=[1, 3, 7, 15, 30],
        index=2,
        format_func=lambda x: f"Últimos {x} dia(s)"
    )

    if "Radar" in modo_op:
        st.info("📡 **Radar Híbrido Ativo:**\n- **Nacional**: Saúde e Social\n- **Regional (GO/DF)**: Infraestrutura")
        opcoes_servicos = list(CNAES_FEDERAL.keys()) + list(CNAES_REGIONAL.keys())
        servicos_sel = st.multiselect(
            "Filtrar Resultados por Serviço",
            options=opcoes_servicos,
            default=opcoes_servicos
        )
        uf_manual = ""
        termo_manual = ""
    else:
        st.success("🔍 **Explorador Manual Ativado**\nLivre de categorias fixas.")
        termo_manual = st.text_input("Palavra-chave (Obrigatório)", placeholder="Ex: vigilância, limpeza, TI...")
        uf_manual = st.selectbox("Estado (UF)", options=[""] + ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"], format_func=lambda x: "🇧🇷 Brasil Todo" if x == "" else x)
        servicos_sel = []

    mods_sel = st.multiselect(
        "Modalidades",
        options=list(MODALIDADES.keys()),
        default=[6, 7],
        format_func=lambda x: MODALIDADES[x],
    )

    ia_ativa = st.toggle("Ativar Consultoria IA 🧠", value=True, help="Usa IA para resumir o edital e dar dicas estratégicas")

    valor_min = st.number_input(
        "Valor mínimo (R$)",
        min_value=0,
        value=VALOR_MINIMO,
        step=1000,
        format="%d"
    )

    municipio_filtro = st.text_input(
        "Filtrar por município (opcional)",
        placeholder="Ex: Goiânia, Brasília..."
    )

    termo_filtro = st.text_input(
        "Filtrar por termo no objeto (opcional)",
        placeholder="Ex: oxigênio, vigilante, obra..."
    )

    st.markdown("---")
    st.markdown("### 📲 Telegram")

    telegram_ok_label = "✅ Configurado" if chat_id_ok else "⚠️ CHAT_ID pendente"
    st.caption(telegram_ok_label)

    # O toggle agora inicia DESLIGADO (False) por padrão para sua segurança. 
    # Use o identificador estável (key) para persistir o estado durante o uso.
    enviar_tg = st.toggle(
        "Enviar ao Telegram", 
        value=False, 
        key="tg_sender_active", 
        disabled=not chat_id_ok,
        help="Ligue apenas quando quiser que os novos resultados sejam disparados para o Telegram."
    )

    if not chat_id_ok:
        st.info("Execute `python obter_chat_id.py` para configurar.")

    st.markdown("---")

    # Informação sobre deduplicação
    ids_enviados = _carregar_enviados()
    st.caption(f"🗂️ {len(ids_enviados)} edital(is) já registrado(s) no histórico")

    col_a, col_b = st.columns(2)
    with col_a:
        buscar = st.button("🔍 Buscar", use_container_width=True, type="primary")
    with col_b:
        if st.button("🗑️ Limpar histórico", use_container_width=True, help="Remove todos os IDs do registro de enviados"):
            _salvar_enviados(set())
            st.success("Histórico limpo!")
            st.rerun()

# ── Estrutura de Abas (Sempre Visível) ───────────────────────
aba_novos, aba_todos, aba_analista = st.tabs([
    "🆕 Novos Editais",
    "📋 Todos",
    "🤖 Analista de Editais (IA)"
])

with aba_analista:
    st.markdown("### 🤖 Analista de Editais Inteligente")
    st.info("Suba o PDF de um edital para que a IA analise, extraia informações e tire suas dúvidas.")

    # Inicialização do estado do chat
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "pdf_context" not in st.session_state:
        st.session_state.pdf_context = ""
    if "pdf_filename" not in st.session_state:
        st.session_state.pdf_filename = ""

    # Uploader
    uploaded_file = st.file_uploader("📂 Arraste o PDF do edital aqui", type="pdf", key="analista_pdf_uploader")

    if uploaded_file:
        if st.session_state.pdf_filename != uploaded_file.name:
            with st.spinner("⏳ Lendo e interpretando edital..."):
                texto = extrair_texto_pdf(uploaded_file)
                st.session_state.pdf_context = texto
                st.session_state.pdf_filename = uploaded_file.name
                st.session_state.chat_messages = [] # Limpa chat ao mudar de edital
                st.success(f"✅ Edital '{uploaded_file.name}' carregado com sucesso!")

    if st.session_state.pdf_context:
        st.markdown("---")
        # Container de Chat
        chat_container = st.container(height=400)
        
        with chat_container:
            for message in st.session_state.chat_messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # Input de Chat
        if prompt := st.chat_input("Pergunte algo sobre este edital..."):
            # Adiciona mensagem do usuário
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)

            # Busca resposta da IA
            with chat_container:
                with st.chat_message("assistant"):
                    with st.spinner("Pensando..."):
                        resposta = obter_pergunta_ia(
                            prompt, 
                            st.session_state.pdf_context, 
                            st.session_state.chat_messages[:-1]
                        )
                        st.markdown(resposta)
            
            # Adiciona mensagem da IA ao histórico
            st.session_state.chat_messages.append({"role": "assistant", "content": resposta})
    else:
        st.write("Aguardando upload de documento...")

# ── Corpo principal (Busca e Listagem) ───────────────────────
if not buscar:
    with aba_novos:
        st.markdown("""
        <div style="text-align:center; padding:60px 20px; color:#666;">
          <div style="font-size:52px; margin-bottom:12px;">🏛️</div>
          <h3 style="color:#1a5c2a;">Busca Híbrida Ativada</h3>
          <p>O LicitaAI agora busca <strong>Saúde e Assistência Social</strong> em todo o Brasil e <strong>Infraestrutura</strong> em GO e DF.</p>
          <p style="font-size:13px;">Otimização Multi-threading ativa · Resultado ultra-rápido</p>
        </div>
        """, unsafe_allow_html=True)
    with aba_todos:
        st.write("Aguardando busca...")
    st.stop()

# ── Busca ────────────────────────────────────────────────────
modo_slug = "RADAR" if "Radar" in modo_op else "MANUAL"

if modo_slug == "MANUAL" and not termo_manual:
    st.warning("⚠️ Insira uma palavra-chave para iniciar a exploração manual.")
    st.stop()

with st.spinner(f"Consultando API do PNCP ({modo_op})…"):
    editais = varrer(
        dias,
        tuple(mods_sel),
        float(valor_min),
        municipio_filtro.strip(),
        modo=modo_slug,
        uf_manual=uf_manual,
        termo_manual=termo_manual.strip()
    )

# ── Filtragem Local (Apenas para modo Radar) ─────────────────
if editais and modo_slug == "RADAR":
    if servicos_sel:
        editais = [e for e in editais if e["_cnae"] in servicos_sel]
    
    if termo_filtro:
        editais = [e for e in editais if termo_filtro.lower() in (e.get("objetoCompra") or "").lower()]
elif editais and modo_slug == "MANUAL" and termo_filtro:
    # No manual, o termo_filtro serve como refinamento extra
    editais = [e for e in editais if termo_filtro.lower() in (e.get("objetoCompra") or "").lower()]

# ── Carrega histórico de enviados ────────────────────────────
ids_enviados = _carregar_enviados()

# ── Calcula novos × já enviados ──────────────────────────────
novos_editais = [e for e in editais if e.get("_pncp_num") not in ids_enviados]
ja_enviados_l = [e for e in editais if e.get("_pncp_num") in ids_enviados]

# ── Métricas ─────────────────────────────────────────────────
total       = len(editais)
abertos     = sum(1 for e in editais if (e.get("_dias") or 0) > 0)
urgentes    = sum(1 for e in editais if e.get("_dias") is not None and e["_dias"] <= 5)
valor_total = sum(e.get("valorTotalEstimado") or 0 for e in editais)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("📋 Editais encontrados", total)
col2.metric("🆕 Novos (não enviados)", len(novos_editais))
col3.metric("✅ Com propostas abertas", abertos)
col4.metric("⚠️ Urgentes (≤5 dias)", urgentes)
col5.metric("💰 Valor total", f"R$ {valor_total:,.0f}".replace(",", ".") if valor_total else "—")

st.markdown("---")

# ── Envio Telegram (apenas novos) ───────────────────────────
if enviar_tg and novos_editais:
    with st.spinner(f"Enviando {len(novos_editais)} novo(s) ao Telegram…"):
        enviados_ok = 0
        for e in novos_editais:
            # 🛑 BREAK DE SEGURANÇA: Se o usuário desligar o toggle no meio do envio, interrompe o loop
            if not st.session_state.get("tg_sender_active", False):
                st.warning("⚠️ Envio interrompido manualmente pelo usuário.")
                break

            if enviar_edital_telegram(e):
                ids_enviados.add(e.get("_pncp_num", ""))
                enviados_ok += 1
                time.sleep(0.8)
        _salvar_enviados(ids_enviados)
        enviar_resumo_telegram(total, enviados_ok, len(ja_enviados_l))
    st.success(f"✅ {enviados_ok} novo(s) edital(is) enviado(s) ao Telegram.")
elif enviar_tg and not novos_editais:
    st.info("ℹ️ Todos os editais encontrados já foram enviados anteriormente.")

# ── Lista de editais ─────────────────────────────────────────
if not editais:
    with aba_novos:
        st.info("Nenhum edital encontrado para os filtros selecionados.")
    with aba_todos:
        st.info("Nenhum edital encontrado.")
    st.stop()

# Atualiza títulos das abas com contadores
# (No Streamlit tabs são estáticas, então apenas preenchemos o conteúdo)

def renderizar_editais(lista: list[dict], ja_enviado: bool = False, prefixo: str = "e"):
    if not lista:
        st.write("Sem editais para exibir.")
        return

    for i, e in enumerate(lista, 1):
        pncp_num = e.get("numeroControlePNCP") or f"ID-{i}"
        orgao    = e["_orgao"]
        municipio = e.get("_municipio") or ""
        uf        = e.get("_uf") or ""
        objeto    = limpar_html(e.get("objetoCompra") or "Objeto não informado")
        cnae      = e["_cnae"]
        valor     = e["_valor_fmt"]
        dias_r    = e.get("_dias")
        abertura  = e["_abertura_fmt"]
        encerra   = e["_encerra_fmt"]
        modalidade= e["_modalidade"]
        link      = e["_link"]

        # IDs para busca de arquivos (Download Direto)
        # O PNCP usa CNPJ/ANO/SEQUENCIAL no path dos arquivos
        cnpj_orgao = (e.get("orgaoEntidade") or {}).get("cnpj")
        ano_compra = e.get("anoCompra")
        seq_compra = e.get("sequencialCompra")

        # Cor da borda
        if dias_r is not None and dias_r <= 2:
            card_class  = "edital-card urgente"
            badge_class = "badge badge-vermelho"
            badge_txt   = f"🚨 URGENTE — {dias_r}d"
        elif dias_r is not None and dias_r <= 5:
            card_class  = "edital-card atencao"
            badge_class = "badge badge-amarelo"
            badge_txt   = f"⚠️ {dias_r} dias restantes"
        elif dias_r is not None:
            card_class  = "edital-card"
            badge_class = "badge badge-verde"
            badge_txt   = f"🟢 {dias_r} dias restantes"
        else:
            card_class  = "edital-card"
            badge_class = "badge badge-cinza"
            badge_txt   = "📋 Sem data"

        if ja_enviado:
            card_class += " ja-enviado"
            historico_badge = '<span class="badge badge-azul" style="margin-left:6px;">📨 Já enviado</span>'
        else:
            historico_badge = ""

        # Renderização HTML limpa
        st.markdown(f"""
        <div class="{card_class}">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:6px; margin-bottom:6px;">
            <div>
              <div class="edital-numero">#{i} · {pncp_num}</div>
              <div class="edital-orgao">{orgao}</div>
              {f'<div style="font-size:12px;color:#666;">📍 {municipio} · {uf}</div>' if municipio else ''}
            </div>
            <div>
              <span class="{badge_class}">{badge_txt}</span>
              {historico_badge}
            </div>
          </div>
          <div class="edital-objeto"><strong>Objeto:</strong> {objeto[:600]}{'...' if len(objeto) > 600 else ''}</div>
          <div class="badge-ia" style="margin-top:6px; margin-bottom:10px;">📡 Radar {e.get("_radar")}</div>
          <div class="edital-meta">
            <span>📋 <strong>Modalidade:</strong> {modalidade}</span>
            <span>📌 <strong>CNAE:</strong> {cnae.split('·')[0].strip()}</span>
            <span>💰 <strong>Valor:</strong> {valor}</span>
            <span>📅 <strong>Abertura:</strong> {abertura}</span>
            <span>⏳ <strong>Encerramento:</strong> {encerra}</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Botões de Ação Dinâmicos
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        
        with col_btn1:
            st.link_button("🔗 Ver no PNCP", link, use_container_width=True, help="Acessar página oficial", key=f"{prefixo}_link_pncp_{pncp_num}_{i}")
        
        with col_btn2:
            # Busca arquivos para tentar download direto
            if cnpj_orgao and ano_compra and seq_compra:
                arquivos = buscar_arquivos_pncp(cnpj_orgao, ano_compra, seq_compra)
                # Filtra o arquivo que parece ser o Edital
                edital_file = next((f for f in arquivos if "edital" in (f.get("titulo") or "").lower() or "retific" in (f.get("titulo") or "").lower()), None)
                if edital_file:
                    url_download = edital_file.get("url") or edital_file.get("linkDownload")
                    if url_download:
                        st.link_button("📥 Baixar Edital", url_download, use_container_width=True, type="primary", key=f"{prefixo}_dl_edital_{pncp_num}_{i}")
                    else:
                        st.button("🚫 S/ Edital", disabled=True, use_container_width=True, key=f"{prefixo}_no_link_{pncp_num}_{i}")
                else:
                    st.button("🔍 S/ Arq", disabled=True, use_container_width=True, help="Nenhum arquivo de edital anexado no PNCP", key=f"{prefixo}_no_arq_{pncp_num}_{i}")
        
        # Seção de IA (fora do markdown para funcionar o st.expander)
        if ia_ativa:
            render_ia_section(e)

with aba_novos:
    st.subheader(f"🆕 Novos Editais ({len(novos_editais)})")
    renderizar_editais(novos_editais, ja_enviado=False, prefixo="novos")

with aba_todos:
    st.subheader(f"📋 Todos os Editais ({total})")
    renderizar_editais(novos_editais, ja_enviado=False, prefixo="todas_novas")
    renderizar_editais(ja_enviados_l, ja_enviado=True, prefixo="todas_velhas")

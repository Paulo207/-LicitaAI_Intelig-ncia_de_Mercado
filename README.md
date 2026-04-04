# 🏛️ LicitaAI — Inteligência Estratégica de Licitações
### Dashboard Híbrido PNCP + Analista de Editais (IA) · PE&CR Soluções Ltda

O **LicitaAI** é uma plataforma de monitoramento e análise de licitações desenvolvida para identificar oportunidades de alto valor de forma automatizada, integrando dados públicos do PNCP com inteligência artificial avançada.

---

## 🚀 Funcionalidades Premium

### 📡 Radar Híbrido Inteligente
- **Nacional**: Monitoramento automático de Saúde e Assistência Social em todo o Brasil.
- **Regional (GO + DF)**: Foco total em Infraestrutura e Manutenção Predial.
- **Busca Híbrida**: Multi-threading para varredura ultrarrápida de editais recentes.

### 🤖 Analista de Editais (IA)
- **Extração OCR**: Upload e leitura de PDFs (editais) com até 50 páginas.
- **Consultoria Estratégica**: Chat interativo para tirar dúvidas sobre prazos, atestados e exigências técnicas.
- **Insights Diretos**: Botão de insight instantâneo em cada card de edital (PE&CR Fit Score).

### 📲 Automação de Leads
- **Telegram Sync**: Notificação em tempo real de novos editais qualificados.
- **Deduplicação**: Inteligência que evita o envio repetido de oportunidades já visualizadas.
- **Download Direto**: Integração com a API de arquivos do PNCP para baixar editais sem sair do sistema.

---

## 📂 Estrutura do Projeto

| Arquivo | Descrição |
|---|---|
| `app.py` | Aplicação principal (Dashboard + Chat IA) |
| `config.py` | Centralizador de regras de negócio e CNAEs |
| `obter_chat_id.py` | Utilitário para configuração do Telegram |
| `.env.example` | Modelo para configuração das credenciais e chaves API |

---

## ⚡ Guia Rápido de Instalação

```bash
# 1. Clone o repositório e acesse a pasta
git clone https://github.com/Paulo207/-LicitaAI_Intelig-ncia_de_Mercado.git
cd -LicitaAI_Intelig-ncia_de_Mercado

# 2. Crie e ative seu ambiente virtual
python -m venv .venv
source .venv/bin/activate # Linux/Mac
.\.venv\Scripts\activate # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure o arquivo .env (veja .env.example)
# Adicione suas chaves: TOKEN_TELEGRAM, CHAT_ID, OPENROUTER_API_KEY
```

## 🏗️ Stack Tecnológica
- **Linguagem**: Python 3.10+
- **Frontend**: Streamlit (Premium UI)
- **IA**: OpenRouter (Llama 3.1 / GLM-4.5)
- **Integração**: API Pública PNCP (gov.br)

---
*Desenvolvido por **PE&CR Soluções Ltda** · CNPJ 13.441.865/0001-35*

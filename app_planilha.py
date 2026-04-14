"""
============================================================
  PREENCHIMENTO AUTOMÁTICO — MARGEM BRUTA
  ibis Budget São Paulo Paraíso

  Uso: streamlit run app_planilha.py
  Dependências: pip install streamlit pdfplumber pandas openpyxl
============================================================
"""

import re
import datetime
import streamlit as st
import pdfplumber
import pandas as pd
from openpyxl import load_workbook
from io import BytesIO

st.set_page_config(page_title="Margem Bruta — Preenchimento Auto", page_icon="🏨", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&family=DM+Mono&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.main{background:#f5f4f0;}
.hdr{background:#1a1a2e;color:white;padding:1.5rem 2rem;border-radius:12px;margin-bottom:1.5rem;}
.hdr h1{color:white;margin:0;font-size:1.4rem;}
.hdr p{color:#aaa;margin:.3rem 0 0;font-size:.85rem;}
.step{background:white;border-radius:12px;padding:1.2rem 1.5rem;margin-bottom:1rem;border-left:4px solid #0d6efd;}
.step h3{margin:0 0 .3rem;font-size:.95rem;color:#1a1a2e;}
.step p{margin:0;font-size:.82rem;color:#666;}
.ok{background:#d1e7dd;border:1px solid #198754;border-radius:8px;padding:.8rem 1rem;font-size:.85rem;margin:.4rem 0;}
.warn{background:#fff3cd;border:1px solid #ffc107;border-radius:8px;padding:.8rem 1rem;font-size:.85rem;margin:.4rem 0;}
.err{background:#f8d7da;border:1px solid #dc3545;border-radius:8px;padding:.8rem 1rem;font-size:.85rem;margin:.4rem 0;}
.sec{font-size:.7rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
     color:#999;margin:1.5rem 0 .5rem;padding-bottom:4px;border-bottom:1px solid #eee;}
.preview-row{background:white;border-radius:8px;padding:.8rem 1rem;margin:.3rem 0;
             display:flex;justify-content:space-between;align-items:center;font-size:.85rem;}
.preview-col{color:#666;font-size:.75rem;}
.preview-val{font-family:'DM Mono',monospace;font-weight:700;color:#1a1a2e;}
</style>
""", unsafe_allow_html=True)

# ── Regex (validados contra PDFs reais) ───────────────────────────────────────

RE_TCPOS = re.compile(
    r'^(\d{1,2}/\d{1,2}/\d{4})\s+'
    r'\$([\d,]+\.\d{2})\s+\$([\d,]+\.\d{2})\s+\(\$([\d,]+\.\d{2})\)\s+'
    r'\$([\d,]+\.\d{2})\s+\$([\d,]+\.\d{2})\s+\$([\d,]+\.\d{2})\s+'
    r'\$([\d,]+\.\d{2})\s+\$([\d,]+\.\d{2})\s+\$([\d,]+\.\d{2})\s+'
    r'\$([\d,]+\.\d{2})\s+\$([\d,]+\.\d{2})\s+\$([\d,]+\.\d{2})'
)
RE_OPERA  = re.compile(r'^\s*(\d{4})\s+(.+?)\s+(- [\d,]+\.\d{2}|[\d,]+\.\d{2})\s*$')
RE_NA02   = re.compile(r'Food And Beverage Revenue\s+([\d,]+\.\d{2})')

def n(s): return float(s.replace(' ','').replace(',',''))
def fmt(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

# ── Funções de extração ───────────────────────────────────────────────────────

def extrair_tcpos(file):
    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            for linha in (p.extract_text() or '').splitlines():
                m = RE_TCPOS.match(linha.strip())
                if m:
                    return {
                        'data':        m.group(1),
                        'alimento':    n(m.group(6)),
                        'cafe_manha':  n(m.group(7)),
                        'pensao':      n(m.group(8)),
                        'nao_alcool':  n(m.group(10)),
                        'cervejas':    n(m.group(13)),
                    }
    return None

def extrair_opera_na03(file):
    campos = {}
    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            for linha in (p.extract_text() or '').splitlines():
                m = RE_OPERA.match(linha)
                if m:
                    campos[m.group(1)] = {'nome': m.group(2).strip(), 'valor': n(m.group(3))}
    return campos

def extrair_opera_na02(file):
    with pdfplumber.open(file) as pdf:
        for p in pdf.pages:
            for linha in (p.extract_text() or '').splitlines():
                m = RE_NA02.search(linha)
                if m:
                    return n(m.group(1))
    return None

# ── Função principal: preenche planilha ──────────────────────────────────────

def preencher_planilha(excel_bytes, tcpos, opera, fb_revenue):
    """
    Recebe:
      - excel_bytes: bytes da planilha do mês
      - tcpos: dict extraído do PDF TCPOS
      - opera: dict extraído do PDF NA03
      - fb_revenue: float extraído do PDF NA02 (ou None)

    Retorna: bytes do Excel atualizado
    """
    def get(cod): return opera.get(cod, {}).get('valor', 0.0)

    # ── Calcula todos os valores ──────────────────────────────────────────────
    alimento   = tcpos['alimento']
    nao_alcool = tcpos['nao_alcool']
    cervejas   = tcpos['cervejas']

    # C = Café da Manhã (+) 2042 + MBUFFF 2049
    cafe_incluso = get('2042') + get('2049')

    # D = Água Inclusa 2013
    agua_inclusa = get('2013')

    # Estornos de bar
    estornos_bar = {
        cod: info for cod, info in opera.items()
        if 'ajuste' in info['nome'].lower()
        and 'bar'   in info['nome'].lower()
        and info['valor'] < 0
    }
    # Separa estorno por tipo para lançar na coluna correta da aba ESTORNO
    # O estorno de "Bebidas Cafe" vai para coluna F (Bebidas Não Alcoólicas)
    estorno_nao_alcool = sum(
        abs(v['valor']) for v in estornos_bar.values()
        if 'bebidas' in v['nome'].lower() or 'bar 1' in v['nome'].lower()
    )
    estorno_alimento = sum(
        abs(v['valor']) for v in estornos_bar.values()
        if 'alimento' in v['nome'].lower()
    )
    estorno_cerveja = sum(
        abs(v['valor']) for v in estornos_bar.values()
        if 'cerv' in v['nome'].lower()
    )

    # ── Identifica a linha do dia na planilha ─────────────────────────────────
    # A planilha começa em A5 = 01/04. Linha = dia_do_mes + 4
    data_str = tcpos['data']  # ex: "01/04/2026"
    partes   = data_str.split('/')
    dia      = int(partes[0])
    linha    = dia + 4  # dia 1 → linha 5, dia 13 → linha 17, etc.

    # ── Abre e edita o Excel ──────────────────────────────────────────────────
    wb = load_workbook(BytesIO(excel_bytes))

    # ── Aba RECEITA ───────────────────────────────────────────────────────────
    ws = wb['RECEITA']

    ws[f'B{linha}'] = alimento      # Alimento TCPOS
    ws[f'C{linha}'] = cafe_incluso  # Café Incluso (2042+2049) — valor puro, não fórmula
    ws[f'D{linha}'] = agua_inclusa  # Pensão / Água Inclusa
    # E (Vinhos) — não preenche, sempre zero no ibis budget
    ws[f'F{linha}'] = nao_alcool    # Bebidas Não Alcoólicas TCPOS
    ws[f'G{linha}'] = cervejas      # Cervejas TCPOS
    # H (Álcool) — não preenche, sempre zero
    # I = SUM(B:H) — já é fórmula na planilha, preservada
    # V = Total Valor Opera (NA02)
    if fb_revenue is not None:
        ws[f'V{linha}'] = fb_revenue

    # Garante que as fórmulas de I, N, R, S, T, U, W existam na linha
    # (caso a linha esteja em branco / seja nova)
    if ws[f'I{linha}'].value is None:
        ws[f'I{linha}'] = f'=SUM(B{linha}:H{linha})'
    if ws[f'N{linha}'].value is None:
        ws[f'N{linha}'] = f'=SUM(J{linha}:M{linha})'
    if ws[f'R{linha}'].value is None:
        ws[f'R{linha}'] = f'=SUM(O{linha}:Q{linha})'
    if ws[f'S{linha}'].value is None:
        ws[f'S{linha}'] = f'=I{linha}+N{linha}+R{linha}'
    if ws[f'T{linha}'].value is None:
        ws[f'T{linha}'] = f"=+'ESTORNO RECEITA'!S{linha}"
    if ws[f'U{linha}'].value is None:
        ws[f'U{linha}'] = f'=+S{linha}-T{linha}'
    if ws[f'W{linha}'].value is None and fb_revenue is not None:
        ws[f'W{linha}'] = f'=+U{linha}-V{linha}'

    # ── Aba ESTORNO RECEITA ───────────────────────────────────────────────────
    ws_est = wb['ESTORNO RECEITA']

    if estorno_alimento > 0:
        ws_est[f'B{linha}'] = estorno_alimento    # col B = Alimento
    if estorno_nao_alcool > 0:
        ws_est[f'F{linha}'] = estorno_nao_alcool  # col F = Bebidas Não Alcoólicas
    if estorno_cerveja > 0:
        ws_est[f'G{linha}'] = estorno_cerveja     # col G = Cervejas

    # Garante fórmulas de total na linha de estorno
    if ws_est[f'I{linha}'].value is None:
        ws_est[f'I{linha}'] = f'=SUM(B{linha}:H{linha})'
    if ws_est[f'N{linha}'].value is None:
        ws_est[f'N{linha}'] = f'=SUM(J{linha}:M{linha})'
    if ws_est[f'R{linha}'].value is None:
        ws_est[f'R{linha}'] = f'=SUM(O{linha}:Q{linha})'
    if ws_est[f'S{linha}'].value is None:
        ws_est[f'S{linha}'] = f'=I{linha}+N{linha}+R{linha}'

    # ── Salva e retorna bytes ─────────────────────────────────────────────────
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue(), linha, {
        'alimento': alimento, 'cafe_incluso': cafe_incluso,
        'agua_inclusa': agua_inclusa, 'nao_alcool': nao_alcool,
        'cervejas': cervejas, 'fb_revenue': fb_revenue,
        'estorno_nao_alcool': estorno_nao_alcool,
        'estorno_alimento': estorno_alimento,
        'estorno_cerveja': estorno_cerveja,
        'data': data_str, 'linha': linha,
    }

# ── UI ────────────────────────────────────────────────────────────────────────

st.markdown('''
<div class="hdr">
    <h1>🏨 Margem Bruta — Preenchimento Automático</h1>
    <p>Suba os PDFs e a planilha do mês → receba o Excel já preenchido</p>
</div>
''', unsafe_allow_html=True)

# ── Passo 1: Planilha do mês ─────────────────────────────────────────────────
st.markdown('<div class="sec">📋 Passo 1 — Planilha do mês (Excel)</div>', unsafe_allow_html=True)
st.markdown("""
<div class="step">
    <h3>📂 Planilha Margem Bruta (.xlsx)</h3>
    <p>A planilha do mês atual com os dias anteriores já preenchidos.</p>
</div>""", unsafe_allow_html=True)
file_planilha = st.file_uploader("Planilha Excel", type=["xlsx"], key="planilha",
                                  label_visibility="collapsed")

# ── Passo 2: PDFs do dia ──────────────────────────────────────────────────────
st.markdown('<div class="sec">📄 Passo 2 — PDFs do dia</div>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("**TCPOS — Margem Bruta**")
    file_tcpos = st.file_uploader("PDF TCPOS", type="pdf", key="tcpos",
                                   label_visibility="collapsed")
with c2:
    st.markdown("**Opera — NA03 Trial Balance**")
    file_na03 = st.file_uploader("PDF NA03", type="pdf", key="na03",
                                  label_visibility="collapsed")
with c3:
    st.markdown("**Opera — NA02 Manager Report**")
    file_na02 = st.file_uploader("PDF NA02 *(col. V)*", type="pdf", key="na02",
                                  label_visibility="collapsed")

st.markdown('<div class="sec">⚙️ Passo 3 — Processar e baixar</div>', unsafe_allow_html=True)

# ── Processamento ─────────────────────────────────────────────────────────────
if st.button("🚀 Preencher planilha agora", use_container_width=True,
             type="primary", disabled=not (file_planilha and file_tcpos and file_na03)):

    with st.spinner("Lendo PDFs e preenchendo planilha..."):

        # Extrai dados
        tcpos = extrair_tcpos(file_tcpos)
        opera = extrair_opera_na03(file_na03)
        fb    = extrair_opera_na02(file_na02) if file_na02 else None

        # Valida
        if not tcpos:
            st.markdown('<div class="err">❌ Não foi possível ler o TCPOS. Verifique se é o PDF correto.</div>', unsafe_allow_html=True)
            st.stop()
        if not opera:
            st.markdown('<div class="err">❌ Não foi possível ler o Opera NA03. Verifique se é o PDF correto.</div>', unsafe_allow_html=True)
            st.stop()

        # Preenche planilha
        excel_bytes   = file_planilha.read()
        resultado, linha, vals = preencher_planilha(excel_bytes, tcpos, opera, fb)

    # ── Preview dos valores preenchidos ──────────────────────────────────────
    st.markdown(f'<div class="ok">✅ Planilha preenchida! Linha <strong>{linha}</strong> → dia <strong>{vals["data"]}</strong></div>', unsafe_allow_html=True)

    if not file_na02:
        st.markdown('<div class="warn">📎 NA02 não enviado — coluna V não foi preenchida. Você pode preencher manualmente.</div>', unsafe_allow_html=True)

    st.markdown('<div class="sec">📊 Valores preenchidos — confirme antes de baixar</div>', unsafe_allow_html=True)

    preview = [
        ("B", "Alimento",                vals['alimento']),
        ("C", "Café Incluso Diária",      vals['cafe_incluso']),
        ("D", "Pensão / Água Inclusa",    vals['agua_inclusa']),
        ("F", "Bebidas Não Alcoólicas",   vals['nao_alcool']),
        ("G", "Cervejas e Chopps",        vals['cervejas']),
    ]
    if vals['fb_revenue'] is not None:
        preview.append(("V", "Total Valor Opera (NA02)", vals['fb_revenue']))

    for col, campo, valor in preview:
        st.markdown(f'''
        <div class="preview-row">
            <div>
                <span class="preview-col">Col. {col} &nbsp;·&nbsp;</span>
                <span>{campo}</span>
            </div>
            <div class="preview-val">{fmt(valor)}</div>
        </div>''', unsafe_allow_html=True)

    # Estornos
    if vals['estorno_nao_alcool'] > 0 or vals['estorno_alimento'] > 0 or vals['estorno_cerveja'] > 0:
        st.markdown('<div class="sec">🟧 Estornos preenchidos na aba ESTORNO RECEITA</div>', unsafe_allow_html=True)
        if vals['estorno_alimento']   > 0:
            st.markdown(f'<div class="preview-row"><div>Col. B · Alimento (estorno)</div><div class="preview-val">{fmt(vals["estorno_alimento"])}</div></div>', unsafe_allow_html=True)
        if vals['estorno_nao_alcool'] > 0:
            st.markdown(f'<div class="preview-row"><div>Col. F · Bebidas Não Alcoólicas (estorno)</div><div class="preview-val">{fmt(vals["estorno_nao_alcool"])}</div></div>', unsafe_allow_html=True)
        if vals['estorno_cerveja']    > 0:
            st.markdown(f'<div class="preview-row"><div>Col. G · Cervejas (estorno)</div><div class="preview-val">{fmt(vals["estorno_cerveja"])}</div></div>', unsafe_allow_html=True)

    # ── Botão de download ─────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    data_nome = vals['data'].replace('/', '-')
    st.download_button(
        label="⬇️ Baixar planilha preenchida",
        data=resultado,
        file_name=f"Margem_Bruta_{data_nome}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )

else:
    # Estado: aguardando uploads
    faltam = []
    if not file_planilha: faltam.append("📋 Planilha Excel do mês")
    if not file_tcpos:    faltam.append("📄 PDF TCPOS")
    if not file_na03:     faltam.append("📄 PDF Opera NA03")

    if faltam:
        st.markdown('<div class="warn">⏳ Aguardando uploads obrigatórios:<br>' +
                    '<br>'.join(f'&nbsp;&nbsp;• {f}' for f in faltam) +
                    '</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="ok">✅ Tudo pronto! Clique no botão acima para processar.</div>',
                    unsafe_allow_html=True)

    with st.expander("ℹ️ O que este app preenche automaticamente"):
        st.markdown("""
**Aba RECEITA** — linha do dia correspondente:

| Coluna | Campo | Fonte |
|--------|-------|-------|
| B | Alimento | TCPOS |
| C | Café Incluso Diária | Opera NA03 (2042 + 2049) |
| D | Pensão / Água Inclusa | Opera NA03 (2013) |
| F | Bebidas Não Alcoólicas | TCPOS |
| G | Cervejas e Chopps | TCPOS |
| V | Total Valor Opera | Opera NA02 (Food & Beverage Revenue) |

**Aba ESTORNO RECEITA** — linha do dia correspondente:
- Detecta automaticamente ajustes negativos de bar no NA03
- Lança no campo correto (Alimento, Bebidas ou Cervejas)

**Fórmulas preservadas:** I, N, R, S, T, U, W continuam como fórmulas — o Excel recalcula automaticamente ao abrir.

**Abas manuais** (só no fechamento do mês): CONSUMO INTERNO, REFEIÇÃO DE FUNCIONÁRIO, FECHAMENTO DE ESTOQUE.
        """)

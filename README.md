# “””

EXTRATOR MARGEM BRUTA — TCPOS × OPERA (NA03 + NA02)
ibis Budget São Paulo Paraíso

# Uso: streamlit run app.py
Dependências: pip install streamlit pdfplumber pandas

“””

import re
import streamlit as st
import pdfplumber
import pandas as pd

st.set_page_config(page_title=“Margem Bruta — ibis Budget”, page_icon=“🏨”, layout=“centered”)

st.markdown(”””

<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&family=DM+Mono&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.main{background:#f5f4f0;}
.hdr{background:#1a1a2e;color:white;padding:1.5rem 2rem;border-radius:12px;margin-bottom:1.5rem;}
.hdr h1{color:white;margin:0;font-size:1.5rem;}
.hdr p{color:#aaa;margin:0.2rem 0 0 0;font-size:0.85rem;}
.card{background:white;border-radius:12px;padding:1.2rem 1.5rem;margin-bottom:1rem;border-left:4px solid #e8e8e8;}
.card-b{border-left-color:#0d6efd;}
.card-g{border-left-color:#198754;}
.card-o{border-left-color:#fd7e14;}
.card-p{border-left-color:#6f42c1;}
.lbl{font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#666;margin-bottom:2px;}
.val{font-family:'DM Mono',monospace;font-size:1.5rem;font-weight:700;color:#1a1a2e;}
.src{font-size:.72rem;color:#999;margin-top:1px;}
.totbox{background:#1a1a2e;color:white;border-radius:12px;padding:1.2rem 1.5rem;margin:1rem 0;display:flex;justify-content:space-between;align-items:center;}
.totlbl{font-size:.8rem;letter-spacing:.1em;text-transform:uppercase;color:#aaa;}
.totval{font-family:'DM Mono',monospace;font-size:2rem;font-weight:700;}
.difbox-ok{background:#1a1a2e;color:white;border-radius:12px;padding:1.2rem 1.5rem;margin:1rem 0;display:flex;justify-content:space-between;align-items:center;}
.difbox-warn{background:#7c2d12;color:white;border-radius:12px;padding:1.2rem 1.5rem;margin:1rem 0;display:flex;justify-content:space-between;align-items:center;}
.sec{font-size:.7rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase;color:#999;margin:1.5rem 0 .5rem;padding-bottom:4px;border-bottom:1px solid #eee;}
.warn{background:#fff3cd;border:1px solid #ffc107;border-radius:8px;padding:.8rem 1rem;font-size:.85rem;margin:.5rem 0;}
.ok{background:#d1e7dd;border:1px solid #198754;border-radius:8px;padding:.8rem 1rem;font-size:.85rem;margin:.5rem 0;}
.missing{background:#f8d7da;border:1px solid #dc3545;border-radius:8px;padding:.8rem 1rem;font-size:.85rem;margin:.5rem 0;}
</style>

“””, unsafe_allow_html=True)

# ── Regex validados contra PDFs reais ──────────────────────────────────────────

# TCPOS: 01/04/2026 $2,183.15 $0.00 ($141.60) $2,041.55 $1,408.01 $0.00 $0.00 $0.00 $531.54 $0.00 $0.00 $102.00

RE_TCPOS = re.compile(
r’^(\d{1,2}/\d{1,2}/\d{4})\s+’
r’$([\d,]+.\d{2})\s+$([\d,]+.\d{2})\s+($([\d,]+.\d{2}))\s+’
r’$([\d,]+.\d{2})\s+$([\d,]+.\d{2})\s+$([\d,]+.\d{2})\s+’
r’$([\d,]+.\d{2})\s+$([\d,]+.\d{2})\s+$([\d,]+.\d{2})\s+’
r’$([\d,]+.\d{2})\s+$([\d,]+.\d{2})\s+$([\d,]+.\d{2})’
)

# Opera NA03: 2042 Cafe da Manha (+) 3,420.00  /  6161 Ajuste Bar 1 Bebidas Cafe - 10.00

RE_OPERA = re.compile(
r’^\s*(\d{4})\s+(.+?)\s+(- [\d,]+.\d{2}|[\d,]+.\d{2})\s*$’
)

# Opera NA02: Food And Beverage Revenue 6,296.55 6,296.55 …  (primeiro valor = DAY)

RE_NA02_FB = re.compile(
r’Food And Beverage Revenue\s+([\d,]+.\d{2})’
)

def n(s): return float(s.replace(’ ‘,’’).replace(’,’,’’))

def fmt(v):
if v is None: return “—”
return f”R$ {v:,.2f}”.replace(”,”,“X”).replace(”.”,”,”).replace(“X”,”.”)

def br(v): return f”{v:,.2f}”.replace(”,”,“X”).replace(”.”,”,”).replace(“X”,”.”)

# ── Funções de extração ────────────────────────────────────────────────────────

def extrair_tcpos(file):
resultado, debug = {}, []
with pdfplumber.open(file) as pdf:
for p in pdf.pages:
txt = p.extract_text()
if not txt: continue
for linha in txt.splitlines():
debug.append(linha)
m = RE_TCPOS.match(linha.strip())
if m:
resultado = {
‘data’:        m.group(1),
‘ttl_bruto’:   n(m.group(2)),
‘servico’:     n(m.group(3)),
‘desconto’:   -n(m.group(4)),
‘ttl_liquido’: n(m.group(5)),
‘alimento’:    n(m.group(6)),
‘cafe_manha’:  n(m.group(7)),
‘pensao’:      n(m.group(8)),
‘vinhos’:      n(m.group(9)),
‘nao_alcool’:  n(m.group(10)),
‘alcool’:      n(m.group(11)),
‘diversos’:    n(m.group(12)),
‘cervejas’:    n(m.group(13)),
}
break
if resultado: break
return resultado, debug

def extrair_opera_na03(file):
campos, debug = {}, []
with pdfplumber.open(file) as pdf:
for p in pdf.pages:
txt = p.extract_text()
if not txt: continue
for linha in txt.splitlines():
debug.append(linha)
m = RE_OPERA.match(linha)
if m:
campos[m.group(1)] = {‘nome’: m.group(2).strip(), ‘valor’: n(m.group(3))}
return campos, debug

def extrair_opera_na02(file):
“””
Extrai ‘Food And Beverage Revenue’ do NA02 — coluna DAY (primeiro valor da linha).
Retorna float ou None se não encontrado.
“””
debug = []
with pdfplumber.open(file) as pdf:
for p in pdf.pages:
txt = p.extract_text()
if not txt: continue
for linha in txt.splitlines():
debug.append(linha)
m = RE_NA02_FB.search(linha)
if m:
return n(m.group(1)), debug
return None, debug

# ── UI ─────────────────────────────────────────────────────────────────────────

st.markdown(’’’

<div class="hdr">
    <h1>🏨 Margem Bruta — ibis Budget Paraíso</h1>
    <p>Extrator automático · TCPOS × Opera NA03 × Opera NA02</p>
</div>
''', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1:
st.markdown(”**📄 TCPOS — Margem Bruta**”)
file_tcpos = st.file_uploader(“PDF TCPOS”, type=“pdf”, key=“tcpos”, label_visibility=“collapsed”)
with c2:
st.markdown(”**📄 Opera — NA03 Trial Balance**”)
file_na03 = st.file_uploader(“PDF NA03”, type=“pdf”, key=“na03”, label_visibility=“collapsed”)
with c3:
st.markdown(”**📄 Opera — NA02 Manager Report**”)
file_na02 = st.file_uploader(“PDF NA02 *(opcional)*”, type=“pdf”, key=“na02”, label_visibility=“collapsed”)

debug = st.checkbox(“🔍 Modo debug”)

# ── Processamento ──────────────────────────────────────────────────────────────

if file_tcpos and file_na03:
st.markdown(”—”)

```
tcpos, td  = extrair_tcpos(file_tcpos)
opera, od  = extrair_opera_na03(file_na03)

# NA02 é opcional
fb_revenue, n2d = (None, [])
if file_na02:
    fb_revenue, n2d = extrair_opera_na02(file_na02)

if not tcpos:
    st.error("❌ Não foi possível ler o TCPOS. Verifique se é o PDF correto.")
    if debug: st.write(td[:20])
    st.stop()
if not opera:
    st.error("❌ Não foi possível ler o Opera NA03. Verifique se é o PDF correto.")
    if debug: st.write(od[:20])
    st.stop()

def get(cod): return opera.get(cod, {}).get('valor', 0.0)

# ── Cálculos ──────────────────────────────────────────────────────────────
alimento   = tcpos.get('alimento',   0.0)
nao_alcool = tcpos.get('nao_alcool', 0.0)
cervejas   = tcpos.get('cervejas',   0.0)

# C = Café da Manhã (+) 2042 + MBUFFF 2049
# Nota: Breakfast (2040) NÃO entra aqui — é uma conta separada do Opera
cafe_incluso = get('2042') + get('2049')

# D = Água Inclusa 2013
agua_inclusa = get('2013')

# H = B + C + D + F + G
total_pdv = alimento + cafe_incluso + agua_inclusa + nao_alcool + cervejas

# Estornos de bar (contas com "ajuste" + "bar" e valor negativo)
estornos_bar = {
    cod: info for cod, info in opera.items()
    if 'ajuste' in info['nome'].lower()
    and 'bar'   in info['nome'].lower()
    and info['valor'] < 0
}
total_estornos = sum(abs(v['valor']) for v in estornos_bar.values())

# U = H - T
total_ab = total_pdv - total_estornos

# V = Food And Beverage Revenue do NA02 (coluna DAY)
total_opera = fb_revenue  # None se NA02 não foi enviado

# Diferença (col. W) = U - V
diferenca = (total_ab - total_opera) if total_opera is not None else None

# ── Data ──────────────────────────────────────────────────────────────────
st.markdown(f"<div class='sec'>📅 Data do relatório: {tcpos.get('data','—')}</div>",
            unsafe_allow_html=True)

# ── TCPOS ─────────────────────────────────────────────────────────────────
st.markdown("<div class='sec'>🟦 Valores do TCPOS — copiar para planilha</div>",
            unsafe_allow_html=True)
ca, cb, cc = st.columns(3)
with ca:
    st.markdown(f'<div class="card card-b"><div class="lbl">Col. B · Alimento</div><div class="val">{fmt(alimento)}</div><div class="src">TCPOS → ALIMENTO</div></div>', unsafe_allow_html=True)
with cb:
    st.markdown(f'<div class="card card-b"><div class="lbl">Col. F · Bebidas Não Alcoólicas</div><div class="val">{fmt(nao_alcool)}</div><div class="src">TCPOS → NAO ALCOOL</div></div>', unsafe_allow_html=True)
with cc:
    st.markdown(f'<div class="card card-b"><div class="lbl">Col. G · Cervejas e Chopps</div><div class="val">{fmt(cervejas)}</div><div class="src">TCPOS → CERVEJAS</div></div>', unsafe_allow_html=True)

# ── Opera NA03 ────────────────────────────────────────────────────────────
st.markdown("<div class='sec'>🟩 Valores do Opera NA03 — copiar para planilha</div>",
            unsafe_allow_html=True)
partes = []
if get('2042'): partes.append(f"Café da Manhã (+) {fmt(get('2042'))}")
if get('2049'): partes.append(f"MBUFFF {fmt(get('2049'))}")
det = " + ".join(partes) or "Nenhum valor"

cd, ce = st.columns(2)
with cd:
    st.markdown(f'<div class="card card-g"><div class="lbl">Col. C · Café Incluso Diária</div><div class="val">{fmt(cafe_incluso)}</div><div class="src">Opera NA03 → {det}</div></div>', unsafe_allow_html=True)
with ce:
    st.markdown(f'<div class="card card-g"><div class="lbl">Col. D · Pensão / Água Inclusa</div><div class="val">{fmt(agua_inclusa)}</div><div class="src">Opera NA03 → Agua Inclusa (2013)</div></div>', unsafe_allow_html=True)

# ── Total H ───────────────────────────────────────────────────────────────
st.markdown(f'''
<div class="totbox">
    <div>
        <div class="totlbl">Col. H · Total PDV Micros (A)</div>
        <div style="color:#aaa;font-size:.75rem;margin-top:4px;">B + C + D + F + G</div>
    </div>
    <div class="totval">{fmt(total_pdv)}</div>
</div>''', unsafe_allow_html=True)

# ── Estornos ──────────────────────────────────────────────────────────────
st.markdown("<div class='sec'>🟧 Estornos do Opera — lançar na aba ESTORNO RECEITA</div>",
            unsafe_allow_html=True)
if estornos_bar:
    for cod, info in estornos_bar.items():
        st.markdown(f'<div class="card card-o"><div class="lbl">Conta {cod} · {info["nome"]}</div><div class="val">{fmt(abs(info["valor"]))}</div><div class="src">Lançar na aba ESTORNO RECEITA da planilha</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="warn">⚠️ <strong>Total estornos de bar: {fmt(total_estornos)}</strong> — preencher coluna T da planilha.</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="ok">✅ Nenhum estorno de bar hoje. Coluna T = R$ 0,00</div>', unsafe_allow_html=True)

# ── Opera NA02 — coluna V ─────────────────────────────────────────────────
st.markdown("<div class='sec'>🟣 Valor do Opera NA02 — coluna V (Total Valor Opera)</div>",
            unsafe_allow_html=True)
if total_opera is not None:
    st.markdown(f'<div class="card card-p"><div class="lbl">Col. V · Total Valor Opera</div><div class="val">{fmt(total_opera)}</div><div class="src">Opera NA02 → Food And Beverage Revenue (coluna DAY)</div></div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="missing">📎 NA02 não enviado — faça o upload para preencher a coluna V automaticamente.</div>', unsafe_allow_html=True)

# ── Diferença W = U - V ───────────────────────────────────────────────────
st.markdown("<div class='sec'>📊 Diferença (col. W) = Col. U − Col. V</div>",
            unsafe_allow_html=True)

if diferenca is not None:
    sinal = "+" if diferenca > 0 else ""
    cor   = "#198754" if abs(diferenca) < 0.02 else ("#fd7e14" if abs(diferenca) < 50 else "#dc3545")
    icone = "✅" if abs(diferenca) < 0.02 else "⚠️"
    msg   = "Em equilíbrio" if abs(diferenca) < 0.02 else (
            "Pequena diferença — verifique virada de dia" if abs(diferenca) < 50
            else "Diferença relevante — use o sistema de conciliação de cupons")
    st.markdown(f'''
    <div style="background:white;border-radius:12px;padding:1.2rem 1.5rem;
                border-left:4px solid {cor};margin-bottom:1rem;">
        <div class="lbl">Col. W · Diferença (TCPOS × Opera)</div>
        <div class="val" style="color:{cor};">{icone} {sinal}{fmt(diferenca, "")}</div>
        <div class="src">{msg}</div>
    </div>''', unsafe_allow_html=True)
else:
    st.markdown('<div class="warn">📎 Envie o NA02 para calcular a diferença automaticamente.</div>', unsafe_allow_html=True)

# ── Tabela completa ───────────────────────────────────────────────────────
st.markdown("<div class='sec'>📋 Tabela completa — copiar para a planilha</div>",
            unsafe_allow_html=True)

colunas  = ["B","C","D","F","G","H","T","U","V","W"]
campos_t = [
    "Alimento",
    "Café Incluso Diária",
    "Pensão / Água Inclusa",
    "Bebidas Não Alcoólicas",
    "Cervejas e Chopps",
    "Total PDV Micros",
    "Total Estornos Opera",
    "Total A-B",
    "Total Valor Opera (NA02)",
    "Diferença (TCPOS × Opera)",
]
valores_t = [
    br(alimento), br(cafe_incluso), br(agua_inclusa),
    br(nao_alcool), br(cervejas), br(total_pdv),
    br(total_estornos), br(total_ab),
    br(total_opera) if total_opera is not None else "— (NA02 não enviado)",
    (("+" if diferenca > 0 else "") + br(diferenca)) if diferenca is not None else "— (NA02 não enviado)",
]
fontes_t = [
    "TCPOS", "Opera NA03 (2042+2049)", "Opera NA03 (2013)",
    "TCPOS", "TCPOS", "Calculado (B+C+D+F+G)",
    "Opera NA03 (Ajustes Bar)", "Calculado (H−T)",
    "Opera NA02 (Food & Beverage Revenue)", "Calculado (U−V)",
]

df = pd.DataFrame({"Col.": colunas, "Campo": campos_t, "Valor (R$)": valores_t, "Fonte": fontes_t})
st.dataframe(df, use_container_width=True, hide_index=True)

# ── Debug ─────────────────────────────────────────────────────────────────
if debug:
    st.markdown("---")
    with st.expander("🔍 Debug TCPOS"):
        st.json(tcpos)
        for i,l in enumerate(td[:15]): st.code(f"{i:02d}: {l}")
    with st.expander("🔍 Debug Opera NA03"):
        st.json(opera)
        for i,l in enumerate(od[:40]): st.code(f"{i:02d}: {l}")
    if file_na02:
        with st.expander("🔍 Debug Opera NA02"):
            st.write(f"Food And Beverage Revenue (DAY): {fb_revenue}")
            for i,l in enumerate(n2d[:60]): st.code(f"{i:02d}: {l}")
```

# ── Estado inicial ─────────────────────────────────────────────────────────────

else:
st.markdown(”””
<div style="background:white;border-radius:12px;padding:2.5rem;
text-align:center;color:#999;margin-top:1rem;">
<div style="font-size:3rem;">📂</div>
<div style="font-size:1rem;margin-top:.5rem;color:#555;">
Faça o upload dos PDFs para extrair os valores automaticamente.
</div>
<div style="font-size:.8rem;margin-top:.4rem;">
TCPOS + NA03 são obrigatórios  ·  NA02 é opcional (col. V e W)
</div>
</div>”””, unsafe_allow_html=True)

```
with st.expander("ℹ️ Como usar · Mapeamento de colunas"):
    st.markdown("""
```

**Passo a passo diário:**

1. Exporte o **Relatório Margem Bruta** do TCPOS em PDF
1. Exporte o **NA03 - Trial Balance Net** do Opera em PDF
1. Exporte o **NA02 - Manager Report Gross** do Opera em PDF
1. Faça upload dos três arquivos acima
1. Copie cada valor para a planilha Margem Bruta

|Coluna|Campo                 |Fonte                                      |
|------|----------------------|-------------------------------------------|
|B     |Alimento              |TCPOS                                      |
|C     |Café Incluso Diária   |Opera NA03: 2042 + 2049                    |
|D     |Pensão / Água Inclusa |Opera NA03: 2013                           |
|F     |Bebidas Não Alcoólicas|TCPOS                                      |
|G     |Cervejas e Chopps     |TCPOS                                      |
|H     |Total PDV Micros      |B + C + D + F + G                          |
|T     |Total Estornos        |Opera NA03: Ajustes Bar (negativos)        |
|U     |Total A-B             |H − T                                      |
|V     |Total Valor Opera     |Opera NA02: Food And Beverage Revenue (DAY)|
|W     |Diferença             |U − V                                      |

**Estornos:** Detectados automaticamente → lançar na aba **ESTORNO RECEITA**.

**Diferenças:** Se aparecer alerta na coluna W, use o sistema de conciliação de cupons para rastrear a virada de dia.
“””)

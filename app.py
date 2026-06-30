import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import json
from fpdf import FPDF

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Business Performance Dashboard",
    page_icon="📊",
    layout="wide",
)

# ─── Design System ────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stAppViewContainer"] { background: #0a0a0a; color: #ffffff; }
  [data-testid="stSidebar"] { background: #16213e; }
  [data-testid="stSidebar"] * { color: #ffffff !important; }
  h1 { color: #ffffff; font-size: 2rem; font-weight: bold; }
  h2 { color: #00ff88; font-size: 1.4rem; }
  h3 { color: #ffffff; font-size: 1.1rem; }
  .stTabs [data-baseweb="tab"] { color: #888888; }
  .stTabs [aria-selected="true"] { color: #00ff88 !important; border-bottom: 2px solid #00ff88; }
  div[data-testid="metric-container"] {
    background: #1a1a2e; border-radius: 8px; padding: 16px;
    border-left: 3px solid #00ff88;
  }
  .alert-ok { background:#003d1a; border-left:4px solid #00ff88; border-radius:4px; padding:10px 16px; margin:6px 0; color:#fff; }
  .alert-warning { background:#3d2f00; border-left:4px solid #ffd700; border-radius:4px; padding:10px 16px; margin:6px 0; color:#fff; }
  .alert-danger { background:#3d0000; border-left:4px solid #ff4444; border-radius:4px; padding:10px 16px; margin:6px 0; color:#fff; }
  .anomaly-tag { display:inline-block; background:#3d0000; color:#ff8888; border:1px solid #ff4444; border-radius:4px; padding:2px 8px; margin:2px; font-size:0.8rem; }
  .health-box { background:#1a1a2e; border:1px solid rgba(0,255,136,0.3); border-radius:12px; padding:20px; text-align:center; margin:8px 0; }
  .whatif-box { background:#1a1a2e; border:1px solid rgba(0,255,136,0.3); border-radius:8px; padding:16px; margin:8px 0; }
  .narrative-box { background:#1a1a2e; border:1px solid #ffd700; border-radius:8px; padding:20px; margin:12px 0; font-size:0.95rem; line-height:1.7; color:#ffffff; }
  .footer-caption { color:#888888; font-size:0.8rem; text-align:center; margin-top:32px; }
  .n1-badge { display:inline-block; background:#1a1a2e; border:1px solid #4ecdc4; border-radius:4px; padding:2px 8px; font-size:0.75rem; color:#4ecdc4; margin-left:6px; }
</style>
""", unsafe_allow_html=True)

CHART_DEFAULTS = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#1a1a2e",
    font_color="#ffffff", font_family="sans-serif",
    title_font_color="#00ff88", title_font_size=16,
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="white")),
    margin=dict(l=20, r=20, t=40, b=20),
)
PALETTE = ["#00ff88", "#ffd700", "#4ecdc4", "#ff4444", "#a855f7", "#f97316"]

# ─── Chargement données ───────────────────────────────────────────────────────
@st.cache_data
def load_controlling():
    return pd.read_csv("data/controlling.csv")

@st.cache_data
def load_supply():
    return pd.read_csv("data/supply_chain.csv")

def detect_file_type(df):
    cols = [c.lower() for c in df.columns]
    if any(k in cols for k in ["budget", "realise", "departement"]):
        return "controlling"
    if any(k in cols for k in ["taux_service", "commandes_total", "livraisons"]):
        return "supply_chain"
    return "unknown"

def load_uploaded(file):
    try:
        content = file.read()
        df = pd.read_csv(io.BytesIO(content), sep=None, engine="python", encoding="utf-8-sig") \
            if file.name.lower().endswith(".csv") \
            else pd.read_excel(io.BytesIO(content))
        return df, detect_file_type(df)
    except Exception as e:
        st.error(f"Erreur lecture : {e}")
        return None, "unknown"

# ─── Health Score ─────────────────────────────────────────────────────────────
def compute_health_ctrl(df, seuil):
    ecart_pct = (df["realise"].sum() - df["budget"].sum()) / df["budget"].sum() * 100
    agg = df.groupby("departement")[["budget", "realise"]].sum()
    agg["ep"] = (agg["realise"] - agg["budget"]) / agg["budget"] * 100
    nb_alertes = (agg["ep"] > seuil).sum()
    score = max(0, 100 - abs(ecart_pct) * 3 - nb_alertes * 10)
    return round(score)

def compute_health_sc(df, seuil_service):
    ts = df["livraisons_a_temps"].sum() / df["commandes_total"].sum() * 100
    tr = df["retours"].sum() / df["commandes_total"].sum() * 100
    delai = df["delai_moyen_jours"].mean()
    score = max(0, (ts - 85) / 15 * 60 + max(0, 10 - tr * 3) + max(0, 30 - delai * 3))
    return round(min(score, 100))

def health_gauge(score, label):
    color = "#00ff88" if score >= 70 else "#ffd700" if score >= 45 else "#ff4444"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": label, "font": {"color": "#ffffff", "size": 14}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#888"},
            "bar": {"color": color},
            "bgcolor": "#1a1a2e",
            "steps": [
                {"range": [0, 45], "color": "#3d0000"},
                {"range": [45, 70], "color": "#3d2f00"},
                {"range": [70, 100], "color": "#003d1a"},
            ],
            "threshold": {"line": {"color": color, "width": 4}, "value": score},
        },
        number={"font": {"color": color, "size": 36}, "suffix": "/100"},
    ))
    fig.update_layout(**CHART_DEFAULTS, height=220)
    return fig

# ─── Anomalies Z-score ────────────────────────────────────────────────────────
def detect_anomalies_ctrl(df):
    agg = df.groupby(["mois", "departement"])["ecart_pct"].mean().reset_index()
    mean = agg["ecart_pct"].mean()
    std = agg["ecart_pct"].std()
    if std == 0:
        return []
    agg["zscore"] = (agg["ecart_pct"] - mean) / std
    anomalies = agg[agg["zscore"].abs() > 2]
    return [
        f"{'⬆️' if row['ecart_pct'] > 0 else '⬇️'} {row['departement']} ({row['mois'][:7]}) "
        f"— écart {row['ecart_pct']:+.1f}% (Z={row['zscore']:.1f}σ)"
        for _, row in anomalies.iterrows()
    ]

def detect_anomalies_sc(df):
    agg = df.groupby(["mois", "region"])["taux_service"].mean().reset_index()
    mean = agg["taux_service"].mean()
    std = agg["taux_service"].std()
    if std == 0:
        return []
    agg["zscore"] = (agg["taux_service"] - mean) / std
    anomalies = agg[agg["zscore"].abs() > 2]
    return [
        f"{'⬇️' if row['taux_service'] < mean else '⬆️'} {row['region']} ({row['mois'][:7]}) "
        f"— taux service {row['taux_service']:.1f}% (Z={row['zscore']:.1f}σ)"
        for _, row in anomalies.iterrows()
    ]

# ─── Alertes ─────────────────────────────────────────────────────────────────
def check_controlling_alerts(df, seuil):
    alerts = []
    agg = df.groupby("departement")[["budget", "realise"]].sum()
    agg["ep"] = (agg["realise"] - agg["budget"]) / agg["budget"] * 100
    for dept, row in agg.iterrows():
        if row["ep"] > seuil:
            alerts.append(("danger", f"⚠️ {dept} — dépassement +{row['ep']:.1f}% ({row['realise']-row['budget']:+,.0f} €)"))
        elif row["ep"] > seuil / 2:
            alerts.append(("warning", f"🟡 {dept} — écart modéré +{row['ep']:.1f}%"))
        elif row["ep"] < -seuil:
            alerts.append(("ok", f"✅ {dept} — sous-consommation {row['ep']:.1f}%"))
    return alerts

def check_supply_alerts(df, seuil_service, seuil_delai):
    alerts = []
    agg = df.groupby("region").agg(
        taux_service=("taux_service", "mean"),
        delai_moyen=("delai_moyen_jours", "mean"),
        retours=("retours", "sum"),
        commandes=("commandes_total", "sum"),
    )
    for region, row in agg.iterrows():
        if row["taux_service"] < seuil_service:
            alerts.append(("danger", f"⚠️ {region} — taux service {row['taux_service']:.1f}% < {seuil_service}%"))
        if row["delai_moyen"] > seuil_delai:
            alerts.append(("warning", f"🟡 {region} — délai {row['delai_moyen']:.1f}j > {seuil_delai}j"))
        if row["retours"] / row["commandes"] * 100 > 3.5:
            alerts.append(("warning", f"🟡 {region} — taux retour {row['retours']/row['commandes']*100:.1f}%"))
    return alerts

# ─── Narratif IA ─────────────────────────────────────────────────────────────
def generate_narrative(mode, kpis, api_key):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        if mode == "controlling":
            prompt = f"""Tu es contrôleur de gestion senior. Rédige un commentaire de gestion concis (3-4 phrases)
pour un comité de direction, basé sur ces indicateurs :
{json.dumps(kpis, ensure_ascii=False, indent=2)}
Règles : français professionnel, mentionne écarts significatifs, termine par une recommandation concrète, style comex factuel."""
        else:
            prompt = f"""Tu es responsable Supply Chain senior. Rédige un commentaire opérationnel concis (3-4 phrases)
pour un comité de pilotage, basé sur ces indicateurs :
{json.dumps(kpis, ensure_ascii=False, indent=2)}
Règles : français professionnel, zones de risque et tendances positives, action prioritaire en conclusion, style rapport opérationnel."""
        response = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Erreur API : {e}"

# ─── Export PDF ───────────────────────────────────────────────────────────────
def generate_pdf(title, kpis_lines, alerts, narrative=""):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(0, 200, 100)
    pdf.cell(0, 12, title, ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Rapport généré automatiquement — Business Performance Dashboard", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(0, 200, 100)
    pdf.cell(0, 8, "Indicateurs clés", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(255, 255, 255)
    pdf.set_fill_color(26, 26, 46)
    for line in kpis_lines:
        pdf.set_text_color(200, 200, 200)
        pdf.cell(0, 7, line, ln=True, fill=True)
    pdf.ln(4)

    if alerts:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(255, 200, 0)
        pdf.cell(0, 8, "Alertes actives", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for _, msg in alerts:
            pdf.set_text_color(200, 200, 200)
            pdf.multi_cell(0, 6, msg)
        pdf.ln(4)

    if narrative:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(0, 200, 100)
        pdf.cell(0, 8, "Commentaire de gestion (IA)", ln=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(200, 200, 200)
        pdf.multi_cell(0, 7, narrative)
        pdf.ln(4)

    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, "Construit avec l'IA — Gisele Metouck — metouck.gisele@gmail.com", ln=True)
    return bytes(pdf.output())

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 📊 Business Performance")
    st.divider()

    mode = st.radio("Module actif",
                    ["💰 Controlling & Variance", "🚚 Supply Chain KPIs"], index=0)
    st.divider()

    st.markdown("### 📁 Données actuelles (N)")
    uploaded = st.file_uploader("CSV / Excel", type=["csv", "xlsx"], key="up_n")
    if uploaded:
        df_up, detected = load_uploaded(uploaded)
        if df_up is not None and detected != "unknown":
            st.session_state["uploaded_data"] = df_up
            st.session_state["uploaded_mode"] = detected
            st.success(f"✅ Détecté : **{detected}**")

    st.markdown("### 📁 Données N-1 (comparaison)")
    uploaded_n1 = st.file_uploader("CSV / Excel N-1", type=["csv", "xlsx"], key="up_n1")
    if uploaded_n1:
        df_n1, _ = load_uploaded(uploaded_n1)
        if df_n1 is not None:
            st.session_state["n1_data"] = df_n1
            st.success("✅ N-1 chargé")

    st.divider()
    st.markdown("### 🔔 Seuils d'alerte")
    if "Controlling" in mode:
        seuil_ecart = st.slider("Dépassement budgétaire (%)", 5, 30, 10)
        st.session_state["seuil_ecart"] = seuil_ecart
    else:
        seuil_service = st.slider("Taux de service min (%)", 85, 99, 93)
        seuil_delai = st.slider("Délai max (jours)", 3, 10, 5)
        st.session_state["seuil_service"] = seuil_service
        st.session_state["seuil_delai"] = seuil_delai

    st.divider()
    st.markdown("### 🤖 Commentaire IA")
    api_key = st.text_input("Clé API Anthropic", type="password", placeholder="sk-ant-...")
    st.caption("~0.01€ · Clé non stockée")
    st.divider()
    st.caption("🔗 [GitHub](https://github.com/Kingdmfncr) · Gisèle Metouck")

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("# 📊 Business Performance Dashboard")
st.markdown("**Écarts budgétaires · KPIs Supply Chain · N vs N-1 · Anomalies · What-if · Rapport PDF**")
st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# MODULE CONTROLLING
# ══════════════════════════════════════════════════════════════════════════════
if "Controlling" in mode:
    use_up = "uploaded_data" in st.session_state and st.session_state.get("uploaded_mode") == "controlling"
    df = st.session_state["uploaded_data"] if use_up else load_controlling()
    df_n1 = st.session_state.get("n1_data")
    has_n1 = df_n1 is not None

    df["mois"] = pd.to_datetime(df["mois"])
    df["ecart"] = df["realise"] - df["budget"]
    df["ecart_pct"] = (df["ecart"] / df["budget"] * 100).round(2)

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        depts = st.multiselect("Départements", sorted(df["departement"].unique()),
                               default=list(df["departement"].unique()))
    with col_f2:
        cats = st.multiselect("Catégories", sorted(df["categorie"].unique()),
                              default=list(df["categorie"].unique()))

    df_f = df[df["departement"].isin(depts) & df["categorie"].isin(cats)]
    if df_f.empty:
        st.markdown('<div class="alert-warning">⚠️ Aucune donnée pour cette sélection.</div>', unsafe_allow_html=True)
        st.stop()

    seuil = st.session_state.get("seuil_ecart", 10)
    budget_total = df_f["budget"].sum()
    realise_total = df_f["realise"].sum()
    ecart_total = realise_total - budget_total
    ecart_pct_total = ecart_total / budget_total * 100
    health = compute_health_ctrl(df_f, seuil)
    anomalies = detect_anomalies_ctrl(df_f)
    alerts = check_controlling_alerts(df_f, seuil)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Vue globale", "📈 Analyse détaillée",
        "🔍 Anomalies & N-1", "🎛️ Simulation what-if", "📄 Rapport & IA"
    ])

    # ── TAB 1 ──
    with tab1:
        st.markdown("## Vue globale — Contrôle budgétaire")

        col_g, col_k = st.columns([1, 3])
        with col_g:
            st.plotly_chart(health_gauge(health, "Score de santé"), use_container_width=True, key="gauge_ctrl")
        with col_k:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Budget total", f"{budget_total:,.0f} €")
            c2.metric("Réalisé total", f"{realise_total:,.0f} €")
            c3.metric("Écart total", f"{ecart_total:+,.0f} €",
                      delta=f"{ecart_pct_total:+.1f}%", delta_color="inverse")
            c4.metric("Alertes actives", len([a for a in alerts if a[0] == "danger"]))

        if alerts:
            st.divider()
            for level, msg in alerts:
                st.markdown(f'<div class="alert-{level}">{msg}</div>', unsafe_allow_html=True)

        st.divider()
        agg_dept = df_f.groupby("departement")[["budget", "realise"]].sum().reset_index()
        fig_dept = go.Figure()
        fig_dept.add_trace(go.Bar(x=agg_dept["departement"], y=agg_dept["budget"],
                                  name="Budget", marker_color="#4ecdc4"))
        fig_dept.add_trace(go.Bar(x=agg_dept["departement"], y=agg_dept["realise"],
                                  name="Réalisé", marker_color="#00ff88"))
        fig_dept.update_layout(**CHART_DEFAULTS, title="Budget vs Réalisé par département", barmode="group")
        st.plotly_chart(fig_dept, use_container_width=True, key="ctrl_dept")

        agg_mois = df_f.groupby("mois")[["budget", "realise"]].sum().reset_index()
        agg_mois["ecart_pct"] = (agg_mois["realise"] - agg_mois["budget"]) / agg_mois["budget"] * 100
        fig_trend = px.line(agg_mois, x="mois", y="ecart_pct",
                            title="Évolution de l'écart budgétaire (%)",
                            markers=True, color_discrete_sequence=["#ffd700"])
        fig_trend.add_hline(y=0, line_dash="dot", line_color="#888888")
        fig_trend.add_hline(y=seuil, line_dash="dash", line_color="#ff4444",
                            annotation_text=f"Seuil {seuil}%")
        fig_trend.update_layout(**CHART_DEFAULTS)
        st.plotly_chart(fig_trend, use_container_width=True, key="ctrl_trend")

    # ── TAB 2 ──
    with tab2:
        st.markdown("## Analyse détaillée — Matrice des écarts")
        col1, col2 = st.columns(2)
        with col1:
            agg_cat = df_f.groupby("categorie")[["budget", "realise"]].sum().reset_index()
            agg_cat["ecart"] = agg_cat["realise"] - agg_cat["budget"]
            agg_cat = agg_cat.sort_values("ecart", ascending=False)
            fig_wf = go.Figure(go.Waterfall(
                x=agg_cat["categorie"], y=agg_cat["ecart"],
                measure=["relative"] * len(agg_cat),
                connector={"line": {"color": "#888888"}},
                increasing={"marker": {"color": "#ff4444"}},
                decreasing={"marker": {"color": "#00ff88"}},
                text=[f"{v:+,.0f} €" for v in agg_cat["ecart"]],
                textposition="outside",
            ))
            fig_wf.update_layout(**CHART_DEFAULTS, title="Décomposition des écarts par catégorie")
            st.plotly_chart(fig_wf, use_container_width=True, key="ctrl_waterfall")
        with col2:
            pivot = df_f.pivot_table(values="ecart_pct", index="departement",
                                     columns="categorie", aggfunc="mean").round(1)
            fig_heat = px.imshow(pivot,
                                 color_continuous_scale=["#00ff88", "#ffd700", "#ff4444"],
                                 title="Heatmap écarts (%) — Département × Catégorie",
                                 text_auto=True)
            fig_heat.update_layout(**CHART_DEFAULTS)
            st.plotly_chart(fig_heat, use_container_width=True, key="ctrl_heat")

        st.divider()
        df_disp = df_f.copy()
        df_disp["mois"] = df_disp["mois"].dt.strftime("%Y-%m")
        df_disp["budget"] = df_disp["budget"].map("{:,.0f} €".format)
        df_disp["realise"] = df_disp["realise"].map("{:,.0f} €".format)
        df_disp["ecart"] = df_disp["ecart"].map("{:+,.0f} €".format)
        df_disp["ecart_pct"] = df_disp["ecart_pct"].map("{:+.1f}%".format)
        st.dataframe(df_disp[["mois", "departement", "categorie", "budget", "realise", "ecart", "ecart_pct"]],
                     use_container_width=True, hide_index=True)
        csv = df_f.to_csv(index=False, sep=";", encoding="utf-8-sig")
        st.download_button("⬇️ Exporter CSV", data=csv,
                           file_name="controlling_export.csv", mime="text/csv")

    # ── TAB 3 — Anomalies & N-1 ──
    with tab3:
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("## 🔍 Anomalies statistiques (Z-score > 2σ)")
            st.caption("Détection automatique des écarts statistiquement anormaux")
            if anomalies:
                for a in anomalies:
                    st.markdown(f'<span class="anomaly-tag">⚡ {a}</span>', unsafe_allow_html=True)
                st.markdown('<div class="alert-danger" style="margin-top:8px">⚠️ Ces points sortent de la distribution normale — investigation recommandée</div>',
                            unsafe_allow_html=True)
            else:
                st.markdown('<div class="alert-ok">✅ Aucune anomalie statistique détectée sur la période</div>',
                            unsafe_allow_html=True)

            # Graphique Z-scores
            agg_z = df_f.groupby(["mois", "departement"])["ecart_pct"].mean().reset_index()
            mean_z = agg_z["ecart_pct"].mean()
            std_z = agg_z["ecart_pct"].std() or 1
            agg_z["zscore"] = (agg_z["ecart_pct"] - mean_z) / std_z
            agg_z["mois_str"] = agg_z["mois"].astype(str).str[:7]
            fig_z = px.scatter(agg_z, x="mois_str", y="zscore",
                               color="departement", size=agg_z["zscore"].abs() + 0.5,
                               color_discrete_sequence=PALETTE,
                               title="Distribution Z-scores par département")
            fig_z.add_hline(y=2, line_dash="dash", line_color="#ff4444", annotation_text="+2σ")
            fig_z.add_hline(y=-2, line_dash="dash", line_color="#ff4444", annotation_text="-2σ")
            fig_z.update_layout(**CHART_DEFAULTS)
            st.plotly_chart(fig_z, use_container_width=True, key="ctrl_zscore")

        with col_b:
            st.markdown("## 📅 Comparaison N vs N-1")
            if not has_n1:
                st.markdown('<div class="alert-warning">💡 Chargez un fichier N-1 dans la sidebar pour activer la comparaison</div>',
                            unsafe_allow_html=True)
            else:
                df_n1_f = df_n1.copy()
                df_n1_f["mois"] = pd.to_datetime(df_n1_f["mois"])
                df_n1_f["ecart"] = df_n1_f["realise"] - df_n1_f["budget"]

                # KPIs comparés
                b_n = df_f["budget"].sum()
                r_n = df_f["realise"].sum()
                r_n1 = df_n1_f["realise"].sum() if "realise" in df_n1_f.columns else 0
                ep_n = (r_n - b_n) / b_n * 100
                ep_n1 = (r_n1 - df_n1_f["budget"].sum()) / df_n1_f["budget"].sum() * 100 \
                    if "budget" in df_n1_f.columns else 0

                c1, c2 = st.columns(2)
                c1.metric("Réalisé N", f"{r_n:,.0f} €", delta=f"{r_n - r_n1:+,.0f} € vs N-1",
                          delta_color="inverse")
                c2.metric("Écart budg. N", f"{ep_n:+.1f}%",
                          delta=f"{ep_n - ep_n1:+.1f}pts vs N-1",
                          delta_color="inverse")

                # Graphique comparaison par département
                agg_n = df_f.groupby("departement")["realise"].sum().reset_index(name="N")
                if "departement" in df_n1_f.columns:
                    agg_n1 = df_n1_f.groupby("departement")["realise"].sum().reset_index(name="N-1")
                    comp = agg_n.merge(agg_n1, on="departement", how="left").fillna(0)
                    comp["delta"] = comp["N"] - comp["N-1"]
                    fig_n1 = go.Figure()
                    fig_n1.add_trace(go.Bar(x=comp["departement"], y=comp["N-1"],
                                           name="N-1", marker_color="#4ecdc4", opacity=0.7))
                    fig_n1.add_trace(go.Bar(x=comp["departement"], y=comp["N"],
                                           name="N (actuel)", marker_color="#00ff88"))
                    fig_n1.update_layout(**CHART_DEFAULTS, title="Réalisé N vs N-1 par département",
                                        barmode="group")
                    st.plotly_chart(fig_n1, use_container_width=True, key="ctrl_n1")

    # ── TAB 4 ──
    with tab4:
        st.markdown("## 🎛️ Simulation what-if")
        st.markdown('<div class="whatif-box">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            delta_sal = st.slider("Variation masse salariale (%)", -15, 20, 0)
            delta_log = st.slider("Variation frais logistiques (%)", -20, 30, 0)
        with col2:
            delta_mkt = st.slider("Variation budget marketing (%)", -30, 30, 0)
            delta_hon = st.slider("Variation honoraires (%)", -20, 50, 0)
        st.markdown('</div>', unsafe_allow_html=True)

        df_sim = df_f.copy()
        df_sim.loc[df_sim["categorie"] == "Masse salariale", "realise"] *= (1 + delta_sal / 100)
        df_sim.loc[df_sim["categorie"] == "Logistique", "realise"] *= (1 + delta_log / 100)
        df_sim.loc[df_sim["categorie"] == "Marketing", "realise"] *= (1 + delta_mkt / 100)
        df_sim.loc[df_sim["categorie"] == "Honoraires", "realise"] *= (1 + delta_hon / 100)

        r_sim = df_sim["realise"].sum()
        ep_sim = (r_sim - budget_total) / budget_total * 100
        delta_base = r_sim - realise_total

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Budget", f"{budget_total:,.0f} €")
        c2.metric("Réalisé simulé", f"{r_sim:,.0f} €")
        c3.metric("Écart simulé", f"{r_sim - budget_total:+,.0f} €",
                  delta=f"{ep_sim:+.1f}%", delta_color="inverse")
        c4.metric("Impact vs base", f"{delta_base:+,.0f} €",
                  delta_color="inverse" if delta_base > 0 else "normal")

        agg_b = df_f.groupby("departement")["realise"].sum().reset_index(name="Base")
        agg_s = df_sim.groupby("departement")["realise"].sum().reset_index(name="Simulation")
        comp = agg_b.merge(agg_s, on="departement")
        fig_wi = go.Figure()
        fig_wi.add_trace(go.Bar(x=comp["departement"], y=comp["Base"],
                                name="Base", marker_color="#4ecdc4"))
        fig_wi.add_trace(go.Bar(x=comp["departement"], y=comp["Simulation"],
                                name="Simulation", marker_color="#ffd700"))
        fig_wi.update_layout(**CHART_DEFAULTS, title="Impact simulation par département", barmode="group")
        st.plotly_chart(fig_wi, use_container_width=True, key="ctrl_wi")

        lvl = "danger" if ep_sim > seuil else "warning" if ep_sim > 0 else "ok"
        msg = f"🔴 Dépassement critique {ep_sim:.1f}%" if ep_sim > seuil \
            else f"🟡 Sous tension +{ep_sim:.1f}%" if ep_sim > 0 \
            else f"✅ Scénario favorable — économie {abs(ep_sim):.1f}%"
        st.markdown(f'<div class="alert-{lvl}">{msg}</div>', unsafe_allow_html=True)

    # ── TAB 5 — Rapport & IA ──
    with tab5:
        st.markdown("## 📄 Rapport de gestion")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 🤖 Commentaire de gestion — IA")
            if not api_key:
                st.markdown('<div class="alert-warning">💡 Entrez votre clé API dans la sidebar</div>',
                            unsafe_allow_html=True)
            else:
                agg_kpis = df_f.groupby("departement")[["budget", "realise"]].sum()
                agg_kpis["ep"] = (agg_kpis["realise"] - agg_kpis["budget"]) / agg_kpis["budget"] * 100
                kpis_dict = {
                    "health_score": health,
                    "budget_total": int(budget_total),
                    "realise_total": int(realise_total),
                    "ecart_pct_global": round(ecart_pct_total, 2),
                    "ecarts_par_departement": agg_kpis["ep"].round(1).to_dict(),
                    "anomalies_detectees": len(anomalies),
                    "top_depassement": agg_kpis["ep"].idxmax(),
                }
                if st.button("🎙️ Générer le commentaire", type="primary", use_container_width=True):
                    with st.spinner("Rédaction..."):
                        narrative = generate_narrative("controlling", kpis_dict, api_key)
                    st.session_state["narrative_ctrl"] = narrative

            if "narrative_ctrl" in st.session_state:
                st.markdown(f'<div class="narrative-box">📝 {st.session_state["narrative_ctrl"]}</div>',
                            unsafe_allow_html=True)

        with col2:
            st.markdown("### 📥 Export PDF")
            st.caption("Rapport complet : KPIs + alertes + commentaire IA")
            kpis_lines = [
                f"Budget total : {budget_total:,.0f} €",
                f"Réalisé total : {realise_total:,.0f} €",
                f"Écart global : {ecart_total:+,.0f} € ({ecart_pct_total:+.1f}%)",
                f"Score de santé : {health}/100",
                f"Anomalies détectées : {len(anomalies)}",
            ]
            narrative_pdf = st.session_state.get("narrative_ctrl", "")
            pdf_bytes = generate_pdf("Rapport Controlling & Variance", kpis_lines, alerts, narrative_pdf)
            st.download_button("⬇️ Télécharger le rapport PDF", data=pdf_bytes,
                               file_name="rapport_controlling.pdf", mime="application/pdf",
                               use_container_width=True)
            st.caption("Format prêt pour comité de direction")

# ══════════════════════════════════════════════════════════════════════════════
# MODULE SUPPLY CHAIN
# ══════════════════════════════════════════════════════════════════════════════
else:
    use_up = "uploaded_data" in st.session_state and st.session_state.get("uploaded_mode") == "supply_chain"
    df = st.session_state["uploaded_data"] if use_up else load_supply()
    df_n1 = st.session_state.get("n1_data")
    has_n1 = df_n1 is not None

    df["mois"] = pd.to_datetime(df["mois"])
    seuil_service = st.session_state.get("seuil_service", 93)
    seuil_delai = st.session_state.get("seuil_delai", 5)

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        regions = st.multiselect("Régions", sorted(df["region"].unique()),
                                 default=list(df["region"].unique()))
    with col_f2:
        cats = st.multiselect("Catégories produit", sorted(df["categorie_produit"].unique()),
                              default=list(df["categorie_produit"].unique()))

    df_f = df[df["region"].isin(regions) & df["categorie_produit"].isin(cats)]

    taux_service_global = df_f["livraisons_a_temps"].sum() / df_f["commandes_total"].sum() * 100
    delai_moyen = df_f["delai_moyen_jours"].mean()
    taux_retour = df_f["retours"].sum() / df_f["commandes_total"].sum() * 100
    cout_total = df_f["cout_logistique"].sum()
    ca_total = df_f["ca_expedie"].sum()
    ratio_cout_ca = cout_total / ca_total * 100
    health = compute_health_sc(df_f, seuil_service)
    anomalies = detect_anomalies_sc(df_f)
    alerts = check_supply_alerts(df_f, seuil_service, seuil_delai)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Vue globale", "📈 Analyse par région",
        "🔍 Anomalies & N-1", "🎛️ Simulation what-if", "📄 Rapport & IA"
    ])

    with tab1:
        st.markdown("## Vue globale — Performance Supply Chain")
        col_g, col_k = st.columns([1, 3])
        with col_g:
            st.plotly_chart(health_gauge(health, "Score de santé"), use_container_width=True, key="gauge_sc")
        with col_k:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Taux de service", f"{taux_service_global:.1f}%",
                      delta=f"{'↑' if taux_service_global >= seuil_service else '↓'} seuil {seuil_service}%",
                      delta_color="normal" if taux_service_global >= seuil_service else "inverse")
            c2.metric("Délai moyen", f"{delai_moyen:.1f}j")
            c3.metric("Taux retour", f"{taux_retour:.1f}%")
            c4.metric("Coût logistique", f"{cout_total/1e6:.2f}M €")
            c5.metric("Ratio coût/CA", f"{ratio_cout_ca:.1f}%")

        if alerts:
            st.divider()
            for level, msg in alerts:
                st.markdown(f'<div class="alert-{level}">{msg}</div>', unsafe_allow_html=True)

        st.divider()
        agg_region = df_f.groupby("region").agg(taux_service=("taux_service","mean")).reset_index()
        fig_ts = px.bar(agg_region.sort_values("taux_service"),
                        x="taux_service", y="region", orientation="h",
                        color="taux_service",
                        color_continuous_scale=["#ff4444","#ffd700","#00ff88"],
                        range_color=[85, 99], title="Taux de service par région (%)")
        fig_ts.add_vline(x=seuil_service, line_dash="dash", line_color="#ff4444",
                         annotation_text=f"Seuil {seuil_service}%")
        fig_ts.update_layout(**CHART_DEFAULTS)
        fig_ts.update_coloraxes(showscale=False)
        st.plotly_chart(fig_ts, use_container_width=True, key="sc_ts")

        agg_mois = df_f.groupby("mois").agg(cout=("cout_logistique","sum"), ca=("ca_expedie","sum")).reset_index()
        agg_mois["ratio"] = agg_mois["cout"] / agg_mois["ca"] * 100
        fig_ratio = px.line(agg_mois, x="mois", y="ratio",
                            title="Évolution ratio coût / CA (%)", markers=True,
                            color_discrete_sequence=["#ffd700"])
        fig_ratio.update_layout(**CHART_DEFAULTS)
        st.plotly_chart(fig_ratio, use_container_width=True, key="sc_ratio")

    with tab2:
        st.markdown("## Analyse par région")
        col1, col2 = st.columns(2)
        with col1:
            agg_r = df_f.groupby(["region","categorie_produit"]).agg(
                commandes=("commandes_total","sum"), taux_service=("taux_service","mean")
            ).reset_index()
            fig_b = px.scatter(agg_r, x="taux_service", y="region",
                               size="commandes", color="categorie_produit",
                               color_discrete_sequence=PALETTE,
                               title="Volume × Taux de service", size_max=40)
            fig_b.update_layout(**CHART_DEFAULTS)
            st.plotly_chart(fig_b, use_container_width=True, key="sc_bubble")
        with col2:
            agg_s = df_f.groupby("region")["stock_couverture_jours"].mean().reset_index()
            fig_s = px.bar(agg_s, x="region", y="stock_couverture_jours",
                           color="stock_couverture_jours",
                           color_continuous_scale=["#00ff88","#ffd700","#ff4444"],
                           title="Couverture stock (jours)")
            fig_s.update_layout(**CHART_DEFAULTS)
            fig_s.update_coloraxes(showscale=False)
            st.plotly_chart(fig_s, use_container_width=True, key="sc_stock")

        st.divider()
        agg_t = df_f.groupby("region").agg(
            Commandes=("commandes_total","sum"), Livraisons_OT=("livraisons_a_temps","sum"),
            Taux_service=("taux_service","mean"), Délai_moyen=("delai_moyen_jours","mean"),
            Retours=("retours","sum"), Coût=("cout_logistique","sum"), CA=("ca_expedie","sum"),
        ).round(1).reset_index()
        agg_t["Taux_service"] = agg_t["Taux_service"].map("{:.1f}%".format)
        agg_t["Délai_moyen"] = agg_t["Délai_moyen"].map("{:.1f}j".format)
        agg_t["Coût"] = agg_t["Coût"].map("{:,.0f} €".format)
        agg_t["CA"] = agg_t["CA"].map("{:,.0f} €".format)
        st.dataframe(agg_t, use_container_width=True, hide_index=True)
        csv = df_f.to_csv(index=False, sep=";", encoding="utf-8-sig")
        st.download_button("⬇️ Exporter CSV", data=csv,
                           file_name="supply_chain_export.csv", mime="text/csv")

    with tab3:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("## 🔍 Anomalies statistiques (Z-score > 2σ)")
            if anomalies:
                for a in anomalies:
                    st.markdown(f'<span class="anomaly-tag">⚡ {a}</span>', unsafe_allow_html=True)
                st.markdown('<div class="alert-danger" style="margin-top:8px">⚠️ Investigation recommandée</div>',
                            unsafe_allow_html=True)
            else:
                st.markdown('<div class="alert-ok">✅ Aucune anomalie détectée</div>', unsafe_allow_html=True)

            agg_z = df_f.groupby(["mois","region"])["taux_service"].mean().reset_index()
            mz = agg_z["taux_service"].mean()
            sz = agg_z["taux_service"].std() or 1
            agg_z["zscore"] = (agg_z["taux_service"] - mz) / sz
            agg_z["mois_str"] = agg_z["mois"].astype(str).str[:7]
            fig_z = px.scatter(agg_z, x="mois_str", y="zscore",
                               color="region", size=agg_z["zscore"].abs() + 0.5,
                               color_discrete_sequence=PALETTE,
                               title="Z-scores taux de service par région")
            fig_z.add_hline(y=2, line_dash="dash", line_color="#ff4444", annotation_text="+2σ")
            fig_z.add_hline(y=-2, line_dash="dash", line_color="#ff4444", annotation_text="-2σ")
            fig_z.update_layout(**CHART_DEFAULTS)
            st.plotly_chart(fig_z, use_container_width=True, key="sc_zscore")

        with col_b:
            st.markdown("## 📅 Comparaison N vs N-1")
            if not has_n1:
                st.markdown('<div class="alert-warning">💡 Chargez un fichier N-1 dans la sidebar</div>',
                            unsafe_allow_html=True)
            else:
                df_n1_f = df_n1.copy()
                ts_n1 = df_n1_f["livraisons_a_temps"].sum() / df_n1_f["commandes_total"].sum() * 100 \
                    if "livraisons_a_temps" in df_n1_f.columns else 0
                c1, c2 = st.columns(2)
                c1.metric("Taux service N", f"{taux_service_global:.1f}%",
                          delta=f"{taux_service_global - ts_n1:+.1f}pts vs N-1",
                          delta_color="normal")
                c2.metric("Coût logistique N", f"{cout_total/1e6:.2f}M €")

                if "region" in df_n1_f.columns and "taux_service" in df_n1_f.columns:
                    agg_n = df_f.groupby("region")["taux_service"].mean().reset_index(name="N")
                    agg_n1 = df_n1_f.groupby("region")["taux_service"].mean().reset_index(name="N-1")
                    comp = agg_n.merge(agg_n1, on="region", how="left").fillna(0)
                    fig_n1 = go.Figure()
                    fig_n1.add_trace(go.Bar(x=comp["region"], y=comp["N-1"],
                                           name="N-1", marker_color="#4ecdc4", opacity=0.7))
                    fig_n1.add_trace(go.Bar(x=comp["region"], y=comp["N"],
                                           name="N (actuel)", marker_color="#00ff88"))
                    fig_n1.update_layout(**CHART_DEFAULTS, title="Taux de service N vs N-1",
                                        barmode="group")
                    st.plotly_chart(fig_n1, use_container_width=True, key="sc_n1")

    with tab4:
        st.markdown("## 🎛️ Simulation what-if — Impact opérationnel")
        st.markdown('<div class="whatif-box">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            delta_delai = st.slider("Variation délai (jours)", -2, 5, 0)
            delta_retours = st.slider("Variation taux retour (%)", -2, 5, 0)
        with col2:
            delta_cout = st.slider("Variation coût logistique (%)", -20, 30, 0)
            delta_cmd = st.slider("Variation volume commandes (%)", -20, 30, 0)
        st.markdown('</div>', unsafe_allow_html=True)

        df_sim = df_f.copy()
        df_sim["delai_moyen_jours"] = (df_sim["delai_moyen_jours"] + delta_delai).clip(lower=1)
        df_sim["retours"] = (df_sim["retours"] * (1 + delta_retours / 100)).round()
        df_sim["cout_logistique"] *= (1 + delta_cout / 100)
        df_sim["commandes_total"] = (df_sim["commandes_total"] * (1 + delta_cmd / 100)).round()

        ts_sim = df_sim["livraisons_a_temps"].sum() / df_sim["commandes_total"].sum() * 100
        cout_sim = df_sim["cout_logistique"].sum()
        retour_sim = df_sim["retours"].sum() / df_sim["commandes_total"].sum() * 100

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Taux service simulé", f"{ts_sim:.1f}%",
                  delta=f"{ts_sim - taux_service_global:+.1f}%",
                  delta_color="normal" if ts_sim >= seuil_service else "inverse")
        c2.metric("Délai simulé", f"{(delai_moyen + delta_delai):.1f}j")
        c3.metric("Coût simulé", f"{cout_sim/1e6:.2f}M €",
                  delta=f"{(cout_sim - cout_total)/1e6:+.2f}M €", delta_color="inverse")
        c4.metric("Taux retour simulé", f"{retour_sim:.1f}%")

        comp_data = pd.DataFrame({
            "Indicateur": ["Taux service (%)", "Délai (j)", "Taux retour (%)", "Coût/CA (%)"],
            "Base": [taux_service_global, delai_moyen, taux_retour, ratio_cout_ca],
            "Simulation": [ts_sim, delai_moyen + delta_delai, retour_sim,
                           cout_sim / df_sim["ca_expedie"].sum() * 100],
        })
        fig_wi = go.Figure()
        fig_wi.add_trace(go.Bar(x=comp_data["Indicateur"], y=comp_data["Base"],
                                name="Base", marker_color="#4ecdc4"))
        fig_wi.add_trace(go.Bar(x=comp_data["Indicateur"], y=comp_data["Simulation"],
                                name="Simulation", marker_color="#ffd700"))
        fig_wi.update_layout(**CHART_DEFAULTS, title="Base vs Simulation", barmode="group")
        st.plotly_chart(fig_wi, use_container_width=True, key="sc_wi")

        lvl = "danger" if ts_sim < seuil_service else "ok"
        msg = f"🔴 Taux de service {ts_sim:.1f}% sous le seuil {seuil_service}%" \
            if ts_sim < seuil_service else f"✅ Taux de service maintenu à {ts_sim:.1f}%"
        st.markdown(f'<div class="alert-{lvl}">{msg}</div>', unsafe_allow_html=True)

    with tab5:
        st.markdown("## 📄 Rapport opérationnel")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### 🤖 Commentaire Supply Chain — IA")
            if not api_key:
                st.markdown('<div class="alert-warning">💡 Entrez votre clé API dans la sidebar</div>',
                            unsafe_allow_html=True)
            else:
                kpis_dict = {
                    "health_score": health,
                    "taux_service_global": round(taux_service_global, 1),
                    "seuil_service": seuil_service,
                    "delai_moyen_jours": round(delai_moyen, 1),
                    "taux_retour_pct": round(taux_retour, 1),
                    "ratio_cout_ca_pct": round(ratio_cout_ca, 1),
                    "anomalies_detectees": len(anomalies),
                    "regions_sous_seuil": [r for r, v in
                                           df_f.groupby("region")["taux_service"].mean().items()
                                           if v < seuil_service],
                }
                if st.button("🎙️ Générer le commentaire opérationnel", type="primary", use_container_width=True):
                    with st.spinner("Rédaction..."):
                        narrative = generate_narrative("supply_chain", kpis_dict, api_key)
                    st.session_state["narrative_sc"] = narrative

            if "narrative_sc" in st.session_state:
                st.markdown(f'<div class="narrative-box">📝 {st.session_state["narrative_sc"]}</div>',
                            unsafe_allow_html=True)

        with col2:
            st.markdown("### 📥 Export PDF")
            kpis_lines = [
                f"Taux de service : {taux_service_global:.1f}% (seuil {seuil_service}%)",
                f"Délai moyen : {delai_moyen:.1f} jours",
                f"Taux de retour : {taux_retour:.1f}%",
                f"Coût logistique : {cout_total/1e6:.2f}M €",
                f"Ratio coût/CA : {ratio_cout_ca:.1f}%",
                f"Score de santé : {health}/100",
                f"Anomalies détectées : {len(anomalies)}",
            ]
            narrative_pdf = st.session_state.get("narrative_sc", "")
            pdf_bytes = generate_pdf("Rapport Supply Chain KPIs", kpis_lines, alerts, narrative_pdf)
            st.download_button("⬇️ Télécharger le rapport PDF", data=pdf_bytes,
                               file_name="rapport_supply_chain.pdf", mime="application/pdf",
                               use_container_width=True)
            st.caption("Format prêt pour comité de pilotage")

# ─── Footer ───────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    '<div class="footer-caption">Construit avec l\'IA · Gisèle Metouck · '
    '<a href="https://github.com/Kingdmfncr" style="color:#00ff88">GitHub</a></div>',
    unsafe_allow_html=True,
)

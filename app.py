import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import re
import json

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
  .whatif-box { background:#1a1a2e; border:1px solid rgba(0,255,136,0.3); border-radius:8px; padding:16px; margin:8px 0; }
  .narrative-box { background:#1a1a2e; border:1px solid #ffd700; border-radius:8px; padding:20px; margin:12px 0; font-size:0.95rem; line-height:1.7; color:#ffffff; }
  .footer-caption { color:#888888; font-size:0.8rem; text-align:center; margin-top:32px; }
  .upload-info { background:#1a1a2e; border-radius:8px; padding:12px 16px; border:1px solid rgba(0,255,136,0.3); margin:8px 0; font-size:0.9rem; }
</style>
""", unsafe_allow_html=True)

# ─── Chart defaults ───────────────────────────────────────────────────────────
CHART_DEFAULTS = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#1a1a2e",
    font_color="#ffffff",
    font_family="sans-serif",
    title_font_color="#00ff88",
    title_font_size=16,
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

def detect_file_type(df: pd.DataFrame) -> str:
    cols = [c.lower() for c in df.columns]
    if any(k in cols for k in ["budget", "realise", "ecart", "departement"]):
        return "controlling"
    if any(k in cols for k in ["taux_service", "commandes_total", "delai_moyen", "livraisons"]):
        return "supply_chain"
    return "unknown"

def load_uploaded(file) -> tuple[pd.DataFrame, str]:
    try:
        content = file.read()
        name = file.name.lower()
        if name.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content), sep=None, engine="python", encoding="utf-8-sig")
        else:
            df = pd.read_excel(io.BytesIO(content))
        return df, detect_file_type(df)
    except Exception as e:
        st.error(f"Erreur lecture fichier : {e}")
        return None, "unknown"

# ─── Alertes ─────────────────────────────────────────────────────────────────
def check_controlling_alerts(df: pd.DataFrame, seuil_ecart: float) -> list:
    alerts = []
    agg = df.groupby("departement")[["budget", "realise"]].sum()
    agg["ecart_pct"] = (agg["realise"] - agg["budget"]) / agg["budget"] * 100
    for dept, row in agg.iterrows():
        if row["ecart_pct"] > seuil_ecart:
            alerts.append(("danger", f"⚠️ {dept} — dépassement budgétaire de +{row['ecart_pct']:.1f}% ({row['realise']-row['budget']:+,.0f} €)"))
        elif row["ecart_pct"] > seuil_ecart / 2:
            alerts.append(("warning", f"🟡 {dept} — écart modéré de +{row['ecart_pct']:.1f}%"))
        elif row["ecart_pct"] < -seuil_ecart:
            alerts.append(("ok", f"✅ {dept} — sous-consommation de {row['ecart_pct']:.1f}% (économies potentielles)"))
    return alerts

def check_supply_alerts(df: pd.DataFrame, seuil_service: float, seuil_delai: float) -> list:
    alerts = []
    agg = df.groupby("region").agg(
        taux_service=("taux_service", "mean"),
        delai_moyen=("delai_moyen_jours", "mean"),
        retours=("retours", "sum"),
        commandes=("commandes_total", "sum"),
    )
    for region, row in agg.iterrows():
        if row["taux_service"] < seuil_service:
            alerts.append(("danger", f"⚠️ {region} — taux de service {row['taux_service']:.1f}% < seuil {seuil_service}%"))
        if row["delai_moyen"] > seuil_delai:
            alerts.append(("warning", f"🟡 {region} — délai moyen {row['delai_moyen']:.1f}j > seuil {seuil_delai}j"))
        taux_retour = row["retours"] / row["commandes"] * 100
        if taux_retour > 3.5:
            alerts.append(("warning", f"🟡 {region} — taux de retour élevé : {taux_retour:.1f}%"))
    return alerts

# ─── Narratif IA ─────────────────────────────────────────────────────────────
def generate_narrative(mode: str, kpis: dict, api_key: str) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        if mode == "controlling":
            prompt = f"""Tu es contrôleur de gestion senior. Rédige un commentaire de gestion concis (3-4 phrases)
pour un comité de direction, basé sur ces indicateurs :
{json.dumps(kpis, ensure_ascii=False, indent=2)}

Règles :
- Langue : français professionnel
- Mentionne les écarts significatifs et leurs causes probables
- Termine par une recommandation concrète
- Style : rapport de comex, factuel et direct"""
        else:
            prompt = f"""Tu es responsable Supply Chain senior. Rédige un commentaire opérationnel concis (3-4 phrases)
pour un comité de pilotage, basé sur ces indicateurs :
{json.dumps(kpis, ensure_ascii=False, indent=2)}

Règles :
- Langue : français professionnel
- Identifie les zones de risque et les tendances positives
- Termine par une action prioritaire
- Style : rapport opérationnel, factuel"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except ImportError:
        return "Package 'anthropic' manquant."
    except Exception as e:
        return f"Erreur API : {e}"

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 📊 Business Performance")
    st.divider()

    # Toggle mode
    mode = st.radio(
        "Module actif",
        ["💰 Controlling & Variance", "🚚 Supply Chain KPIs"],
        index=0,
    )

    st.divider()

    # Upload données réelles
    st.markdown("### 📁 Vos données")
    uploaded = st.file_uploader("Charger un fichier CSV/Excel", type=["csv", "xlsx"])
    if uploaded:
        df_up, detected = load_uploaded(uploaded)
        if df_up is not None and detected != "unknown":
            st.session_state["uploaded_data"] = df_up
            st.session_state["uploaded_mode"] = detected
            st.success(f"✅ Fichier chargé — type détecté : **{detected}**")
        elif detected == "unknown":
            st.warning("Type de fichier non reconnu. Vérifiez les colonnes.")

    st.divider()

    # Seuils d'alerte
    st.markdown("### 🔔 Seuils d'alerte")
    if "Controlling" in mode:
        seuil_ecart = st.slider("Dépassement budgétaire (%)", 5, 30, 10)
        st.session_state["seuil_ecart"] = seuil_ecart
    else:
        seuil_service = st.slider("Taux de service minimum (%)", 85, 99, 93)
        seuil_delai = st.slider("Délai de livraison max (jours)", 3, 10, 5)
        st.session_state["seuil_service"] = seuil_service
        st.session_state["seuil_delai"] = seuil_delai

    st.divider()

    # API Claude
    st.markdown("### 🤖 Commentaire IA")
    api_key = st.text_input("Clé API Anthropic (optionnel)", type="password", placeholder="sk-ant-...")
    st.caption("~0.01€ par commentaire · Clé non stockée")

    st.divider()
    st.caption("🔗 [GitHub](https://github.com/Kingdmfncr) · Gisèle Metouck")

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("# 📊 Business Performance Dashboard")
st.markdown("**Analyse d'écarts budgétaires · KPIs Supply Chain · Simulation what-if · Commentaire de gestion IA**")
st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# MODULE CONTROLLING
# ══════════════════════════════════════════════════════════════════════════════
if "Controlling" in mode:
    # Choix source données
    use_uploaded = "uploaded_data" in st.session_state and st.session_state.get("uploaded_mode") == "controlling"
    df = st.session_state["uploaded_data"] if use_uploaded else load_controlling()
    if use_uploaded:
        st.markdown('<div class="alert-ok">✅ Données chargées depuis votre fichier</div>', unsafe_allow_html=True)

    df["mois"] = pd.to_datetime(df["mois"])
    df["ecart"] = df["realise"] - df["budget"]
    df["ecart_pct"] = (df["ecart"] / df["budget"] * 100).round(2)

    # Filtres
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

    tab1, tab2, tab3, tab4 = st.tabs(["📋 Vue globale", "📈 Analyse détaillée", "🎛️ Simulation what-if", "🤖 Commentaire IA"])

    with tab1:
        st.markdown("## Vue globale — Contrôle budgétaire")
        budget_total = df_f["budget"].sum()
        realise_total = df_f["realise"].sum()
        ecart_total = realise_total - budget_total
        ecart_pct_total = ecart_total / budget_total * 100

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Budget total", f"{budget_total:,.0f} €")
        c2.metric("Réalisé total", f"{realise_total:,.0f} €")
        c3.metric("Écart total", f"{ecart_total:+,.0f} €",
                  delta=f"{ecart_pct_total:+.1f}%",
                  delta_color="inverse")
        seuil = st.session_state.get("seuil_ecart", 10)
        statut = "🔴 Dépassement" if ecart_pct_total > seuil else "🟢 Sous contrôle"
        c4.metric("Statut", statut)

        st.divider()

        # Alertes
        alerts = check_controlling_alerts(df_f, seuil)
        if alerts:
            st.markdown("### 🔔 Alertes actives")
            for level, msg in alerts:
                st.markdown(f'<div class="alert-{level}">{msg}</div>', unsafe_allow_html=True)
            st.divider()

        # Graphique par département
        agg_dept = df_f.groupby("departement")[["budget", "realise"]].sum().reset_index()
        agg_dept["ecart_pct"] = (agg_dept["realise"] - agg_dept["budget"]) / agg_dept["budget"] * 100

        fig_dept = go.Figure()
        fig_dept.add_trace(go.Bar(x=agg_dept["departement"], y=agg_dept["budget"],
                                  name="Budget", marker_color="#4ecdc4"))
        fig_dept.add_trace(go.Bar(x=agg_dept["departement"], y=agg_dept["realise"],
                                  name="Réalisé", marker_color="#00ff88"))
        fig_dept.update_layout(**CHART_DEFAULTS, title="Budget vs Réalisé par département",
                               barmode="group")
        st.plotly_chart(fig_dept, use_container_width=True, key="ctrl_dept")

        # Évolution écart dans le temps
        agg_mois = df_f.groupby("mois")[["budget", "realise"]].sum().reset_index()
        agg_mois["ecart_pct"] = (agg_mois["realise"] - agg_mois["budget"]) / agg_mois["budget"] * 100
        fig_trend = px.line(agg_mois, x="mois", y="ecart_pct",
                            title="Évolution de l'écart budgétaire (%)",
                            markers=True, color_discrete_sequence=["#ffd700"])
        fig_trend.add_hline(y=0, line_dash="dot", line_color="#888888")
        fig_trend.add_hline(y=seuil, line_dash="dash", line_color="#ff4444",
                            annotation_text=f"Seuil alerte {seuil}%")
        fig_trend.update_layout(**CHART_DEFAULTS)
        st.plotly_chart(fig_trend, use_container_width=True, key="ctrl_trend")

    with tab2:
        st.markdown("## Analyse détaillée — Matrice des écarts")

        col1, col2 = st.columns(2)
        with col1:
            # Waterfall écart par catégorie
            agg_cat = df_f.groupby("categorie")[["budget", "realise"]].sum().reset_index()
            agg_cat["ecart"] = agg_cat["realise"] - agg_cat["budget"]
            agg_cat = agg_cat.sort_values("ecart", ascending=False)

            fig_wf = go.Figure(go.Waterfall(
                x=agg_cat["categorie"],
                y=agg_cat["ecart"],
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
            # Heatmap dept × catégorie
            pivot = df_f.pivot_table(values="ecart_pct", index="departement",
                                     columns="categorie", aggfunc="mean").round(1)
            fig_heat = px.imshow(pivot,
                                 color_continuous_scale=["#00ff88", "#ffd700", "#ff4444"],
                                 title="Heatmap écarts (%) — Département × Catégorie",
                                 text_auto=True)
            fig_heat.update_layout(**CHART_DEFAULTS)
            st.plotly_chart(fig_heat, use_container_width=True, key="ctrl_heat")

        st.divider()
        st.markdown("### Tableau détaillé")
        df_display = df_f.copy()
        df_display["mois"] = df_display["mois"].dt.strftime("%Y-%m")
        df_display["budget"] = df_display["budget"].map("{:,.0f} €".format)
        df_display["realise"] = df_display["realise"].map("{:,.0f} €".format)
        df_display["ecart"] = df_display["ecart"].map("{:+,.0f} €".format)
        df_display["ecart_pct"] = df_display["ecart_pct"].map("{:+.1f}%".format)
        st.dataframe(df_display[["mois", "departement", "categorie", "budget", "realise", "ecart", "ecart_pct"]],
                     use_container_width=True, hide_index=True)

        csv = df_f.to_csv(index=False, sep=";", encoding="utf-8-sig")
        st.download_button("⬇️ Exporter (CSV)", data=csv,
                           file_name="controlling_export.csv", mime="text/csv")

    with tab3:
        st.markdown("## 🎛️ Simulation what-if")
        st.markdown("*Modifiez les hypothèses pour simuler l'impact sur le budget consolidé*")

        st.markdown('<div class="whatif-box">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            delta_masse_sal = st.slider("Variation masse salariale (%)", -15, 20, 0)
            delta_logistique = st.slider("Variation frais logistiques (%)", -20, 30, 0)
        with col2:
            delta_marketing = st.slider("Variation budget marketing (%)", -30, 30, 0)
            delta_honoraires = st.slider("Variation honoraires externes (%)", -20, 50, 0)
        st.markdown('</div>', unsafe_allow_html=True)

        # Calcul simulation
        df_sim = df_f.copy()
        mask_sal = df_sim["categorie"] == "Masse salariale"
        mask_log = df_sim["categorie"] == "Logistique"
        mask_mkt = df_sim["categorie"] == "Marketing"
        mask_hon = df_sim["categorie"] == "Honoraires"

        df_sim.loc[mask_sal, "realise"] = df_sim.loc[mask_sal, "realise"] * (1 + delta_masse_sal / 100)
        df_sim.loc[mask_log, "realise"] = df_sim.loc[mask_log, "realise"] * (1 + delta_logistique / 100)
        df_sim.loc[mask_mkt, "realise"] = df_sim.loc[mask_mkt, "realise"] * (1 + delta_marketing / 100)
        df_sim.loc[mask_hon, "realise"] = df_sim.loc[mask_hon, "realise"] * (1 + delta_honoraires / 100)

        budget_sim = df_sim["budget"].sum()
        realise_sim = df_sim["realise"].sum()
        ecart_sim = realise_sim - budget_sim
        ecart_pct_sim = ecart_sim / budget_sim * 100

        realise_base = df_f["realise"].sum()
        delta_vs_base = realise_sim - realise_base

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Budget", f"{budget_sim:,.0f} €")
        c2.metric("Réalisé simulé", f"{realise_sim:,.0f} €")
        c3.metric("Écart simulé", f"{ecart_sim:+,.0f} €", delta=f"{ecart_pct_sim:+.1f}%",
                  delta_color="inverse")
        c4.metric("Impact vs base", f"{delta_vs_base:+,.0f} €",
                  delta_color="inverse" if delta_vs_base > 0 else "normal")

        # Comparaison base vs simulation
        agg_base = df_f.groupby("departement")["realise"].sum().reset_index(name="Base")
        agg_sim_dept = df_sim.groupby("departement")["realise"].sum().reset_index(name="Simulation")
        comp = agg_base.merge(agg_sim_dept, on="departement")

        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(x=comp["departement"], y=comp["Base"],
                                  name="Base actuelle", marker_color="#4ecdc4"))
        fig_comp.add_trace(go.Bar(x=comp["departement"], y=comp["Simulation"],
                                  name="Simulation", marker_color="#ffd700"))
        fig_comp.update_layout(**CHART_DEFAULTS,
                               title="Impact de la simulation par département",
                               barmode="group")
        st.plotly_chart(fig_comp, use_container_width=True, key="ctrl_whatif")

        if ecart_pct_sim > seuil:
            st.markdown(f'<div class="alert-danger">🔴 Scénario critique — dépassement de {ecart_pct_sim:.1f}% sur ce scénario</div>',
                        unsafe_allow_html=True)
        elif ecart_pct_sim > 0:
            st.markdown(f'<div class="alert-warning">🟡 Scénario sous tension — écart de +{ecart_pct_sim:.1f}%</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="alert-ok">✅ Scénario favorable — économie de {abs(ecart_pct_sim):.1f}% par rapport au budget</div>',
                        unsafe_allow_html=True)

    with tab4:
        st.markdown("## 🤖 Commentaire de gestion — IA")
        st.caption("Génère un commentaire de comité de direction basé sur vos indicateurs actuels")

        if not api_key:
            st.markdown('<div class="alert-warning">💡 Entrez votre clé API Anthropic dans la sidebar pour activer cette fonctionnalité</div>',
                        unsafe_allow_html=True)
        else:
            agg_kpis = df_f.groupby("departement")[["budget", "realise"]].sum()
            agg_kpis["ecart_pct"] = (agg_kpis["realise"] - agg_kpis["budget"]) / agg_kpis["budget"] * 100
            kpis_dict = {
                "budget_total": int(df_f["budget"].sum()),
                "realise_total": int(df_f["realise"].sum()),
                "ecart_pct_global": round((df_f["realise"].sum() - df_f["budget"].sum()) / df_f["budget"].sum() * 100, 2),
                "ecarts_par_departement": agg_kpis["ecart_pct"].round(1).to_dict(),
                "top_depassement": agg_kpis["ecart_pct"].idxmax(),
                "top_economie": agg_kpis["ecart_pct"].idxmin(),
            }

            if st.button("🎙️ Générer le commentaire de gestion", type="primary", use_container_width=True):
                with st.spinner("Rédaction en cours..."):
                    narrative = generate_narrative("controlling", kpis_dict, api_key)
                st.session_state["narrative_ctrl"] = narrative

            if "narrative_ctrl" in st.session_state:
                st.markdown(f'<div class="narrative-box">📝 {st.session_state["narrative_ctrl"]}</div>',
                            unsafe_allow_html=True)
                st.download_button("⬇️ Télécharger le commentaire",
                                   data=st.session_state["narrative_ctrl"],
                                   file_name="commentaire_gestion.txt")

# ══════════════════════════════════════════════════════════════════════════════
# MODULE SUPPLY CHAIN
# ══════════════════════════════════════════════════════════════════════════════
else:
    use_uploaded = "uploaded_data" in st.session_state and st.session_state.get("uploaded_mode") == "supply_chain"
    df = st.session_state["uploaded_data"] if use_uploaded else load_supply()
    if use_uploaded:
        st.markdown('<div class="alert-ok">✅ Données chargées depuis votre fichier</div>', unsafe_allow_html=True)

    df["mois"] = pd.to_datetime(df["mois"])
    seuil_service = st.session_state.get("seuil_service", 93)
    seuil_delai = st.session_state.get("seuil_delai", 5)

    # Filtres
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        regions = st.multiselect("Régions", sorted(df["region"].unique()),
                                 default=list(df["region"].unique()))
    with col_f2:
        cats = st.multiselect("Catégories produit", sorted(df["categorie_produit"].unique()),
                              default=list(df["categorie_produit"].unique()))

    df_f = df[df["region"].isin(regions) & df["categorie_produit"].isin(cats)]

    tab1, tab2, tab3, tab4 = st.tabs(["📋 Vue globale", "📈 Analyse par région", "🎛️ Simulation what-if", "🤖 Commentaire IA"])

    with tab1:
        st.markdown("## Vue globale — Performance Supply Chain")

        taux_service_global = (df_f["livraisons_a_temps"].sum() / df_f["commandes_total"].sum() * 100)
        delai_moyen = df_f["delai_moyen_jours"].mean()
        taux_retour = df_f["retours"].sum() / df_f["commandes_total"].sum() * 100
        cout_total = df_f["cout_logistique"].sum()
        ca_total = df_f["ca_expedie"].sum()
        ratio_cout_ca = cout_total / ca_total * 100

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Taux de service", f"{taux_service_global:.1f}%",
                  delta=f"{'↑' if taux_service_global >= seuil_service else '↓'} seuil {seuil_service}%",
                  delta_color="normal" if taux_service_global >= seuil_service else "inverse")
        c2.metric("Délai moyen", f"{delai_moyen:.1f}j",
                  delta_color="inverse" if delai_moyen > seuil_delai else "normal")
        c3.metric("Taux de retour", f"{taux_retour:.1f}%",
                  delta_color="inverse" if taux_retour > 3 else "normal")
        c4.metric("Coût logistique", f"{cout_total/1e6:.2f}M €")
        c5.metric("Ratio coût/CA", f"{ratio_cout_ca:.1f}%")

        st.divider()

        # Alertes
        alerts = check_supply_alerts(df_f, seuil_service, seuil_delai)
        if alerts:
            st.markdown("### 🔔 Alertes actives")
            for level, msg in alerts:
                st.markdown(f'<div class="alert-{level}">{msg}</div>', unsafe_allow_html=True)
            st.divider()

        col1, col2 = st.columns(2)
        with col1:
            agg_region = df_f.groupby("region").agg(
                taux_service=("taux_service", "mean"),
                delai_moyen=("delai_moyen_jours", "mean"),
            ).reset_index()
            fig_ts = px.bar(agg_region.sort_values("taux_service"),
                            x="taux_service", y="region", orientation="h",
                            color="taux_service",
                            color_continuous_scale=["#ff4444", "#ffd700", "#00ff88"],
                            range_color=[85, 99],
                            title="Taux de service par région (%)")
            fig_ts.add_vline(x=seuil_service, line_dash="dash", line_color="#ff4444",
                             annotation_text=f"Seuil {seuil_service}%")
            fig_ts.update_layout(**CHART_DEFAULTS)
            fig_ts.update_coloraxes(showscale=False)
            st.plotly_chart(fig_ts, use_container_width=True, key="sc_taux_service")

        with col2:
            agg_mois = df_f.groupby("mois").agg(
                taux_service=("taux_service", "mean"),
                cout=("cout_logistique", "sum"),
                ca=("ca_expedie", "sum"),
            ).reset_index()
            agg_mois["ratio"] = agg_mois["cout"] / agg_mois["ca"] * 100
            fig_ratio = px.line(agg_mois, x="mois", y="ratio",
                                title="Évolution ratio coût logistique / CA (%)",
                                markers=True, color_discrete_sequence=["#ffd700"])
            fig_ratio.update_layout(**CHART_DEFAULTS)
            st.plotly_chart(fig_ratio, use_container_width=True, key="sc_ratio")

    with tab2:
        st.markdown("## Analyse par région")

        col1, col2 = st.columns(2)
        with col1:
            agg_r = df_f.groupby(["region", "categorie_produit"]).agg(
                commandes=("commandes_total", "sum"),
                taux_service=("taux_service", "mean"),
            ).reset_index()
            fig_bubble = px.scatter(agg_r, x="taux_service", y="region",
                                    size="commandes", color="categorie_produit",
                                    color_discrete_sequence=PALETTE,
                                    title="Volume × Taux de service par région",
                                    size_max=40)
            fig_bubble.update_layout(**CHART_DEFAULTS)
            st.plotly_chart(fig_bubble, use_container_width=True, key="sc_bubble")

        with col2:
            agg_stock = df_f.groupby("region")["stock_couverture_jours"].mean().reset_index()
            fig_stock = px.bar(agg_stock, x="region", y="stock_couverture_jours",
                               color="stock_couverture_jours",
                               color_continuous_scale=["#00ff88", "#ffd700", "#ff4444"],
                               title="Couverture stock moyenne (jours)")
            fig_stock.update_layout(**CHART_DEFAULTS)
            fig_stock.update_coloraxes(showscale=False)
            st.plotly_chart(fig_stock, use_container_width=True, key="sc_stock")

        st.divider()
        st.markdown("### Tableau de bord opérationnel")
        agg_table = df_f.groupby("region").agg(
            Commandes=("commandes_total", "sum"),
            Livraisons_OT=("livraisons_a_temps", "sum"),
            Taux_service=("taux_service", "mean"),
            Délai_moyen=("delai_moyen_jours", "mean"),
            Retours=("retours", "sum"),
            Coût_logistique=("cout_logistique", "sum"),
            CA_expédié=("ca_expedie", "sum"),
        ).round(1).reset_index()
        Agg_table = agg_table.copy()
        Agg_table["Taux_service"] = Agg_table["Taux_service"].map("{:.1f}%".format)
        Agg_table["Délai_moyen"] = Agg_table["Délai_moyen"].map("{:.1f}j".format)
        Agg_table["Coût_logistique"] = Agg_table["Coût_logistique"].map("{:,.0f} €".format)
        Agg_table["CA_expédié"] = Agg_table["CA_expédié"].map("{:,.0f} €".format)
        st.dataframe(Agg_table, use_container_width=True, hide_index=True)

        csv = df_f.to_csv(index=False, sep=";", encoding="utf-8-sig")
        st.download_button("⬇️ Exporter (CSV)", data=csv,
                           file_name="supply_chain_export.csv", mime="text/csv")

    with tab3:
        st.markdown("## 🎛️ Simulation what-if — Impact opérationnel")
        st.markdown("*Simulez l'effet de variations sur vos indicateurs clés*")

        st.markdown('<div class="whatif-box">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            delta_delai = st.slider("Variation délai de livraison (jours)", -2, 5, 0)
            delta_retours = st.slider("Variation taux de retour (%)", -2, 5, 0)
        with col2:
            delta_cout = st.slider("Variation coût logistique (%)", -20, 30, 0)
            delta_commandes = st.slider("Variation volume commandes (%)", -20, 30, 0)
        st.markdown('</div>', unsafe_allow_html=True)

        # Calcul simulation
        df_sim = df_f.copy()
        df_sim["delai_moyen_jours"] = (df_sim["delai_moyen_jours"] + delta_delai).clip(lower=1)
        df_sim["retours"] = (df_sim["retours"] * (1 + delta_retours / 100)).round()
        df_sim["cout_logistique"] = df_sim["cout_logistique"] * (1 + delta_cout / 100)
        df_sim["commandes_total"] = (df_sim["commandes_total"] * (1 + delta_commandes / 100)).round()

        ts_sim = df_sim["livraisons_a_temps"].sum() / df_sim["commandes_total"].sum() * 100
        delai_sim = df_sim["delai_moyen_jours"].mean()
        cout_sim = df_sim["cout_logistique"].sum()
        retour_sim = df_sim["retours"].sum() / df_sim["commandes_total"].sum() * 100

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Taux de service simulé", f"{ts_sim:.1f}%",
                  delta=f"{ts_sim - taux_service_global:+.1f}%",
                  delta_color="normal" if ts_sim >= seuil_service else "inverse")
        c2.metric("Délai simulé", f"{delai_sim:.1f}j",
                  delta=f"{delai_sim - delai_moyen:+.1f}j",
                  delta_color="inverse" if delai_sim > seuil_delai else "normal")
        c3.metric("Coût logistique simulé", f"{cout_sim/1e6:.2f}M €",
                  delta=f"{(cout_sim - cout_total)/1e6:+.2f}M €",
                  delta_color="inverse")
        c4.metric("Taux de retour simulé", f"{retour_sim:.1f}%",
                  delta=f"{retour_sim - taux_retour:+.1f}%",
                  delta_color="inverse")

        # Comparaison
        comp_data = pd.DataFrame({
            "Indicateur": ["Taux de service (%)", "Délai moyen (j)", "Taux retour (%)", "Ratio coût/CA (%)"],
            "Base": [taux_service_global, delai_moyen, taux_retour, ratio_cout_ca],
            "Simulation": [ts_sim, delai_sim, retour_sim,
                           cout_sim / df_sim["ca_expedie"].sum() * 100],
        })
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(x=comp_data["Indicateur"], y=comp_data["Base"],
                                  name="Base", marker_color="#4ecdc4"))
        fig_comp.add_trace(go.Bar(x=comp_data["Indicateur"], y=comp_data["Simulation"],
                                  name="Simulation", marker_color="#ffd700"))
        fig_comp.update_layout(**CHART_DEFAULTS, title="Base vs Simulation — Indicateurs clés",
                               barmode="group")
        st.plotly_chart(fig_comp, use_container_width=True, key="sc_whatif")

        if ts_sim < seuil_service:
            st.markdown(f'<div class="alert-danger">🔴 Scénario critique — taux de service {ts_sim:.1f}% sous le seuil {seuil_service}%</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="alert-ok">✅ Taux de service maintenu à {ts_sim:.1f}%</div>',
                        unsafe_allow_html=True)

    with tab4:
        st.markdown("## 🤖 Commentaire opérationnel — IA")
        st.caption("Génère un commentaire de comité de pilotage basé sur vos KPIs Supply Chain")

        if not api_key:
            st.markdown('<div class="alert-warning">💡 Entrez votre clé API Anthropic dans la sidebar</div>',
                        unsafe_allow_html=True)
        else:
            kpis_dict = {
                "taux_service_global": round(taux_service_global, 1),
                "seuil_service": seuil_service,
                "delai_moyen_jours": round(delai_moyen, 1),
                "taux_retour_pct": round(taux_retour, 1),
                "ratio_cout_ca_pct": round(ratio_cout_ca, 1),
                "regions_sous_seuil": [
                    r for r, row in df_f.groupby("region")["taux_service"].mean().items()
                    if row < seuil_service
                ],
                "meilleure_region": df_f.groupby("region")["taux_service"].mean().idxmax(),
            }

            if st.button("🎙️ Générer le commentaire opérationnel", type="primary", use_container_width=True):
                with st.spinner("Rédaction en cours..."):
                    narrative = generate_narrative("supply_chain", kpis_dict, api_key)
                st.session_state["narrative_sc"] = narrative

            if "narrative_sc" in st.session_state:
                st.markdown(f'<div class="narrative-box">📝 {st.session_state["narrative_sc"]}</div>',
                            unsafe_allow_html=True)
                st.download_button("⬇️ Télécharger le commentaire",
                                   data=st.session_state["narrative_sc"],
                                   file_name="commentaire_supply_chain.txt")

# ─── Footer ───────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    '<div class="footer-caption">Construit avec l\'IA · Gisèle Metouck · '
    '<a href="https://github.com/Kingdmfncr" style="color:#00ff88">GitHub</a></div>',
    unsafe_allow_html=True,
)

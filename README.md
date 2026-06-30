# 📊 Business Performance Dashboard

**Analyse d'écarts budgétaires · KPIs Supply Chain · N vs N-1 · Anomalies Z-score · Simulation what-if · Rapport PDF · Commentaire IA**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://business-performance-dashboard.streamlit.app)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square)](https://python.org)
[![Claude API](https://img.shields.io/badge/Claude-Haiku-00ff88?style=flat-square)](https://anthropic.com)

---

## Ce que ça fait

Un dashboard unifié couvrant deux périmètres métier distincts :

### 💰 Module Controlling & Variance
- Analyse d'écarts budgétaires par département et catégorie
- Waterfall de décomposition des écarts
- Heatmap département × catégorie
- **Simulation what-if** : impact d'une hausse de 8% des coûts logistiques ? → recalcul instantané
- Alertes automatiques sur seuils configurables
- **Détection d'anomalies Z-score** : points statistiquement aberrants flaggés automatiquement (>2σ)
- **Comparaison N vs N-1** : upload deux fichiers, visualisation des deltas sur tous les KPIs
- **Export PDF** : rapport complet (KPIs + alertes + commentaire IA) en un clic
- **Commentaire de gestion IA** : synthèse niveau comité de direction (Claude API)

### 🚚 Module Supply Chain KPIs
- Taux de service, délai moyen, taux de retour, ratio coût/CA par région
- Analyse bubble : volume × performance
- Couverture stock par région
- **Détection d'anomalies Z-score** : régions statistiquement anormales identifiées automatiquement
- **Comparaison N vs N-1** : delta taux de service, coût logistique par région
- **Simulation what-if** : impact d'un retard de 2 jours sur toute la chaîne ?
- **Export PDF** : rapport opérationnel prêt pour comité de pilotage
- **Commentaire opérationnel IA** : synthèse niveau comité de pilotage

---

## Démo immédiate

👉 **[Ouvrir l'app](https://business-performance-dashboard.streamlit.app)**

Données simulées pré-chargées — 6 mois, 4 départements, 5 régions.
Upload de vos propres données (CSV/Excel) disponible sans configuration.

---

## Upload vos données réelles

Le dashboard **détecte automatiquement** le type de fichier uploadé :
- Colonnes `budget`, `realise`, `ecart` → module Controlling
- Colonnes `taux_service`, `commandes_total`, `delai_moyen` → module Supply Chain

**Format CSV attendu :**

| Controlling | Supply Chain |
|-------------|--------------|
| mois, departement, categorie, budget, realise | mois, region, categorie_produit, commandes_total, livraisons_a_temps, taux_service, delai_moyen_jours, cout_logistique, ca_expedie |

---

## Stack technique

| Composant | Technologie |
|-----------|------------|
| Interface | Streamlit |
| Visualisations | Plotly (waterfall, heatmap, bubble, line) |
| Données | Pandas |
| Commentaire IA | Claude Haiku (Anthropic API) — BYOK |
| Export PDF | fpdf2 — rapport prêt pour comité |
| Export CSV | UTF-8 BOM compatible Excel FR |
| Formats upload | CSV (auto-séparateur) + Excel (.xlsx) |
| Détection anomalies | Z-score manuel (scipy-free) |

---

## Méthode IA

Voir [`PROMPT_LOG.md`](PROMPT_LOG.md) — prompts utilisés, décisions d'architecture, limites.

---

## Adapter à votre contexte

- **Controlling** : modifiez les catégories budgétaires dans `data/controlling.csv`
- **Supply Chain** : ajoutez vos régions et catégories produit dans `data/supply_chain.csv`
- **Seuils** : entièrement configurables via les sliders sidebar (aucun code à toucher)
- **Narratif IA** : le prompt est dans `app.py` → `generate_narrative()`, modifiable librement

---

## Freelance

Je livre ce type d'outil adapté à votre périmètre en **2-3 semaines** :
audit budgétaire, tableau de bord Supply Chain, simulation de scénarios.

📩 metouck.gisele@gmail.com

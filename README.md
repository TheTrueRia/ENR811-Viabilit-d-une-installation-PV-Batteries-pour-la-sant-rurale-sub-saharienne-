# Étude de faisabilité technico-économique d’une installation solaire : application a un centre médical rural sub-saharien

Ce projet propose un outil de dimensionnement technico-économique pour des systèmes micro-réseaux hybrides en Afrique subsaharienne. Il automatise la récupération de données géospatiales et calcule la viabilité d'installations photovoltaïques couplées à un stockage Lithium-ion pour des infrastructures de santé.

---

## Fonctionnalités Principales

* **Interfaçage API PVGIS 5.2 :** Récupération dynamique des données d'irradiation mensuelles et annuelles en fonction des coordonnées géographiques (Latitude/Longitude).
* **Calcul de Performance (PR) :** Intégration d'un *Performance Ratio* rigoureux ($\approx 0.68$) incluant les pertes thermiques, de câblage et de conversion.
* **Analyse Économique (LCOE) :** Estimation du coût actualisé de l'énergie sur 25 ans, incluant le CAPEX, l'OPEX et le remplacement du parc de batteries.

## Logique de Dimensionnement

L'algorithme suit une approche de sécurité énergétique basée sur le **mois le plus sombre** pour garantir la continuité des soins :

1.  **Besoin Énergétique :** Correction de la charge nominale par un facteur de sécurité (1.25).
2.  **Puissance PV ($\text{P}_c$) :** Calculée pour satisfaire la charge durant le mois de plus faible irradiation ($I_{\text{min}}$).
    $$P_c = \frac{E_{\text{besoin}}}{PR \times I_{\text{min}}}$$
3.  **Stockage :** Dimensionnement basé sur des modules Lithium (type Pylontech US5000) avec gestion de la profondeur de décharge (DoD).
4.  **Indicateur LCOE :** $$LCOE = \frac{CAPEX + OPEX_{25} + Remplacement}{\sum_{t=1}^{25} E_{produite}(t)}$$

## Structure du Code

Le script est architecturé autour de deux classes principales :
* `Composant` : Définit les caractéristiques techniques et le coût unitaire des modules PV, batteries, onduleurs et régulateurs.
* `ProjetSolaire` : Cœur de l'application gérant les appels API, la matrice des établissements et les calculs de dimensionnement.

### Exemples d'établissements paramétrés
| Type | Surface Type | Description |
| :--- | :--- | :--- |
| **District Hospital** | 1500 m² | Hôpital de district (charge élevée) |
| **Rural Clinic** | 150 m² | Petit dispensaire rural |
| **Test Case** | 1000 m² | Cas d'étude de référence (40 kWh/j) |

## Installation et Utilisation

```bash
# Clonage du dépôt
git clone https://github.com/TheTrueRia/ENR811-Viabilit-d-une-installation-PV-Batteries-pour-la-sant-rurale-sub-saharienne-.git](https://github.com/TheTrueRia/ENR811-Viabilit-d-une-installation-PV-Batteries-pour-la-sant-rurale-sub-saharienne-.git

# Accès au répertoire
cd ENR811-Viabilit-d-une-installation-PV-Batteries-pour-la-sant-rurale-sub-saharienne-

# Installation des dépendances
pip install requests

# Lancement de la simulation
python main.py

```

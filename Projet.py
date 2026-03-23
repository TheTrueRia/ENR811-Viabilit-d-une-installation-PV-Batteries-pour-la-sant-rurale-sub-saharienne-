import math
import requests

class Composant:
    def __init__(self, nom, prix_unitaire, specs):
        self.nom = nom
        self.prix = prix_unitaire
        self.specs = specs

class ProjetSolaire:
    MATRICE_ETABLISSEMENTS = {
        "District Hospital": {"ratio": 138, "surface_type": 1500, "description": "Hôpital de district"},
        "Rural Clinic": {"conso_fixe": 15, "surface_type": 150, "description": "Petit dispensaire rural"},
        "Test Case (Doc)": {"conso_fixe": 40, "surface_type": 1000, "description": "Cas d'étude 40kWh/j"}
    }

    MATRICE_PAYS_BASE = {
        "Afrique du Sud": {"lat": -26.204, "lon": 28.047, "soiling": 0.05, "t_air": 18.5},
        "Sénégal":         {"lat": 14.497,  "lon": -14.452, "soiling": 0.15, "t_air": 28.0},
        "Mali":            {"lat": 17.570,  "lon": -3.996,  "soiling": 0.30, "t_air": 29.5},
        "Kenya":           {"lat": -0.023,  "lon": 37.906,  "soiling": 0.07, "t_air": 22.0},
        "RDC (Congo)":     {"lat": -4.038,  "lon": 21.758,  "soiling": 0.03, "t_air": 25.0}
    }

    def __init__(self, pays, type_etab):
        self.pays_nom = pays
        self.config_pays = self.MATRICE_PAYS_BASE[pays]
        self.lat, self.lon = self.config_pays['lat'], self.config_pays['lon']
        self.etab = self.MATRICE_ETABLISSEMENTS[type_etab]
        
        # Récupération sécurisée via API
        self.pvgis = self._fetch_pvgis_data()
        
        # --- PERFORMANCE RATIO (PR) : CALCUL DU DOCUMENT ---
        # (1-0.15) * 0.98 * 0.90 * 0.95 * 0.98 = ~0.68
        self.rp = (1 - 0.15) * 0.98 * 0.90 * 0.95 * 0.98 

    def _fetch_pvgis_data(self):
        url_pv = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"
        params_pv = {
            'lat': self.lat, 'lon': self.lon, 
            'peakpower': 1, 'loss': 13.63, 
            'slope': 20, 'azimuth': 0,
            'outputformat': 'json'
        }

        jours_par_mois = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        noms_mois = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", 
                     "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]

        try:
            res_pv = requests.get(url_pv, params=params_pv, timeout=10).json()
            
            # Extraction des données mensuelles et annuelles
            monthly_raw = res_pv['outputs']['monthly']['fixed']
            totals = res_pv.get('outputs', {}).get('totals', {}).get('fixed', {})
            irr_annuelle_plan = totals.get('H(i)_y', 1623.34)
            
            # Calcul précis par jour réel
            irr_journalieres = []
            for i, m in enumerate(monthly_raw):
                # H(i)_m est l'irradiation totale mensuelle (kWh/m2/mois)
                irr_journalieres.append(m['H(i)_m'] / jours_par_mois[i])

            val_min = min(irr_journalieres)
            mois_sombre = noms_mois[irr_journalieres.index(val_min)]
            irr_moy_annuelle = sum(irr_journalieres) / 12

            return {
                'angle': 20.0,
                'azimut': 0.0,
                'perte_sys_pvgis': 13.63,
                'irr_min': round(val_min, 3),
                'liste_mensuelle': irr_journalieres, # Utile pour tracer la courbe de balance
                'mois_sombre': mois_sombre,
                'irr_moy': round(irr_moy_annuelle, 3),
                'irr_annuelle_plan': round(irr_annuelle_plan, 2),
                'statut': "CONNECTÉ (API PVGIS v5.2)"
            }

        except Exception as e:
            # Mode secours avec les valeurs du rapport
            return {
                'angle': 20.0, 'azimut': 0.0, 'perte_sys_pvgis': 13.63, 
                'irr_min': 5.18, 'mois_sombre': "Juin", 
                'irr_moy': 5.5, 'irr_annuelle_plan': 1623.34, 
                'statut': "MODE SECOURS (VALEURS RAPPORT)"
            }
        
    def dimensionner_et_imprimer(self, panel, battery, inverter, regulator):
        # 1. BESOINS
        conso_wh = 40 * 1000
        e_besoin_corrige = conso_wh * 1.25
        
        # 2. DIMENSIONNEMENT PV (SÉCURITÉ HIVER)
        pc_req = e_besoin_corrige / (self.rp * self.pvgis['irr_min'])
        nb_panneaux = math.ceil((pc_req / panel.specs['Pmax']) / 3) * 3
        pc_inst = nb_panneaux * panel.specs['Pmax']
        
        # 3. PRODUCTION ANNUELLE 
        # Prod = P_inst * Irradiation_Annuelle_Plan * PR
        prod_annuelle_estimee = pc_inst * (self.pvgis['irr_annuelle_plan'] / 1000) * self.rp
        
        # 4. ÉCONOMIE (LCOE 25 ANS)
        capex = ((nb_panneaux * panel.prix) + (16 * battery.prix) + inverter.prix + (3 * regulator.prix)) * 1.15
        opex_25ans = (capex * 0.015) * 25
        rempl_bat = (16 * battery.prix) * 0.8
        
        prod_an1 = pc_inst * self.pvgis['irr_moy'] * self.rp * 365 / 1000
        total_kwh_25ans = sum([prod_an1 * (0.996**i) for i in range(25)])
        lcoe = (capex + opex_25ans + rempl_bat) / total_kwh_25ans

        # --- PRINT FINAL HARMONISÉ AVEC LE DOCUMENT ---
        print("\n" + "═"*75)
        print(f" ÉTUDE DE FAISABILITÉ : {self.etab['description'].upper()}")
        print(f" Lieu : {self.pays_nom} | Statut : {self.pvgis['statut']}")
        print("═"*75)
        
        print(f"\n[1] PARAMÈTRES PVGIS")
        print(f"  • Irradiation annuelle (Plan) : {round(self.pvgis['irr_annuelle_plan'], 2)} kWh/m²")
        print(f"  • Irradiation Min ({self.pvgis['mois_sombre']}) : {round(self.pvgis['irr_min'], 2)} kWh/m²/j")
        
        print(f"\n[2] PERFORMANCE ET BILAN ÉNERGÉTIQUE")
        print(f"  • Consommation journalière    : {round(conso_wh/1000, 1)} kWh/j")
        print(f"  • Performance Ratio (PR)      : {round(self.rp, 3)}")
        print(f"  • Production annuelle estimée : {round(prod_annuelle_estimee, 2)} kWh/an")
        
        print(f"\n[3] DIMENSIONNEMENT DU SYSTÈME")
        print(f"  • Puissance PV recommandée    : {round(pc_inst/1000, 2)} kWp")
        print(f"  • Nombre de modules (495Wc)   : {nb_panneaux} unités")
        print(f"  • Capacité de stockage (kWh)  : 76.8 kWh (16 x US5000)")
        print(f"  • Tension du système (DC)     : 96 V")
        
        print(f"\n[4] ANALYSE ÉCONOMIQUE (LCOE - BASE 25 ANS)")
        print(f"  • Coût d'investissement (CAPEX): {round(capex, 0):,} $")
        print(f"  • Coût d'exploitation (OPEX)   : {round(opex_25ans/25, 0):,} $/an")
        print(f"  • Coût actualisé (LCOE)        : {round(lcoe, 3)} $/kWh")
        print("═"*75)

# EXECUTION
pv = Composant("HiMAX 495Wc", 175, {'Pmax': 495})
bat = Composant("US5000", 1850, {'kWh': 4.8, 'DOD': 0.8, 'Rb': 0.9})
inv = Composant("Quattro 8kVA", 3800, {'Pnom': 8000}) 
reg = Composant("MPPT 250/60", 850, {}) 

ProjetSolaire("Afrique du Sud", "Test Case (Doc)").dimensionner_et_imprimer(pv, bat, inv, reg)
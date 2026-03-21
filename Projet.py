import math
import requests

class Composant:
    def __init__(self, nom, prix_unitaire, specs):
        self.nom = nom
        self.prix = prix_unitaire
        self.specs = specs

class ProjetSolaireExpert:
    # Matrice des établissements avec ratios (kWh/m2/an) et surfaces types (m2)
    MATRICE_ETABLISSEMENTS = {
        "District Hospital": {"ratio": 138, "surface_type": 1500, "description": "Hôpital de district"},
        "National Central": {"ratio": 371, "surface_type": 5000, "description": "Hôpital central national"},
        "Provincial Tertiary": {"ratio": 470, "surface_type": 3000, "description": "Hôpital tertiaire provincial"},
        "Regional Hospital": {"ratio": 71, "surface_type": 2500, "description": "Hôpital régional"},
        "Rural Clinic": {"conso_fixe": 15, "surface_type": 150, "description": "Petit dispensaire rural"},
        
        "Test Case (Doc)": {"conso_fixe": 40, "surface_type": 1000, "description": "Cas d'étude 40kWh/j"}
    }

    # Données pays : Coordonnées, Soiling (poussière) et Température moyenne
    MATRICE_PAYS_BASE = {
        "Afrique du Sud": {"lat": -30.559, "lon": 22.938, "soiling": 0.05, "t_air": 18.5},
        "Sénégal":        {"lat": 14.497,  "lon": -14.452, "soiling": 0.15, "t_air": 28.0},
        "Mali":           {"lat": 17.570,  "lon": -3.996,  "soiling": 0.30, "t_air": 29.5},
        "Kenya":          {"lat": -0.023,  "lon": 37.906,  "soiling": 0.07, "t_air": 22.0},
        "RDC (Congo)":    {"lat": -4.038,  "lon": 21.758,  "soiling": 0.03, "t_air": 25.0}
    }

    def __init__(self, pays, type_etab, surface_perso=None):
        self.pays_nom = pays
        self.config_pays = self.MATRICE_PAYS_BASE[pays]
        self.etab = self.MATRICE_ETABLISSEMENTS[type_etab]
        self.surface = surface_perso if surface_perso else self.etab["surface_type"]
        
        # --- CALCUL DES PERTES THERMIQUES ---
        noct = 45 
        gamma = -0.0030 # Coefficient de température du HiMAX 5N
        # T_cellule = T_air + 25°C (échauffement standard sous 800W/m2)
        t_cell = self.config_pays["t_air"] + 25 
        self.perte_temp = max(0, (t_cell - 25) * abs(gamma))
        
        # --- SITE FACTOR & PERFORMANCE RATIO (Rp) ---
        # Rp global = Pertes env * Rendements techniques 
        self.f_soiling = (1 - self.config_pays["soiling"])
        self.f_temp = (1 - self.perte_temp)
        self.site_factor = self.f_soiling * self.f_temp
        self.rendement_tech = 0.82 # (Régulateur x Batterie x Câbles)
        self.rp = self.site_factor * self.rendement_tech # Cible ~0.68 
        
        self.irr_min,  self.irr_moy = self._fetch_pvgis_data()

    #Va chercher les info de pvgis pour l'irradiation solaire
    def _fetch_pvgis_data(self):
        """Extraction des données d'irradiation PVGIS"""
        url = "https://re.jrc.ec.europa.eu/api/v5_2/MRcalc"
        params = {'lat': self.config_pays['lat'], 'lon': self.config_pays['lon'], 'horirrad': 1, 'outputformat': 'json'}
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            mensuel = [m['H(h)_m'] / 30.41 for m in data['outputs']['monthly']]
            return min(mensuel), sum(mensuel)/len(mensuel)
        except: return 5.18, 5.50 # Valeurs de secours

    def dimensionner_et_imprimer(self, panel, battery, inverter, regulator):
        # 1. BESOINS ÉNERGÉTIQUES
        if "ratio" in self.etab:
            conso_base = (self.etab["ratio"] * self.surface / 365) * 1000
        else:
            conso_base = self.etab["conso_fixe"] * 1000
        e_besoin_pv = conso_base * 1.25 # Coefficient sécurité Module 4 
        
        # 2. DIMENSIONNEMENT CHAMP PV
        pc_min = e_besoin_pv / (self.rp * self.irr_min)
        nps = 3 # 3 panneaux en série pour système 96V
        nb_panneaux = math.ceil((pc_min / panel.specs['Pmax']) / nps) * nps
        pc_installee = nb_panneaux * panel.specs['Pmax']
        
        # 3. STOCKAGE BATTERIE 
        e_nuit = conso_base * 0.6 # 60% de consommation nocturne 
        us = 96 if pc_installee > 10000 else 48 # Tension selon puissance 
        # Cp = (Ejnuit * Nj) / (Us * DOD * Rb) 
        cp_ah = (e_nuit * 2) / (us * battery.specs['DOD'] * battery.specs['Rb'])
        e_stockage_kwh = (cp_ah * us * 1.15) / 1000 # Marge 15% incluse
        nb_bat = math.ceil(e_stockage_kwh / battery.specs['kWh'])
        
        # 4. RÉGULATEUR MPPT
        # Puissance reg requise >= 1.25 * Pmax_total 
        p_reg_requis = pc_installee * 1.25
        nb_reg = math.ceil(pc_installee / 5000) # Configuration modulaire (1 reg / ~5kWc) 
        
        # 5. ONDULEUR 
        # P_ond = (1.25 * Ppt) / Rendement
        # Estimation Ppt = 30% de la puissance PV installée (charges simultanées)
        p_pointe_estimee = pc_installee * 0.3
        p_ond_requise = (p_pointe_estimee * 1.25) / 0.95
        
        # 6. ANALYSE FINANCIÈRE
        cout_pv = nb_panneaux * panel.prix
        cout_bat = nb_bat * battery.prix
        cout_inv = inverter.prix if inverter.specs['Pnom'] >= p_ond_requise else inverter.prix * 2
        cout_reg = nb_reg * regulator.prix
        
        capex_materiel = cout_pv + cout_bat + cout_inv + cout_reg
        installation_bos = capex_materiel * 0.15 # 15% structure/câblage 
        capex_total = capex_materiel + installation_bos
        
        # Maintenance (Nettoyage indexé sur soiling + entretien 1.5%) 
        nb_nettoyages = math.ceil(self.config_pays['soiling'] * 40)
        opex_an = (nb_panneaux * nb_nettoyages * 0.8) + (capex_total * 0.015)

        # 6. CALCUL DU LCOE SUR 10 ANS
        duree_vie = 10
        degradation_annuelle = 0.004 # 0.40%/an 
        prod_an_1 = pc_installee * self.irr_moy * self.rp * 365 / 1000 # kWh/an
        
        total_kwh_10ans = 0
        for annee in range(duree_vie):
            total_kwh_10ans += prod_an_1 * ((1 - degradation_annuelle) ** annee)
        
        total_couts_10ans = capex_total + (opex_an * duree_vie)
        lcoe = total_couts_10ans / total_kwh_10ans

# --- PRINT  ---
        print("\n" + "="*70)
        print(f"RAPPORT TECHNIQUE : {self.etab['description'].upper()}")
        print(f"Lieu : {self.pays_nom} ({self.config_pays['lat']}, {self.config_pays['lon']})")
        print("="*70)
        
        print(f"\n[1] DONNÉES D'ENTRÉE ET HYPOTHÈSES")
        print(f"  - Surface calculée          : {self.surface} m2")
        print(f"  - Température Air Moyenne   : {self.config_pays['t_air']} °C")
        print(f"  - Irradiation Min (PVGIS)   : {round(self.irr_min, 2)} kWh/m2/j")
        print(f"  - Irradiation Moy. Annuelle : {round(self.irr_moy, 2)} kWh/m2/j") 
        print(f"  - Coefficient de sécurité   : 1.25") 
        
        print(f"\n[2] BILAN ÉNERGÉTIQUE")
        print(f"  - Consommation brute        : {round(conso_base/1000, 2)} kWh/j")
        print(f"  - Besoin Corrigé (x1.25)    : {round(e_besoin_pv/1000, 2)} kWh/j")
        print(f"  - Part de conso nocturne    : {round(e_nuit/1000, 2)} kWh/j (60%)")
        
        print(f"\n[3] ANALYSE DES PERTES ET PERFORMANCE")
        print(f"  - Pertes Salissure (Soiling): {self.config_pays['soiling']*100} %")
        print(f"  - Pertes Chaleur (Cellule)  : {round(self.perte_temp*100, 2)} %")
        print(f"  - Site Factor               : {round(self.site_factor, 3)}")
        print(f"  - Performance Ratio (Rp)    : {round(self.rp, 3)}")
        
        print(f"\n[4] DIMENSIONNEMENT DU MATÉRIEL")
        print(f"  - Puissance PV Installée    : {round(pc_installee/1000, 2)} kWc")
        print(f"  - Panneaux ({panel.nom}) : {nb_panneaux} modules")
        print(f"  - Configuration électrique  : {nb_panneaux // nps} strings de {nps} panneaux")
        print(f"  - Capacité Batteries        : {round(nb_bat * battery.specs['kWh'], 1)} kWh")
        print(f"  - Nombre de batteries       : {nb_bat} modules {battery.nom}")
        print(f"  - Régulation (MPPT)         : {nb_reg} unité(s) modulaire(s)")
        print(f"  - Onduleur (Quattro)        : Pnom requis > {round(p_ond_requise, 0)} W")
        print(f"  - Tension du système        : {us} V")
        
        print(f"\n[5] ANALYSE FINANCIÈRE")
        print(f"  - INVESTISSEMENT (CAPEX)    : {round(capex_total, 0):,} $")
        print(f"    > Matériel principal      : {round(capex_materiel, 0):,} $")
        print(f"    > Installation (BOS/15%)  : {round(installation_bos, 0):,} $")
        print(f"  - FONCTIONNEMENT (OPEX/an)  : {round(opex_an, 0):,} $")
        print(f"    > Nettoyage ({nb_nettoyages} passages/an) : {round(nb_panneaux*nb_nettoyages*0.8, 0)} $")
        print(f"    > Entretien technique     : {round(capex_total*0.015, 0)} $")
        print(f"  - PRODUCTION TOTALE (10 ans): {round(total_kwh_10ans/1000, 0):,} MWh")
        print(f"  - LCOE (Coût du kWh)        : {round(lcoe, 3)} $/kWh")
        print("="*70)


#########################################################
#################         MAIN          #################
#########################################################

# --- CONFIGURATION ---
pv = Composant("HiMAX 5N 495Wc", 175, {'Pmax': 495})
bat = Composant("Pylontech US5000", 1850, {'kWh': 4.8, 'DOD': 0.8, 'Rb': 0.9})
inv = Composant("Victron Quattro 8kVA", 3800, {'Pnom': 8000}) 
reg = Composant("SmartSolar 250/60", 850, {}) 

# --- LANCEMENT ---
ProjetSolaireExpert("Mali", "Test Case (Doc)").dimensionner_et_imprimer(pv, bat, inv, reg)
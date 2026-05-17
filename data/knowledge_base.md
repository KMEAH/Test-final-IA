# Base de Connaissance RH & IT - Gvivva Corp

## [Component: Support_IT]

### [ID: module_it_connexion]
**Action:** Resoudre_Probleme_Connexion
**Logic:** Si l'utilisateur ne peut pas se connecter, suivre la procedure : 1) Verifier identifiants (login/mot de passe), 2) Reinitialiser le mot de passe via le portail SSO, 3) Contacter le support IT si le probleme persiste apres 3 tentatives. Delai de resolution : 2h ouvrables.
**Data_Connections:** svc:portail_sso, svc:active_directory, db:users_credentials
**Access:** Role_IT_Support, Role_Employee
**Events:** Login_Failed, Password_Reset_Requested, Account_Locked

### [ID: module_it_acces_vpn]
**Action:** Configurer_Acces_VPN
**Logic:** L'acces VPN necessite une autorisation du manager. Fournir l'adresse IP du serveur VPN et les identifiants fournis par le departement IT. Protocole utilise : OpenVPN.
**Data_Connections:** svc:vpn_server, db:vpn_authorizations
**Access:** Role_IT_Admin, Role_Manager
**Events:** VPN_Access_Granted, VPN_Connection_Established

---

## [Component: RH_Remboursements]

### [ID: module_rh_remboursement]
**Action:** Traiter_Demande_Remboursement
**Logic:** Pour soumettre une demande de remboursement : 1) Remplir le formulaire NDF (Note de Frais) sur le portail RH, 2) Joindre les justificatifs originaux (factures/tickets), 3) Faire valider par le manager direct, 4) Soumettre avant le 25 du mois pour remboursement le mois suivant. Plafond voyage : 500 EUR/mois. Plafond repas : 20 EUR/repas.
**Data_Connections:** svc:portail_rh, db:ndf_database, svc:systeme_paie
**Access:** Role_Employee, Role_Manager, Role_RH_Admin
**Events:** NDF_Soumise, NDF_Validee, Remboursement_Effectue, NDF_Rejetee

### [ID: module_rh_remboursement_formation]
**Action:** Remboursement_Frais_Formation
**Logic:** Les frais de formation professionnelle sont remboursables a 100% sur justificatif si la formation est prealablement approuvee par le responsable RH. Delai de traitement : 30 jours. Budget annuel par employe : 2000 EUR.
**Data_Connections:** svc:portail_rh, db:budget_formation, svc:opco_connector
**Access:** Role_Employee, Role_RH_Admin
**Events:** Formation_Approuvee, Remboursement_Formation_Effectue

---

## [Component: RH_Conges]

### [ID: module_rh_conges]
**Action:** Gerer_Demande_Conge
**Logic:** Les conges doivent etre soumis 15 jours a l'avance via le portail RH. Le manager a 5 jours ouvrables pour approuver ou refuser. Solde annuel : 25 jours ouvrables. Conges reportables : max 5 jours sur l'annee suivante.
**Data_Connections:** svc:portail_rh, db:conges_database, svc:calendrier_equipe
**Access:** Role_Employee, Role_Manager
**Events:** Conge_Demande, Conge_Approuve, Conge_Refuse

---

## [Component: Securite_Acces]

### [ID: module_securite_droits]
**Action:** Gerer_Droits_Acces_Applicatif
**Logic:** Toute demande d'acces a une nouvelle application doit passer par une validation en 2 etapes : 1) Approbation du manager direct, 2) Validation de la DSI. Delai : 3 jours ouvrables. Les acces sont revus trimestriellement.
**Data_Connections:** svc:iam_system, db:access_rights, svc:active_directory
**Access:** Role_IT_Admin, Role_Manager, Role_CISO
**Events:** Access_Requested, Access_Granted, Access_Revoked, Quarterly_Review

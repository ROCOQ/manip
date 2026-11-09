# GeForce NOW sur iPad : fluidité et dépannage

Le cloud gaming dépend à 90 % du **réseau**, pas de l'iPad. Un iPad Pro 2018
(A12X) décode sans problème un flux 1080p/60.

## Réglages recommandés (offre gratuite)

| Réglage GFN | Valeur |
|---|---|
| Qualité du flux | Personnalisée : 1080p, 60 i/s |
| Débit max | auto ; si ça saccade, baissez à 15-20 Mb/s |
| Ajuster selon le réseau | activé |
| Serveur | automatique (sinon le plus proche : Paris / Francfort / Amsterdam…) |

Dans le jeu lui-même, la qualité graphique ne change **pas** la latence : elle
est calculée sur le serveur. Visez un jeu stable à 60 i/s plutôt que des effets
au maximum.

## Réseau, du plus au moins efficace

1. **Câble** : adaptateur USB-C → Ethernet (≈ 15 €, ou un hub USB-C avec port
   RJ45 et recharge). C'est la vraie solution anti-saccades.
2. **Wi-Fi 5 GHz** (ou 6 GHz) dans la même pièce que la box. Évitez le 2,4 GHz
   et les répéteurs/CPL.
3. Personne d'autre ne télécharge ou ne regarde de vidéo 4K pendant la partie.
4. Box : si possible, activez la QoS / priorité « jeu » pour l'iPad.
5. En 4G/5G : jouable en 5G avec bon signal, mais attention au forfait (≈ 5-10 Go/h).

## Pannes fréquentes

| Symptôme | Causes probables → solution |
|---|---|
| Image floue / pixellisée par moments | Débit instable → Ethernet ou 5 GHz, baisser le débit max. |
| Latence (input lag) | Wi-Fi 2,4 GHz, VPN, serveur éloigné → corriger le réseau, désactiver le VPN, manette Bluetooth plutôt que tactile. |
| « Votre réseau ne convient pas » | Lancez le test réseau GFN ; redémarrez box et iPad ; désactivez « Relais privé iCloud » et « Limiter le suivi d'adresse IP » pour ce réseau Wi-Fi. |
| Manette non détectée | Appairez-la dans Réglages → Bluetooth **avant** d'ouvrir GFN ; lancez GFN depuis l'icône d'écran d'accueil ; touchez un bouton une fois la page chargée. |
| Session coupée au bout d'1 h | Normal en offre gratuite. Sauvegardez avant, relancez. |
| Longue file d'attente | Heures creuses ; Safari au premier plan ; écran qui ne se verrouille pas (Réglages → Luminosité → Verrouillage auto : Jamais, pendant l'attente). |
| Jeu « non disponible » alors qu'il est dans la liste | Vérifiez la **boutique** sélectionnée (Steam et non Epic) sur la page du jeu GFN ; certains jeux sont temporairement en maintenance. |
| Steam redemande les identifiants à chaque fois | Cochez « Se souvenir de moi » ; validez Steam Guard ; liez le compte dans Paramètres → Connexions. |
| Sauvegarde perdue | Le jeu ne gère pas Steam Cloud → privilégiez d'autres jeux en offre gratuite. |
| iPad qui chauffe / baisse de luminosité | Retirez la coque, baissez la luminosité, évitez la charge rapide pendant le jeu. |

## Clavier et souris

Dans Safari sur iPad, la souris et le clavier fonctionnent mal pour les jeux
qui capturent le pointeur (FPS). Préférez les jeux jouables **à la manette**
(sur la page du jeu dans GFN : mention « Support manette »).

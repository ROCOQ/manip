# Installation sur iPad

## 0. Vérifier la compatibilité

| Critère | Minimum conseillé | Idéal |
|---|---|---|
| Puce | A12Z / A14 | M1, M2, M4 (iPad Pro / Air) |
| RAM | 6 Go | 8 Go ou plus |
| iPadOS | 15 (MuffinEMU), 17 (Fin) | dernière version stable |
| Stockage libre | 30 Go | 100 Go+ (un jeu Wii U pèse souvent 2 à 15 Go) |

Pour voir votre modèle : **Réglages → Général → Informations → Nom du modèle**.

Les jeux Wii U sont lourds. Sous 6 Go de RAM, attendez-vous à des crashs dans
beaucoup de jeux.

---

## Option A — Fin (App Store) : le plus simple

1. Ouvrez l'App Store et installez **Fin** :
   https://apps.apple.com/us/app/fin-game-emulator/id6758910777 (iOS 17+).
2. Lancez l'app et autorisez l'accès aux fichiers.
3. Importez vos jeux depuis l'app **Fichiers** (voir [DUMP_JEUX.md](DUMP_JEUX.md)).
4. Connectez une manette (voir « Manettes » plus bas).

Les apps de l'App Store n'ont pas le droit d'utiliser le JIT. Les performances
peuvent donc être plus basses que celles d'un émulateur sideloadé.

---

## Option B — MeloCafe (Cemu, sideload) : le plus performant

### B1. Installer un outil de sideload
- **SideStore** (recommandé, pas besoin d'un PC une fois installé) ou **AltStore**.
- Il faut un **Apple ID** (un compte gratuit suffit, mais l'app expire au bout
  de 7 jours et il faut la rafraîchir). Avec un compte développeur payant, ça
  tient 1 an et vous avez plus d'entitlements.
- Activez le **Mode développeur** : Réglages → Confidentialité et sécurité → Mode développeur.

### B2. Installer MeloCafe
1. Récupérez l'IPA **uniquement depuis la source officielle du développeur**
   (celui de MeloNX). Méfiez-vous des sites qui proposent des « versions
   modifiées ».
2. Installez l'IPA avec SideStore ou AltStore.
3. L'entitlement **Increased Memory Limit** est indispensable. Il est accordé
   automatiquement avec un compte développeur payant. Avec un compte gratuit,
   ça dépend de l'outil de sideload : consultez la doc de SideStore.

### B3. Activer le JIT
Les émulateurs Cemu ont besoin du **JIT** pour tourner correctement. Sur iPadOS 17+ :
- installez **StikDebug** (ex-StikJIT) ou utilisez la fonction JIT de SideStore ;
- ouvrez MeloCafe **via** l'outil JIT, à chaque lancement.

Si l'app plante tout de suite ou se lance avec quelques images par seconde, il y a
de grandes chances que le JIT ne soit pas activé.

---

## Option C — MuffinEMU (Cemu, open source)

- Site : https://muffinemu.github.io/MuffinEMU/
- iOS 15+, installation via SideStore / AltStore / **TrollStore**.
- Avec TrollStore (seulement certaines versions d'iPadOS), l'app est installée
  de façon permanente et les entitlements sont plus simples à obtenir.
- Le JIT s'active comme pour MeloCafe.

---

## Fichiers nécessaires (émulateurs basés sur Cemu)

- **`keys.txt`** : les clés de déchiffrement de *vos* jeux (une clé hexadécimale
  de 32 caractères par ligne). Inutile pour les jeux au format `.wua` ou déjà
  déchiffrés (dossiers `code/content/meta`).
- **Online files** (`otp.bin`, `seeprom.bin`) : seulement pour jouer en ligne,
  extraits de votre console avec Dumpling. Facultatif.
- **Graphic packs** de Cemu : ils sont souvent compatibles avec les ports et
  peuvent corriger des bugs ou améliorer les performances (en baissant la
  résolution, par exemple).

## Manettes

Toute manette compatible avec iPadOS fonctionne : Xbox, PlayStation DualSense/DualShock,
Switch Pro et MFi.
Réglages → Bluetooth → maintenez le bouton d'appairage de la manette.

Le **GamePad Wii U** (deuxième écran tactile) est émulé sur l'écran de l'iPad.
Certains jeux qui en dépendent beaucoup (*Nintendo Land*, *Star Fox Zero*…) sont
pénibles à jouer sur un seul écran.

## Réglages de performance conseillés

- **Résolution** : 1x (native, 720p) pour commencer.
- **Async shader compilation** : activée, ce qui réduit les saccades.
- Pensez à **brancher l'iPad** et à couper le mode économie d'énergie.
- Laissez le cache des shaders se remplir : la première partie saccade toujours.

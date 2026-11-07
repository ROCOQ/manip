# Récupérer (dumper) vos propres jeux Wii U

Seuls des jeux que vous possédez et que vous avez dumpés depuis **votre** console
sont légitimes.

## Outils (sur la Wii U, avec le homebrew Aroma)
1. Installez l'environnement homebrew **Aroma** sur votre Wii U.
2. Lancez **Dumpling** :
   - jeux disque ou eShop → dossier `code/ content/ meta/` (déjà déchiffré) ;
   - « Online files » → `otp.bin`, `seeprom.bin` (facultatif).
3. Copiez le résultat de la carte SD ou de la clé USB vers votre ordinateur.

## Formats pris en charge par les ports de Cemu

| Format | Description | Clés nécessaires ? |
|---|---|---|
| `.wua` | Archive Cemu (jeu + mises à jour + DLC). **Le plus pratique** | Non |
| dossier `code/content/meta` | Dump Dumpling déchiffré | Non |
| `.wud` | Image disque brute | Oui (`keys.txt`) |
| `.wux` | Image disque compressée | Oui (`keys.txt`) |
| `.rpx` | Exécutable seul (dans `code/`) | Non |

**Conseil** : convertissez vos dumps en `.wua` avec Cemu sur PC
(*Tools → Title Manager → Convert to compressed Wii U archive*). Vous obtenez un
seul fichier, plus petit, qui contient les mises à jour et les DLC. C'est
idéal pour l'iPad.

## Transférer sur l'iPad
- **Câble USB-C** + Finder (Mac) ou iTunes / Appareils Apple (Windows) → onglet Fichiers.
- **Clé USB / SSD** branché directement sur l'iPad → app Fichiers → copier.
- **AirDrop** (Mac), seulement pour les fichiers de quelques Go.

Avant le transfert, vérifiez vos fichiers avec :
```bash
python3 tools/check_wiiu_files.py /chemin/vers/jeux --keys keys.txt
```

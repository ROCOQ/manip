# Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| L'app se ferme dès le lancement | JIT non activé | Lancez l'émulateur via StikDebug / SideStore JIT |
| L'app « n'est plus disponible » | Certificat de 7 jours expiré (compte gratuit) | Rafraîchissez l'app dans SideStore / AltStore |
| Crash en plein jeu | Manque de RAM / entitlement mémoire absent | Vérifiez l'entitlement *Increased Memory Limit*, fermez les autres apps, baissez la résolution |
| Jeu absent de la liste | Mauvais format ou dossier | `python3 tools/check_wiiu_files.py <dossier>` |
| « Missing key » / écran noir avec un .wud/.wux | Clé absente de `keys.txt` | Ajoutez la clé de votre disque, ou convertissez en `.wua` |
| Saccades au début | Compilation des shaders | C'est normal la première fois. Activez *async shaders* |
| Jeu très lent | Pas de JIT, ou iPad trop faible | Activez le JIT, passez à la résolution 1x, utilisez des graphic packs |
| Manette non détectée | Pas appairée ou mappage absent | Réappairez-la et configurez-la dans les réglages d'entrée de l'émulateur |
| Le GamePad gêne l'affichage | Jeu à double écran | Réglez la disposition des écrans, ou changez d'écran avec un bouton dédié |

Toujours bloqué ? Lancez Claude Code dans ce dépôt et demandez :
*« Utilise l'agent wiiu-troubleshooter : <description du problème> »*.

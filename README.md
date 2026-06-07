# Cahier-de-prepa-downloader (CDPD)
Un utilitaire afin d'automatiser le téléchargement de l'ensemble des fichiers du site cahier-de-prepa.fr, avec une intégration des identifiants.
Le projet reste libre à la modification et à l'amélioration, tout n'est pas parfait (notamment sur la gestion de l'identifiant et des mots de passes qui restent très amateur).
Libre à chacun de modifier le code à sa guise en fonction de ses besoins, il est perfectible et il en a besoin.
Merci beaucoup à *[Azuxul](https://github.com/Azuxul/cahier-de-prepa-downloader)* d'avoir conçu en premier un projet de ce type, je m'en suis bien inspiré.
Je me suis par ailleurs aidé de l'IA puisque je n'ai que des conaissances amateur en programmation (uniquement à but scientifique).

***Avis de non responsabilité : Cet utilitaire n'a pas pour but de violer les propriétés intellectuelles, mais simplement de pouvoir fournir un utilitaire fiable et efficace à l'ensemble des étudiants utilisants CDP afin de télécharger les fichiers déposés par les professeurs. Ce projet respecte les conditions d'utilisation du site Cahier-de-Prépa. Il ne contourne pas les protections des fichiers non autorisés et suppose que l'utilisateur dispose des droits d'accès nécessaires.***

## Installation
Installer python [Python3](https://www.python.org/downloads/) 
Installer ensuite (si besoin, mais fortement recommandé) la bibliothèque requests et beautifulsoup4 (via le CMD)  :
```
pip install requests
pip install beautifulsoup4
```

## Utilisation 
Ouvrir le fichier _cdpDumpingUtils.cfg_ et rentrer l'identifiant et le mot de passe de votre compte Cahier-De-Prepa , dans le cas échéant laisser ces deux derniers __vides__.
Rentrer également l'URL principale de votre Cahier-De-Prépa (le miens étant TSI1 Benjam)

Lancer le script (en l'ouvrant depuis le dossier) avec :
```
python main.py
```
Ou en ouvrant le fichier Start.bat

Maintenant plus qu'à suivre les instructions ! 
Le mode verbeux (verbose) permet de voir dans la console les opérations qui s'effectuent.

Les fichiers sont classés automatiquement selon l’arborescence du site (par répertoire). Chaque fichier est sauvegardé avec :
Son nom d’origine (nettoyé si nécessaire)
La bonne extension (basée sur le ```Content-Type``` lors du téléchargement)
Par exemple : 
```
Maths
  └── DM n°4 - Suites.pdf
Physique
  └── TD_Optique.docx
```

Distribué sous Licence MIT. Vous pouvez utiliser, modifier et redistribuer ce script librement, dans le respect de ses termes.

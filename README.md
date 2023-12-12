# Script de création de BDD ProgrammeTV

BDD : MariaDB (MySQL)

- URL de la BDD : nono0302.hopto.me
- Port : 3306
- Utilisateur : public
- Mot de passe : MW24WgrDB
- Database : ProgrammeTV

mysql -h nono0302.hopto.me -P 3306 -u public -pMW24WgrDB ProgrammeTV

## Si vous voulez créer votre propre BDD

- Utilisez Python 3.10.5 (recommandé)
- Installez MariaDB

Pour se connecter à votre base de donnée :

### config.ini
```
[mysql]
host = localhost
user = {votre_user}
password = {votre_mdp}

[fournisseurs]
NumTNT = https://www.programme-tv.net/programme/programme-tnt.html
NumOrange = https://www.programme-tv.net/programme/orange-12/
NumSFR = https://www.programme-tv.net/programme/sfr-25/
NumFree = https://www.programme-tv.net/programme/free-13/
NumBouygues = https://www.programme-tv.net/programme/bouygues-24/
NumCanal = https://www.programme-tv.net/programme/canal-5/
```

**La BDD est insensible à la casse**

## Table 'Chaines'
| Colonne               | Type                  | Description                            |
|-----------------------|-----------------------|----------------------------------------|
| `idChaine`            | INT AUTO_INCREMENT    | Clé primaire, identifiant unique       |
| `nomChaine`           | TEXT                  | Nom de la chaîne                       |
| `numTNT`              | INT                   | Numéro de la chaîne sur TNT            |
| `numOrange`           | INT                   | Numéro de la chaîne chez Orange        |
| `numSFR`              | INT                   | Numéro de la chaîne chez SFR           |
| `numFree`             | INT                   | Numéro de la chaîne chez Free          |
| `numBouygues`         | INT                   | Numéro de la chaîne chez Bouygues      |
| `numCanal`            | INT                   | Numéro de la chaîne chez Canal         |
| `urlChaine`           | TEXT                  | URL de la chaîne                       |
| `urlLogo`             | TEXT                  | URL du logo de la chaîne               |

## Table 'Programmation'
| Colonne               | Type                  | Description                            |
|-----------------------|-----------------------|----------------------------------------|
| `idProgrammation`     | INT AUTO_INCREMENT    | Clé primaire, identifiant unique       |
| `idChaine`            | INT                   | Clé étrangère vers la table Chaines    |
| `dateEmission`        | DATE                  | Date de l'émission                     |
| `heureEmission`       | TIME                  | Heure de l'émission                    |
| `nomEmission`         | TEXT                  | Nom de l'émission                      |
| `nomEpisode`          | TEXT                  | Nom de l'épisode                       |
| `typeEpisode`         | TEXT                  | Type de l'épisode                      |
| `dureeEpisode`        | TEXT                  | Durée de l'épisode                     |
| `urlEpisode`          | TEXT                  | URL de l'épisode                       |
| `urlVignette`         | TEXT                  | URL de la vignette de l'épisode        |
| `urlProgrammeChaineDate` | TEXT              | URL du programme de la chaîne pour une date donnée |

## Table 'Resumes'
| Colonne               | Type                  | Description                            |
|-----------------------|-----------------------|----------------------------------------|
| `idResume`            | INT AUTO_INCREMENT    | Clé primaire, identifiant unique       |
| `idProgrammation`     | INT                   | Clé étrangère vers la table Programmation |
| `nomCompletEpisode`   | TEXT                  | Nom complet de l'épisode              |
| `resumeEpisode`       | TEXT                  | Résumé de l'épisode                    |

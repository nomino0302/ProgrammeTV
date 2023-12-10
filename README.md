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
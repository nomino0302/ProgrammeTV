# Script de création de BDD ProgrammeTV

BDD : MariaDB (MySQL)

- URL de la BDD : https://nono0302.hopto.me
- Port : 3306
- Utilisateur : public
- Mot de passe : MW24WgrDB
- Database : ProgrammeTV

mysql -h nono0302.hopto.me -P 3306 -u public -pMW24WgrDB ProgrammeTV

## Si vous voulez créer votre propre BDD

- Installez MariaDB

Pour se connecter à votre base de donnée :

### config.ini
```
[mysql]
host = localhost
user = {votre_user}
password = {votre_mdp}
```
import mysql.connector
import configparser
from bs4 import BeautifulSoup


def main():
    # Lire le fichier de configuration
    config = configparser.ConfigParser()
    config.read('config.ini')

    conn = mysql.connector.connect(
        host=config['mysql']['host'],          # Par exemple, "localhost" ou l'adresse IP du serveur
        user=config['mysql']['user'],          # Votre nom d'utilisateur
        password=config['mysql']['password']   # Votre mot de passe
    )

    cursor = conn.cursor()

    # Créer la base de données si elle n'existe pas
    cursor.execute("CREATE DATABASE IF NOT EXISTS ProgrammeTV")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()

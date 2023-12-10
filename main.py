import mysql.connector
from mysql.connector.cursor import MySQLCursor
import configparser
import requests
from bs4 import BeautifulSoup
import traceback


def init_database(cursor: MySQLCursor):
    """Permet de créer la database et les tables si elles n'existent pas"""

    # Créer la base de données (insensible à la casse) si elle n'existe pas
    cursor.execute("CREATE DATABASE IF NOT EXISTS ProgrammeTV CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    cursor.execute("USE ProgrammeTV;")

    # Créer les tables si elles n'existent pas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Chaines (
            idChaine INT AUTO_INCREMENT,
            nomChaine TEXT,
            urlChaine TEXT,
            urlLogo TEXT,
            numTNT INT,
            numOrange INT,
            numSFR INT,
            numFree INT,
            numBouygues INT,
            numCanal INT,
            PRIMARY KEY (idChaine)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Programmation (
            idProgrammation INT AUTO_INCREMENT,
            idChaine INT,
            heureEmission TIME,
            dateEmission DATE,
            nomEmission TEXT,
            nomEpisode TEXT,
            urlEpisode TEXT,
            urlImageEpisode TEXT,
            typeEpisode TEXT,
            dureeEpisode TEXT,
            PRIMARY KEY (idProgrammation),
            FOREIGN KEY (idChaine) REFERENCES Chaines(idChaine)
        );
    """)

    cursor.execute("USE ProgrammeTV;")


def get_channels(cursor: MySQLCursor, fournisseurs: dict):
    """Permet de mettre à jour les chaînes dans la base de donnée"""

    cursor.execute("SELECT NomChaine FROM Chaines;")
    database_chaines = [item[0].lower() for item in cursor.fetchall()]

    session = requests.session()
    for column_name, url_fournisseur in fournisseurs.items():

        page = session.get(url_fournisseur)
        soup = BeautifulSoup(page.content, "html.parser")

        numeros = [int(num.get_text().strip().replace("N°", "")) for num in soup.find_all(class_="gridRow-cardsChannelNumber")]
        chaines = [chaine.get_text().strip() for chaine in soup.find_all(class_="gridRow-cardsChannelItemLink")]
        chaines = [chaines[i].replace(f"N°{numeros[i]}", "").strip() for i in range(len(numeros))]
        urls = ["https://www.programme-tv.net" + url["href"] for url in soup.find_all(class_="gridRow-cardsChannelItemLink")]
        imgs_urls_elts = soup.find_all(class_="gridRow-cardsChannelItem")
        imgs_urls = []
        for elt in imgs_urls_elts:
            new_elt = elt.find("img")
            if new_elt:
                if "lazyload" in new_elt["class"]:
                    imgs_urls.append(new_elt["data-src"])
                else:
                    imgs_urls.append(new_elt["src"])
            else:
                imgs_urls.append(None)

        for i in range(len(numeros)):

            if chaines[i].lower() not in database_chaines:
                query = "INSERT INTO chaines (NomChaine, URLChaine, URLLogo) VALUES (%s, %s, %s);"
                values = (chaines[i], urls[i], imgs_urls[i])
                cursor.execute(query, values)
                database_chaines.append(chaines[i].lower())
            query = f"UPDATE chaines SET {column_name} = %s WHERE NomChaine = %s;"
            values = (numeros[i], chaines[i])
            cursor.execute(query, values)


def main(cursor: MySQLCursor, fournisseurs: dict):
    
    nb_etapes = 2
    etape = 1

    print(f"({etape}/{nb_etapes}) Préparation de la base de donnée ", end="")
    init_database(cursor)
    print(" ..... OK!")
    etape += 1

    print(f"({etape}/{nb_etapes}) Récupération des chaînes et mise à jour de la BDD ", end="")
    get_channels(cursor, fournisseurs)
    print(" ..... OK!")
    etape += 1


if __name__ == "__main__":

    DEBUG = False

     # Lire le fichier de configuration
    config = configparser.ConfigParser()
    config.read('config.ini')
    cred = config['mysql']
    fournisseurs = config['fournisseurs']

    # Établir la connexion à la base de données
    conn = mysql.connector.connect(
        host=cred['host'],        
        user=cred['user'],        
        password=cred['password'],
    )
    cursor = conn.cursor()

    try:
        cursor.execute("START TRANSACTION;")
        main(cursor, fournisseurs)
    except Exception as err:
        if DEBUG:
            traceback.print_exc()
        else:
            print(f"Erreur : {err}")
        cursor.execute("ROLLBACK;")
    else:
         cursor.execute("COMMIT;")
    finally:
        cursor.close()
        conn.close()

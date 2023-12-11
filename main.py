import mysql.connector
from mysql.connector.cursor import MySQLCursor
import configparser
import requests
from bs4 import BeautifulSoup
import traceback
from datetime import datetime, timedelta


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
            numTNT INT,
            numOrange INT,
            numSFR INT,
            numFree INT,
            numBouygues INT,
            numCanal INT,
            urlChaine TEXT,
            urlLogo TEXT,
            PRIMARY KEY (idChaine)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Programmation (
            idProgrammation INT AUTO_INCREMENT,
            idChaine INT,
            dateEmission DATE,
            heureEmission TIME,
            nomEmission TEXT,
            nomEpisode TEXT,
            typeEpisode TEXT,
            dureeEpisode TEXT,
            urlEpisode TEXT,
            urlVignette TEXT,
            urlProgrammeChaineDate TEXT,
            PRIMARY KEY (idProgrammation),
            FOREIGN KEY (idChaine) REFERENCES Chaines(idChaine)
        );
    """)

    cursor.execute("USE ProgrammeTV;")


def get_channels(cursor: MySQLCursor, session: requests.Session, fournisseurs: dict):
    """Permet de mettre à jour les chaînes dans la base de donnée"""

    cursor.execute("SELECT nomChaine FROM Chaines;")
    database_chaines = [item[0].lower() for item in cursor.fetchall()]

    for column_name, url_fournisseur in fournisseurs.items():

        page = session.get(url_fournisseur)
        soup = BeautifulSoup(page.content, "html.parser")

        numeros = [int(num.get_text().strip().replace("N°", "")) if num else None for num in soup.find_all(class_="gridRow-cardsChannelNumber")]
        chaines = [chaine.get_text().strip() if chaine else None for chaine in soup.find_all(class_="gridRow-cardsChannelItemLink")]
        chaines = [chaines[i].replace(f"N°{numeros[i]}", "").strip() if chaines[i] else None for i in range(len(numeros))]
        urls = ["https://www.programme-tv.net" + url["href"] if url else None for url in soup.find_all(class_="gridRow-cardsChannelItemLink")]
        imgs_urls_elts = [img_url_elt if img_url_elt else None for img_url_elt in soup.find_all(class_="gridRow-cardsChannelItem")]
        imgs_urls = []
        for elt in imgs_urls_elts:
            if elt:
                new_elt = elt.find("img")
                if new_elt:
                    if "lazyload" in new_elt["class"]:
                        imgs_urls.append(new_elt["data-src"])
                    else:
                        imgs_urls.append(new_elt["src"])
                else:
                    imgs_urls.append(None)
            else:
                imgs_urls.append(None)

        for i in range(len(numeros)):

            if chaines[i].lower() not in database_chaines:
                query = "INSERT INTO Chaines (nomChaine, urlChaine, urlLogo) VALUES (%s, %s, %s);"
                values = (chaines[i], urls[i], imgs_urls[i])
                cursor.execute(query, values)
                database_chaines.append(chaines[i].lower())
            query = f"UPDATE Chaines SET {column_name} = %s WHERE nomChaine = %s;"
            values = (numeros[i], chaines[i])
            cursor.execute(query, values)


def delete_old_shows(cursor: MySQLCursor):
    """Supprime les données trop vieilles (avant hier) et renvoie la liste de dates à récupérer"""

    today = datetime.now().date()

    cursor.execute("SELECT DISTINCT(dateEmission) FROM Programmation;")
    database_dates = [item[0] for item in cursor.fetchall()]
    to_have_dates = [today + timedelta(days=i) for i in range(-1, 8)]
    to_delete_dates = [element for element in database_dates if element not in to_have_dates]
    if (today not in to_delete_dates) and (today in database_dates):
        to_delete_dates.append(today)
    needed_dates = [element for element in to_have_dates if element not in database_dates]
    if today not in needed_dates:
        needed_dates = [today] + needed_dates

    for date in to_delete_dates:
        query = f"DELETE FROM Programmation WHERE dateEmission = %s;"
        values = (date,)
        cursor.execute(query, values)

    return needed_dates


def get_shows(cursor: MySQLCursor, needed_dates: set, session: requests.Session, nb_etapes: int):
    """Permet de mettre à jour les programmes TV : on supprime les données des programmes d'avant hier,
    On réactualise les programmes d'aujourd'hui, et on récupére le programme de dans 7 jours"""

    cursor.execute("SELECT idChaine, urlChaine FROM Chaines;")
    ids_urls = cursor.fetchall()

    nb_operations = len(ids_urls) * len(needed_dates)
    nb = 0

    for id, url in ids_urls:
        for date in needed_dates:

            print(f"(4/{nb_etapes}) Récupération des émissions et mise à jour de la BDD ({nb}/{nb_operations}) ", end="\r")

            url_chaine = url.split("/")
            url_chaine.insert(-1, str(date))
            url_chaine = "/".join(url_chaine)

            page = session.get(url)
            soup = BeautifulSoup(page.content, "html.parser")

            heures = [datetime.strptime(heure.get_text().strip(), "%Hh%M").time() if heure else None for heure in soup.find_all(class_="mainBroadcastCard-startingHour")]
            emissions_elts = [emission_elt if emission_elt else None for emission_elt in soup.find_all(class_="mainBroadcastCard-title")]
            emissions = [emission.get_text().strip() if emission else None for emission in emissions_elts]
            episodes = []
            for emission_elt in emissions_elts:
                if emission_elt:
                    episode = emission_elt.find_next_sibling(class_="mainBroadcastCard-subtitle")
                    if episode:
                        episodes.append(episode.get_text().strip())
                    else:
                        episodes.append(None)
                else:
                    episodes.append(None)
            types_episodes = [type_episode.get_text().strip() if type_episode else None for type_episode in soup.find_all(class_="mainBroadcastCard-format")]
            durees = [duree.get_text().strip() if duree else None for duree in soup.find_all(class_="mainBroadcastCard-durationContent")]
            a_elts = [a_elt.find("a") if a_elt else None for a_elt in soup.find_all(class_="mainBroadcastCard-title")]
            urls = [url["href"] if url else None for url in a_elts]
            vignettes_urls = []
            visuals_elts = [visual_elt if visual_elt else None for visual_elt in soup.find_all(class_="mainBroadcastCard-visual")]
            for visual_elt in visuals_elts:
                if visual_elt:
                    vignette_url_elt = visual_elt.find(class_="mainBroadcastCard-imageContent")
                    if vignette_url_elt:
                        new_elt = vignette_url_elt.find("img")
                        if new_elt:
                            if "lazyload" in new_elt["class"]:
                                vignettes_urls.append(new_elt["data-src"])
                            else:
                                vignettes_urls.append(new_elt["src"])
                        else:
                            vignettes_urls.append(None)
                    else:
                        vignettes_urls.append(None)
                else:
                    vignettes_urls.append(None)

            for i in range(len(heures)):
                query = "INSERT INTO Programmation (idChaine, dateEmission, heureEmission, nomEmission, nomEpisode, typeEpisode, dureeEpisode, urlEpisode, urlVignette, urlProgrammeChaineDate) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"
                values = (id, date, heures[i], emissions[i], episodes[i], types_episodes[i], durees[i], urls[i], vignettes_urls[i], url_chaine)
                cursor.execute(query, values)
            
            nb += 1
    
    print(f"(4/{nb_etapes}) Récupération des émissions et mise à jour de la BDD ({nb}/{nb_operations}) ", end="")


def main(cursor: MySQLCursor, session: requests.Session, fournisseurs: dict):
    
    nb_etapes = 4

    print(f"(1/{nb_etapes}) Préparation de la base de donnée ", end="")
    init_database(cursor)
    print("..... OK!")

    print(f"(2/{nb_etapes}) Récupération des chaînes et mise à jour de la BDD ", end="")
    get_channels(cursor, session, fournisseurs)
    print("..... OK!")

    print(f"(3/{nb_etapes}) Suppression des anciennes données ", end="")
    needed_dates = delete_old_shows(cursor)
    print("..... OK!")

    print(f"(4/{nb_etapes}) Récupération des émissions et mise à jour de la BDD ", end="\r")
    get_shows(cursor, needed_dates, session, nb_etapes)
    print("..... OK!")


if __name__ == "__main__":

    DEBUG = True

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

    session = requests.Session()

    try:
        cursor.execute("START TRANSACTION;")
        main(cursor, session, fournisseurs)
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

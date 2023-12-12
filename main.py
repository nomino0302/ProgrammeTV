import mysql.connector
import configparser
import requests
from bs4 import BeautifulSoup
import traceback
from datetime import datetime, timedelta
import sys
import os
import logging
import pickle


def init_database():
    """Permet de créer la database et les tables si elles n'existent pas"""

    # Reset de la base de donnée si RESET = True
    if RESET:
        cursor.execute("DROP DATABASE IF EXISTS ProgrammeTV;")
        logger.debug("Base de donnée 'ProgrammeTV' supprimée")


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
            FOREIGN KEY (idChaine) REFERENCES Chaines(idChaine) ON DELETE CASCADE
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Resumes (
            idResume INT AUTO_INCREMENT,
            idProgrammation INT,
            nomCompletEpisode TEXT,
            resumeEpisode TEXT,
            PRIMARY KEY (idResume),
            FOREIGN KEY (idProgrammation) REFERENCES Programmation(idProgrammation) ON DELETE CASCADE
        );
    """)

    cursor.execute("USE ProgrammeTV;")

    logger.debug("Bases de données et tables correctement créées et utilisées")


def update_channels():
    """Permet de mettre à jour les chaînes dans la base de donnée"""

    # On récupère les noms de chaines déjà présentes dans la BDD
    cursor.execute("SELECT nomChaine FROM Chaines;")
    database_chaines = [item[0].lower() for item in cursor.fetchall()]

    for column_name, url_fournisseur in fournisseurs.items():

        # On récupère les données de l'URL (le code HTML) avec un timeout de 5 secondes
        try:
            page = session.get(url_fournisseur, timeout=5)
            if not page.ok:
                raise RuntimeError(f"Code {page.status_code}")
        except Exception as err:
            logger.warning(f"Erreur {url_fournisseur} : {err}")
            continue
            
        soup = BeautifulSoup(page.content, "html.parser")

        # On récupère les numéros de chaines, les nom de chaines et les URLs de chaines et de logo, avec les valeurs nettoyées dans des listes
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
        
        logger.debug(f"[{column_name}] numeros[len()={len(numeros)},None={numeros.count(None)}] / chaines[len()={len(chaines)},None={chaines.count(None)}] / urls[len()={len(urls)},None={urls.count(None)}] / imgs_urls[len()={len(imgs_urls)},None={imgs_urls.count(None)}]")

        for i in range(len(numeros)):

            # On ajoute la chaine dans Chaines si elle n'existe pas, on update le numéro de chaine dans tous les cas
            if chaines[i].lower() not in database_chaines:
                query = "INSERT INTO Chaines (nomChaine, urlChaine, urlLogo) VALUES (%s, %s, %s);"
                values = (chaines[i], urls[i], imgs_urls[i])
                cursor.execute(query, values)
                database_chaines.append(chaines[i].lower())
                logger.debug(f"[{column_name}] {chaines[i]} ajouté à la BDD")
            query = f"UPDATE Chaines SET {column_name} = %s WHERE nomChaine = %s;"
            values = (numeros[i], chaines[i])
            cursor.execute(query, values)


def delete_old_shows():
    """Supprime les données trop vieilles (avant hier) et renvoie la liste de dates à récupérer"""

    today = datetime.now().date()

    # On récupère les dates utilisés dans Programmations et on fait plusieurs liste qu'on va traiter après
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
        logger.debug(f"Programmation et Resumes de {date} supprimés")

    logger.debug(f"Dates à récupérer : {needed_dates}")
    return needed_dates


def get_shows(needed_dates: list, nb_etapes: int):
    """Permet de mettre à jour les programmes TV : on supprime les données des programmes d'avant hier,
    On réactualise les programmes d'aujourd'hui, et on récupére le programme de dans 7 jours"""

    cursor.execute("SELECT idChaine, urlChaine FROM Chaines;")
    ids_urls = cursor.fetchall()

    # Opérations max à faire (boucles)
    nb_operations = len(ids_urls) * len(needed_dates)
    nb = 0

    for id, url in ids_urls:
        for date in needed_dates:

            print(f"(4/{nb_etapes}) Récupération des émissions et mise à jour de la BDD ({nb}/{nb_operations}) ", end="\r")

            # url = URL de base de la chaine, url_chaine = URL avec la date
            url_chaine = url.split("/")
            url_chaine.insert(-1, str(date))
            url_chaine = "/".join(url_chaine)

            logger.debug(f"[{id} | {date}] ({nb}/{nb_operations}) Récupération de {url_chaine}")

            try:
                page = session.get(url_chaine, timeout=5)
                if not page.ok:
                    raise RuntimeError(f"Code {page.status_code}")
            except Exception as err:
                logger.warning(f"Erreur {url_chaine} : {err}")
                continue

            soup = BeautifulSoup(page.content, "html.parser")

            # Meme principe que pour update_channels
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
            
            logger.debug(f"[{id} | {date}] ({nb}/{nb_operations}) heures[len()={len(heures)},None={heures.count(None)}] / emissions[len()={len(emissions)},None={emissions.count(None)}] / episodes[len()={len(episodes)},None={episodes.count(None)}] / types_episodes[len()={len(types_episodes)},None={types_episodes.count(None)}] / durees[len()={len(durees)},None={durees.count(None)}] / urls[len()={len(urls)},None={urls.count(None)}] / vignettes_urls[len()={len(vignettes_urls)},None={vignettes_urls.count(None)}]")

            # On ajoute dans la BDD dans tous les cas
            for i in range(len(heures)):
                query = "INSERT INTO Programmation (idChaine, dateEmission, heureEmission, nomEmission, nomEpisode, typeEpisode, dureeEpisode, urlEpisode, urlVignette, urlProgrammeChaineDate) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"
                values = (id, date, heures[i], emissions[i], episodes[i], types_episodes[i], durees[i], urls[i], vignettes_urls[i], url_chaine)
                cursor.execute(query, values)
            logger.debug(f"[{id} | {date}] ({nb}/{nb_operations}) Données enregistrées dans la BDD")

            nb += 1
    
    print(f"(4/{nb_etapes}) Récupération des émissions et mise à jour de la BDD ({nb}/{nb_operations}) ", end="")


def get_resumes(needed_dates: list, nb_etapes: int):
    """Permet de récupérer les résumés des épisodes et de mettre à jour la base de donnée"""

    formatted_dates = ', '.join(f"'{date}'" for date in needed_dates)
    cursor.execute(f"SELECT idProgrammation, urlEpisode FROM Programmation WHERE dateEmission IN ({formatted_dates});")
    ids_urls = cursor.fetchall()

    nb_operations = len(ids_urls)
    nb = 0

    for id, url in ids_urls:

        print(f"(5/{nb_etapes}) Récupération des résumées et mise à jour de la BDD ({nb}/{nb_operations}) ", end="\r")
        logger.debug(f"[{id}] ({nb}/{nb_operations}) Récupération de {url}")

        try:
            page = session.get(url, timeout=5)
            if not page.ok:
                raise RuntimeError(f"Code {page.status_code}")
        except Exception as err:
            logger.warning(f"Erreur {url} : {err}")
            continue

        soup = BeautifulSoup(page.content, "html.parser")

        # Toutes les émissions/épisodes n'ont pas de "résumé", seulement ceux qui en ont seront enregistrés dans la BDD
        if soup.find(class_="programCollectionEpisode-synopsis"):
            vrai_titre = soup.find(class_="synopsis-title")
            if vrai_titre:
                vrai_titre = vrai_titre.get_text().strip().replace("Résumé ", "")
            
            resume = soup.find(class_="synopsis-teaser")
            if resume:
                resume = resume.get_text().strip()
            
            logger.debug(f"[{id}] ({nb}/{nb_operations}) vrai_titre[None={vrai_titre is None}] / resume[None={resume is None}]")
            
            query = "INSERT INTO Resumes (idProgrammation, nomCompletEpisode, resumeEpisode) VALUES (%s, %s, %s);"
            values = (id, vrai_titre, resume)
            cursor.execute(query, values)
            logger.debug(f"[{id}] ({nb}/{nb_operations}) Données enregistrées dans la BDD")

        nb += 1
    
    print(f"(5/{nb_etapes}) Récupération des résumées et mise à jour de la BDD ({nb}/{nb_operations}) ", end="")


def clear_channels():
    """Fonction qui permet de supprimer les chaines dont 'idChaine' ne sont pas présentent en tant que clés étrangères dans Programmation"""

    cursor.execute("SELECT idChaine, nomChaine FROM Chaines WHERE idChaine NOT IN (SELECT DISTINCT idChaine FROM Programmation);")
    to_delete_ids_chaines = cursor.fetchall()
    for id, chaine in to_delete_ids_chaines:
        query = "DELETE FROM Chaines WHERE idChaine = %s;"
        values = (id,)
        cursor.execute(query, values)
        logger.debug(f"Chaine {chaine} (idChaine={id}) supprimée")


def main():
    """Fonction principale, elle exécute toutes les autres fonctions"""
    
    nb_etapes = 6

    # On utilise "START TRANSACTION ... COMMIT" à toutes les fonctions au cas où elles
    # viendraient à retourner une exception, elles retrouveront leurs états d'origine (ROLLBACK dans le else à la fin du script)
    cursor.execute("START TRANSACTION;")
    print(f"(1/{nb_etapes}) Préparation de la base de donnée (RESET={RESET}) ", end="")
    init_database()
    print("..... OK!")
    cursor.execute("COMMIT;")

    cursor.execute("START TRANSACTION;")
    print(f"(2/{nb_etapes}) Récupération des chaînes et mise à jour de la BDD ", end="")
    update_channels()
    print("..... OK!")
    cursor.execute("COMMIT;")

    cursor.execute("START TRANSACTION;")
    print(f"(3/{nb_etapes}) Suppression des anciennes données (non comprises entre J-1 et J+7) ", end="")
    needed_dates = delete_old_shows()
    print("..... OK!")
    cursor.execute("COMMIT;")

    cursor.execute("START TRANSACTION;")
    print(f"(4/{nb_etapes}) Récupération des émissions et mise à jour de la BDD ", end="\r")
    get_shows(needed_dates, nb_etapes)
    print("..... OK!")
    cursor.execute("COMMIT;")

    cursor.execute("START TRANSACTION;")
    print(f"(5/{nb_etapes}) Récupération des résumées et mise à jour de la BDD ", end="\r")
    get_resumes(needed_dates, nb_etapes)
    print("..... OK!")
    cursor.execute("COMMIT;")

    cursor.execute("START TRANSACTION;")
    print(f"(6/{nb_etapes}) Suppression des chaînes non utilisées (notamment par Programmation)", end="")
    clear_channels()
    print("..... OK!")
    cursor.execute("COMMIT;")

    print("Base de donnée ProgrammeTV à jour !")
    logger.info("Base de donnée ProgrammeTV à jour !")


if __name__ == "__main__":

    DEBUG = False
    RESET = False

    if "-d" in sys.argv or "--debug" in sys.argv:
        DEBUG = True
    if "-r" in sys.argv or "--reset" in sys.argv:
        RESET = True

    # Créer le dossier 'logs' si nécessaire
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.mkdir(log_dir)
    
    # Suppression des fichiers log si + de 5
    for file in os.listdir(log_dir):
        if file[-4:] != ".log":
            os.remove(os.path.join(log_dir, file))
    liste_logs = sorted(os.listdir(log_dir))
    for i in range(len(liste_logs) - 4): # 4 anciens + 1 nouveau
        os.remove(os.path.join(log_dir, liste_logs[i]))

    # Configuration du logger
    logging.basicConfig(level=logging.DEBUG, filename=os.path.join(log_dir, f"{datetime.now()}.log"),
                        format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')
    logging.getLogger("requests").setLevel(logging.WARNING) # logging souhaité du module 'requests'
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)  # Ou le niveau de logging souhaité

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
    logger.info(f"Connecté à MariaDB {cred['host']} avec l'utilisateur {cred['user']}")

    # On récupère le fichier cookies.pkl si il existe
    session = requests.Session()
    if "cookies.pkl" in os.listdir():
        with open("cookies.pkl", "rb") as f:
            session.cookies.update(pickle.load(f))
        logger.info("Fichier cookies.pkl chargé")

    try:
        main()
    except Exception as err:
        print()
        if DEBUG:
            traceback.print_exc()
        else:
            print(f"Erreur : {err}")
        logger.error(f"Erreur : {err}", exc_info=True)
        # Si il y a une erreur, on ne prend pas en compte les nouvelles requêtes SQL
        cursor.execute("ROLLBACK;")
    finally:
        cursor.close()
        conn.close()
        logger.info(f"Déconnecté de MariaDB {cred['host']}")

        # Sauvegarde des cookies
        with open("cookies.pkl", "wb") as f:
            pickle.dump(session.cookies, f)
        logger.info("Fichier cookies.pkl sauvegardé")

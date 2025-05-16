#!/usr/bin/env python
#  -*- coding: utf-8 -*-

import argparse
import json
import os
import re
import requests
from bs4 import BeautifulSoup
import configparser
import mimetypes

config_file = 'cdpDumpingUtils.cfg'
output_dir = os.getcwd()
base_url = None
username = None
password = None
verbose = False

def load_config():
    global base_url, username, password
    config = configparser.ConfigParser()
    if os.path.exists(config_file):
        config.read(config_file)
        base_url = config.get('DEFAULT', 'base_url', fallback=None)
        username = config.get('DEFAULT', 'username', fallback=None)
        password = config.get('DEFAULT', 'password', fallback=None)

def start():
    global output_dir, base_url, username, password, verbose
    load_config()

    log_user = username is not None and password is not None and username != "" and password != ""

    if base_url.endswith("/"):
        base_url = base_url[:-1]

    session = requests.Session()
    jsonRep = None

    if log_user:
        print("Connexion en cours...")

        data = {
            "csrf-token": "undefined",
            "login": username,
            "motdepasse": password,
            "connexion": "1"
        }

        try:
            response = session.post(base_url + "/ajax.php", data=data)
            response.raise_for_status()
            jsonRep = response.json()
        except requests.RequestException as e:
            print(f"Erreur lors de la connexion : {e}")
            exit()

        if jsonRep is not None and jsonRep.get("etat") != "ok":
            print("Informations de connexion incorrectes")
            exit()

        print("Connexion réussie")

    pages = {}
    docs = {}

    def explore(explore_page):
        if verbose:
            print(f"Exploring {base_url}/docs?rep={explore_page}")

        try:
            rep = session.get(f"{base_url}/docs?rep={explore_page}")
            rep.raise_for_status()
        except requests.RequestException as e:
            print(f"Erreur lors de l'exploration de la page {explore_page}: {e}")
            return

        sec = BeautifulSoup(rep.text, "html.parser").find("section")

        if not sec:
            return

        txt = sec.find("div", class_="warning")
        if txt and txt.get_text() in [
            "Mauvais paramètre d'accès à cette page.",
            "Ce contenu est protégé. Vous devez vous connecter pour l'afficher."]:
            return

        pages[explore_page] = sec.find("span", class_="nom").get_text().strip()

        for r in sec.find_all("a", href=re.compile("rep=")):
            try:
                page = int(r["href"].split("rep=")[-1])
                if page not in pages:
                    explore(page)
            except ValueError:
                continue

        docs[explore_page] = {}
        for d in sec.find_all("p", class_="doc"):
            a_tag = d.find("a", href=re.compile("download"))
            if a_tag and a_tag.has_attr("href"):
                try:
                    file_id = int(a_tag["href"].split("id=")[-1])
                    docs[explore_page][file_id] = d.find("span", class_="nom").get_text()
                except (ValueError, AttributeError):
                    continue

    print(f"Exploration de {base_url} en cours...")
    for i in range(100):
        explore(i)

    print(f"Exploration terminée. ({len(pages)} pages trouvées)")

    print("Téléchargement des documents...")
    nbDoc = 0
    nbDocRef = 0

    for p, page_name in pages.items():
        for file_id, file_name in docs.get(p, {}).items():
            try:
                dl = session.get(f"{base_url}/download?id={file_id}&dl")
                dl.raise_for_status()
                content_type = dl.headers.get("Content-Type", "").lower()

                if "text/html" in content_type:
                    page_content = BeautifulSoup(dl.text, "html.parser").find("section")
                    if page_content and page_content.find("div", class_="warning"):
                        nbDocRef += 1
                        continue

                ext = mimetypes.guess_extension(content_type.split(';')[0]) or ".pdf"
                file_name_clean = re.sub(r'[\\/:*?"<>|]', '_', file_name) + ext

                if verbose:
                    print(f"Téléchargement de {file_name_clean}...")

                file_path = os.path.join(output_dir, page_name, file_name_clean)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                with open(file_path, "wb") as f:
                    f.write(dl.content)

                nbDoc += 1
            except requests.RequestException as e:
                print(f"Erreur lors du téléchargement du fichier {file_name} : {e}")

    print(f"{nbDoc} documents téléchargés")
    print(f"{nbDocRef} documents protégés")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cahier de Prépa - Download Tool")
    parser.add_argument('--output', type=str, help='Répertoire de téléchargement')
    parser.add_argument('--verbose', action='store_true', help='Mode verbeux')
    args = parser.parse_args()

    if args.output:
        output_dir = args.output
    verbose = args.verbose

    start()

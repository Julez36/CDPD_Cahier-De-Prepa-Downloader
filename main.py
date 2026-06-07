#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import configparser
import logging
import mimetypes
import re
import sys
import urllib.parse
from pathlib import Path
import requests
from bs4 import BeautifulSoup

CONFIG_FILE = Path('cdpDumpingUtils.cfg')

class CahierDePrepaDownloader:
    
    def __init__(self, base_url: str, username: str = "", password: str = "", output_dir: str = "."):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.output_dir = Path(output_dir).resolve()

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        self.downloaded_files = set()
        self.stats = {"telecharges": 0, "proteges": 0, "erreurs": 0, "dossiers_valides": 0}

    def _sanitize_filename(self, name: str) -> str:
        """Nettoyage strict des caractères interdits par le système d'exploitation."""
        clean_name = re.sub(r'[<>:"/\\|?*\u00a0]', '_', name.strip())
        return clean_name.rstrip('. ')

    def login(self) -> bool:
        """Séquence d'authentification."""
        if not self.username or not self.password:
            logging.info("[INFO] Mode navigation anonyme actif.")
            return True

        logging.info("[INFO] Établissement de la connexion HTTP...")
        payload = {
            "csrf-token": "undefined",
            "login": self.username,
            "motdepasse": self.password,
            "connexion": "1"
        }

        try:
            response = self.session.post(f"{self.base_url}/ajax.php", data=payload)
            response.raise_for_status()
            data = response.json()

            if data.get("etat") != "ok":
                logging.error("[ERREUR] Authentification rejetée par le serveur.")
                return False

            logging.info("[SUCCÈS] Session sécurisée établie.")
            return True
        except requests.RequestException as e:
            logging.error(f"[ERREUR] Échec de transaction HTTP : {e}")
            return False

    def start_exploration(self, max_id: int = 400):
        """Balayage itératif exhaustif (Racine + IDs 0 à 400)."""
        logging.info("\n[INFO] Lancement de l'exploration structurée...")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logging.info("[INFO] Analyse de la racine du site (Documents récents)...")
        self._process_page(f"{self.base_url}/docs", self.output_dir, is_root=True)

        logging.info(f"[INFO] Balayage des répertoires profonds (ID 0 à {max_id})...")
        for rep_id in range(0, max_id + 1):
            target_url = f"{self.base_url}/docs?rep={rep_id}"
            self._process_page(target_url, self.output_dir, is_root=False, rep_id=rep_id)

    def _process_page(self, url: str, base_path: Path, is_root: bool, rep_id: int = None):
        """Extraction des chemins d'accès multi-séparateurs et routage des documents."""
        try:
            response = self.session.get(url)
            response.raise_for_status()
        except requests.RequestException:
            return

        soup = BeautifulSoup(response.text, "html.parser")
        section = soup.find("section")

        if not section:
            return

        # Vérification des autorisations
        warning = section.find("div", class_="warning")
        if warning:
            warning_text = warning.get_text().strip()
            if "Mauvais paramètre" in warning_text or "invalide" in warning_text:
                return
            if "protégé" in warning_text.lower() or "accès" in warning_text.lower():
                logging.debug(f"[ATTENTION] Répertoire ID={rep_id} protégé.")
                return

        target_path = base_path
        
        # Découpage du chemin d'accès principal
        if not is_root:
            nom_span = section.find("span", class_="nom")
            if nom_span:
                raw_breadcrumb = nom_span.get_text()
                # Split regex tolérant les chevrons (>) et les barres obliques (/)
                parts = re.split(r'\s*(?:/|>)\s*', raw_breadcrumb)
                path_parts = [self._sanitize_filename(p) for p in parts if p.strip()]
                target_path = base_path.joinpath(*path_parts)
                self.stats["dossiers_valides"] += 1

        target_path.mkdir(parents=True, exist_ok=True)

        # Extraction des fichiers
        for doc_p in section.find_all("p", class_="doc"):
            link = doc_p.find("a", href=re.compile("download"))
            if not link:
                continue

            try:
                file_id_str = re.search(r"id=(\d+)", link["href"])
                if not file_id_str:
                    continue
                file_id = int(file_id_str.group(1))

                if file_id in self.downloaded_files:
                    continue

                nom_span = doc_p.find("span", class_="nom")
                if nom_span:
                    raw_name = nom_span.get_text(strip=True)
                else:
                    raw_name = link.get_text(strip=True) or f"document_{file_id}"

                # Analyse du nom du fichier pour intercepter les chemins inclus (ex: Documents récents)
                name_parts = re.split(r'\s*(?:/|>)\s*', raw_name)
                
                # Le vrai nom du fichier est obligatoirement le dernier élément
                file_raw = name_parts[-1]
                file_name = self._sanitize_filename(file_raw)

                # S'il y a des éléments avant le nom, ce sont des dossiers parents
                file_specific_dir = target_path
                if len(name_parts) > 1:
                    extra_dirs = [self._sanitize_filename(p) for p in name_parts[:-1] if p.strip()]
                    file_specific_dir = target_path.joinpath(*extra_dirs)
                    file_specific_dir.mkdir(parents=True, exist_ok=True)

                self._download_file(file_id, file_name, file_specific_dir)

            except (ValueError, AttributeError):
                continue

    def _download_file(self, file_id: int, base_name: str, target_dir: Path):
        """Requête binaire, détermination de l'extension et écriture sur le disque."""
        download_url = f"{self.base_url}/download?id={file_id}&dl"

        try:
            response = self.session.get(download_url, stream=True)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" in content_type:
                self.stats["proteges"] += 1
                return

            cd = response.headers.get('content-disposition', '')
            ext = ""
            
            filename_match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, re.IGNORECASE)

            if filename_match:
                original_filename = urllib.parse.unquote(filename_match.group(1))
                ext = Path(original_filename).suffix
                if base_name.startswith("document_"):
                    base_name = Path(original_filename).stem
            else:
                ext = mimetypes.guess_extension(content_type.split(';')[0]) or ".pdf"

            if not base_name.lower().endswith(ext.lower()):
                file_name = base_name + ext
            else:
                file_name = base_name

            file_name = self._sanitize_filename(file_name)
            file_path = target_dir / file_name

            if file_path.exists() and file_path.stat().st_size > 0:
                logging.debug(f"[INFO] Fichier existant ignoré : {file_name}")
                self.downloaded_files.add(file_id)
                return

            relative_out = target_dir.relative_to(self.output_dir) if target_dir != self.output_dir else "Racine"
            logging.info(f"[ÉCRITURE] {file_name} -> {relative_out}")
            
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            self.stats["telecharges"] += 1
            self.downloaded_files.add(file_id)

        except requests.RequestException:
            self.stats["erreurs"] += 1


def manage_config():
    """Routage des paramètres de configuration."""
    config = configparser.ConfigParser()
    params = {'base_url': '', 'username': '', 'password': '', 'output_dir': Path.cwd()}

    if CONFIG_FILE.exists():
        use_cfg = input("[SYSTÈME] Utiliser la configuration enregistrée ? (o/n) : ").strip().lower()
        if use_cfg == 'o':
            config.read(CONFIG_FILE)
            params['base_url'] = config.get('DEFAULT', 'base_url', fallback='')
            params['username'] = config.get('DEFAULT', 'username', fallback='')
            params['password'] = config.get('DEFAULT', 'password', fallback='')

    if not params['base_url']:
        params['base_url'] = input("[ENTRÉE] URL du Cahier De Prépa : ").strip()
    if not params['username']:
        params['username'] = input("[ENTRÉE] Identifiant (vide si accès libre) : ").strip()
    if not params['password']:
        params['password'] = input("[ENTRÉE] Mot de passe (vide si accès libre) : ").strip()

    out_input = input(f"[ENTRÉE] Dossier de destination (sans les guillemets) [{params['output_dir']}] : ").strip()
    if out_input:
        params['output_dir'] = Path(out_input)

    save_cfg = input("[SYSTÈME] Enregistrer les identifiants ? (o/n) : ").strip().lower()
    if save_cfg == 'o':
        config['DEFAULT'] = {
            'base_url': params['base_url'],
            'username': params['username'],
            'password': params['password']
        }
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)

    return params


def main():
    """Contrôleur d'exécution."""
    parser = argparse.ArgumentParser(description="CDPD - Extracteur d'arborescence structurelle")
    parser.add_argument('--output', type=str, help='Répertoire de destination cible')
    parser.add_argument('--verbose', action='store_true', help='Activer les logs réseau (debug)')
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(message)s")

    print("\n" + "="*75)
    print("CDP-DOWNLOADER par Julez36")
    print("="*75 + "\n")

    if not args.output:
        params = manage_config()
    else:
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        params = {
            'base_url': config.get('DEFAULT', 'base_url', fallback=''),
            'username': config.get('DEFAULT', 'username', fallback=''),
            'password': config.get('DEFAULT', 'password', fallback=''),
            'output_dir': Path(args.output)
        }

    downloader = CahierDePrepaDownloader(
        base_url=params['base_url'],
        username=params['username'],
        password=params['password'],
        output_dir=params['output_dir']
    )

    if not downloader.login():
        sys.exit(1)

    downloader.start_exploration()

    print("\n" + "="*75)
    print("BILAN OPÉRATIONNEL :")
    print(f"   [ÉTATS]    {downloader.stats['dossiers_valides']} répertoires valides détectés")
    print(f"   [COPIES]   {downloader.stats['telecharges']} documents sauvegardés")
    print(f"   [BLOQUES]  {downloader.stats['proteges']} dossiers inaccessibles (droits insuffisants)")
    print(f"   [ÉCHECS]   {downloader.stats['erreurs']} paquets corrompus ou erreurs serveur")
    print("="*75 + "\n")

if __name__ == "__main__":
    main()

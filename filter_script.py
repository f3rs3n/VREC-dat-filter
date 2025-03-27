# -*- coding: utf-8 -*-
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from thefuzz import fuzz # Use thefuzz (fork of fuzzywuzzy)
import sys
import os
import re
import argparse
import csv
import traceback
import urllib.parse
# Import colorama
from colorama import Fore, Style, init
# Import tqdm for progress bar
from tqdm import tqdm

# --- Definisci costanti colore ---
C_INFO = Fore.CYAN
C_SUCCESS = Fore.GREEN
C_WARNING = Fore.YELLOW
C_ERROR = Fore.RED
C_LABEL = Style.BRIGHT
C_RESET = Style.RESET_ALL
C_DIM = Style.DIM
C_NORMAL = Style.NORMAL

# Inizializza colorama
init(autoreset=True)

# --- fetch_single_url_titles (invariata) ---
def fetch_single_url_titles(url):
    """Scarica una singola pagina web ed estrae i titoli dei giochi consigliati."""
    print(f"{C_INFO}Recupero titoli da: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"{C_ERROR}Attenzione: Errore durante il recupero dell'URL {url}: {e}", file=sys.stderr)
        return None
    try:
        soup = BeautifulSoup(response.content, 'lxml')
        titles = set()
        tables = soup.find_all('table', class_='wikitable')
        if not tables:
            print(f"{C_WARNING}Attenzione: Nessuna tabella 'wikitable' trovata su {url}.", file=sys.stderr)
            print(f"Trovati {C_SUCCESS}{len(titles)}{C_NORMAL} titoli unici su {url}.")
            return titles
        table_index = 0
        for table in tables:
            table_index += 1
            rows = table.find_all('tr')
            for row in rows[1:]:
                try:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) > 1:
                        title_text = cells[1].get_text(strip=True)
                        cleaned_title_block = re.sub(r'\[.*?\]', '', title_text).strip()
                        title_lines = [line.strip() for line in cleaned_title_block.split('\n') if line.strip()]
                        if title_lines:
                            for final_title in title_lines:
                                if final_title:
                                    titles.add(final_title)
                except Exception as row_error:
                    print(f"{C_ERROR}ERRORE durante l'analisi di una riga nell'URL {url}: {row_error}", file=sys.stderr)
        print(f"Trovati {C_SUCCESS}{len(titles)}{C_NORMAL} titoli unici su {url}.")
        return titles
    except Exception as e:
        print(f"{C_ERROR}Attenzione: Errore durante l'analisi HTML dell'URL {url}: {e}", file=sys.stderr)
        traceback.print_exc()
        return None

# --- fetch_all_titles (invariata) ---
def fetch_all_titles(url_list):
    """Scarica e combina i titoli da una lista di URL, tenendo traccia per URL."""
    all_recommended_titles = set()
    titles_by_url = {}
    if not url_list:
        print(f"{C_ERROR}Nessun URL fornito.", file=sys.stderr)
        return None, None
    for url in url_list:
        titles_from_url = fetch_single_url_titles(url)
        if titles_from_url is not None:
            titles_by_url[url] = titles_from_url
            all_recommended_titles.update(titles_from_url)
    if not all_recommended_titles:
        print(f"{C_WARNING}Attenzione: Nessun titolo raccomandato VALIDO trovato negli URL forniti dopo l'analisi.", file=sys.stderr)
        return set(), titles_by_url if titles_by_url else {}
    print(f"\n{C_SUCCESS}Totale: Trovati {len(all_recommended_titles)} titoli unici raccomandati da tutti gli URL.")
    return all_recommended_titles, titles_by_url

# --- filter_dat_file (invariata) ---
def filter_dat_file(input_dat_path, output_dat_path, all_recommended_titles, titles_by_url, similarity_threshold):
    """Filtra il file DAT, genera report e scrive CSV multipli (uno per URL)."""
    if not os.path.exists(input_dat_path):
        print(f"{C_ERROR}Errore: Il file di input '{input_dat_path}' non esiste.", file=sys.stderr)
        return False
    if all_recommended_titles is None:
         print(f"{C_ERROR}Errore: Impossibile procedere, errore nel recupero dei titoli raccomandati.", file=sys.stderr)
         return False
    if not all_recommended_titles:
        print(f"\n{C_WARNING}Attenzione: Nessun titolo web valido trovato per il confronto, il file DAT di output sarà vuoto.")

    print(f"\n{C_INFO}Lettura e parsing del file DAT: {input_dat_path}")
    try:
        original_header_lines = []
        with open(input_dat_path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line.startswith('<datafile>'):
                    break
                original_header_lines.append(line)
            if stripped_line.startswith('<datafile>'):
                 original_header_lines.append(line)
        tree = ET.parse(input_dat_path)
        root = tree.getroot()
    except Exception as e:
        print(f"{C_ERROR}Errore imprevisto durante la lettura/parsing del file DAT: {e}", file=sys.stderr)
        traceback.print_exc()
        return False

    filtered_games_elements = {}
    matched_recommended_titles = set()

    print(f"{C_INFO}Filtraggio dei giochi (Soglia: {similarity_threshold}%, Algoritmo: token_set_ratio)...")
    original_header_element = root.find('header')
    all_game_elements = root.findall('game')
    original_game_count = len(all_game_elements)

    for game_element in tqdm(all_game_elements, desc=f"{C_INFO}Filtraggio{C_NORMAL}", unit=" gioco", ncols=100, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'):
        dat_title_original = game_element.get('name')
        if not dat_title_original: continue
        cleaned_dat_title = re.sub(r'\s*\([^)]*\)', '', dat_title_original)
        cleaned_dat_title = re.sub(r'\s*\[[^]]*\]', '', cleaned_dat_title)
        cleaned_dat_title = cleaned_dat_title.strip()

        game_matched_this_iteration = False
        if all_recommended_titles and cleaned_dat_title:
            for recommended_title in all_recommended_titles:
                similarity = fuzz.token_set_ratio(cleaned_dat_title, recommended_title)
                if similarity >= similarity_threshold:
                    if dat_title_original not in filtered_games_elements:
                         filtered_games_elements[dat_title_original] = game_element
                    matched_recommended_titles.add(recommended_title)
                    game_matched_this_iteration = True
                    # BREAK RIMOSSO!

    print()
    print(f"{C_SUCCESS}Filtraggio completato.")

    filtered_games = list(filtered_games_elements.values())
    new_root = ET.Element('datafile')
    if original_header_element is not None: new_root.append(original_header_element)
    for game in filtered_games: new_root.append(game)
    new_tree = ET.ElementTree(new_root)
    print(f"{C_INFO}Scrittura del file DAT filtrato in: {output_dat_path}")
    try:
        ET.indent(new_tree, space="\t", level=0)
        with open(output_dat_path, 'wb') as f:
             for line in original_header_lines:
                 if not line.strip().startswith('<datafile>'): f.write(line.encode('utf-8'))
             new_tree.write(f, encoding='utf-8', xml_declaration=False)
    except IOError as e:
        print(f"{C_ERROR}Errore durante la scrittura del file DAT di output: {e}", file=sys.stderr)

    csv_files_created = []
    output_dir = os.path.dirname(output_dat_path)
    url_counter = 0
    print()
    if titles_by_url:
        for url, titles_from_this_url in titles_by_url.items():
            url_counter += 1
            unmatched_for_this_url = titles_from_this_url - matched_recommended_titles
            if unmatched_for_this_url:
                try:
                    url_path = urllib.parse.urlparse(url).path
                    base_name_url = os.path.basename(url_path.strip('/')) if url_path.strip('/') else f'url_{url_counter}'
                    sanitized_name = re.sub(r'[^\w.-]+', '_', base_name_url).strip('_')
                    if not sanitized_name: sanitized_name = f"url_{url_counter}"
                    csv_filename = f"{sanitized_name}_unmatched.csv"
                    full_csv_path = os.path.join(output_dir, csv_filename)
                    print(f"{C_INFO}Scrittura CSV per {url} -> {C_LABEL}{csv_filename}{C_NORMAL} ({len(unmatched_for_this_url)} titoli)...")
                    with open(full_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow([f'Unmatched Recommended Title from {url}'])
                        for title in sorted(list(unmatched_for_this_url)):
                            writer.writerow([title])
                    csv_files_created.append(csv_filename)
                except Exception as e:
                    print(f"{C_ERROR}Errore creazione/scrittura CSV per {url}: {e}", file=sys.stderr)

    if not all_recommended_titles: print(f"{C_WARNING}Nessun titolo web valido trovato inizialmente, nessun file CSV creato.")
    elif not csv_files_created:
        all_matched_check = True
        if titles_by_url:
            for url, titles_from_this_url in titles_by_url.items():
                 if bool(titles_from_this_url - matched_recommended_titles): all_matched_check = False; break
        if all_matched_check: print(f"{C_SUCCESS}Tutti i titoli web validi trovati hanno avuto una corrispondenza nel DAT, nessun file CSV creato.")
    elif csv_files_created: print(f"{C_SUCCESS}Creati {len(csv_files_created)} file CSV con i titoli non corrispondenti.")

    total_matched_dat_games = len(filtered_games)
    total_unmatched_dat_games = original_game_count - total_matched_dat_games
    global_unmatched_recommended_titles = all_recommended_titles - matched_recommended_titles if all_recommended_titles else set()

    print(f"\n{C_LABEL}--- Resoconto Operazione ---{C_NORMAL}")
    print(f"{'File DAT Input:':<28} {input_dat_path}")
    print(f"{'File DAT Output:':<28} {output_dat_path}")
    print(f"{'Totale Giochi nel DAT:':<28} {original_game_count:>7}")
    print(f"\n{C_LABEL}Titoli Raccomandati (Web):{C_NORMAL}")
    if titles_by_url:
        max_url_len = max(len(url) for url in titles_by_url.keys()) if titles_by_url else 0
        for url, titles in titles_by_url.items():
            count = len(titles) if titles is not None else 'Errore'
            print(f"- URL: {url:<{max_url_len}} -> {C_SUCCESS}{count}{C_NORMAL} titoli trovati")
    total_web_titles = len(all_recommended_titles) if all_recommended_titles is not None else 'Errore'
    print(f"{'Totale Titoli Web Unici:':<28} {C_SUCCESS}{total_web_titles:>7}{C_NORMAL}")
    print(f"\n{C_LABEL}Soglia Similarità Usata:{C_NORMAL} {similarity_threshold}%")
    print(f"{C_LABEL}Algoritmo Confronto:{C_NORMAL}   token_set_ratio")
    print(f"\n{C_LABEL}Risultati Filtraggio DAT:{C_NORMAL}")
    print(f"{'- Giochi Corrispondenti:':<28} {C_SUCCESS}{total_matched_dat_games:>7}{C_NORMAL}")
    print(f"{'- Giochi Non Corrispondenti:':<28} {C_WARNING}{total_unmatched_dat_games:>7}{C_NORMAL}")
    print(f"\n{C_LABEL}Confronto Titoli Web vs DAT:{C_NORMAL}")
    print(f"{'- Titoli Web con Match nel DAT:':<28} {C_SUCCESS}{len(matched_recommended_titles):>7}{C_NORMAL}")
    print(f"{'- Titoli Web SENZA Match:':<28} {C_WARNING if global_unmatched_recommended_titles else C_SUCCESS}{len(global_unmatched_recommended_titles):>7}{C_NORMAL}")
    print(f"{C_LABEL}-----------------------------{C_NORMAL}\n")

    print(f"\n{C_SUCCESS}Operazione completata.")
    return True


# --- Blocco __main__ con help aggiornato ---
if __name__ == "__main__":
    # Setup Argparse
    parser = argparse.ArgumentParser(
        description="Filtra un file DAT/XML basandosi su titoli web. Output DAT e CSV opzionali.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # --- MODIFICA HELP TEXT ---
    parser.add_argument("input_file",
                        help="Percorso del file .dat (o .xml/.txt contenente XML) di input (obbligatorio).")
    # --- FINE MODIFICA HELP ---
    parser.add_argument("output_file", nargs='?', default=None, help="Percorso del file DAT di output (opzionale). Default: '[input]_filtered.dat'.")
    parser.add_argument("-u", "--urls", nargs='+', required=True, help="Uno o più URL delle pagine web con i titoli raccomandati (obbligatorio).")
    parser.add_argument("-t", "--threshold", type=int, default=90, choices=range(0, 101), metavar="[0-100]", help="Soglia di similarità percentuale.")
    # Argomento --csv_output è stato rimosso

    # Parsing Argomenti
    try:
        args = parser.parse_args()
    except Exception as e:
        print(f"{C_ERROR}ERRORE CRITICO durante il parsing degli argomenti: {e}", file=sys.stderr)
        sys.exit(1)

    # Determinazione Percorsi
    try:
        input_path = args.input_file
        if not os.path.exists(input_path):
             print(f"{C_ERROR}ERRORE CRITICO: Il file di input specificato non esiste: {input_path}", file=sys.stderr)
             sys.exit(1)
        input_dir = os.path.dirname(os.path.abspath(input_path))
        base_name, _ = os.path.splitext(os.path.basename(input_path))
        if args.output_file:
            output_dat_path = args.output_file
        else:
            output_dat_path = os.path.join(input_dir, f"{base_name}_filtered.dat")
        # final_csv_path non è più necessario qui
    except Exception as e:
        print(f"{C_ERROR}ERRORE CRITICO durante la determinazione dei percorsi: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    # Stampa info iniziali
    print(f"{C_LABEL}File Input:{C_NORMAL} {input_path}")
    print(f"{C_LABEL}File Output DAT (pianificato):{C_NORMAL} {output_dat_path}")

    # Esecuzione Logica Principale
    all_titles, titles_by_url = fetch_all_titles(args.urls)
    if all_titles is not None:
        try:
            # Chiama filter_dat_file senza final_csv_path
            filter_dat_file(
                input_path,
                output_dat_path,
                # final_csv_path, # RIMOSSO
                all_titles,
                titles_by_url,
                args.threshold
            )
        except Exception as e:
             print(f"\n{C_ERROR}ERRORE CRITICO durante l'esecuzione di filter_dat_file: {e}", file=sys.stderr)
             traceback.print_exc()
             sys.exit(1)
    else:
        print(f"{C_ERROR}Impossibile procedere con il filtraggio a causa di errori critici nel recupero dei titoli.", file=sys.stderr)
        sys.exit(1)

    # Fine
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
import urllib.parse
import datetime # Imported for current date
import string # Imported for punctuation cleaning
import logging # Import logging module
import coloredlogs # Import coloredlogs for colored console output
# Import tqdm for progress bar
from tqdm import tqdm

# --- Script Info ---
SCRIPT_VERSION = "1.4.2" # Changed fuzzy algorithm to WRatio, Best Match Logic
SCRIPT_AUTHOR = "f3rs3n, Gemini" # Authors
SCRIPT_HOMEPAGE = "https://github.com/f3rs3n/VREC-dat-filter" # Project homepage

# --- Pre-compiled Regex Patterns ---
is_disc_1_regex = re.compile(r'\((?:Disc|Disk|Side|Tape)\s+1\)', flags=re.IGNORECASE)
is_disc_n_regex = re.compile(r'\((?:Disc|Disk|Side|Tape)\s+\d+\)', flags=re.IGNORECASE)

# --- Helper Functions ---
def clean_title_for_comparison(title):
    """Applies aggressive cleaning to improve fuzzy matching."""
    if not title: return ""
    text = title.lower()
    text = re.sub(r'\s*\[[^]]*\]', '', text)
    text = re.sub(r'\s*\([^)]*\)', '', text)
    translator = str.maketrans('', '', ''.join(p for p in string.punctuation if p not in ['-']))
    text = text.translate(translator)
    text = text.replace('-', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_name_without_disc_info(original_name):
    """Removes disc information like (Disc N), (Disk N), etc. for multi-disc comparison."""
    if not original_name: return ""
    base = re.sub(r'\s*\((?:Disc|Disk|Side|Tape)\s+\d+\)\s*$', '', original_name, flags=re.IGNORECASE).strip()
    return base

# --- Web Scraping Functions ---
# fetch_single_url_titles and fetch_all_titles remain the same as 1.7.1
def fetch_single_url_titles(url):
    """Downloads a single web page and extracts recommended game titles."""
    headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36' }
    try:
        logging.debug(f"Attempting to fetch URL: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 404: logging.warning(f"URL not found (404), skipping: {url}"); return None
        else: logging.error(f"HTTP Error {http_err.response.status_code} fetching {url}: {http_err}"); return None
    except requests.exceptions.RequestException as e: logging.error(f"Network/Request Error fetching {url}: {e}"); return None
    except Exception as e: logging.exception(f"Unexpected error during fetch for {url}:"); return None

    logging.info(f"Processing successful fetch from: {url}")
    try:
        soup = BeautifulSoup(response.content, 'lxml')
        titles = set()
        tables = soup.find_all('table', class_='wikitable')
        if not tables: logging.warning(f"No 'wikitable' table found on {url}.")
        else:
            table_index = 0
            for table in tables:
                table_index += 1; logging.debug(f"Processing table {table_index} on {url}")
                rows = table.find_all('tr')
                for i, row in enumerate(rows[1:]):
                    row_num = i + 2
                    try:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) > 1:
                            title_text_raw = cells[1].get_text(strip=True)
                            cleaned_title_block = re.sub(r'\[.*?\]', '', title_text_raw).strip()
                            title_lines = [line.strip() for line in cleaned_title_block.split('\n') if line.strip()]
                            if title_lines:
                                for raw_line_title in title_lines:
                                    cleaned_for_match = clean_title_for_comparison(raw_line_title)
                                    if cleaned_for_match:
                                        logging.debug(f" Found raw='{raw_line_title}', cleaned='{cleaned_for_match}' in row {row_num} of table {table_index}")
                                        titles.add(cleaned_for_match)
                    except Exception as row_error: logging.error(f"Error parsing row {row_num} in table {table_index} of URL {url}: {row_error}")
            logging.info(f"Found {len(titles)} unique cleaned titles on {url}.")
        return titles
    except Exception as e: logging.exception(f"Error during HTML parsing of URL {url}:"); return None

def fetch_all_titles(url_list):
    """Downloads and combines titles from a list of URLs, tracking source."""
    all_recommended_titles = set(); titles_by_url = {}; processed_urls = set()
    if not url_list: logging.error("No URLs provided for fetching."); return set(), {}
    logging.info("Starting title fetching from URLs...")
    for url in tqdm(url_list, desc="Scanning URLs", unit="URL", ncols=100, leave=False):
        if url in processed_urls: logging.debug(f"Skipping already processed URL: {url}"); continue
        titles_from_url = fetch_single_url_titles(url); processed_urls.add(url)
        if titles_from_url is not None:
            titles_by_url[url] = titles_from_url
            if titles_from_url: all_recommended_titles.update(titles_from_url)
            else: logging.info(f"No titles extracted from {url} (but fetch was successful).")
        else: logging.warning(f"Fetch or parsing failed for {url}. No titles added.")
    if not all_recommended_titles: logging.warning("No valid recommended titles found in any accessible URLs.")
    else: logging.info(f"Total: Found {len(all_recommended_titles)} unique cleaned recommended titles from all accessible URLs.")
    return all_recommended_titles, titles_by_url

# --- DAT Filtering and Writing Function ---
# Removed 'args' parameter
def filter_dat_file(input_dat_path, output_dat_path, all_recommended_titles, titles_by_url, similarity_threshold):
    """Filters the DAT file based on best match per web title, generates reports, updates header."""
    # Initial checks and DAT parsing
    if not os.path.exists(input_dat_path): logging.critical(f"Input file '{input_dat_path}' does not exist."); return False
    if all_recommended_titles is None: logging.critical("Cannot proceed, error fetching recommended titles."); return False
    if not all_recommended_titles: logging.warning("No valid web titles found for comparison...");
    logging.info(f"Reading and parsing DAT file: {input_dat_path}")
    try:
        tree = ET.parse(input_dat_path); root = tree.getroot()
        if root.tag != 'datafile': logging.critical(f"Input DAT file '{input_dat_path}' has wrong root '<{root.tag}>'. Aborting."); return False
        logging.debug(f"Successfully parsed DAT file. Root element is '<{root.tag}>'.")
    except ET.ParseError as parse_err: logging.critical(f"Error parsing DAT file '{input_dat_path}': {parse_err}"); return False
    except Exception as e: logging.exception(f"Unexpected error during DAT file reading/parsing:"); return False

    # Header Processing
    logging.info("Processing and updating header information...")
    # ... (Identical Header processing logic) ...
    original_header_element = root.find('header'); new_header = ET.Element('header'); today_date = datetime.date.today().strftime('%Y-%m-%d')
    original_name_text = "Unknown System"; original_description_text = "Unknown DAT"; elements_to_copy = []
    if original_header_element is not None:
        logging.debug("Found existing <header> element.")
        name_el = original_header_element.find('name'); desc_el = original_header_element.find('description')
        if name_el is not None and name_el.text: original_name_text = name_el.text.strip()
        if desc_el is not None and desc_el.text: original_description_text = desc_el.text.strip()
        logging.debug(f" Original Name: '{original_name_text}', Original Description: '{original_description_text}'")
        tags_to_copy = ['version', 'date', 'author', 'homepage', 'url', 'retool', 'clrmamepro', 'comment']
        manual_tags = ['name', 'description', 'version', 'date', 'author', 'homepage']
        for child in original_header_element:
            if child.tag in tags_to_copy and child.tag not in manual_tags:
                 logging.debug(f" Copying header tag: <{child.tag}>"); elements_to_copy.append({'tag': child.tag, 'text': child.text, 'attrib': child.attrib})
    else: logging.warning("No <header> element found in input DAT.")
    processed_name = re.sub(r'\s*\([^)]*\)$', '', original_name_text).strip()
    ET.SubElement(new_header, 'name').text = f"{processed_name} (VREC DAT Filter)"; ET.SubElement(new_header, 'description').text = f"{original_description_text} (VREC DAT Filter)"
    ET.SubElement(new_header, 'version').text = SCRIPT_VERSION; ET.SubElement(new_header, 'date').text = today_date
    ET.SubElement(new_header, 'author').text = SCRIPT_AUTHOR; ET.SubElement(new_header, 'homepage').text = SCRIPT_HOMEPAGE
    for element_data in elements_to_copy: ET.SubElement(new_header, element_data['tag'], attrib=element_data['attrib']).text = element_data['text']
    logging.debug("Constructed new header.")

    # --- STAGE 1: Find only HIGH-scoring potential matches ---
    logging.info(f"Finding potential matches >= {similarity_threshold}% (Algorithm: WRatio)...")
    matches_per_web_title = {}
    all_game_elements = root.findall('.//game'); original_game_count = len(all_game_elements)
    if original_game_count == 0: logging.warning("No <game> elements found in the input DAT file.")
    game_iterator_stage1 = tqdm(all_game_elements, desc="Finding Matches", unit=" game", ncols=100, leave=False, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]')
    for game_element in game_iterator_stage1:
        dat_title_original = game_element.get('name'); cleaned_dat_title = clean_title_for_comparison(dat_title_original)
        if not dat_title_original or not cleaned_dat_title: continue
        for recommended_title in all_recommended_titles:
            try:
                similarity = fuzz.WRatio(cleaned_dat_title, recommended_title)
                if similarity >= similarity_threshold:
                    logging.debug(f"  Storing HIGH potential match for Web '{recommended_title}': DAT '{dat_title_original}' (Score: {similarity}%)")
                    match_info = (similarity, game_element); matches_per_web_title.setdefault(recommended_title, []).append(match_info)
            except Exception as fuzz_error: logging.error(f"Error during WRatio comparison between DAT:'{cleaned_dat_title}' and WEB:'{recommended_title}': {fuzz_error}")
    logging.info(f"Found high-scoring potential matches for {len(matches_per_web_title)} unique web titles.")

    # --- STAGE 2: Select best match for each web title and handle multi-discs ---
    final_filtered_games_dict = {}; matched_web_titles_with_selected_games = set()
    logging.info("Selecting best automatic match for each recommended title...")
    web_title_iterator_stage2 = tqdm(matches_per_web_title.items(), desc="Selecting Best", unit=" web title", ncols=100, leave=False)
    for recommended_title, potential_matches in web_title_iterator_stage2:
        logging.debug(f"Processing Web '{recommended_title}', potential DAT matches: { [(s, e.get('name')) for s, e in potential_matches] }")
        if not potential_matches: continue
        sorted_matches = sorted(potential_matches, key=lambda item: item[0], reverse=True)
        logging.debug(f" -> Sorted potential matches: { [(s, e.get('name')) for s, e in sorted_matches] }")
        best_match_score, best_match_element = sorted_matches[0]; best_match_name = best_match_element.get('name')
        logging.debug(f" -> Best match for Web '{recommended_title}' is DAT '{best_match_name}' (Score: {best_match_score}%)")
        games_to_keep_for_this_web_title = set([best_match_element])
        if is_disc_1_regex.search(best_match_name):
            logging.debug(f" -> '{best_match_name}' looks like Disc 1. Checking for other discs...")
            best_match_base = get_name_without_disc_info(best_match_name)
            logging.debug(f"    Base name for multi-disc check: '{best_match_base}'")
            for other_score, other_element in sorted_matches[1:]:
                 if other_score < similarity_threshold: continue
                 other_name = other_element.get('name')
                 if is_disc_n_regex.search(other_name):
                     other_base = get_name_without_disc_info(other_name)
                     logging.debug(f"    Comparing base '{other_base}' from '{other_name}' (Score: {other_score}%)")
                     if best_match_base == other_base:
                         games_to_keep_for_this_web_title.add(other_element)
                         logging.debug(f"    -> Also selecting multi-disc match: '{other_name}'")
        added_new_for_web_title = False
        for game_element_to_keep in games_to_keep_for_this_web_title:
             game_name = game_element_to_keep.get('name')
             if game_name not in final_filtered_games_dict:
                 final_filtered_games_dict[game_name] = game_element_to_keep; logging.debug(f" -> Added DAT game '{game_name}' to final list (Stage 2)."); added_new_for_web_title = True
             else: logging.debug(f" -> DAT game '{game_name}' was already added to final list."); added_new_for_web_title = True
        if added_new_for_web_title:
             matched_web_titles_with_selected_games.add(recommended_title); logging.debug(f" -> Marked Web '{recommended_title}' as having selected game(s) (Stage 2).")
    logging.info(f"Completed automatic best match selection. Found {len(final_filtered_games_dict)} games.")

    # --- NO STAGE 3 Interactive Review in this version ---

    # --- Final calculations based on Stage 2 results ---
    filtered_games = list(final_filtered_games_dict.values())
    total_matched_dat_games = len(filtered_games)
    total_unmatched_dat_games = original_game_count - total_matched_dat_games
    global_unmatched_recommended_titles = all_recommended_titles - matched_web_titles_with_selected_games # Based on stage 2 results
    logging.info(f"Final selected game count: {total_matched_dat_games}")

    # --- Write Filtered DAT File ---
    new_root = ET.Element('datafile'); new_root.append(new_header);
    for game in filtered_games: new_root.append(game)
    new_tree = ET.ElementTree(new_root); logging.info(f"Writing filtered DAT file to: {output_dat_path}")
    reread_count = -1
    try:
        ET.indent(new_tree, space="\t", level=0)
        with open(output_dat_path, 'w', encoding='utf-8') as f: new_tree.write(f, encoding='unicode', xml_declaration=True, short_empty_elements=True)
        logging.debug(f"Successfully wrote filtered DAT to {output_dat_path}")
        # Confirmation Read Block
        logging.info("Confirming entry count in output file...")
        try:
            reread_tree = ET.parse(output_dat_path); reread_root = reread_tree.getroot()
            if reread_root.tag != 'datafile': logging.error(f"Re-read validation failed...")
            else: reread_games = reread_root.findall('.//game'); reread_count = len(reread_games); logging.debug(f"Re-read successful. Found {reread_count} <game> elements.")
        except ET.ParseError as parse_err: logging.error(f"Failed to re-parse output file...: {parse_err}")
        except IOError as io_err: logging.error(f"Failed to re-open output file...: {io_err}")
        except Exception as reread_err: logging.exception("Unexpected error during output file count confirmation:")
    except IOError as e: logging.critical(f"Error writing filtered DAT file '{output_dat_path}': {e}"); reread_count = -1
    except Exception as e: logging.exception(f"Unexpected error during file writing or confirmation for '{output_dat_path}':"); reread_count = -1

    # --- Write Multiple CSV Files ---
    csv_files_created = []; output_dir = os.path.dirname(os.path.abspath(output_dat_path)); url_counter = 0
    logging.info("Checking for unmatched web titles to generate CSV reports...")
    if titles_by_url:
        for url, titles_from_this_url in titles_by_url.items():
            if titles_from_this_url is None: continue
            url_counter += 1
            # Use global_unmatched_recommended_titles calculated after Stage 2
            unmatched_for_this_url = titles_from_this_url.intersection(global_unmatched_recommended_titles)
            logging.debug(f"URL: {url} - Found {len(titles_from_this_url)} titles, {len(unmatched_for_this_url)} are unmatched.")
            if unmatched_for_this_url:
                try:
                    url_path = urllib.parse.urlparse(url).path; path_parts = [part for part in url_path.strip('/').split('/') if part and part.lower() != 'wiki']
                    if path_parts: base_name_url = '_'.join(path_parts)
                    else: base_name_url = f'url_{url_counter}'
                    sanitized_name = re.sub(r'[^\w.-]+', '_', base_name_url).strip('_');
                    if not sanitized_name: sanitized_name = f"url_{url_counter}"
                    csv_filename = f"{sanitized_name}_unmatched.csv"; full_csv_path = os.path.join(output_dir, csv_filename)
                    logging.info(f"Writing CSV for unmatched titles from {url} -> '{csv_filename}' ({len(unmatched_for_this_url)} titles)...")
                    with open(full_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                        writer = csv.writer(csvfile); writer.writerow([f'Unmatched Recommended Title from {url}']) # Simpler header
                        for title in sorted(list(unmatched_for_this_url)): writer.writerow([title])
                    csv_files_created.append(csv_filename)
                except Exception as e: logging.exception(f"Error creating/writing CSV for {url} to {full_csv_path}:")
    # --- Final CSV Summary Message ---
    if not all_recommended_titles: logging.warning("No valid web titles found initially, no CSV files created.")
    elif not titles_by_url: logging.warning("No URL data available to generate CSV files.")
    elif not csv_files_created:
        if not global_unmatched_recommended_titles: logging.info("All valid web titles found resulted in a kept game match, no CSV files needed or created.")
        else: logging.warning("Some web titles remain unmatched, but no CSV files were created (check logs for writing errors).")
    elif csv_files_created: logging.info(f"Created {len(csv_files_created)} CSV file(s) with unmatched titles in '{output_dir}'.")

    # --- Final Report ---
    logging.info("--- Final Operation Summary ---")
    logging.info(f"{'Input DAT File:':<30} {input_dat_path}"); logging.info(f"{'Output DAT File:':<30} {output_dat_path}")
    logging.info(f"{'Total Games in Original DAT:':<30} {original_game_count:>7}")
    logging.info("Recommended Titles (Web Sources):")
    if titles_by_url:
        max_url_len = max(len(url) for url in titles_by_url.keys()) if titles_by_url else 0
        for url, titles in titles_by_url.items():
            count_str = str(len(titles)) if titles is not None else "Fetch Error"; status = "found" if titles is not None else "error"
            logging.info(f"- URL: {url:<{max_url_len}} -> {count_str} cleaned titles {status}")
    total_web_titles_str = str(len(all_recommended_titles)) if all_recommended_titles is not None else 'Error'
    logging.info(f"{'Total Unique Web Titles (cleaned):':<30} {total_web_titles_str:>7}")
    logging.info(f"{'Similarity Threshold Used:':<30} {similarity_threshold}%"); logging.info(f"{'Comparison Algorithm:':<30} WRatio")
    # Removed interactive review line from summary
    logging.info("DAT Filtering Results:")
    logging.info(f"{'- Matching Games Kept:':<30} {total_matched_dat_games:>7} (After best match selection)") # Simplified description
    logging.info(f"{'- Games Removed/Not Selected:':<30} {total_unmatched_dat_games:>7}")
    logging.info("Web Titles vs DAT Comparison:")
    logging.info(f"{'- Web Titles Matched (Game Kept):':<30} {len(matched_web_titles_with_selected_games):>7}")
    logging.info(f"{'- Web Titles NOT Matched (No Game Kept):':<30} {len(global_unmatched_recommended_titles):>7}")
    logging.info("--------------------------------")
    # Confirmation Count Output
    if reread_count != -1:
        level = logging.INFO if reread_count == total_matched_dat_games else logging.WARNING
        logging.log(level, f"Confirmation: Counted {reread_count} <game> entries in '{os.path.basename(output_dat_path)}'.")
        if reread_count != total_matched_dat_games: logging.warning(f"Re-read count ({reread_count}) differs from final filtered count ({total_matched_dat_games}).")
    else: logging.warning("Could not confirm final game count due to an error during file writing or re-parsing.")
    logging.info("Operation completed."); return True

# --- Main execution block ---
if __name__ == "__main__":
    # Setup Argparse
    parser = argparse.ArgumentParser(
        description="Filters a DAT/XML file based on recommended titles scraped from web pages (using 'wikitable' structure). Selects best match per web title using WRatio. Creates a filtered DAT and optional CSV reports for unmatched web titles.", # Removed interactive review part
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=f"Version: {SCRIPT_VERSION} by {SCRIPT_AUTHOR}. Homepage: {SCRIPT_HOMEPAGE}"
    )
    # Removed --interactive-review argument
    parser.add_argument("input_file", help="Path to the input .dat file (XML format, expected root <datafile>).")
    parser.add_argument("output_file", nargs='?', default=None, help="Path for the filtered DAT output file (optional). Default: '[input_filename]_filtered.dat'.")
    parser.add_argument("-u", "--urls", nargs='+', required=True, help="One or more base URLs of web pages containing recommended titles in 'wikitable' HTML tables (title expected in the second column).")
    parser.add_argument("-t", "--threshold", type=int, default=90, choices=range(0, 101), metavar="[0-100]", help="Similarity percentage threshold (0-100) for fuzzy matching (using WRatio). Default: 90.")
    parser.add_argument("--check-homebrew", "-hb", action='store_true', help="Automatically check for and include '/Homebrew' suffixed URLs based on provided URLs.")
    parser.add_argument("--check-japan", "-j", action='store_true', help="Automatically check for and include '/Japan' suffixed URLs based on provided URLs.")
    parser.add_argument( "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Set the logging level for console output.")
    parser.add_argument( "--log-file", default=None, help="Path to an optional file to write logs to (all levels DEBUG and above).")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {SCRIPT_VERSION}")

    # Parse Arguments
    try: args = parser.parse_args()
    except SystemExit as e: sys.exit(e.code)
    except Exception as e: print(f"CRITICAL ERROR during argument parsing: {e}", file=sys.stderr); sys.exit(1)

    # --- Logging Setup ---
    log_level_console = getattr(logging, args.log_level.upper(), logging.INFO); console_log_format = '%(levelname)s: %(message)s'; file_log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logger = logging.getLogger(); logger.setLevel(logging.DEBUG);
    if logger.hasHandlers(): logger.handlers.clear()
    coloredlogs.install(level=log_level_console, logger=logger, fmt=console_log_format, stream=sys.stderr)
    if args.log_file:
        try:
            log_dir = os.path.dirname(args.log_file);
            if log_dir and not os.path.exists(log_dir): os.makedirs(log_dir); logging.info(f"Created directory for log file: {log_dir}")
            file_handler = logging.FileHandler(args.log_file, mode='w', encoding='utf-8'); file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(file_log_format)); logger.addHandler(file_handler)
            logging.info(f"Logging detailed output (DEBUG level and above) to: {args.log_file}")
        except IOError as e: logging.error(f"Could not open log file {args.log_file} for writing: {e}", exc_info=False)
        except OSError as e: logging.error(f"Could not create directory for log file {args.log_file}: {e}", exc_info=False)

    # --- Conditional URL Expansion ---
    user_urls = args.urls; expanded_urls = set(user_urls); logging.debug(f"Initial URLs provided: {user_urls}")
    if args.check_homebrew:
        logging.info("Checking for '/Homebrew' URL variants...")
        homebrew_variants = set();
        for base_url in user_urls:
            if not base_url.lower().rstrip('/').endswith('/homebrew'): hb_url = base_url.rstrip('/') + "/Homebrew"; homebrew_variants.add(hb_url); logging.debug(f" Adding Homebrew variant: {hb_url}")
        expanded_urls.update(homebrew_variants)
    if args.check_japan:
        logging.info("Checking for '/Japan' URL variants...")
        japan_variants = set();
        for base_url in user_urls:
            if not base_url.lower().rstrip('/').endswith('/japan'): jp_url = base_url.rstrip('/') + "/Japan"; japan_variants.add(jp_url); logging.debug(f" Adding Japan variant: {jp_url}")
        expanded_urls.update(japan_variants)
    final_urls_to_fetch = sorted(list(expanded_urls))
    if len(final_urls_to_fetch) > len(user_urls):
        logging.info(f"Final list includes expanded URLs ({len(final_urls_to_fetch)} total):");
        for u in final_urls_to_fetch: logging.debug(f"  - {u}")
    else: logging.info(f"Processing only the provided URLs ({len(final_urls_to_fetch)} total).")

    # --- Determine Output DAT Path ---
    try:
        input_path = args.input_file
        if not os.path.isfile(input_path): logging.critical(f"Specified input path is not a file or does not exist: {input_path}"); sys.exit(1)
        input_dir = os.path.dirname(os.path.abspath(input_path)); base_name, _ = os.path.splitext(os.path.basename(input_path))
        if args.output_file:
            output_dat_path = args.output_file
            output_dir_specified = os.path.dirname(os.path.abspath(output_dat_path))
            if output_dir_specified and not os.path.exists(output_dir_specified):
                 try: os.makedirs(output_dir_specified); logging.info(f"Created output directory: {output_dir_specified}")
                 except OSError as e: logging.critical(f"Could not create output directory '{output_dir_specified}': {e}"); sys.exit(1)
        else: output_dat_path = os.path.join(input_dir, f"{base_name}_filtered.dat")
        output_dat_path = os.path.abspath(output_dat_path)
    except Exception as e: logging.critical(f"Error during path determination: {e}", exc_info=True); sys.exit(1)

    # --- Log Initial Info ---
    logging.info(f"Input File:                {os.path.abspath(input_path)}")
    logging.info(f"Output DAT File (planned): {output_dat_path}")
    logging.info(f"Similarity Threshold:      {args.threshold}%")
    # Removed interactive review log line

    # --- Execute Main Logic ---
    all_titles, titles_by_url = fetch_all_titles(final_urls_to_fetch)
    if all_titles is not None:
        try:
            # Removed 'args' pass to filter_dat_file
            success = filter_dat_file( input_path, output_dat_path, all_titles, titles_by_url, args.threshold )
            if not success: logging.critical("Filtering process reported an error. Please check logs."); sys.exit(1)
        except Exception as e: logging.exception("CRITICAL ERROR during filter_dat_file execution:"); sys.exit(1)
    else: logging.critical("Cannot proceed with filtering due to critical errors during title fetching."); sys.exit(1)
    sys.exit(0)
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

# --- Define color constants ---
C_INFO = Fore.CYAN
C_SUCCESS = Fore.GREEN
C_WARNING = Fore.YELLOW
C_ERROR = Fore.RED
C_LABEL = Style.BRIGHT
C_RESET = Style.RESET_ALL
C_DIM = Style.DIM
C_NORMAL = Style.NORMAL

# Initialize colorama
init(autoreset=True)

# --- Functions ---

def fetch_single_url_titles(url):
    """Downloads a single web page and extracts recommended game titles."""
    # Message printed by caller upon successful fetch only
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
    except requests.exceptions.HTTPError as http_err:
        # Specific handling for 404 Not Found (relevant for optional URLs)
        if http_err.response.status_code == 404:
            print(f"{C_DIM}Info: URL not found (404), skipping: {url}")
            return None # Return None silently for 404
        else:
            # Print other HTTP errors
            print(f"{C_ERROR}Warning: HTTP Error {http_err.response.status_code} fetching {url}: {http_err}", file=sys.stderr)
            return None
    except requests.exceptions.RequestException as e:
        # Handle other request errors
        print(f"{C_ERROR}Warning: Network/Request Error fetching {url}: {e}", file=sys.stderr)
        return None

    # Fetch was successful (status 200 OK)
    print(f"{C_INFO}Processing successful fetch from: {url}")
    try:
        soup = BeautifulSoup(response.content, 'lxml')
        titles = set()
        tables = soup.find_all('table', class_='wikitable')
        if not tables:
            print(f"{C_WARNING}Warning: No 'wikitable' table found on {url}.", file=sys.stderr)
        else:
             table_index = 0
             for table in tables:
                table_index += 1
                rows = table.find_all('tr')
                for row in rows[1:]: # Skip main table header row
                    try:
                        # Find both data and header cells within the row
                        cells = row.find_all(['td', 'th'])
                        # Title is in the second cell (index 1)
                        if len(cells) > 1:
                            title_text = cells[1].get_text(strip=True)
                            # Clean potential region tags like [USA] etc. from web source
                            cleaned_title_block = re.sub(r'\[.*?\]', '', title_text).strip()
                            # Handle potential alternate titles separated by <br/> (newline)
                            title_lines = [line.strip() for line in cleaned_title_block.split('\n') if line.strip()]
                            if title_lines:
                                for final_title in title_lines: # Add all non-empty lines
                                    if final_title:
                                        titles.add(final_title)
                    except Exception as row_error:
                        # Log error parsing a specific row but continue
                        print(f"{C_ERROR}ERROR parsing a row in URL {url}: {row_error}", file=sys.stderr)
        print(f"Found {C_SUCCESS}{len(titles)}{C_NORMAL} unique titles on {url}.")
        return titles # Return the set (might be empty)
    except Exception as e:
        # Handle errors during HTML parsing phase
        print(f"{C_ERROR}Warning: Error during HTML parsing of URL {url}: {e}", file=sys.stderr)
        traceback.print_exc()
        return None # Indicate failure

def fetch_all_titles(url_list):
    """Downloads and combines titles from a list of URLs, tracking source."""
    all_recommended_titles = set() # Combined set of all unique titles found
    titles_by_url = {} # Dictionary mapping URL -> set of titles from that URL
    processed_urls = set() # Avoid reprocessing identical URLs

    if not url_list:
        print(f"{C_ERROR}No URLs provided for fetching.", file=sys.stderr)
        return set(), {} # Return empty structures

    print(f"\n{C_INFO}Starting title fetching from URLs...")
    # Iterate through URLs with a progress bar
    for url in tqdm(url_list, desc=f"{C_INFO}Scanning URLs{C_NORMAL}", unit="URL ", ncols=100):
        if url in processed_urls: continue # Skip if already seen

        titles_from_url = fetch_single_url_titles(url) # Fetch and parse
        processed_urls.add(url)

        # Only process if fetch didn't have critical error (returned None)
        if titles_from_url is not None: # Empty set is okay (page exists, no titles found)
             titles_by_url[url] = titles_from_url
             if titles_from_url: # Update combined set only if titles were found
                 all_recommended_titles.update(titles_from_url)

    print() # Newline after progress bar
    if not all_recommended_titles:
        print(f"{C_WARNING}Warning: No valid recommended titles found in any accessible URLs.", file=sys.stderr)
        return set(), titles_by_url # Return empty set, possibly non-empty dict
    else:
        print(f"\n{C_SUCCESS}Total: Found {len(all_recommended_titles)} unique recommended titles from all accessible URLs.")
        return all_recommended_titles, titles_by_url

def filter_dat_file(input_dat_path, output_dat_path, all_recommended_titles, titles_by_url, similarity_threshold):
    """Filters the DAT file, generates report, and writes multiple CSV files (one per URL)."""
    # Initial checks
    if not os.path.exists(input_dat_path):
        print(f"{C_ERROR}Error: Input file '{input_dat_path}' does not exist.", file=sys.stderr); return False
    if all_recommended_titles is None: # Critical fetch error occurred
         print(f"{C_ERROR}Error: Cannot proceed, error fetching recommended titles.", file=sys.stderr); return False
    if not all_recommended_titles: # No web titles found, but no critical error
        print(f"\n{C_WARNING}Warning: No valid web titles found for comparison, output DAT file will be empty.")

    # Read and Parse DAT
    print(f"\n{C_INFO}Reading and parsing DAT file: {input_dat_path}")
    try:
        original_header_lines = []
        with open(input_dat_path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped_line = line.strip();
                if stripped_line.startswith('<datafile>'): break
                original_header_lines.append(line)
            if stripped_line.startswith('<datafile>'): original_header_lines.append(line)
        tree = ET.parse(input_dat_path); root = tree.getroot()
    except Exception as e:
        print(f"{C_ERROR}Unexpected error during DAT file reading/parsing: {e}", file=sys.stderr); traceback.print_exc(); return False

    # Initialize results
    filtered_games_elements = {} # Use dict {original_dat_name: game_element} to handle duplicates
    matched_recommended_titles = set() # Set of web titles that got at least one match

    print(f"{C_INFO}Filtering games (Threshold: {similarity_threshold}%, Algorithm: token_set_ratio)...")
    original_header_element = root.find('header')
    all_game_elements = root.findall('game')
    original_game_count = len(all_game_elements)

    # Filtering loop with Progress Bar
    for game_element in tqdm(all_game_elements,
                             desc=f"{C_INFO}Filtering{C_NORMAL}",
                             unit=" game",
                             ncols=100,
                             bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
                            ):
        dat_title_original = game_element.get('name')
        if not dat_title_original: continue # Skip game if no name attribute

        # Clean DAT title (remove (...) and [...] tags)
        cleaned_dat_title = re.sub(r'\s*\([^)]*\)', '', dat_title_original)
        cleaned_dat_title = re.sub(r'\s*\[[^]]*\]', '', cleaned_dat_title)
        cleaned_dat_title = cleaned_dat_title.strip()

        # Compare cleaned DAT title against all unique web titles if available
        if all_recommended_titles and cleaned_dat_title:
            for recommended_title in all_recommended_titles:
                # Use token_set_ratio (good for subset matching like Title vs Title+Subtitle)
                similarity = fuzz.token_set_ratio(cleaned_dat_title, recommended_title)
                if similarity >= similarity_threshold:
                    # If matched, store the *original* game element using original name as key
                    if dat_title_original not in filtered_games_elements:
                         filtered_games_elements[dat_title_original] = game_element
                    # Add the web title that caused the match to the set of matched web titles
                    matched_recommended_titles.add(recommended_title)
                    # NOTE: No 'break' here - allows multiple web titles to match the same DAT game
                    # and ensures all matched web titles are correctly recorded

    print() # Newline after progress bar
    print(f"{C_SUCCESS}Filtering complete.")

    # --- Write Filtered DAT File ---
    filtered_games = list(filtered_games_elements.values()) # Get the unique game elements
    new_root = ET.Element('datafile')
    if original_header_element is not None: new_root.append(original_header_element)
    for game in filtered_games: new_root.append(game) # Add filtered games
    new_tree = ET.ElementTree(new_root)
    print(f"{C_INFO}Writing filtered DAT file to: {output_dat_path}")
    try:
        ET.indent(new_tree, space="\t", level=0) # Pretty print XML
        with open(output_dat_path, 'wb') as f:
             # Write original header lines (DOCTYPE etc.)
             for line in original_header_lines:
                 if not line.strip().startswith('<datafile>'): f.write(line.encode('utf-8'))
             # Write the main XML tree
             new_tree.write(f, encoding='utf-8', xml_declaration=False)
    except IOError as e:
        print(f"{C_ERROR}Error writing filtered DAT file: {e}", file=sys.stderr)

    # --- Write Multiple CSV Files ---
    csv_files_created = []
    output_dir = os.path.dirname(output_dat_path) # Save CSVs in the same dir as the output DAT
    url_counter = 0 # Fallback counter for naming
    print() # Blank line before CSV messages

    if titles_by_url: # Check if the dictionary has entries
        for url, titles_from_this_url in titles_by_url.items():
            # Skip URLs that had fetch errors (titles_from_this_url is None)
            if titles_from_this_url is None: continue

            url_counter += 1
            # Find titles from *this* specific URL that are not in the globally matched set
            unmatched_for_this_url = titles_from_this_url - matched_recommended_titles

            if unmatched_for_this_url: # Only create CSV if there are unmatched titles for this URL
                try:
                    # Generate filename based on URL path parts after '/wiki/'
                    url_path = urllib.parse.urlparse(url).path
                    path_parts = [part for part in url_path.split('/') if part and part.lower() != 'wiki']
                    if path_parts:
                        base_name_url = '_'.join(path_parts) # e.g., PlayStation_Japan
                    else: # Fallback name if path parsing fails
                        base_name_url = f'url_{url_counter}'
                    # Sanitize filename (allow alphanum, underscore, hyphen, dot)
                    sanitized_name = re.sub(r'[^\w.-]+', '_', base_name_url).strip('_')
                    if not sanitized_name: sanitized_name = f"url_{url_counter}" # Final fallback
                    csv_filename = f"{sanitized_name}_unmatched.csv"
                    full_csv_path = os.path.join(output_dir, csv_filename)

                    print(f"{C_INFO}Writing CSV for {url} -> {C_LABEL}{csv_filename}{C_NORMAL} ({len(unmatched_for_this_url)} titles)...")
                    # Write the CSV file
                    with open(full_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow([f'Unmatched Recommended Title from {url}']) # Header
                        for title in sorted(list(unmatched_for_this_url)): # Write sorted titles
                            writer.writerow([title])
                    csv_files_created.append(csv_filename) # Track created files
                except Exception as e:
                    print(f"{C_ERROR}Error creating/writing CSV for {url}: {e}", file=sys.stderr)

    # --- Final CSV Summary Message ---
    if not all_recommended_titles:
        print(f"{C_WARNING}No valid web titles found initially, no CSV files created.")
    elif not csv_files_created:
        # Check if this is because all titles actually matched
        all_titles_were_matched = True
        if titles_by_url:
            for url, titles_from_this_url in titles_by_url.items():
                 if titles_from_this_url is not None and bool(titles_from_this_url - matched_recommended_titles):
                     all_titles_were_matched = False; break
        if all_titles_were_matched:
            print(f"{C_SUCCESS}All valid web titles found had a match in the DAT, no CSV files created.")
        else: # Should only happen if writing failed for all non-matched sets
             print(f"{C_WARNING}Some web titles did not find a match, but an error occurred writing their CSV file(s).")
    elif csv_files_created:
         print(f"{C_SUCCESS}Created {len(csv_files_created)} CSV file(s) with unmatched titles.")


    # --- Final Report Section ---
    total_matched_dat_games = len(filtered_games) # Use count of unique elements added
    total_unmatched_dat_games = original_game_count - total_matched_dat_games
    # Global unmatched count for report summary
    global_unmatched_recommended_titles = all_recommended_titles - matched_recommended_titles if all_recommended_titles else set()

    print(f"\n{C_LABEL}--- Operation Summary ---{C_NORMAL}")
    # Use f-string alignment: <28 means left-aligned in 28 chars, >7 means right-aligned in 7 chars
    print(f"{'Input DAT File:':<28} {input_dat_path}")
    print(f"{'Output DAT File:':<28} {output_dat_path}")
    print(f"{'Total Games in DAT:':<28} {original_game_count:>7}")

    print(f"\n{C_LABEL}Recommended Titles (Web):{C_NORMAL}")
    if titles_by_url:
        # Find max URL length for alignment
        max_url_len = max(len(url) for url in titles_by_url.keys()) if titles_by_url else 0
        for url, titles in titles_by_url.items():
            # Display count or error status for each URL checked
            count_str = str(len(titles)) if titles is not None else f"{C_ERROR}Fetch Error{C_NORMAL}"
            color = C_SUCCESS if titles is not None and len(titles)>0 else C_WARNING if titles is not None else C_ERROR
            print(f"- URL: {url:<{max_url_len}} -> {color}{count_str}{C_NORMAL} titles found")
    total_web_titles_str = str(len(all_recommended_titles)) if all_recommended_titles is not None else 'Error'
    print(f"{'Total Unique Web Titles:':<28} {C_SUCCESS if all_recommended_titles else C_ERROR}{total_web_titles_str:>7}{C_NORMAL}")

    print(f"\n{C_LABEL}Similarity Threshold Used:{C_NORMAL} {similarity_threshold}%")
    print(f"{C_LABEL}Comparison Algorithm:{C_NORMAL}   token_set_ratio") # Reflects the algorithm used

    print(f"\n{C_LABEL}DAT Filtering Results:{C_NORMAL}")
    print(f"{'- Matching Games:':<28} {C_SUCCESS}{total_matched_dat_games:>7}{C_NORMAL}")
    print(f"{'- Non-Matching Games:':<28} {C_WARNING}{total_unmatched_dat_games:>7}{C_NORMAL}")

    print(f"\n{C_LABEL}Web Titles vs DAT Comparison:{C_NORMAL}")
    print(f"{'- Web Titles Matched in DAT:':<28} {C_SUCCESS}{len(matched_recommended_titles):>7}{C_NORMAL}")
    # Use global count for summary report
    unmatched_color = C_WARNING if global_unmatched_recommended_titles else C_SUCCESS
    print(f"{'- Web Titles NOT Matched:':<28} {unmatched_color}{len(global_unmatched_recommended_titles):>7}{C_NORMAL}")
    print(f"{C_LABEL}-----------------------------{C_NORMAL}\n")

    print(f"\n{C_SUCCESS}Operation completed.")
    return True


# --- Main execution block ---
if __name__ == "__main__":
    # Setup Argparse
    parser = argparse.ArgumentParser(
        description="Filters a DAT/XML file based on web titles. Optional DAT and CSV outputs.", # English description
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # Positional Arguments
    parser.add_argument("input_file",
                        help="Path to the input .dat file (or .xml/.txt containing XML) (required).")
    parser.add_argument("output_file", nargs='?', default=None,
                        help="Path for the filtered DAT output file (optional). Default: '[input]_filtered.dat'.")
    # Optional Flag Arguments
    parser.add_argument("-u", "--urls", nargs='+', required=True,
                        help="One or more base URLs of web pages with recommended titles.") # Updated help
    parser.add_argument("-t", "--threshold", type=int, default=90, choices=range(0, 101), metavar="[0-100]",
                        help="Similarity percentage threshold (0-100). Default: 90.")
    parser.add_argument("--check-homebrew", "-hb", action='store_true',
                        help="Automatically check for and include '/Homebrew' suffixed URLs.")
    parser.add_argument("--check-japan", "-j", action='store_true',
                        help="Automatically check for and include '/Japan' suffixed URLs.")
    # --csv_output argument removed

    # Parse Arguments
    try:
        args = parser.parse_args()
    except Exception as e:
        print(f"{C_ERROR}CRITICAL ERROR during argument parsing: {e}", file=sys.stderr)
        sys.exit(1)

    # --- URL Expansion (Conditional) ---
    user_urls = args.urls
    expanded_urls = set(user_urls) # Start with user-provided URLs

    print() # Blank line

    # Check if Homebrew flag is set
    if args.check_homebrew:
        print(f"{C_INFO}Checking for '/Homebrew' URL variants...")
        homebrew_variants = set()
        for base_url in user_urls:
            homebrew_variants.add(base_url.rstrip('/') + "/Homebrew")
        expanded_urls.update(homebrew_variants)

    # Check if Japan flag is set
    if args.check_japan:
        print(f"{C_INFO}Checking for '/Japan' URL variants...")
        japan_variants = set()
        for base_url in user_urls:
            japan_variants.add(base_url.rstrip('/') + "/Japan")
        expanded_urls.update(japan_variants)

    # Final list of URLs to actually fetch
    final_urls_to_fetch = sorted(list(expanded_urls))

    # Print info about final list only if different from original
    if len(final_urls_to_fetch) > len(user_urls):
         print(f"{C_INFO}Final list includes expanded URLs ({len(final_urls_to_fetch)} total):")
         for u in final_urls_to_fetch: print(f"{C_DIM}  - {u}")
    else:
         print(f"{C_INFO}Processing only the provided URLs ({len(final_urls_to_fetch)} total).")
    # --- End URL Expansion ---

    # Determine Output DAT Path
    try:
        input_path = args.input_file
        if not os.path.exists(input_path):
             print(f"{C_ERROR}CRITICAL ERROR: Specified input file does not exist: {input_path}", file=sys.stderr); sys.exit(1)
        input_dir = os.path.dirname(os.path.abspath(input_path))
        base_name, _ = os.path.splitext(os.path.basename(input_path))
        if args.output_file:
            output_dat_path = args.output_file
        else: # Default output DAT path
            output_dat_path = os.path.join(input_dir, f"{base_name}_filtered.dat")
        # final_csv_path is determined inside filter_dat_file now
    except Exception as e:
        print(f"{C_ERROR}CRITICAL ERROR during path determination: {e}", file=sys.stderr); traceback.print_exc(); sys.exit(1)

    # Print Initial Info
    print(f"\n{C_LABEL}Input File:{C_NORMAL} {input_path}")
    print(f"{C_LABEL}Output DAT File (planned):{C_NORMAL} {output_dat_path}")

    # Execute Main Logic: Fetch Titles then Filter DAT
    all_titles, titles_by_url = fetch_all_titles(final_urls_to_fetch)

    # Proceed only if fetch didn't return critical error (None)
    if all_titles is not None:
        try:
            # Call the main filtering function
            filter_dat_file(
                input_path,
                output_dat_path,
                all_titles, # Pass the set of web titles (can be empty)
                titles_by_url, # Pass the dict mapping URL to its titles
                args.threshold
            )
        except Exception as e: # Catch unexpected errors during filtering
             print(f"\n{C_ERROR}CRITICAL ERROR during filter_dat_file execution: {e}", file=sys.stderr); traceback.print_exc(); sys.exit(1)
    else: # Critical error during fetch_all_titles
        print(f"{C_ERROR}Cannot proceed with filtering due to critical errors during title fetching.", file=sys.stderr); sys.exit(1)

    # End of script execution
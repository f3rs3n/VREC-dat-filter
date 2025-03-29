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

# Initialize colorama (for Windows compatibility and autoreset)
init(autoreset=True)

# --- Functions ---

def fetch_single_url_titles(url):
    """Downloads a single web page and extracts recommended game titles."""
    # Message will be printed by caller if fetch is successful

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        # print(f"{C_DIM}Attempting fetch: {url}") # Optional debug
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
    except requests.exceptions.HTTPError as http_err:
        # --- Specific handling for 404 Not Found ---
        if http_err.response.status_code == 404:
            # Print a dim info message or comment out for silence
            print(f"{C_DIM}Info: URL not found (404), skipping: {url}")
            return None # Return None silently for 404
        else:
            # Print other HTTP errors (e.g., 403 Forbidden, 500 Server Error)
            print(f"{C_ERROR}Warning: HTTP Error {http_err.response.status_code} fetching {url}: {http_err}", file=sys.stderr)
            return None
        # --- End 404 handling ---
    except requests.exceptions.RequestException as e:
        # Handle other request errors (connection, timeout, etc.)
        print(f"{C_ERROR}Warning: Network/Request Error fetching {url}: {e}", file=sys.stderr)
        return None

    # If we reached here, the request was successful (e.g., 200 OK)
    print(f"{C_INFO}Fetching titles from: {url}") # Print success message

    try:
        # Parse HTML content
        soup = BeautifulSoup(response.content, 'lxml')
        titles = set() # Set to store unique titles found
        # Find tables with the 'wikitable' class
        tables = soup.find_all('table', class_='wikitable')

        if not tables:
            # Warn if no relevant tables are found
            print(f"{C_WARNING}Warning: No 'wikitable' table found on {url}.", file=sys.stderr)
            # Continue anyway, maybe titles are elsewhere or expected 0
        else:
             # Process found tables
             table_index = 0
             for table in tables:
                table_index += 1
                rows = table.find_all('tr') # Find all rows
                for row in rows[1:]: # Iterate from second row (skip header)
                    try:
                        # Find all cell types (td and th) in the row
                        cells = row.find_all(['td', 'th'])
                        # Title is expected in the second cell (index 1)
                        if len(cells) > 1:
                            title_text = cells[1].get_text(strip=True) # Raw text
                            # Clean common region tags etc. from the whole block first
                            cleaned_title_block = re.sub(r'\[.*?\]', '', title_text).strip()
                            # Handle potential alternate titles separated by <br/> (newline)
                            title_lines = [line.strip() for line in cleaned_title_block.split('\n') if line.strip()]
                            if title_lines:
                                for final_title in title_lines: # Add all non-empty lines
                                    if final_title:
                                        titles.add(final_title)
                    except Exception as row_error:
                         # Log error if parsing a specific row fails
                        print(f"{C_ERROR}ERROR parsing a row in URL {url}: {row_error}", file=sys.stderr)

        # Print final count for this URL
        print(f"Found {C_SUCCESS}{len(titles)}{C_NORMAL} unique titles on {url}.")
        return titles # Return the set of found titles (could be empty)
    except Exception as e:
        # Handle errors during HTML parsing
        print(f"{C_ERROR}Warning: Error during HTML parsing of URL {url}: {e}", file=sys.stderr)
        traceback.print_exc()
        return None # Indicate failure


def fetch_all_titles(url_list):
    """Downloads and combines titles from a list of URLs, tracking source."""
    all_recommended_titles = set() # Set for all unique titles combined
    titles_by_url = {} # Dict mapping url -> set of titles from that url
    processed_urls = set() # Avoid processing duplicates if passed in url_list

    if not url_list:
        print(f"{C_ERROR}No URLs provided for fetching.", file=sys.stderr)
        return set(), {} # Return empty set and dict

    print(f"\n{C_INFO}Starting title fetching from URLs...")
    # Use tqdm for progress bar during fetching
    for url in tqdm(url_list, desc=f"{C_INFO}Scanning URLs{C_NORMAL}", unit="URL ", ncols=100):
        if url in processed_urls: continue # Skip if already processed

        titles_from_url = fetch_single_url_titles(url) # Call the modified fetch function
        processed_urls.add(url)

        # If fetch didn't return a critical error (None)
        if titles_from_url is not None: # An empty set is success (page exists but no titles found)
             titles_by_url[url] = titles_from_url
             if titles_from_url: # Only update the combined set if titles were actually found
                 all_recommended_titles.update(titles_from_url)

    print() # Newline after tqdm bar
    if not all_recommended_titles:
        # If no titles found across *any* valid URL
        print(f"{C_WARNING}Warning: No valid recommended titles found in any accessible URLs.", file=sys.stderr)
        return set(), titles_by_url # Return empty set, but potentially populated titles_by_url dict
    else:
        # Success: Print total unique titles found
        print(f"\n{C_SUCCESS}Total: Found {len(all_recommended_titles)} unique recommended titles from all accessible URLs.")
        return all_recommended_titles, titles_by_url


def filter_dat_file(input_dat_path, output_dat_path, all_recommended_titles, titles_by_url, similarity_threshold):
    """Filters the DAT file, generates report, and writes multiple CSV files (one per URL)."""
    # Initial checks
    if not os.path.exists(input_dat_path):
        print(f"{C_ERROR}Error: Input file '{input_dat_path}' does not exist.", file=sys.stderr)
        return False
    if all_recommended_titles is None: # Critical error during web fetch
         print(f"{C_ERROR}Error: Cannot proceed, error fetching recommended titles.", file=sys.stderr)
         return False
    if not all_recommended_titles: # No titles found, but no critical error
        print(f"\n{C_WARNING}Warning: No valid web titles found for comparison, output DAT file will be empty (header only).")

    # Read and Parse DAT
    print(f"\n{C_INFO}Reading and parsing DAT file: {input_dat_path}")
    try:
        original_header_lines = []
        with open(input_dat_path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line.startswith('<datafile>'): break
                original_header_lines.append(line)
            if stripped_line.startswith('<datafile>'): original_header_lines.append(line)
        tree = ET.parse(input_dat_path)
        root = tree.getroot()
    except Exception as e:
        print(f"{C_ERROR}Unexpected error during DAT file reading/parsing: {e}", file=sys.stderr)
        traceback.print_exc(); return False

    # Initialize results containers
    filtered_games_elements = {} # Use dict to handle duplicate DAT entries gracefully
    matched_recommended_titles = set() # Stores web titles that got at least one match

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

        # Compare cleaned DAT title against all unique web titles
        if all_recommended_titles and cleaned_dat_title:
            for recommended_title in all_recommended_titles:
                # Use token_set_ratio for better handling of subsets/extra words
                similarity = fuzz.token_set_ratio(cleaned_dat_title, recommended_title)
                if similarity >= similarity_threshold:
                    # Add game element to dict (keyed by original name to avoid duplicates)
                    if dat_title_original not in filtered_games_elements:
                         filtered_games_elements[dat_title_original] = game_element
                    # Add the web title that caused the match to the matched set
                    matched_recommended_titles.add(recommended_title)
                    # Note: No 'break' here, allows multiple web titles to match one DAT game
                    # and ensures all matching web titles are recorded in matched_recommended_titles

    print() # Newline after tqdm bar
    print(f"{C_SUCCESS}Filtering complete.")

    # --- Write Filtered DAT File ---
    filtered_games = list(filtered_games_elements.values()) # Get unique game elements
    new_root = ET.Element('datafile')
    if original_header_element is not None: new_root.append(original_header_element)
    for game in filtered_games: new_root.append(game)
    new_tree = ET.ElementTree(new_root)
    print(f"{C_INFO}Writing filtered DAT file to: {output_dat_path}")
    try:
        ET.indent(new_tree, space="\t", level=0)
        with open(output_dat_path, 'wb') as f:
             for line in original_header_lines:
                 if not line.strip().startswith('<datafile>'): f.write(line.encode('utf-8'))
             new_tree.write(f, encoding='utf-8', xml_declaration=False)
    except IOError as e:
        print(f"{C_ERROR}Error writing filtered DAT file: {e}", file=sys.stderr)

    # --- Write Multiple CSV Files ---
    csv_files_created = []
    output_dir = os.path.dirname(output_dat_path) # Save CSVs in the same dir as the output DAT
    url_counter = 0
    print() # Blank line before CSV messages

    if titles_by_url: # Check if the dictionary has entries
        for url, titles_from_this_url in titles_by_url.items():
            if titles_from_this_url is None: continue # Skip URLs that had fetch errors

            url_counter += 1
            # Find titles from *this* URL that are *not* in the globally matched set
            unmatched_for_this_url = titles_from_this_url - matched_recommended_titles

            if unmatched_for_this_url: # If there are any unmatched titles for this URL
                try:
                    # Generate CSV filename based on URL path parts
                    url_path = urllib.parse.urlparse(url).path
                    path_parts = [part for part in url_path.split('/') if part and part.lower() != 'wiki']
                    if path_parts:
                        base_name_url = '_'.join(path_parts)
                    else: # Fallback name
                        base_name_url = f'url_{url_counter}'
                    # Sanitize filename
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
        # Check if all titles from all successful fetches were matched
        all_titles_were_matched = True
        if titles_by_url:
            for url, titles_from_this_url in titles_by_url.items():
                 if titles_from_this_url is not None and bool(titles_from_this_url - matched_recommended_titles):
                     all_titles_were_matched = False; break
        if all_titles_were_matched:
            print(f"{C_SUCCESS}All valid web titles found had a match in the DAT, no CSV files created.")
        else: # Should not happen often if writing doesn't fail
             print(f"{C_WARNING}Some web titles did not find a match, but an error occurred writing their CSV file(s).")
    elif csv_files_created:
         print(f"{C_SUCCESS}Created {len(csv_files_created)} CSV file(s) with unmatched titles.")


    # --- Final Report Section ---
    total_matched_dat_games = len(filtered_games) # Count unique games included
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
            count_str = str(len(titles)) if titles is not None else f"{C_ERROR}Fetch Error{C_NORMAL}"
            # Color code count based on success/failure/zero
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
    # --- English Help Texts ---
    parser.add_argument("input_file",
                        help="Path to the input .dat file (or .xml/.txt containing XML) (required).")
    parser.add_argument("output_file", nargs='?', default=None,
                        help="Path for the filtered DAT output file (optional). Default: '[input]_filtered.dat'.")
    parser.add_argument("-u", "--urls", nargs='+', required=True,
                        help="One or more *base* URLs of web pages with recommended titles (/Homebrew and /Japan variants will also be checked).")
    parser.add_argument("-t", "--threshold", type=int, default=90, choices=range(0, 101), metavar="[0-100]",
                        help="Similarity percentage threshold (0-100). Default: 90.")
    # --csv_output argument removed

    # Parse Arguments
    try:
        args = parser.parse_args()
    except Exception as e:
        print(f"{C_ERROR}CRITICAL ERROR during argument parsing: {e}", file=sys.stderr)
        sys.exit(1)

    # Determine Paths
    try:
        input_path = args.input_file
        if not os.path.exists(input_path):
             print(f"{C_ERROR}CRITICAL ERROR: Specified input file does not exist: {input_path}", file=sys.stderr)
             sys.exit(1)
        input_dir = os.path.dirname(os.path.abspath(input_path))
        base_name, _ = os.path.splitext(os.path.basename(input_path))
        if args.output_file:
            output_dat_path = args.output_file
        else: # Default output DAT path
            output_dat_path = os.path.join(input_dir, f"{base_name}_filtered.dat")
        # final_csv_path is no longer determined here
    except Exception as e:
        print(f"{C_ERROR}CRITICAL ERROR during path determination: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    # Print Initial Info
    print(f"{C_LABEL}Input File:{C_NORMAL} {input_path}")
    print(f"{C_LABEL}Output DAT File (planned):{C_NORMAL} {output_dat_path}")

    # --- URL Expansion ---
    user_urls = args.urls
    expanded_urls = set()
    print(f"\n{C_INFO}Expanding URLs to automatically check for '/Homebrew' and '/Japan'...")
    for base_url in user_urls:
        base_url_stripped = base_url.rstrip('/')
        expanded_urls.add(base_url_stripped)
        homebrew_url = base_url_stripped + "/Homebrew"; expanded_urls.add(homebrew_url)
        japan_url = base_url_stripped + "/Japan"; expanded_urls.add(japan_url)
    final_urls_to_fetch = sorted(list(expanded_urls))
    print(f"{C_INFO}Final list of URLs to check ({len(final_urls_to_fetch)}):")
    for u in final_urls_to_fetch:
         print(f"{C_DIM}  - {u}")
    # --- End URL Expansion ---

    # Execute Main Logic
    all_titles, titles_by_url = fetch_all_titles(final_urls_to_fetch)

    # Proceed only if fetch didn't return critical error (None)
    if all_titles is not None:
        try:
            # Call the main filtering function (no CSV path needed here)
            filter_dat_file(
                input_path,
                output_dat_path,
                all_titles, # Pass the set of web titles (can be empty)
                titles_by_url, # Pass the dict mapping URL to its titles
                args.threshold
            )
        except Exception as e:
             print(f"\n{C_ERROR}CRITICAL ERROR during filter_dat_file execution: {e}", file=sys.stderr)
             traceback.print_exc()
             sys.exit(1)
    else: # Critical error during fetch_all_titles
        print(f"{C_ERROR}Cannot proceed with filtering due to critical errors during title fetching.", file=sys.stderr)
        sys.exit(1)

    # End of script
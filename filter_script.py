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
# traceback removed (using logging.exception)
import urllib.parse
import datetime # Imported for current date
import string # Imported for punctuation cleaning
import logging # Import logging module
import coloredlogs # Import coloredlogs for colored console output
# Import tqdm for progress bar
from tqdm import tqdm

# --- Script Info ---
SCRIPT_VERSION = "1.3.2" # Script version (updated for console log format)
SCRIPT_AUTHOR = "f3rs3n, Gemini" # Authors
SCRIPT_HOMEPAGE = "https://github.com/f3rs3n/VREC-dat-filter" # Project homepage

# --- Title Cleaning Function ---
def clean_title_for_comparison(title):
    """Applies aggressive cleaning to improve fuzzy matching."""
    if not title:
        return ""
    text = title.lower()
    text = re.sub(r'\s*\[[^]]*\]', '', text) # Remove [...]
    text = re.sub(r'\s*\([^)]*\)', '', text) # Remove (...)
    # Punctuation to None, keep space and hyphen for now, then replace hyphen with space
    translator = str.maketrans('', '', ''.join(p for p in string.punctuation if p not in ['-']))
    text = text.translate(translator)
    text = text.replace('-', ' ') # Replace hyphen with space AFTER removing other punctuation
    text = re.sub(r'\s+', ' ', text).strip() # Normalize whitespace
    return text

# --- Web Scraping Functions ---
def fetch_single_url_titles(url):
    """Downloads a single web page and extracts recommended game titles."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        logging.debug(f"Attempting to fetch URL: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 404:
            logging.warning(f"URL not found (404), skipping: {url}")
            return None # Return None silently for 404
        else:
            logging.error(f"HTTP Error {http_err.response.status_code} fetching {url}: {http_err}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Network/Request Error fetching {url}: {e}")
        return None
    except Exception as e:
        logging.exception(f"Unexpected error during fetch for {url}:")
        return None

    logging.info(f"Processing successful fetch from: {url}")
    try:
        soup = BeautifulSoup(response.content, 'lxml')
        titles = set() # Set to store unique titles found
        tables = soup.find_all('table', class_='wikitable') # Find relevant tables
        if not tables:
            logging.warning(f"No 'wikitable' table found on {url}.")
        else:
            table_index = 0
            for table in tables: # Iterate through found tables
                table_index += 1
                logging.debug(f"Processing table {table_index} on {url}")
                rows = table.find_all('tr') # Find all rows
                for i, row in enumerate(rows[1:]): # Iterate from second row (skip header)
                    row_num = i + 2 # Actual row number in table
                    try:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) > 1:
                            title_text_raw = cells[1].get_text(strip=True) # Raw text
                            # Clean potential region tags like [USA] etc. (aggressive cleaning handles this later)
                            cleaned_title_block = re.sub(r'\[.*?\]', '', title_text_raw).strip()
                            # Handle potential alternate titles separated by <br/> (newline)
                            title_lines = [line.strip() for line in cleaned_title_block.split('\n') if line.strip()]
                            if title_lines:
                                for raw_line_title in title_lines: # Add all non-empty lines
                                    # Apply aggressive cleaning for matching
                                    cleaned_for_match = clean_title_for_comparison(raw_line_title)
                                    if cleaned_for_match:
                                        logging.debug(f" Found raw='{raw_line_title}', cleaned='{cleaned_for_match}' in row {row_num} of table {table_index}")
                                        titles.add(cleaned_for_match)
                                    # else: # Optional: Log titles that become empty after cleaning
                                    #     logging.debug(f" Raw title '{raw_line_title}' became empty after cleaning in row {row_num} of table {table_index}")
                            # else: # Optional: Log when the cell has no processable lines
                            #      logging.debug(f" No valid title lines extracted from cell 2 in row {row_num} of table {table_index}")
                        # else: # Optional: Log rows with unexpected cell counts
                        #      logging.debug(f" Row {row_num} in table {table_index} has less than 2 cells.")

                    except Exception as row_error:
                        # Log error parsing a specific row but continue
                        logging.error(f"Error parsing row {row_num} in table {table_index} of URL {url}: {row_error}")
            logging.info(f"Found {len(titles)} unique cleaned titles on {url}.") # Final count for this URL
        return titles # Return the set (might be empty)
    except Exception as e:
        # Handle errors during HTML parsing phase
        logging.exception(f"Error during HTML parsing of URL {url}:") # Automatically includes traceback
        return None # Indicate failure

def fetch_all_titles(url_list):
    """Downloads and combines titles from a list of URLs, tracking source."""
    all_recommended_titles = set() # Combined set of all unique titles found
    titles_by_url = {} # Dictionary mapping URL -> set of titles from that URL
    processed_urls = set() # Avoid reprocessing identical URLs

    if not url_list:
        logging.error("No URLs provided for fetching.")
        return set(), {} # Return empty structures

    logging.info("Starting title fetching from URLs...")
    # Iterate through URLs with a progress bar
    # tqdm writes to stderr by default, which is fine as our console logger also uses stderr
    for url in tqdm(url_list, desc="Scanning URLs", unit="URL", ncols=100, leave=False): # Use leave=False if logs might overwrite bar
        if url in processed_urls:
             logging.debug(f"Skipping already processed URL: {url}")
             continue # Skip if already seen

        titles_from_url = fetch_single_url_titles(url) # Fetch and parse (returns cleaned titles)
        processed_urls.add(url)

        # Only process if fetch didn't return a critical error (None)
        if titles_from_url is not None: # An empty set is okay
            titles_by_url[url] = titles_from_url # Store cleaned titles per URL
            if titles_from_url: # Update combined set only if titles were actually found
                all_recommended_titles.update(titles_from_url)
            else:
                logging.info(f"No titles extracted from {url} (but fetch was successful).")
        else:
             logging.warning(f"Fetch or parsing failed for {url}. No titles added.")

    # Newline after progress bar finishes if leave=True, might not be needed if leave=False
    # print()

    if not all_recommended_titles:
        logging.warning("No valid recommended titles found in any accessible URLs.")
        # Return empty set, possibly non-empty dict if some URLs were accessed but yielded no titles
        return set(), titles_by_url
    else:
        logging.info(f"Total: Found {len(all_recommended_titles)} unique cleaned recommended titles from all accessible URLs.")
        return all_recommended_titles, titles_by_url


# --- DAT Filtering and Writing Function ---
def filter_dat_file(input_dat_path, output_dat_path, all_recommended_titles, titles_by_url, similarity_threshold):
    """Filters the DAT file, generates report, updates header, and writes multiple CSV files."""
    # Initial checks
    if not os.path.exists(input_dat_path):
        logging.critical(f"Input file '{input_dat_path}' does not exist.")
        return False
    if all_recommended_titles is None: # Critical fetch error occurred
         logging.critical("Cannot proceed, error fetching recommended titles.")
         return False
    if not all_recommended_titles: # No web titles found, but no critical error
        logging.warning("No valid web titles found for comparison, output DAT file will be empty (or contain only the header).")
        # Proceed, as user might want an empty DAT with correct header

    # Read and Parse DAT
    logging.info(f"Reading and parsing DAT file: {input_dat_path}")
    try:
        tree = ET.parse(input_dat_path)
        root = tree.getroot()
        # *** ADDED VALIDATION: Check root tag ***
        if root.tag != 'datafile':
            logging.critical(f"Input DAT file '{input_dat_path}' does not have the expected root element '<datafile>'. Found '<{root.tag}>'. Aborting.")
            return False
        logging.debug(f"Successfully parsed DAT file. Root element is '<{root.tag}>'.")
        # *** END VALIDATION ***
    except ET.ParseError as parse_err:
        logging.critical(f"Error parsing DAT file '{input_dat_path}': {parse_err}")
        return False
    except Exception as e:
        # Catch other potential errors during file reading/parsing
        logging.exception(f"Unexpected error during DAT file reading/parsing:")
        return False

    # --- Header Processing ---
    logging.info("Processing and updating header information...")
    original_header_element = root.find('header')
    new_header = ET.Element('header')
    today_date = datetime.date.today().strftime('%Y-%m-%d')
    original_name_text = "Unknown System"; original_description_text = "Unknown DAT"
    elements_to_copy = []
    if original_header_element is not None:
        logging.debug("Found existing <header> element.")
        name_el = original_header_element.find('name')
        if name_el is not None and name_el.text: original_name_text = name_el.text.strip()
        desc_el = original_header_element.find('description')
        if desc_el is not None and desc_el.text: original_description_text = desc_el.text.strip()
        logging.debug(f" Original Name: '{original_name_text}', Original Description: '{original_description_text}'")
        # Copy relevant original header tags
        # Define which tags from original header should be copied if they exist
        tags_to_copy = ['version', 'date', 'author', 'homepage', 'url', 'retool', 'clrmamepro', 'comment']
        # Define tags that this script sets manually (to avoid copying them if they exist)
        manual_tags = ['name', 'description', 'version', 'date', 'author', 'homepage']
        for child in original_header_element:
            # Only copy if the tag is in our list AND we are not setting it manually
            if child.tag in tags_to_copy and child.tag not in manual_tags:
                 logging.debug(f" Copying header tag: <{child.tag}>")
                 elements_to_copy.append({'tag': child.tag, 'text': child.text, 'attrib': child.attrib})
    else: logging.warning("No <header> element found in input DAT.")

    processed_name = re.sub(r'\s*\([^)]*\)$', '', original_name_text).strip()
    # Add new header elements
    ET.SubElement(new_header, 'name').text = f"{processed_name} (VREC DAT Filter)"
    ET.SubElement(new_header, 'description').text = f"{original_description_text} (VREC DAT Filter)"
    ET.SubElement(new_header, 'version').text = SCRIPT_VERSION # Use script version
    ET.SubElement(new_header, 'date').text = today_date # Use current date
    ET.SubElement(new_header, 'author').text = SCRIPT_AUTHOR # Use script author
    ET.SubElement(new_header, 'homepage').text = SCRIPT_HOMEPAGE # Use script homepage
    # Append the copied elements
    for element_data in elements_to_copy: ET.SubElement(new_header, element_data['tag'], attrib=element_data['attrib']).text = element_data['text']
    logging.debug("Constructed new header.")
    # --- End Header Processing ---

    filtered_games_elements = {}
    matched_web_titles_that_matched_something = set() # Tracks which web titles got matched
    logging.info(f"Filtering games (Threshold: {similarity_threshold}%, Algorithm: token_set_ratio)...")
    all_game_elements = root.findall('.//game') # Use .//game to find games anywhere under the root
    original_game_count = len(all_game_elements)
    if original_game_count == 0:
        logging.warning("No <game> elements found in the input DAT file.")

    # Filtering loop
    # Wrap the iterator with tqdm for the progress bar
    game_iterator = tqdm(all_game_elements, desc="Filtering DAT", unit=" game", ncols=100, leave=False, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]')
    for game_element in game_iterator:
        dat_title_original = game_element.get('name')
        if not dat_title_original:
             logging.debug("Skipping game element with no 'name' attribute.")
             continue
        # Apply aggressive cleaning to DAT title for matching
        cleaned_dat_title = clean_title_for_comparison(dat_title_original)
        logging.debug(f"Processing DAT Game: '{dat_title_original}' -> Cleaned: '{cleaned_dat_title}'")

        best_match_score = 0
        matching_web_title = None
        found_match_above_threshold = False

        # Compare cleaned DAT title with cleaned web titles
        if all_recommended_titles and cleaned_dat_title:
            for recommended_title in all_recommended_titles: # Web titles are already cleaned
                try:
                    similarity = fuzz.token_set_ratio(cleaned_dat_title, recommended_title)
                    if similarity >= similarity_threshold:
                        # *** Log individual matches only at DEBUG level ***
                        if not found_match_above_threshold:
                             logging.debug(f" Match Found! DAT: '{dat_title_original}' ~ Web: '{recommended_title}' (Score: {similarity}%)")
                        found_match_above_threshold = True
                        # Store game element using original name as key (handles DAT duplicates)
                        if dat_title_original not in filtered_games_elements:
                            filtered_games_elements[dat_title_original] = game_element
                        # Record the web title that resulted in a match
                        matched_web_titles_that_matched_something.add(recommended_title)
                        # Keep track of the best match for this DAT game (optional, for debug/reporting)
                        if similarity > best_match_score:
                            best_match_score = similarity
                            matching_web_title = recommended_title
                        # Don't break; a DAT game might match multiple web titles if they are similar
                    elif similarity > best_match_score: # Track best score even if below threshold
                         best_match_score = similarity
                         matching_web_title = recommended_title

                except Exception as fuzz_error:
                     logging.error(f"Error during fuzzy comparison between '{cleaned_dat_title}' and '{recommended_title}': {fuzz_error}")

            # Log if no match was found above threshold for this game
            if not found_match_above_threshold:
                 logging.debug(f" No match >= {similarity_threshold}% for DAT: '{cleaned_dat_title}'. Best score: {best_match_score}% with Web: '{matching_web_title}'")

    logging.info("Filtering complete.")

    # --- Write Filtered DAT File ---
    filtered_games = list(filtered_games_elements.values()) # Get unique elements to write
    new_root = ET.Element('datafile')
    new_root.append(new_header) # Append the MODIFIED header
    for game in filtered_games: new_root.append(game) # Append filtered game elements
    new_tree = ET.ElementTree(new_root)

    logging.info(f"Writing filtered DAT file to: {output_dat_path}")
    reread_count = -1 # Initialize confirmation count
    try:
        # Indent the tree for readability BEFORE writing
        ET.indent(new_tree, space="\t", level=0)

        # Write using text mode ('w') and let ElementTree handle encoding/declaration.
        with open(output_dat_path, 'w', encoding='utf-8') as f:
            new_tree.write(f,
                           encoding='unicode',        # Use 'unicode' with text mode file handle
                           xml_declaration=True,      # Let ET write <?xml ...?> declaration
                           short_empty_elements=True) # Optional: Use <tag/> for empty elements
        logging.debug(f"Successfully wrote filtered DAT to {output_dat_path}")

        # --- Confirmation Read Block ---
        logging.info("Confirming entry count in output file...")
        try:
            reread_tree = ET.parse(output_dat_path)
            # Check root element again on re-read, just in case
            reread_root = reread_tree.getroot()
            if reread_root.tag != 'datafile':
                 logging.error(f"Re-read validation failed: Output file '{os.path.basename(output_dat_path)}' root tag is '<{reread_root.tag}>', expected '<datafile>'")
            else:
                reread_games = reread_root.findall('.//game') # Find all 'game' tags anywhere
                reread_count = len(reread_games)
                logging.debug(f"Re-read successful. Found {reread_count} <game> elements.")
        except ET.ParseError as parse_err:
            logging.error(f"Failed to re-parse output file '{os.path.basename(output_dat_path)}' for count confirmation: {parse_err}")
        except IOError as io_err:
            logging.error(f"Failed to re-open output file '{os.path.basename(output_dat_path)}' for count confirmation: {io_err}")
        except Exception as reread_err: # Catch other errors during re-read
            logging.exception("Unexpected error during output file count confirmation:") # Log full traceback
        # --- End Confirmation Read Block ---

    except IOError as e:
        logging.critical(f"Error writing filtered DAT file '{output_dat_path}': {e}")
        reread_count = -1 # Set to -1 if the initial write fails
    except Exception as e:
        logging.exception(f"Unexpected error during file writing or confirmation for '{output_dat_path}':") # Log full traceback
        reread_count = -1


    # --- Write Multiple CSV Files ---
    csv_files_created = []
    output_dir = os.path.dirname(os.path.abspath(output_dat_path)) # Ensure output_dir is absolute
    url_counter = 0
    logging.info("Checking for unmatched web titles to generate CSV reports...")
    if titles_by_url:
        for url, titles_from_this_url in titles_by_url.items():
            if titles_from_this_url is None:
                logging.debug(f"Skipping CSV generation for {url} as fetch failed.")
                continue # Skip if fetch failed for this URL

            url_counter += 1
            # Find titles from this URL that were NOT matched by any game in the DAT
            unmatched_for_this_url = titles_from_this_url - matched_web_titles_that_matched_something
            logging.debug(f"URL: {url} - Found {len(titles_from_this_url)} titles, {len(unmatched_for_this_url)} were not matched in DAT.")

            if unmatched_for_this_url:
                try:
                    # Create a sanitized filename from the URL path
                    url_path = urllib.parse.urlparse(url).path
                    # Remove leading/trailing slashes and 'wiki' part if present
                    path_parts = [part for part in url_path.strip('/').split('/') if part and part.lower() != 'wiki']
                    if path_parts: base_name_url = '_'.join(path_parts)
                    else: base_name_url = f'url_{url_counter}' # Fallback name
                    # Sanitize further for filesystem compatibility
                    sanitized_name = re.sub(r'[^\w.-]+', '_', base_name_url).strip('_')
                    if not sanitized_name: sanitized_name = f"url_{url_counter}" # Ensure name is not empty

                    csv_filename = f"{sanitized_name}_unmatched.csv"
                    # Ensure CSV is written to the correct output directory
                    full_csv_path = os.path.join(output_dir, csv_filename)
                    logging.info(f"Writing CSV for unmatched titles from {url} -> '{csv_filename}' ({len(unmatched_for_this_url)} titles)...")
                    with open(full_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow([f'Unmatched Recommended Title from {url}']) # Header row
                        for title in sorted(list(unmatched_for_this_url)): writer.writerow([title])
                    csv_files_created.append(csv_filename)
                except Exception as e:
                     logging.exception(f"Error creating/writing CSV for {url} to {full_csv_path}:") # Log full traceback

    # --- Final CSV Summary Message ---
    if not all_recommended_titles: logging.warning("No valid web titles found initially, no CSV files created.")
    elif not titles_by_url: logging.warning("No URL data available to generate CSV files.")
    elif not csv_files_created:
        # Check if ALL potentially available titles were matched
        any_unmatched_possible = False
        for url, titles_set in titles_by_url.items():
            if titles_set is not None and bool(titles_set - matched_web_titles_that_matched_something):
                any_unmatched_possible = True
                break
        if not any_unmatched_possible:
             logging.info("All valid web titles found had a match in the DAT, no CSV files needed or created.")
        else:
             # This case means some titles were unmatched, but no CSVs were made (check logs for write errors)
             logging.warning("Some web titles did not find a match, but no CSV files were created (check logs for writing errors).")
    elif csv_files_created: logging.info(f"Created {len(csv_files_created)} CSV file(s) with unmatched titles in '{output_dir}'.")


    # --- Final Report ---
    # Count based on what was intended to be written
    total_matched_dat_games = len(filtered_games)
    total_unmatched_dat_games = original_game_count - total_matched_dat_games
    global_unmatched_recommended_titles = all_recommended_titles - matched_web_titles_that_matched_something if all_recommended_titles else set()

    # Log the summary using INFO level
    logging.info("--- Operation Summary ---")
    logging.info(f"{'Input DAT File:':<30} {input_dat_path}")
    logging.info(f"{'Output DAT File:':<30} {output_dat_path}")
    logging.info(f"{'Total Games in Original DAT:':<30} {original_game_count:>7}")
    logging.info("Recommended Titles (Web Sources):")
    if titles_by_url:
        # Calculate max URL length for better alignment, handle case where dict is empty
        max_url_len = max(len(url) for url in titles_by_url.keys()) if titles_by_url else 0
        for url, titles in titles_by_url.items():
            count_str = str(len(titles)) if titles is not None else "Fetch Error"
            status = "found" if titles is not None else "error"
            # Pad URL for alignment
            logging.info(f"- URL: {url:<{max_url_len}} -> {count_str} cleaned titles {status}")
    total_web_titles_str = str(len(all_recommended_titles)) if all_recommended_titles is not None else 'Error'
    logging.info(f"{'Total Unique Web Titles (cleaned):':<30} {total_web_titles_str:>7}")

    logging.info(f"{'Similarity Threshold Used:':<30} {similarity_threshold}%")
    logging.info(f"{'Comparison Algorithm:':<30} token_set_ratio") # Ensure alignment

    logging.info("DAT Filtering Results:")
    logging.info(f"{'- Matching Games Kept:':<30} {total_matched_dat_games:>7}")
    logging.info(f"{'- Non-Matching Games Removed:':<30} {total_unmatched_dat_games:>7}")

    logging.info("Web Titles vs DAT Comparison:")
    logging.info(f"{'- Web Titles Matched in DAT:':<30} {len(matched_web_titles_that_matched_something):>7}")
    logging.info(f"{'- Web Titles NOT Matched:':<30} {len(global_unmatched_recommended_titles):>7}")
    logging.info("--------------------------------")

    # --- Confirmation Count Output ---
    if reread_count != -1: # Log only if re-read was successful
        # Determine log level based on whether counts match
        level = logging.INFO if reread_count == total_matched_dat_games else logging.WARNING
        logging.log(level, f"Confirmation: Counted {reread_count} <game> entries in '{os.path.basename(output_dat_path)}'.")
        # Optional warning if counts don't match
        if reread_count != total_matched_dat_games:
            logging.warning(f"Re-read count ({reread_count}) differs from initial filtered count ({total_matched_dat_games}). This might indicate an issue.")
    else:
        logging.warning("Could not confirm final game count due to an error during file writing or re-parsing.")
    # --- End Confirmation Count Output ---


    logging.info("Operation completed.")
    return True


# --- Main execution block ---
if __name__ == "__main__":
    # Setup Argparse
    parser = argparse.ArgumentParser(
        description="Filters a DAT/XML file based on recommended titles scraped from web pages (using 'wikitable' structure). Creates a filtered DAT and optional CSV reports for unmatched web titles.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=f"Version: {SCRIPT_VERSION} by {SCRIPT_AUTHOR}. Homepage: {SCRIPT_HOMEPAGE}"
    )
    parser.add_argument("input_file", help="Path to the input .dat file (XML format, expected root <datafile>).")
    parser.add_argument("output_file", nargs='?', default=None, help="Path for the filtered DAT output file (optional). Default: '[input_filename]_filtered.dat'.")
    parser.add_argument("-u", "--urls", nargs='+', required=True, help="One or more base URLs of web pages containing recommended titles in 'wikitable' HTML tables (title expected in the second column).")
    parser.add_argument("-t", "--threshold", type=int, default=90, choices=range(0, 101), metavar="[0-100]", help="Similarity percentage threshold (0-100) for fuzzy matching. Default: 90.")
    parser.add_argument("--check-homebrew", "-hb", action='store_true', help="Automatically check for and include '/Homebrew' suffixed URLs based on provided URLs.")
    parser.add_argument("--check-japan", "-j", action='store_true', help="Automatically check for and include '/Japan' suffixed URLs based on provided URLs.")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level for console output."
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Path to an optional file to write logs to (all levels DEBUG and above)."
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {SCRIPT_VERSION}")

    # Parse Arguments
    try:
        args = parser.parse_args()
    except SystemExit as e: # Catch SystemExit from --help, --version
        sys.exit(e.code) # Exit cleanly
    # Cannot use logging here yet, as it's not configured. Print critical errors to stderr.
    except Exception as e:
        print(f"CRITICAL ERROR during argument parsing: {e}", file=sys.stderr)
        sys.exit(1)


    # --- Logging Setup ---
    log_level_console = getattr(logging, args.log_level.upper(), logging.INFO)
    # Define DIFFERENT formats for console and file
    console_log_format = '%(levelname)s: %(message)s' # Format for console (Level: Message)
    file_log_format = '%(asctime)s - %(levelname)s - %(message)s' # Format for file (Timestamp - Level - Message)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG) # Set root logger level to DEBUG to capture everything

    # Clear existing handlers (important for multiple runs in same session or library usage)
    if logger.hasHandlers():
        logger.handlers.clear()

    # Install coloredlogs handler for the console using the CONSOLE format
    coloredlogs.install(level=log_level_console, # User-defined level for console
                        logger=logger,           # Attach to the root logger
                        fmt=console_log_format,  # Use console format (NO timestamp)
                        stream=sys.stderr)       # Log to stderr (like tqdm)

    # File Handler (optional) - Added AFTER coloredlogs install
    if args.log_file:
        try:
            # Create output directory for log file if it doesn't exist
            log_dir = os.path.dirname(args.log_file)
            if log_dir and not os.path.exists(log_dir):
                 os.makedirs(log_dir)
                 # Log this creation attempt (will go to console via coloredlogs too)
                 logging.info(f"Created directory for log file: {log_dir}")

            file_handler = logging.FileHandler(args.log_file, mode='w', encoding='utf-8')
            file_handler.setLevel(logging.DEBUG) # Log everything (DEBUG and above) to the file
            # Use the FILE format for the file handler's formatter
            file_handler.setFormatter(logging.Formatter(file_log_format)) # Use file format (WITH timestamp)
            logger.addHandler(file_handler)
            # This message will now appear differently in console vs file
            logging.info(f"Logging detailed output (DEBUG level and above) to: {args.log_file}")
        except IOError as e:
            logging.error(f"Could not open log file {args.log_file} for writing: {e}", exc_info=False)
        except OSError as e:
             logging.error(f"Could not create directory for log file {args.log_file}: {e}", exc_info=False)
    # --- End Logging Setup ---


    # --- Conditional URL Expansion ---
    user_urls = args.urls
    expanded_urls = set(user_urls) # Start with user-provided URLs
    logging.debug(f"Initial URLs provided: {user_urls}")
    if args.check_homebrew:
        logging.info("Checking for '/Homebrew' URL variants...")
        homebrew_variants = set()
        # Add '/Homebrew' only if the base URL doesn't already end with it (case-insensitive check)
        for base_url in user_urls:
            if not base_url.lower().rstrip('/').endswith('/homebrew'):
                 hb_url = base_url.rstrip('/') + "/Homebrew"
                 homebrew_variants.add(hb_url)
                 logging.debug(f" Adding Homebrew variant: {hb_url}")
        expanded_urls.update(homebrew_variants)
    if args.check_japan:
        logging.info("Checking for '/Japan' URL variants...")
        japan_variants = set()
         # Add '/Japan' only if the base URL doesn't already end with it (case-insensitive check)
        for base_url in user_urls:
            if not base_url.lower().rstrip('/').endswith('/japan'):
                 jp_url = base_url.rstrip('/') + "/Japan"
                 japan_variants.add(jp_url)
                 logging.debug(f" Adding Japan variant: {jp_url}")
        expanded_urls.update(japan_variants)

    final_urls_to_fetch = sorted(list(expanded_urls))
    if len(final_urls_to_fetch) > len(user_urls):
        logging.info(f"Final list includes expanded URLs ({len(final_urls_to_fetch)} total):")
        # Log expanded URLs only at DEBUG level to avoid clutter
        for u in final_urls_to_fetch: logging.debug(f"  - {u}")
    else:
        logging.info(f"Processing only the provided URLs ({len(final_urls_to_fetch)} total).")


    # Determine Output DAT Path
    try:
        input_path = args.input_file
        if not os.path.isfile(input_path): # Check if it's a file specifically
            logging.critical(f"Specified input path is not a file or does not exist: {input_path}")
            sys.exit(1)

        # Get absolute path for input directory to ensure correct joins
        input_dir = os.path.dirname(os.path.abspath(input_path))
        base_name, _ = os.path.splitext(os.path.basename(input_path))

        if args.output_file:
            output_dat_path = args.output_file
            # Ensure output directory exists if specified as part of the path
            output_dir_specified = os.path.dirname(os.path.abspath(output_dat_path)) # Use absolute path
            if output_dir_specified and not os.path.exists(output_dir_specified):
                 try:
                     os.makedirs(output_dir_specified)
                     logging.info(f"Created output directory: {output_dir_specified}")
                 except OSError as e:
                     logging.critical(f"Could not create output directory '{output_dir_specified}': {e}")
                     sys.exit(1)
        else:
            # Default output path in the same directory as the input
            output_dat_path = os.path.join(input_dir, f"{base_name}_filtered.dat")

        # Ensure the final output path is absolute for clarity in logs
        output_dat_path = os.path.abspath(output_dat_path)

    except Exception as e:
        logging.critical(f"Error during path determination: {e}", exc_info=True) # Include traceback for path errors
        sys.exit(1)


    # Log Initial Info
    logging.info(f"Input File:                {os.path.abspath(input_path)}") # Log absolute path
    logging.info(f"Output DAT File (planned): {output_dat_path}") # Already absolute
    logging.info(f"Similarity Threshold:      {args.threshold}%")


    # Execute Main Logic
    all_titles, titles_by_url = fetch_all_titles(final_urls_to_fetch) # Gets cleaned titles

    # Proceed only if fetching didn't encounter a fatal error (all_titles is None)
    if all_titles is not None:
        try:
            # filter_dat_file cleans DAT titles internally and compares vs cleaned web titles
            success = filter_dat_file( input_path, output_dat_path, all_titles, titles_by_url, args.threshold )
            if not success:
                 logging.critical("Filtering process reported an error. Please check logs.")
                 sys.exit(1) # Exit with error status if filtering function returned False
        except Exception as e:
            # Catch unexpected errors during the main filtering process
            logging.exception("CRITICAL ERROR during filter_dat_file execution:") # Log exception with traceback
            sys.exit(1)
    else:
        # If fetch_all_titles returned None (indicating a critical fetch error)
        logging.critical("Cannot proceed with filtering due to critical errors during title fetching.")
        sys.exit(1)

    # Exit successfully if we reach here
    sys.exit(0)
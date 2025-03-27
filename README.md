# VREC-dat-filter
Python script to filter .dat files using /v/'s Recommended Games Wiki

=========================================
VREC DAT Game Filter Script - User Manual
=========================================

== 1. Purpose ==

This Python script filters a game list file in DAT/XML format (like those used by ROM managers based on the Logiqx DTD, e.g., from redump.org) based on recommended game titles scraped from one or more specified web pages (e.g., wiki lists).

It works by:
1. Fetching the recommended game titles from the provided URL(s).
2. Parsing your input DAT file to get the game names.
3. Cleaning both the web titles and the DAT titles (removing common tags like (USA), [Europe], etc.).
4. Comparing the cleaned DAT titles against the cleaned web titles using fuzzy matching (specifically, the 'token_set_ratio' algorithm, which is good at handling extra words/subtitles) with a configurable similarity threshold.
5. Generating a new, filtered DAT file containing only the games that matched the web list criteria.
6. Generating separate CSV files for each source URL, listing any recommended titles from that specific URL that were *not* found with sufficient similarity in your DAT file.
7. Displaying colored status messages, a progress bar, and a final summary report in the terminal.

== 2. Prerequisites ==

Before running the script, you need:

1.  Python 3: Version 3.8 or later is recommended.
    - Download from: https://www.python.org/downloads/windows/
    - IMPORTANT: During installation on Windows, make sure to check the box "Add Python X.Y to PATH".
    - Verify installation by opening Command Prompt (Cmd) or PowerShell and typing `python --version` and `pip --version`.

2.  Required Python Libraries:
    - These libraries are needed: `requests`, `beautifulsoup4`, `lxml`, `thefuzz`, `colorama`, `tqdm`.
    - The easiest way to install them is using the `requirements.txt` file method described in the Setup section below.

== 3. Setup ==

1.  Save the Script: Save the complete Python script code provided to you in a file named `filter_script.py` (or any name ending in `.py`).

2.  Create `requirements.txt`: In the SAME directory where you saved `filter_script.py`, create a new, plain text file named exactly `requirements.txt`.

3.  Populate `requirements.txt`: Open `requirements.txt` with a text editor (like Notepad) and paste the following lines into it:

    requests
    beautifulsoup4
    lxml
    thefuzz
    colorama
    tqdm

4.  Save `requirements.txt`.

5.  Install Dependencies: Open your terminal (Cmd or PowerShell), navigate to the directory containing the script and `requirements.txt` (using the `cd` command), and run:

    pip install -r requirements.txt

    This command will read the file and install all the necessary libraries. You only need to do this once for your Python environment.

== 4. How to Run the Script ==

1.  Open your terminal (Command Prompt, PowerShell, Windows Terminal, etc.).
2.  Navigate to the directory where you saved `filter_script.py` and your input DAT file using the `cd` command.
    Example: `cd C:\Users\YourName\Scripts\DATFilter`
3.  Run the script using the following command structure:

    python filter_script.py <INPUT_FILE> [OUTPUT_FILE] --urls <URL1> [URL2...] [OPTIONS]

    - Replace `<INPUT_FILE>` with the path to your .dat file (or .xml/.txt containing XML).
    - `[OUTPUT_FILE]` is optional (see Arguments below).
    - Replace `<URL1> [URL2...]` with the web page URL(s) containing the recommended titles.
    - `[OPTIONS]` are other optional flags like `--threshold`.
    - IMPORTANT: If any file path or URL contains spaces, enclose it in double quotes (`"`).

== 5. Command Line Arguments ==

* `<INPUT_FILE>` (Required)
    - The first argument after the script name.
    - Path to the input .dat file (or .xml/.txt containing XML) (required).
    - Example: `"Sony - PlayStation.dat"`

* `[OUTPUT_FILE]` (Optional)
    - The second argument after the script name (if provided).
    - Path where the filtered output DAT file will be saved.
    - If omitted: A file named `<input_filename>_filtered.dat` will be created in the same directory as the input file.
    - Example: `"Filtered PSX Games.dat"`

* `--urls <URL1> [URL2...]` or `-u <URL1> [URL2...]` (Required)
    - Must be followed by one or more web page URLs, separated by spaces.
    - These URLs point to the pages containing the lists of recommended game titles.
    - Example: `--urls "https://site.com/list1" "https://othersite.org/page2"`

* `--threshold <0-100>` or `-t <0-100>` (Optional)
    - Sets the minimum similarity percentage (0-100) required for a match between a DAT title and a web title.
    - Default: `90`
    - Example: `--threshold 85`

* (Note: The `--csv_output` argument was removed, as CSV files are now generated automatically per URL).

== 6. Examples ==

* Basic usage (output DAT/CSVs named automatically, 90% threshold):
    python filter_script.py "Sony - PlayStation.dat" --urls "https://wiki.example.com/PSX_Recommended"

* Specifying output DAT name, multiple URLs, 85% threshold:
    python filter_script.py "input/psx_full.dat" "output/psx_filtered.dat" --urls "https://url1.com" "https://url2.net" -t 85

* Using short flags:
    python filter_script.py game_list.xml -u "https://wiki.example.com/best_games"

== 7. Output Files ==

1.  Filtered DAT File:
    - Named either as specified by `[OUTPUT_FILE]` or `<input_filename>_filtered.dat`.
    - Created in the location specified or in the input file's directory.
    - Contains the original header and only the `<game>` entries from the input DAT that had a name matching (with >= threshold similarity using `token_set_ratio`) at least one title found on the specified web pages.

2.  Unmatched Titles CSV File(s):
    - One CSV file may be created for *each URL* provided *if* that URL contained recommended titles that did *not* find a match in your DAT file.
    - Location: Saved in the same directory as the filtered DAT file.
    - Naming: `<url_path_part>_unmatched.csv` (e.g., `PlayStation_unmatched.csv`, `PlayStation_Japan_unmatched.csv`). The name is derived from the last part of the URL path, sanitized to be filename-safe.
    - Content: A single column listing the recommended titles from that *specific URL* that were *not* found in your DAT file according to the matching criteria. This helps identify potential missing games or naming discrepancies for each source list.

== 8. Console Output ==

While running, the script will display:
- Status messages (fetching, parsing, filtering, writing) usually in cyan.
- Warnings in yellow and Errors in red (printed to stderr).
- A progress bar (`tqdm`) during the main filtering stage.
- A final summary report with colored results and aligned numbers, showing counts for total games, web titles, matches found, non-matches, etc., and the matching algorithm used (`token_set_ratio`).

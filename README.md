# VREC DAT Filter Script

**Version:** 1.3.2 (as of 2025-03-30)

## 1. Purpose

This Python script filters a game list file in DAT/XML format (like those used by ROM managers based on the Logiqx DTD, e.g., from Redump.org) based on recommended game titles scraped from one or more specified web pages.

**Important:** The current web scraping logic is specifically designed to extract titles from HTML tables having the class `wikitable`, expecting the game title to be in the *second* column of each row (skipping the header row). It may not work correctly on pages with different structures.

It works by:
1.  Taking the base URL(s) you provide via `--urls`.
2.  Optionally checking for corresponding `/Homebrew` and `/Japan` pages if requested via flags (`-hb`, `-j`).
3.  Fetching the recommended game titles from all existing/valid URLs found (targeting `wikitable` structure).
4.  Parsing your input DAT file (validating it has a `<datafile>` root element).
5.  Cleaning both the web titles and the DAT titles (removing common tags like `(USA)`, `[Europe]`, parentheses content, most punctuation).
6.  Comparing the cleaned DAT titles against the cleaned web titles using fuzzy matching (specifically, the `'token_set_ratio'` algorithm from `thefuzz` library) with a configurable similarity threshold (`--threshold`).
7.  Generating a new, filtered DAT file containing only the games that matched the web list criteria, updating the DAT header information in the process.
8.  Generating separate CSV files for each source URL successfully processed, listing any recommended titles from that specific URL that were *not* found with sufficient similarity in your DAT file.
9.  Displaying status messages using standard Python `logging`. Console output is colored (via `coloredlogs`) and formatted without timestamps by default (`LEVEL: Message`). An optional log file captures detailed DEBUG-level logs with timestamps. Progress bars (`tqdm`) are shown during lengthy operations.

## 2. Input File Recommendations (1G1R DATs)

For the best results with this script, it is **highly recommended** to use a **"1 Game 1 ROM" (1G1R)** style DAT file as your input.

### What are 1G1R DATs?
Standard DAT files from sources like Redump or No-Intro often list multiple versions of the same game (regions, revisions, etc.). A 1G1R DAT file aims to include only one "best" or preferred version of each unique game, usually prioritizing your preferred region(s) and the latest official revision, removing most duplicates.

### Why use 1G1R with this script?
-   **Fewer Duplicates:** Reduces the chance of multiple entries in your DAT file matching the same recommended title.
-   **Faster Processing:** Filtering a smaller DAT file is quicker.
-   **Better Matching Focus:** Improves the relevance of the matches found and reduces noise in the output DAT.

### How to get 1G1R DATs?
You typically create 1G1R DAT files yourself using ROM manager tools like **RomVault**, **Romulus**, **Retool**, or **ClrMamePro** by filtering comprehensive DAT files (e.g., from Redump or No-Intro) based on your preferences (regions, languages, removing demos, etc.).

Using a 1G1R DAT as the `<input_file>` is likely to produce the most useful and manageable results.

## 3. Prerequisites

1.  **Python 3:** Version 3.8 or later is recommended.
    * Download from: [python.org](https://www.python.org/downloads/)
    * **IMPORTANT:** During installation on Windows, make sure to check the box **"Add Python X.Y to PATH"**.
    * Verify installation by opening your terminal (Command Prompt, PowerShell, etc.) and typing `python --version` and `pip --version`.

2.  **Required Python Libraries:**
    * `requests`, `beautifulsoup4`, `lxml`, `thefuzz`, `coloredlogs`, `tqdm`.
    * Install using the `requirements.txt` file (see Setup).

## 4. Setup

1.  **Save the Script:** Save the Python script code to a file named `vrec_filter.py` (or your preferred `.py` filename).
2.  **Create `requirements.txt`:** In the SAME directory as the script, create a plain text file named exactly `requirements.txt`. Paste the following lines into this file:
    ```text
    requests
    beautifulsoup4
    lxml
    thefuzz
    coloredlogs
    tqdm
    ```
3.  **Install Dependencies:** Open your terminal in the script's directory and run:
    ```bash
    pip install -r requirements.txt
    ```
    (You only need to run this install command once per environment, or each time you create a new virtual environment).

## 5. How to Run

1.  Open your terminal (Command Prompt, PowerShell, Windows Terminal, etc.).
2.  Navigate (`cd`) to the directory containing `vrec_filter.py` and your input DAT file.
3.  Run the script using the command structure:
    ```bash
    python vrec_filter.py <input_file> [output_file] --urls <URL1> [URL2...] [OPTIONS]
    ```
    * Remember to use quotes (`"..."`) around file paths or URLs that contain spaces.

## 6. Command Line Arguments

* `input_file` (Positional, Required)
    * Path to the input `.dat` file (XML format, expected root `<datafile>`).
    * Example: `"Sony - PlayStation (1G1R).dat"`

* `output_file` (Positional, Optional)
    * Path for the filtered output `.dat` file.
    * If omitted, defaults to `<input_filename>_filtered.dat` in the same directory as the input file.
    * Example: `"Filtered PSX Games.dat"`

* `--urls <URL1> [URL2...]` or `-u <URL1> [URL2...]` (Flag, Required)
    * One or more *base* URLs of the web pages containing the recommended game titles.
    * **Crucially, these pages must use HTML tables with `class="wikitable"` and have the game title in the second column.**
    * Example: `--urls "https://vsrecommendedgames.miraheze.org/wiki/PlayStation"`

* `--threshold <0-100>` or `-t <0-100>` (Flag, Optional)
    * Minimum similarity percentage (0-100) for a fuzzy match using `thefuzz.token_set_ratio`.
    * Default: `90`
    * Example: `-t 85`

* `--check-homebrew` or `-hb` (Flag, Optional)
    * If included, also checks for and processes `/Homebrew` pages relative to the provided base URLs.

* `--check-japan` or `-j` (Flag, Optional)
    * If included, also checks for and processes `/Japan` pages relative to the provided base URLs.

* `--log-level <LEVEL>` (Flag, Optional)
    * Sets the minimum logging level displayed on the console.
    * Choices: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
    * Default: `INFO` (Shows standard progress, warnings, errors). `DEBUG` shows much more detail, including individual match results.

* `--log-file <FILEPATH>` (Flag, Optional)
    * Path to a file where detailed logs should be written.
    * The log file will always contain messages from `DEBUG` level upwards, including timestamps.
    * Example: `--log-file filter_run.log`

* `-v` or `--version` (Flag, Optional)
    * Displays the script's version number and exits.

## 7. Matching Strategy and Accuracy

This script uses the `thefuzz` library for fuzzy string matching, specifically the **`token_set_ratio`** algorithm.

### Why `token_set_ratio`?
It's generally effective at handling differences in word order and situations where one title might be a subset of another (ignoring extra words). This helps match DAT names (like `"Final Fantasy Anthology - Final Fantasy IV (USA)"`) against cleaner web names (like `"Final Fantasy Anthology"`), reducing the chances of *missing* desired games due to minor naming variations (false negatives).

### The Trade-off
This flexibility might occasionally match related but distinct games that share core words (e.g., `"Metal Gear Solid - VR Missions (USA)"` might match `"Metal Gear Solid"`). This can lead to *false positives* (including potentially unwanted related games in the filtered list).

### Tuning
Use the `--threshold` (`-t`) value (default 90) to balance this:
-   **Increase threshold** (e.g., `-t 95`): Requires a closer match, reducing false positives but potentially missing some valid variations.
-   **Decrease threshold** (e.g., `-t 85`): Allows for more variation, catching more potential matches but increasing the risk of false positives.
Experimentation with the threshold might be needed depending on the source list and DAT file quality.

## 8. Examples

* Basic usage (Checks base URL only, default output name):
    ```bash
    python vrec_filter.py "Sony - PlayStation (1G1R).dat" -u "[https://vsrecommendedgames.miraheze.org/wiki/PlayStation](https://vsrecommendedgames.miraheze.org/wiki/PlayStation)"
    ```
* Processing base URL AND its '/Japan' variant, specifying output file:
    ```bash
    python vrec_filter.py "Sony - PlayStation (1G1R).dat" "My Filtered PSX.dat" -u "[https://vsrecommendedgames.miraheze.org/wiki/PlayStation](https://vsrecommendedgames.miraheze.org/wiki/PlayStation)" -j
    ```
* Processing base URL AND '/Homebrew' AND '/Japan' for SNES, with 88% threshold and saving a detailed log file:
    ```bash
    python vrec_filter.py "input/snes_1g1r.dat" "output/snes_filtered.dat" -u "[https://vsrecommendedgames.miraheze.org/wiki/SNES](https://vsrecommendedgames.miraheze.org/wiki/SNES)" -hb -j -t 88 --log-file snes_filter.log
    ```
* Showing DEBUG output on console while filtering Mega Drive/Genesis:
    ```bash
    python vrec_filter.py "input/genesis_1g1r.dat" -u "[https://vsrecommendedgames.miraheze.org/wiki/Mega_Drive](https://vsrecommendedgames.miraheze.org/wiki/Mega_Drive)" --log-level DEBUG
    ```

## 9. Output Files

1.  **Filtered DAT File:**
    * Named as specified by `output_file` or defaults to `<input_filename>_filtered.dat`.
    * Contains `<game>` entries from the input DAT that matched a recommended title from the scraped URLs based on the fuzzy matching threshold.
    * **Updated Header:** The `<header>` section is modified:
        * `<name>`: Appends ` (VREC DAT Filter)` (after attempting to remove original final parentheses like `(Retool)`).
        * `<description>`: Appends ` (VREC DAT Filter)`.
        * `<version>`: Set to the script's current version (e.g., `1.3.2`).
        * `<date>`: Set to the date the script was run (YYYY-MM-DD).
        * `<author>`: Set to "f3rs3n, Gemini".
        * `<homepage>`: Set to the script's GitHub repository URL.
        * Other relevant tags like `<url>`, `<retool>`, `<clrmamepro>`, `<comment>` are generally preserved from the original header if they existed.

2.  **Unmatched Titles CSV File(s):**
    * One CSV file *may* be created for *each unique URL processed* (including expanded `/Homebrew`, `/Japan` variants).
    * A CSV is only created for a specific URL if titles were successfully scraped from it, *and* some of those titles did *not* find a match in the input DAT file.
    * **Location:** Same directory as the output DAT file.
    * **Naming:** Derived from the URL path, sanitized for filesystem use, ending with `_unmatched.csv` (e.g., `PlayStation_unmatched.csv`, `PlayStation_Homebrew_unmatched.csv`, `Mega_Drive_Japan_unmatched.csv`).
    * **Content:** A simple list of the cleaned recommended titles from that specific URL that were *not* found with sufficient similarity in the input DAT. Useful for investigating potential misses or DAT naming issues.

3.  **Log File (Optional):**
    * Created only if the `--log-file <FILEPATH>` argument is used.
    * Contains detailed logging information from the `DEBUG` level upwards, including timestamps, individual match results (if found), errors, and the final summary. Useful for debugging and record-keeping.

## 10. Console Output

* Uses Python's `logging` module.
* Requires the `coloredlogs` library for colored output (otherwise output is monochrome).
* Default log level is `INFO`, showing major steps, warnings, errors, and the final summary.
* Use `--log-level DEBUG` for much more verbose output, including scraping details and individual match results.
* Console messages (by default) are formatted as `LEVEL: Message` (e.g., `INFO: Filtering complete.`) without timestamps.
* Progress bars (`tqdm`) are displayed during web scraping and DAT filtering phases.

## 11. Origin and Acknowledgements

The initial idea for filtering DAT files based on the Vs. Recommended Games wiki recommendations was inspired by rishooty's vrec-dat-filter script ([https://github.com/rishooty/vrec-dat-filter](https://github.com/rishooty/vrec-dat-filter)).

However, this particular Python script is a complete rewrite from scratch. It was developed collaboratively with the assistance of Google Gemini (using an experimental version available around March 2025), as the primary author did not have the necessary programming expertise to implement the desired features and iterative refinements independently.
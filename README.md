# VREC DAT Filter Script

**Version:** 1.4.2 (as of 2025-04-01)

## 1. Purpose

This Python script filters a game list file in DAT/XML format (like those used by ROM managers based on the Logiqx DTD, e.g., from Redump.org) based on recommended game titles scraped from one or more specified web pages.

**Important:** The current web scraping logic is specifically designed to extract titles from HTML tables having the class `wikitable`, expecting the game title to be in the *second* column of each row (skipping the header row). It may not work correctly on pages with different structures.

It works by:
1.  Taking the base URL(s) you provide via `--urls`.
2.  Optionally checking for corresponding `/Homebrew` and `/Japan` pages if requested via flags (`-hb`, `-j`).
3.  Fetching the recommended game titles from all existing/valid URLs found (targeting `wikitable` structure).
4.  Parsing your input DAT file (validating it has a `<datafile>` root element).
5.  Cleaning both the web titles and the DAT titles (removing common tags like `(USA)`, `[Europe]`, parentheses content, most punctuation).
6.  Finding all potential matches where a cleaned DAT title has a similarity score >= `--threshold` compared to a cleaned web title, using the `fuzz.WRatio` algorithm.
7.  For each web title, selecting the single **best** matching DAT game (highest score) from the potential matches found in the previous step.
8.  Adding special handling to keep all discs (`(Disc 1)`, `(Disc 2)`, etc.) if the best match selected was `(Disc 1)` and other discs of the *exact same base name* were also potential matches.
9.  Generating a new, filtered DAT file containing only the selected best-matching games (and their associated discs), updating the DAT header information in the process.
10. Generating separate CSV files for each source URL successfully processed, listing any recommended titles from that specific URL that did *not* result in a game being kept in the final DAT.
11. Displaying status messages using standard Python `logging`. Console output is colored (via `coloredlogs`) and formatted without timestamps by default (`LEVEL: Message`). An optional log file captures detailed DEBUG-level logs with timestamps. Progress bars (`tqdm`) are shown during lengthy operations.

## 2. Input File Recommendations (1G1R DATs)

For the best results with this script, it is **highly recommended** to use a **"1 Game 1 ROM" (1G1R)** style DAT file as your input.

### What are 1G1R DATs?
Standard DAT files from sources like Redump or No-Intro often list multiple versions of the same game. A 1G1R DAT file aims to include only one "best" or preferred version of each unique game, usually prioritizing your preferred region(s) and the latest official revision, removing most duplicates.

### Why use 1G1R with this script?
-   **Fewer Duplicates:** Reduces the chance of multiple entries in your DAT file matching the same recommended title.
-   **Faster Processing:** Filtering a smaller DAT file is quicker.
-   **Better Matching Focus:** Improves the relevance of the matches found and reduces noise in the output DAT.

### How to get 1G1R DATs?
You typically create 1G1R DAT files yourself using ROM manager tools like **RomVault**, **Romulus**, **Retool**, or **ClrMamePro** by filtering comprehensive DAT files (e.g., from Redump or No-Intro) based on your preferences.

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
    * Minimum similarity percentage (0-100) for a fuzzy match using `fuzz.WRatio`. Only DAT games meeting this threshold against a web title are considered potential candidates.
    * Default: `90`
    * Example: `-t 85`

* `--check-homebrew` or `-hb` (Flag, Optional)
    * If included, also checks for and processes `/Homebrew` pages relative to the provided base URLs.

* `--check-japan` or `-j` (Flag, Optional)
    * If included, also checks for and processes `/Japan` pages relative to the provided base URLs.

* `--log-level <LEVEL>` (Flag, Optional)
    * Sets the minimum logging level displayed on the console.
    * Choices: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
    * Default: `INFO` (Shows standard progress, warnings, errors). `DEBUG` shows much more detail.

* `--log-file <FILEPATH>` (Flag, Optional)
    * Path to a file where detailed logs should be written.
    * The log file will always contain messages from `DEBUG` level upwards, including timestamps.
    * Example: `--log-file filter_run.log`

* `-v` or `--version` (Flag, Optional)
    * Displays the script's version number and exits.

## 7. Matching Strategy and Accuracy

This script uses a two-stage process with the `fuzz.WRatio` algorithm:

1.  **Finding Potential Matches:** It compares every cleaned DAT title against every cleaned web title. If the `WRatio` score is greater than or equal to the specified `--threshold`, the DAT game is considered a *potential* match for that web title.
2.  **Selecting the Best Match:** For each web title, the script looks at all its potential DAT matches found in stage 1. It selects the DAT game with the **highest `WRatio` score** as the "best match" for that web title.
3.  **Multi-Disc Handling:** If the selected best match is identified as "(Disc 1)", the script also checks the *other potential matches for the same web title*. If any of those other matches are also discs (Disc 2, Disc 3, etc.) of the *exact same base game name* (comparing names with disc info removed), they are *also* kept.
4.  **Final Output:** Only the selected best matches (and their associated multi-discs) are included in the final filtered DAT file.

### Why `WRatio`?
It's a more sophisticated algorithm than simple ratio, attempting to handle different kinds of string variations using weighting and heuristics. However, as observed, it can sometimes produce unintuitive scores, especially giving high scores for partial matches involving common words or numbers.

### Threshold Importance
The `--threshold` (`-t`) value (default 90) remains crucial. It determines the **minimum quality** required for a DAT game to even be considered a potential candidate in Stage 1.
-   **Increase threshold** (e.g., `-t 95`): Stricter filtering in Stage 1. Fewer candidates reach Stage 2, reducing chances of a slightly wrong title being selected as "best" if the true match scores just below 95. Higher risk of missing valid matches if they score below the threshold.
-   **Decrease threshold** (e.g., `-t 85`): Looser filtering in Stage 1. More candidates reach Stage 2. Increases the chance that the correct match (even if scoring lower, like 88) is included in the potential list, allowing Stage 2 to pick it if it's the highest scorer *in that list*. Also increases the risk that unrelated games pass the threshold and potentially get selected in Stage 2 if they happen to score highest for a given web title.

Experimentation may be needed. Using a 1G1R DAT helps minimize ambiguity.

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
    * Contains `<game>` entries selected by the "best match" (and multi-disc) logic.
    * **Updated Header:** The `<header>` section is modified:
        * `<name>`: Appends ` (VREC DAT Filter)`.
        * `<description>`: Appends ` (VREC DAT Filter)`.
        * `<version>`: Set to the script's current version (e.g., `1.4.2`).
        * `<date>`: Set to the date the script was run (YYYY-MM-DD).
        * `<author>`: Set to "f3rs3n, Gemini".
        * `<homepage>`: Set to the script's GitHub repository URL.
        * Other relevant tags are generally preserved.

2.  **Unmatched Titles CSV File(s):**
    * One CSV file *may* be created for *each unique URL processed*.
    * A CSV is only created for a specific URL if titles were scraped from it, *and* some of those titles did *not* result in a game being kept in the final DAT via the best match logic.
    * **Location:** Same directory as the output DAT file.
    * **Naming:** Derived from the URL path, sanitized, ending with `_unmatched.csv` (e.g., `PlayStation_unmatched.csv`).
    * **Content:** A simple list of the cleaned recommended titles from that specific URL for which no corresponding game was kept in the filtered DAT. Useful for investigating regional title differences (like Spyro 2) or other misses.

3.  **Log File (Optional):**
    * Created only if the `--log-file <FILEPATH>` argument is used.
    * Contains detailed logging information from the `DEBUG` level upwards, including timestamps, potential matches found, best match selections, errors, and the final summary.

## 10. Console Output

* Uses Python's `logging` module.
* Requires the `coloredlogs` library for colored output (otherwise output is monochrome).
* Default log level is `INFO`, showing major steps, warnings, errors, and the final summary.
* Use `--log-level DEBUG` for much more verbose output.
* Console messages (by default) are formatted as `LEVEL: Message` without timestamps.
* Progress bars (`tqdm`) are displayed during web scraping and DAT filtering phases.

## 11. Origin and Acknowledgements

The initial idea for filtering DAT files based on the Vs. Recommended Games wiki recommendations was inspired by rishooty's vrec-dat-filter script ([https://github.com/rishooty/vrec-dat-filter](https://github.com/rishooty/vrec-dat-filter)).

However, this particular Python script is a complete rewrite from scratch. It was developed collaboratively with the assistance of Google Gemini (using an experimental version available around March/April 2025), as the primary author did not have the necessary programming expertise to implement the desired features and iterative refinements independently.
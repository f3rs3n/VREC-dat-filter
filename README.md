# VREC DAT Filter Script

**Version:** 1.8.5 (as of 2025-04-01)

## 1. Purpose

This Python script filters a game list file in DAT/XML format (like those used by ROM managers based on the Logiqx DTD, e.g., from Redump.org) based on recommended game titles scraped from one or more specified web pages.

**Important:** The current web scraping logic is specifically designed to extract titles from HTML tables having the class `wikitable`, expecting the game title to be in the *second* column of each row (skipping the header row). It may not work correctly on pages with different structures.

It works by:
1.  Taking the base URL(s) you provide via `--urls`.
2.  Optionally checking for corresponding `/Homebrew` and `/Japan` pages if requested via flags (`-hb`, `-j`).
3.  Fetching the recommended game titles from all existing/valid URLs found (targeting `wikitable` structure).
4.  Parsing your input DAT file (validating it has a `<datafile>` root element).
5.  Pre-cleaning all DAT titles and web titles (removing common tags, parentheses content, most punctuation).
6.  **Stage 1 (Finding High Matches):** Finding potential matches where a cleaned DAT title has a `WRatio` score >= `--threshold` compared to a cleaned web title. Both `WRatio` and `TokenSortRatio` scores are stored for these high matches.
7.  **Stage 2 (Automatic Best Match Selection):** For each web title, selecting the single "best" matching DAT game from the high-scoring candidates found in Stage 1. The selection prioritizes the highest `WRatio` score, using the `TokenSortRatio` score as a tie-breaker if WRatio scores are identical. Special handling automatically includes all discs (`(Disc 1)`, `(Disc 2)`, etc.) if Disc 1 is selected as the best match and other discs of the same base game were also high-scoring candidates.
8.  **Stage 3 (Optional Interactive Review):** If the `-ir` flag is used, the script identifies web titles for which no automatic match was kept in Stage 2. For each of these, it recalculates `WRatio` and `TokenSortRatio` scores against all discarded DAT games. It presents the user with a filtered list of candidates where *both* scores meet a minimum low threshold (default 51%). The user can then choose to manually keep one of the candidates (and its related discs, if applicable).
9.  Generating a new, filtered DAT file containing only the selected games (from Stage 2 and optionally Stage 3), updating the DAT header information.
10. Generating separate CSV files for each source URL, listing any recommended titles from that URL for which no game was ultimately kept in the filtered DAT.
11. Displaying status messages using standard Python `logging`. Console output is colored (via `coloredlogs`) and formatted without timestamps by default (`LEVEL: Message`). An optional log file captures detailed DEBUG-level logs with timestamps. Progress bars (`tqdm`) are shown during lengthy operations. Interactive prompts use `colorama` for better readability.

## 2. Input File Recommendations (1G1R DATs)

For the best results with this script, it is **highly recommended** to use a **"1 Game 1 ROM" (1G1R)** style DAT file as your input.

### What are 1G1R DATs?
Standard DAT files often list multiple versions of the same game. A 1G1R DAT file aims to include only one "best" or preferred version of each unique game, usually prioritizing your preferred region(s) and the latest official revision, removing most duplicates.

### Why use 1G1R with this script?
-   **Fewer Duplicates:** Reduces ambiguity during matching.
-   **Faster Processing:** Filtering a smaller DAT file is quicker.
-   **Better Matching Focus:** Improves the relevance of matches.

### How to get 1G1R DATs?
You typically create 1G1R DAT files yourself using ROM manager tools like **RomVault**, **Romulus**, **Retool**, or **ClrMamePro** by filtering comprehensive DAT files based on your preferences.

Using a 1G1R DAT as the `<input_file>` is likely to produce the most useful results.

## 3. Prerequisites

1.  **Python 3:** Version 3.8 or later is recommended.
    * Download from: [python.org](https://www.python.org/downloads/)
    * **IMPORTANT:** During installation on Windows, make sure to check the box **"Add Python X.Y to PATH"**.
    * Verify installation by opening your terminal and typing `python --version` and `pip --version`.

2.  **Required Python Libraries:**
    * `requests`, `beautifulsoup4`, `lxml`, `thefuzz`, `coloredlogs`, `colorama`, `tqdm`.
    * Install using the `requirements.txt` file (see Setup).

## 4. Setup

1.  **Save the Script:** Save the Python script code to a file named `filter_script.py` (or your preferred `.py` filename).
2.  **Create `requirements.txt`:** In the SAME directory as the script, create a plain text file named exactly `requirements.txt`. Paste the following lines into this file:
    ```text
    requests
    beautifulsoup4
    lxml
    thefuzz
    coloredlogs
    colorama
    tqdm
    ```
3.  **Install Dependencies:** Open your terminal in the script's directory and run:
    ```bash
    pip install -r requirements.txt
    ```
    (You only need to run this install command once per environment).

## 5. How to Run

1.  Open your terminal (Command Prompt, PowerShell, Windows Terminal, etc.).
2.  Navigate (`cd`) to the directory containing `filter_script.py` and your input DAT file.
3.  Run the script using the command structure:
    ```bash
    python filter_script.py <input_file> [output_file] --urls <URL1> [URL2...] [OPTIONS]
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
    * Minimum similarity percentage (0-100) using `fuzz.WRatio` required for a DAT game to be considered a candidate during the automatic matching stage (Stage 1 & 2).
    * Default: `90`
    * Example: `-t 85`

* `--check-homebrew` or `-hb` (Flag, Optional)
    * If included, also checks for and processes `/Homebrew` pages relative to the provided base URLs.

* `--check-japan` or `-j` (Flag, Optional)
    * If included, also checks for and processes `/Japan` pages relative to the provided base URLs.

* `--interactive-review` or `-ir` (Flag, Optional)
    * If included, activates Stage 3. After automatic matching, interactively review web titles that had no automatic match kept. Shows discarded DAT candidates where *both* `WRatio` and `TokenSortRatio` scores (recalculated against the web title) are >= `51` (the default low threshold). Allows manually selecting a candidate (automatically includes other discs if Disc 1 is chosen).
    * Default low threshold: `51` (defined by `INTERACTIVE_LOW_THRESHOLD` constant in script).

* `--log-level <LEVEL>` (Flag, Optional)
    * Sets the minimum logging level displayed on the console.
    * Choices: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
    * Default: `INFO`. `DEBUG` shows much more detail.

* `--log-file <FILEPATH>` (Flag, Optional)
    * Path to a file where detailed logs should be written.
    * The log file will always contain messages from `DEBUG` level upwards, including timestamps.
    * Example: `--log-file filter_run.log`

* `-v` or `--version` (Flag, Optional)
    * Displays the script's version number and exits.

## 7. Matching Strategy and Accuracy

This script uses a multi-stage process with fuzzy matching:

1.  **Stage 1 (Finding High Matches):** Compares every cleaned DAT title against every cleaned web title using `fuzz.WRatio`. If the score is >= `--threshold`, it also calculates `fuzz.token_sort_ratio` and stores both scores along with the DAT game element, associated with the web title.
2.  **Stage 2 (Automatic Best Match Selection):** For each web title, it examines the high-scoring candidates found in Stage 1. It sorts these candidates first by `WRatio` score (highest first), then by `TokenSortRatio` score (highest first) as a tie-breaker. The top candidate after this sort is selected as the "best match".
3.  **Stage 2 (Multi-Disc Auto-Add):** If the selected best match is identified as "(Disc 1)", the script checks the other high-scoring candidates *for the same web title*. If any represent subsequent discs (Disc 2, 3, etc.) of the *exact same base game name*, they are automatically added alongside Disc 1.
4.  **Stage 3 (Optional Interactive Review):** If `-ir` is used, this stage addresses web titles left unmatched after Stage 2.
    * It finds all DAT games discarded previously.
    * It compares the unmatched web title against *each* discarded DAT game, calculating both `WRatio` and `TokenSortRatio`.
    * It presents a list of candidates where *both* scores meet the `INTERACTIVE_LOW_THRESHOLD` (default 51).
    * The user can select one candidate from the list. If Disc 1 is selected, subsequent discs from the *presented candidate list* are automatically added.
5.  **Final Output:** The filtered DAT includes games selected in Stage 2 plus any games manually selected (including auto-added discs) in Stage 3.

### Algorithm Notes (`WRatio`, `TokenSortRatio`)
-   `WRatio` is used as the primary score due to its general robustness but can sometimes give unintuitively high scores for partially similar titles (e.g., those sharing numbers or specific words like "Rage").
-   `TokenSortRatio` is used as a tie-breaker in Stage 2 and a secondary filter in Stage 3. It handles word order differences better than simple ratio but is less complex than `WRatio`.
-   The `--threshold` only applies to the initial `WRatio` comparison in Stage 1. The interactive stage uses the separate `INTERACTIVE_LOW_THRESHOLD` for both algorithms.

### Tuning
-   Adjust `--threshold` (`-t`) to control the strictness of the *automatic* matching. Higher values are stricter.
-   The interactive mode (`-ir`) helps catch specific cases missed by automatic matching (like regional titles with low scores) but requires user intervention. The fixed low threshold of 51 for the interactive filter aims to balance showing potential matches without being overwhelming, but might still show some noise or miss very low-scoring correct matches.

## 8. Examples

* Basic usage (Automatic matching only):
    ```bash
    python filter_script.py "Sony - PlayStation (1G1R).dat" -u "[https://vsrecommendedgames.miraheze.org/wiki/PlayStation](https://vsrecommendedgames.miraheze.org/wiki/PlayStation)"
    ```
* Automatic matching + '/Japan' variant, specifying output file:
    ```bash
    python filter_script.py "Sony - PlayStation (1G1R).dat" "My Filtered PSX.dat" -u "[https://vsrecommendedgames.miraheze.org/wiki/PlayStation](https://vsrecommendedgames.miraheze.org/wiki/PlayStation)" -j
    ```
* Automatic matching + '/Homebrew' + '/Japan' for SNES, 88% threshold, saving log:
    ```bash
    python filter_script.py "input/snes_1g1r.dat" "output/snes_filtered.dat" -u "[https://vsrecommendedgames.miraheze.org/wiki/SNES](https://vsrecommendedgames.miraheze.org/wiki/SNES)" -hb -j -t 88 --log-file snes_filter.log
    ```
* Showing DEBUG output on console while filtering Mega Drive/Genesis:
    ```bash
    python filter_script.py "input/genesis_1g1r.dat" -u "[https://vsrecommendedgames.miraheze.org/wiki/Mega_Drive](https://vsrecommendedgames.miraheze.org/wiki/Mega_Drive)" --log-level DEBUG
    ```
* Using **interactive review** for unmatched titles (after automatic matching with default 90% threshold):
    ```bash
    python filter_script.py "input/psx_1g1r.dat" -u "[https://vsrecommendedgames.miraheze.org/wiki/PlayStation](https://vsrecommendedgames.miraheze.org/wiki/PlayStation)" -ir
    ```

## 9. Output Files

1.  **Filtered DAT File:**
    * Named as specified by `output_file` or defaults to `<input_filename>_filtered.dat`.
    * Contains `<game>` entries selected automatically (Stage 2) and potentially via user input (Stage 3).
    * **Updated Header:** The `<header>` section is modified (Name/Desc suffix, script Version, Date, Author, Homepage). Other relevant tags are preserved.

2.  **Unmatched Titles CSV File(s):**
    * One CSV file *may* be created for *each unique URL processed*.
    * A CSV is only created for a specific URL if titles were scraped from it, *and* some of those titles were *still* considered unmatched after both automatic selection and the optional interactive review.
    * **Location:** Same directory as the output DAT file.
    * **Naming:** Derived from URL path, sanitized, ending with `_unmatched.csv`.
    * **Content:** List of cleaned recommended titles from that URL for which no game was kept. Useful for identifying misses.

3.  **Log File (Optional):**
    * Created if `--log-file` is used.
    * Contains detailed DEBUG-level logs with timestamps.

## 10. Console Output

* Uses Python's `logging` module with colors via `coloredlogs`.
* Default level (`INFO`) shows major steps, warnings, errors, summary.
* `--log-level DEBUG` shows detailed processing, including match scores.
* Console format (default): `LEVEL: Message` (no timestamp).
* Interactive prompts (if `-ir` used) use `colorama` for highlighting.
* Progress bars (`tqdm`) show progress for lengthy steps.

## 11. Origin and Acknowledgements

The initial idea for filtering DAT files based on the Vs. Recommended Games wiki recommendations was inspired by rishooty's vrec-dat-filter script ([https://github.com/rishooty/vrec-dat-filter](https://github.com/rishooty/vrec-dat-filter)).

However, this particular Python script is a complete rewrite from scratch. It was developed collaboratively with the assistance of Google Gemini (using versions available around March/April 2025), as the primary author did not have the necessary programming expertise to implement the desired features and iterative refinements independently.

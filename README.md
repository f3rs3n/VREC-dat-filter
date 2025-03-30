# VREC DAT Game Filter Script

## 1. Purpose

This Python script filters a game list file in DAT/XML format (like those used by ROM managers based on the Logiqx DTD, e.g., from redump.org) based on recommended game titles scraped from one or more specified web pages (e.g., wiki lists like Vs. Recommended Games).

It works by:
1.  Taking the base URL(s) you provide via `--urls`.
2.  Optionally checking for corresponding `/Homebrew` and `/Japan` pages if requested via flags (`-hb`, `-j`).
3.  Fetching the recommended game titles from all existing/valid URLs found.
4.  Parsing your input DAT file to get the game names.
5.  Cleaning both the web titles and the DAT titles (removing common tags like `(USA)`, `[Europe]`, etc.).
6.  Comparing the cleaned DAT titles against the cleaned web titles using fuzzy matching (specifically, the `'token_set_ratio'` algorithm from `thefuzz` library) with a configurable similarity threshold.
7.  Generating a new, filtered DAT file containing only the games that matched the web list criteria, updating the DAT header information in the process.
8.  Generating separate CSV files for each source URL successfully processed, listing any recommended titles from that specific URL that were *not* found with sufficient similarity in your DAT file.
9.  Displaying colored status messages, a progress bar (`tqdm`), and a final summary report in the terminal.

## 2. Input File Recommendations (1G1R DATs)

For the best results with this script, it is **highly recommended** to use a **"1 Game 1 ROM" (1G1R)** style DAT file as your input.

### What are 1G1R DATs?
Standard DAT files from sources like Redump or No-Intro often list multiple versions of the same game. A 1G1R DAT file aims to include only one "best" or preferred version of each unique game, usually prioritizing your preferred region(s) and the latest official revision, removing most duplicates.

### Why use 1G1R with this script?
- **Fewer Duplicates:** Reduces the chance of multiple entries in your DAT file matching the same recommended title.
- **Faster Processing:** Filtering a smaller DAT file is quicker.
- **Better Matching Focus:** Improves the relevance of the matches found.

### How to get 1G1R DATs?
You typically create 1G1R DAT files yourself using ROM manager tools like **RomVault**, **Romulus**, **Retool**, or **ClrMamePro** by filtering comprehensive DAT files (e.g., from Redump or No-Intro) based on your preferences.

Using a 1G1R DAT as the `<INPUT_FILE>` is likely to produce the most useful results.

## 3. Prerequisites

1.  **Python 3:** Version 3.8 or later is recommended.
    - Download from: [python.org](https://www.python.org/downloads/windows/)
    - **IMPORTANT:** During installation on Windows, make sure to check the box **"Add Python X.Y to PATH"**.
    - Verify installation by opening your terminal (Command Prompt, PowerShell, etc.) and typing `python --version` and `pip --version`.

2.  **Required Python Libraries:**
    - `requests`, `beautifulsoup4`, `lxml`, `thefuzz`, `colorama`, `tqdm`.
    - Install using the `requirements.txt` file (see Setup).

## 4. Setup

1.  **Save the Script:** Save the Python script code to a file named `filter_script.py` (or your preferred `.py` filename).
2.  **Create `requirements.txt`:** In the SAME directory as the script, create a plain text file named exactly `requirements.txt`. Paste the following lines into this file:
    ```text
    requests
    beautifulsoup4
    lxml
    thefuzz
    colorama
    tqdm
    ```
3.  **Install Dependencies:** Open your terminal in the script's directory and run:
    ```bash
    pip install -r requirements.txt
    ```
    (You only need to run this install command once per environment, or each time you create a new virtual environment).

## 5. How to Run

1.  Open your terminal (Command Prompt, PowerShell, Windows Terminal, etc.).
2.  Navigate (`cd`) to the directory containing `filter_script.py` and your input DAT file.
3.  Run the script using the command structure:
    ```bash
    python filter_script.py <INPUT_FILE> [OUTPUT_FILE] --urls <URL1> [URL2...] [OPTIONS]
    ```
    - Remember to use quotes (`"..."`) around file paths or URLs that contain spaces.

## 6. Command Line Arguments

* `INPUT_FILE` (Positional, Required)
    - Path to the input `.dat` file (or `.xml`/`.txt` containing XML).
    - Example: `"Sony - PlayStation (1G1R).dat"`

* `OUTPUT_FILE` (Positional, Optional)
    - Path for the filtered output `.dat` file.
    - If omitted, defaults to `<input_filename>_filtered.dat` in the same directory as the input file.
    - Example: `"Filtered PSX Games.dat"`

* `--urls <URL1> [URL2...]` or `-u <URL1> [URL2...]` (Flag, Required)
    - One or more *base* URLs of the web pages containing the recommended game titles.
    - Example: `--urls "https://vsrecommendedgames.miraheze.org/wiki/PlayStation"`

    *NOTE ON URLs:* Source wikis may change domains. Provide the current *base* URL(s). The script should work if the path structure (e.g., `/wiki/SystemName`) remains similar. Use the optional flags (`-hb`, `-j`) to automatically check for specific sub-pages.

* `--threshold <0-100>` or `-t <0-100>` (Flag, Optional)
    - Minimum similarity percentage (0-100) for a match.
    - Default: `90`
    - Example: `-t 85`

* `--check-homebrew` or `-hb` (Flag, Optional)
    - If included, also checks for and processes `/Homebrew` pages relative to base URLs.

* `--check-japan` or `-j` (Flag, Optional)
    - If included, also checks for and processes `/Japan` pages relative to base URLs.

## 7. Matching Strategy and Accuracy

This script uses the `thefuzz` library for fuzzy string matching, specifically the **`token_set_ratio`** algorithm.

### Why `token_set_ratio`?
It's good at handling word order differences and cases where one title is a subset of another (ignoring extra words). This helps match DAT names (like "Final Fantasy Anthology - FFIV") against cleaner web names (like "Final Fantasy Anthology"), minimizing *false negatives* (missing desired games).

### The Trade-off
This flexibility might occasionally match related but distinct games sharing core words (e.g., "Metal Gear Solid - VR Missions" might match "Metal Gear Solid"). This can lead to *false positives* (including potentially unwanted games).

### Tuning
Use the `--threshold` (`-t`) value (default 90) to balance this:
- **Increase threshold** (e.g., `-t 95`): Stricter matching, fewer false positives, higher risk of missing variations.
- **Decrease threshold** (e.g., `-t 85`): Looser matching, catches more variations, higher risk of false positives.
Experimentation may be needed.

## 8. Examples

* Basic usage (Checks base URL only):
    ```bash
    python filter_script.py "Sony - PlayStation (1G1R).dat" -u "[https://vsrecommendedgames.miraheze.org/wiki/PlayStation](https://vsrecommendedgames.miraheze.org/wiki/PlayStation)"
    ```
* Processing base URL AND its '/Japan' variant:
    ```bash
    python filter_script.py "Sony - PlayStation (1G1R).dat" -u "[https://vsrecommendedgames.miraheze.org/wiki/PlayStation](https://vsrecommendedgames.miraheze.org/wiki/PlayStation)" -j
    ```
* Processing base URL AND '/Homebrew' AND '/Japan' variants, with 88% threshold:
    ```bash
    python filter_script.py "input/snes_1g1r.dat" "output/snes_filtered.dat" -u "[https://wiki.example.com/wiki/SNES](https://wiki.example.com/wiki/SNES)" -hb -j -t 88
    ```
* Processing multiple systems, checking '/Japan' for both:
    ```bash
    python filter_script.py "input/all_systems.dat" -u "[https://wiki.example.com/wiki/PlayStation](https://wiki.example.com/wiki/PlayStation)" "[https://wiki.example.com/wiki/Saturn](https://wiki.example.com/wiki/Saturn)" -j
    ```

## 9. Output Files

1.  **Filtered DAT File:**
    - Named as specified or `<input_filename>_filtered.dat`.
    - Contains `<game>` entries matching web titles (using `token_set_ratio`).
    - **Updated Header:** The `<header>` section is modified:
        - `<name>`: Appends ` (VREC DAT Filter)` (after removing original final parentheses like `(Retool)`).
        - `<description>`: Appends ` (VREC DAT Filter)`.
        - `<version>`: Set to the script's version (e.g., 1.1.0).
        - `<date>`: Set to the date the script was run (YYYY-MM-DD).
        - `<author>`: Set to "f3rs3n, Gemini".
        - `<homepage>`: Set to the script's GitHub repository URL.
        - Other tags like `<url>`, `<retool>`, `<clrmamepro>` are generally preserved from the original header.

2.  **Unmatched Titles CSV File(s):**
    - One CSV may be created for *each URL processed* (including optional `/Homebrew`, `/Japan`) *if* it had titles not matched in the DAT.
    - Location: Same directory as the output DAT file.
    - Naming: `<SystemName>_<Variant>_unmatched.csv` (e.g., `PlayStation_unmatched.csv`, `PlayStation_Homebrew_unmatched.csv`). Derived from URL path.
    - Content: List of recommended titles from that specific URL not found in the DAT.

## 10. Console Output

Displays: Status messages (colored), progress bars (`tqdm`), and a final summary report (colored, aligned). 404 errors for optional URLs are shown as dim info messages.

## 11. Origin and Acknowledgements

The initial idea for filtering DAT files based on the V.Rec wiki recommendations was inspired by rishooty's vrec-dat-filter script ([https://github.com/rishooty/vrec-dat-filter](https://github.com/rishooty/vrec-dat-filter)).

However, this particular Python script is a complete rewrite from scratch. It was developed collaboratively with the assistance of Google Gemini (using an experimental version available around March 2025), as I did not have the necessary programming expertise to implement the desired features and iterative refinements independently.
# conference-h-indexes
A set of scripts for scraping citation data to enable h-index comparisons among scientific conferences

## Scraper functionality
In this repository, there are three scripts present for scraping and processing of conference information from dblp.

### 1. Scraper ([scraper.py](scraper.py))  
It works by finding all articles in requested volumes based on [scraper seettings](#scraper-settings) from dblp.org
and then finds their respective citation counts on google scholar either through the article's DOI or title.  
By default, the raw scraped data gets saved into an ```out/``` folder where for each volume of each conference a 
separate csv file is created.  
Here csv naming is created by concatenating the conference shortcut (e. g. "acl"), and the year (e. g. "2023"). Additionally,
if the processed volume is a finding, the name will be appended with "_f".

**Example names**:
- **acl_2023.csv**: Main conference of ACL 2023
- **acl_2023_f.csv**: Findings of ACL 2023

### 2. H-index calculator  ([h_index_calculator.py](h_index_calculation.py))    
It aggregates all csv files in the ```out/``` folder and calculates the h-index for each conference volume. The output
is then saved in a csv file with name ```conferences_h_indices.csv```

### 3. Manual revision ([manual_revision.py](manual_revision.py))
This script scans all csv files and searches for papers that have a citation count of -1, which indicates that the 
scraper was not able to find the paper on google scholar.  
Then script asks for revision for each of the identified papers, where use can either input a valid citation count or
just press Enter to skip the revision. Afterwards, the revisions are updated in their corresponding csv files.

### Scraper settings
In order to scrape a conference volume, the scraper needs at least 2 pieces of information:
1. The conference name abbreviation, such that the following URL is valid: https://dblp.org/db/conf/CONFERENCE_NAME
2. The volume title you want to scrape articles from. The title needs to be copy pasted from https://dblp.org/db/conf/CONFERENCE_NAME, however, you do not need to copy paste the entire title, as they tend to be quite verbose. Instead, you only need to copy enough of the title so that it is unique.

These 2 instructions need to be written on separate lines. To scrape multiple volumes from the same conference, the conference name does not need to be specified again, you only have to put each volume on a separate line.

You can also specify the method individual articles are searched on google scholar. By default, the scraper performs searches through DOIs, you can change this behavior to title search by adding (title) next to the conference name. From my observations, acl conferences have reliable DOIs which are searchable on google scholar, however, non-acl conferences either do not have DOIs or they return irrelevant results and have more reliable results when searched by title. If an article is set to search by DOI, but a DOI is not available, it switches to title search.

Lastly, by adding a ```#``` at the beginning of a line, it will be ignored when reading the file.

#### Example:
```
acl (doi)
Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)
Findings of the Association for Computational Linguistics, ACL 2024

emnlp (title)
Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing
Findings of the Association for Computational Linguistics: EMNLP 2024
Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing
```
The complete settings for the current release of the scraper blog can be found in the [scraper_settings.txt](scraper_settings.txt) file. 

## Running the scripts

### Python version: 3.10
The latest version of the scraper was run on python __3.10__, so this is the recommended version to use.

### 1. Scraper
To run the scraper itself you can use the following command:
```
python scraper.py
```
The command also allows following options:
```
options:
  -h, --help           show this help message and exit
  --settings SETTINGS  Path to the scrape settings file (default: scrape_settings.txt)
  --out OUT            Path to the output folder (default: out/)
```

### 2. H-index calculator
Command:
```
python h_index_calculation.py
```
Options: 
```
options:
  -h, --help            show this help message and exit
  --csv-folder CSV_FOLDER
                        Path to the folder containing the CSV files (default: out/)
  --out OUT             Name of the output CSV file (default: conferences_h_indices.csv)
```

### 3. Manual revision
Command:
```
python manual_revision.py
```
This command has to arguments but you have to interact with the revision prompts described in the 
[manual revision section](#3-manual-revision-manual_revisionpy).


# Limitations
The scraper does not cycle proxies and instead tries to stay undetected by captcha as long as possible. Consequently, the scraping speed is quite slow, only around 100 articles get scraped in an hour. Moreover, it is possible for captcha to block scraping, however, it is uncommon. In such a case, the ip address has to be changed to continue scraping, or wait around a day to reset the block.

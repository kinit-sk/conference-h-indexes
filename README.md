# conference-h-indexes
A set of scripts for scraping citation data to enable h-index comparisons among scientific conferences
# Scraper
The scraper is saved in the scraper.py file. It works by finding all articles in requested volumes on dblp and then finds their respective citation counts on google scholar either through the article's DOI or title. By default, the raw scraped data get saved into raw_data.csv, which is used for h-index calculation.

## Scraper settings
In order to scrape a conference volume, the scraper needs at least 2 pieces of information:
1. The conference name abbreviation, such that the following URL is valid: https://dblp.org/db/conf/CONFERENCE_NAME
2. The volume title you want to scrape articles from. The title needs to be copy pasted from https://dblp.org/db/conf/CONFERENCE_NAME, however, you do not need to copy paste the entire title, as they tend to be quite verbose. Instead, you only need to copy enough of the title so that it is unique.

These 2 instructions need to be written on separate lines. To scrape multiple volumes from the same conference, the conference name does not need to be specified again, you only have to put each volume on a separate line.

You can also specify the method individual articles are searched on google scholar. By default, the scraper performs searches through DOIs, you can change this behavior to title search by adding (title) next to the conference name. From my observations, acl conferences have reliable DOIs which are searchable on google scholar, however, non-acl conferences either do not have DOIs or they return irrelevant results and have more reliable results when searched by title. If an article is set to search by DOI, but a DOI is not available, it switches to title search.

Lastly, by adding # at the beginning of a line, it will be ignored when reading the file.

## Examples
Examples of the correct scrape settings can be found in the scrape_settings file.

# Limitations
The scraper does not cycle proxies and instead tries to stay undetected by captcha as long as possible. Consequently, the scraping speed is quite slow, only around 100 articles get scraped in an hour. Moreover, it is possible for captcha to block scraping, however, it is uncommon. In such a case, the ip address has to be changed to continue scraping, or wait around a day to reset the block.

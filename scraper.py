from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

import selenium.webdriver.support.expected_conditions as ec
import undetected_chromedriver as uc
from fake_useragent import UserAgent

import speech_recognition as sr
from lxml.html.soupparser import fromstring
from time import sleep
from pydub import AudioSegment
from random import randrange
from collections import defaultdict
from datetime import datetime
import requests
import pandas as pd


OUTPUT_FILE_PATH = "raw_data.csv"


def initiate_scraper():
    """
    Initiates the scraper
    """
    scrape_targets = extract_scrape_settings()
    root_url = "https://dblp.org/db/conf/"
    driver = create_driver()
    recognizer = create_recognizer()
    conference_links = get_conference_links(scrape_targets, root_url)
    manage_conference_info(conference_links, scrape_targets, driver, recognizer)
    driver.quit()


def extract_scrape_settings():
    """
    Extracts conferences, volumes and Google Scholar scrape method (through DOI or title)
    from the scrape_settings.txt file
    """

    scrape_targets = defaultdict(list)
    conference = ""
    is_conference = True

    with open("scrape_settings.txt") as file:
        for line in file:
            line = line.strip()

            if "#" in line:
                continue

            if is_conference:
                is_conference = False
                split = line.split(" (")
                mode = "doi"
                if len(split) == 2 and "title" in split[1].lower():
                    mode = "title"
                conference = (split[0], mode)

            elif line == "":
                is_conference = True
            else:
                scrape_targets[conference].append(line)

    return scrape_targets


def create_driver():
    """
    Creates a Selenium driver
    """
    ua = UserAgent()
    user_agent = ua.random
    options = Options()
    # options.add_argument("--headless")
    options.add_argument(f'user-agent={user_agent}')
    options.add_argument("--disable-blink-features=AutomationControlled")

    # NOTE: if driver cannot be created due to incorrect version, you can edit the version in the uc.Chrome parameter
    driver = uc.Chrome(version_main=126, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    driver.maximize_window()
    return driver


def create_recognizer():
    return sr.Recognizer()


def get_elements_urls(elements):
    return list(map(get_element_url, elements))


def get_element_url(element):
    return element.attrib["href"]


def get_element_text(element):
    return element.text_content()


def format_volume_name(volume):
    return f'"{volume}"' if "'" in volume else f"'{volume}'"


def get_conference_links(scrape_data, root_url):
    """
    Finds the links of conference volumes specified in scrape settings
    """

    links = defaultdict(list)
    for conference, volumes in scrape_data.items():
        conference_page = fromstring(requests.get(root_url + conference[0]).text)
        for volume in volumes:
            volume = format_volume_name(volume)
            conference_link = conference_page.xpath(f"""//span[contains(text(), {volume})]/ancestor::cite/preceding-sibling::nav[@class='publ']//a""")[0]
            year = conference_link.xpath("./ancestor::ul/preceding-sibling::header[1]/h2")[0].attrib["id"]
            links[conference].append([get_element_url(conference_link), year])
    return links


def manage_conference_info(conference_data, scrape_data, driver, recognizer):
    """
    Iterates through all conferences and papers and saves their information
    """

    raw_data = {"DOI": [], "conference_title": [], "scholar_title": [], "conference": [], "volume": [], "citations": [],
                "year": [], "retrieved_at": []}
    for conference_info, conference_data in conference_data.items():
        conference, mode = conference_info
        conference_scrape_volumes = list(scrape_data[conference_info])
        for index, (link, year) in enumerate(conference_data):
            scrape_conference_info(conference_scrape_volumes, index,
                                  link, year, conference, raw_data, mode, driver, recognizer)
    return raw_data


def scrape_conference_info(conference_scrape_volumes, index, link, year, conference, raw_data, mode, driver, recognizer):
    """
    Gets data of conference papers from dblp and Google Scholar
    and saves it to raw_data.csv
    """

    dois = []
    page_data = fromstring(requests.get(link).text)
    volume = conference_scrape_volumes[index]
    print(f"Getting data from the volume {volume}")
    paper_containers = page_data.xpath("//ul[@class='publ-list']")

    for container in paper_containers:
        papers_list = container.xpath("./li[not(@class='no-pub')]")
        for paper in papers_list:
            paper_title = get_element_text(paper.xpath(f"./cite/span[@itemprop='name']")[0])

            if mode == "doi":
                paper_doi = paper.xpath(".//a[contains(text(), 'DOI')]")
                if paper_doi:
                    dois.append(get_element_url(paper_doi[0]).strip("https://doi.org/"))
                else:
                    print(f"No DOI for {paper_title}, using the title instead")
                    dois.append(paper_title)
            else:
                dois.append(f'"{paper_title}"')

            raw_data["conference_title"].append(paper_title)
            raw_data["conference"].append(conference)
            raw_data["volume"].append(volume)
            raw_data["year"].append(year)

    citations, retrieved_at, scholar_titles = get_citations(dois, driver, recognizer)
    raw_data["DOI"] += dois
    raw_data["citations"] += citations
    raw_data["retrieved_at"] += retrieved_at
    raw_data["scholar_title"] += scholar_titles
    save_results(raw_data)


def get_citations(dois, driver, recognizer):
    """
    Searches for every downloaded paper on Google Scholar and finds its citation count
    """
    print(f"Getting citations from {len(dois)} papers")
    citation_counts = []
    retrieved_at = []
    titles = []
    for index, doi in enumerate(dois):
        if (index + 1) % 50 == 0:
            print(f"{index} papers scraped")
        if doi == -1:
            retrieved_at.append(datetime.now())
            citation_counts.append(-1)
            titles.append(-1)
            continue

        driver.get(f"https://scholar.google.com/scholar?q={doi}")
        while """Sorry, we can't verify that you're not a robot when JavaScript is turned off.</div><div>Please <a href="//support.google.com/answer/23852?hl=en">enable JavaScript</a> in your browser and reload this page.""" in driver.page_source:
            driver.refresh()
            solve_captcha(driver, recognizer)

        get_result_information(titles, citation_counts, retrieved_at, driver)
        sleep(randrange(300, 700) / 100)

    print("Citations collected")
    return citation_counts, retrieved_at, titles


def get_result_information(titles, citation_counts, retrieved_at, driver):
    """
    Returns the citation count for the current google scholar article
    """
    try:
        title = driver.find_element(By.XPATH, "//div[@data-rp='0']//h3/a").text
        titles.append(title)
        try:
            citation_element = WebDriverWait(driver, 10).until(
                ec.presence_of_element_located((By.XPATH, "//a[contains(text(), 'Cited by')]"))
            )
            citation_counts.append(int(citation_element.text.split()[-1]))
        except TimeoutException:
            citation_counts.append(0)
            print("No citations")
    except NoSuchElementException:
        titles.append(-1)
        citation_counts.append(-1)
        print("Paper is not on google scholar")

    retrieved_at.append(datetime.now())


def save_results(data):
    print("Saving results")
    pd.DataFrame(data).to_csv(OUTPUT_FILE_PATH, index=False)


def solve_captcha(driver, recognizer):
    """
    Attempts to solve a detected captcha by clicking captcha checkbox
    or by solving the captcha audio. Will fail if the audio solve is no longer available
    and will require a cooldown period until captcha is solvable again.
    """
    
    print("Solving captcha..")
    frame = WebDriverWait(driver, 20).until(ec.presence_of_element_located(
        (By.CSS_SELECTOR, "iframe")))
    driver.switch_to.frame(frame)
    driver.find_element(By.CSS_SELECTOR, "span.recaptcha-checkbox").click()
    driver.switch_to.default_content()
    sleep(randrange(300, 700) / 100)
    try:
        frame = driver.find_elements(By.CSS_SELECTOR, "iframe")[2]
        driver.switch_to.frame(frame)
        WebDriverWait(driver, 20).until(ec.presence_of_element_located(
            (By.CSS_SELECTOR, "#recaptcha-audio-button"))).click()
    except (IndexError, TimeoutException):
        driver.switch_to.default_content()
        print("No additional Captcha check")
        return

    try:
        link = WebDriverWait(driver, 20).until(ec.presence_of_element_located(
            (By.CSS_SELECTOR, "a.rc-audiochallenge-tdownload-link"))).get_attribute("href")
    except TimeoutException:
        if "automated queries" in driver.page_source:
            raise Exception("Captcha blocked, can't scrape more")
        else:
            raise Exception("An error occurred")
    solve_audio_captcha(driver, recognizer, link)
    sleep(randrange(300, 700) / 100)


def solve_audio_captcha(driver, recognizer, link):
    with open("audio.mp3", "wb") as file:
        file.write(requests.get(link).content)

    sound = AudioSegment.from_mp3("audio.mp3")
    sound.export("audio.wav", format="wav")

    with sr.AudioFile("audio.wav") as source:
        audio_data = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio_data)
        except sr.UnknownValueError:
            print("Speech recognition failed. Retrying..")
            return
    print(f"Captcha text: {text}")
    text_field = driver.find_element(By.CSS_SELECTOR, "input#audio-response")
    text_field.send_keys(text)
    text_field.send_keys(Keys.ENTER)


initiate_scraper()

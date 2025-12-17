import os
import requests
import argparse
import dataclasses
import pandas as pd
import speech_recognition as sr
import undetected_chromedriver as uc
from lxml.html.soupparser import fromstring
import selenium.webdriver.support.expected_conditions as ec


from tqdm import tqdm
from time import sleep
from random import randrange
from datetime import datetime
from pydub import AudioSegment
from fake_useragent import UserAgent
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

ROOT_URL = "https://dblp.org/db/conf/"
STOP_MESSAGE = """Sorry, we can't verify that you're not a robot when JavaScript is turned off.</div><div>Please 
<a href="//support.google.com/answer/23852?hl=en">enable JavaScript</a> in your browser and reload this page."""


def create_driver():
    """
    Creates a Selenium driver
    """
    ua = UserAgent()
    user_agent = ua.random
    options = Options()
    options.add_argument("--headless")
    options.add_argument('--accept-lang=en-GB')
    options.add_argument(f'user-agent={user_agent}')
    options.add_argument("--disable-blink-features=AutomationControlled")

    # NOTE: if driver cannot be created due to incorrect version, you can edit the version in the uc.Chrome parameter
    driver = uc.Chrome(version_main=126, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    driver.maximize_window()
    return driver



@dataclasses.dataclass
class Volume:
    driver: sr.Recognizer
    recognizer: sr.Recognizer
    conference: str
    mode: str
    name: str
    year: str
    url: str
    output_folder: str = "out/"
    search_interval: tuple = (300, 700)
    checkpoint_interval: int = 50


    def __post_init__(self):
        if not os.path.exists(self.output_folder):
            os.mkdir(self.output_folder)
        findings_str = "_f" if "findings" in self.name.lower() else ""
        self.output_file_name = os.path.join(self.output_folder, f"{self.conference}_{self.year}{findings_str}.csv")
        self.all_papers = self.get_all_papers()
        self.all_papers["scholar_title"] = self.all_papers["scholar_title"].astype(str)

    @property
    def output_file_exists(self):
        return os.path.exists(self.output_file_name)


    def scrape(self):
        """
        Searches for every downloaded paper on Google Scholar and finds its citation count.
        """
        unscraped_count = len(self.all_papers[self.all_papers["citations"] == -1])
        if unscraped_count < 3:
            return

        print(f"Getting citation counts for {unscraped_count} papers | Saving progress every {self.checkpoint_interval} steps")
        count = 0
        for index, paper in self.all_papers.iterrows():
            # Skip if scraped
            if paper["citations"] != -1:
                continue
            scholar_title, citation_count = -1, -1

            doi = paper["DOI"]
            if doi != -1:
                self.driver.get(f"https://scholar.google.com/scholar?q={doi}")

                # Check and solve CAPTCHA
                while STOP_MESSAGE in self.driver.page_source or "not a robot" in self.driver.page_source:
                    self.driver.refresh()
                    solve_captcha(self.driver, self.recognizer)

                # Scrape citation count
                scholar_title, citation_count = self._parse_scholar_entry()

            self.all_papers.at[index, "scholar_title"] = scholar_title
            self.all_papers.at[index, "citations"] = citation_count
            self.all_papers.at[index, "retrieved_at"] = datetime.now()
            count += 1
            sleep(randrange(*self.search_interval) / 100)

            # Save if checkpoint or end
            if count % self.checkpoint_interval == 0 or count == unscraped_count:
                print(f"Checkpoint: {count} scrapings saved")
                self.all_papers.to_csv(self.output_file_name, mode='w', header=True, index=False)

        print("Citations collected")

    def get_all_papers(self):
        """
        Initializes the papers from volume page on dblp.
        """
        # If it was done before, load the saved data
        if self.output_file_exists:
            return pd.read_csv(self.output_file_name)

        raw_data = {"DOI": [], "conference_title": [], "conference": [], "volume": [], "year": [],
                    "scholar_title": [], "citations": [], "retrieved_at": []}

        page_data = fromstring(requests.get(self.url).text)
        print(f"Getting data from the volume {self.name}")
        paper_containers = page_data.xpath("//ul[@class='publ-list']")

        for container in paper_containers:
            papers_list = container.xpath("./li[not(@class='no-pub')]")
            for paper in papers_list:
                paper_title = get_element_text(paper.xpath(f"./cite/span[@itemprop='name']")[0])

                doi = paper_title
                if self.mode == "doi":
                    paper_doi = paper.xpath(".//a[contains(text(), 'DOI')]")
                    if paper_doi:
                        doi = paper_doi[0].attrib["href"].strip("https://doi.org/")

                raw_data["DOI"].append(doi)
                raw_data["conference_title"].append(paper_title)
                raw_data["conference"].append(self.conference)
                raw_data["volume"].append(self.name)
                raw_data["year"].append(self.year)
                raw_data["scholar_title"].append(-1)
                raw_data["citations"].append(-1)
                raw_data["retrieved_at"].append(-1)

        df = pd.DataFrame(raw_data)
        # Save the data
        df.to_csv(self.output_file_name, mode='w', header=True, index=False)
        return df


    def _parse_scholar_entry(self):
        """
        Returns the citation count for the current google scholar article
        """

        try:
            title = self.driver.find_element(By.XPATH, "//div[@data-rp='0']//h3/a").text
            try:
                citation_element = WebDriverWait(self.driver, 10).until(
                    ec.presence_of_element_located((By.XPATH, "//a[contains(text(), 'Cited by')]"))
                )
                citation_count = int(citation_element.text.split()[-1])
            except TimeoutException:
                citation_count = 0
        except NoSuchElementException:
            title = -1
            citation_count = -1

        return title, citation_count


def parse_scrape_settings(settings_file="scrape_settings.txt"):
    """
    Extracts conferences, volumes and Google Scholar scrape method (through DOI or title)
    from the scrape_settings.txt file
    """

    scrape_targets = []
    conference = {}
    is_conference = True

    with open(settings_file) as file:
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
                conference = {"conference": split[0], "mode": mode}

            elif line == "":
                conference = {}
                is_conference = True
            else:
                scrape_targets.append({**conference, "name": line})

    return scrape_targets


def get_elements_urls(elements):
    return list(map(get_element_url, elements))


def get_element_url(element):
    return element.attrib["href"]


def get_element_text(element):
    return element.text_content()


def format_volume_name(volume):
    return f'"{volume}"' if "'" in volume else f"'{volume}'"


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


def search_volume_info(scrape_data):
    """
    Finds the links of conference volumes specified in scrape settings
    """
    with tqdm(scrape_data, desc="Searching conference info") as data:
        for volume in data:
            data.set_postfix({"conference": f"{volume['conference']}"})
            conference_page = fromstring(requests.get(ROOT_URL + volume["conference"]).text)

            volume_name = volume["name"]
            formatted_name =  f'"{volume_name}"' if "'" in volume_name else f"'{volume_name}'"

            conference_link = conference_page.xpath(
                f"""//span[contains(text(), {formatted_name})]/ancestor::cite/preceding-sibling::nav[@class='publ']//a""")[0]
            year = conference_link.xpath("./ancestor::ul/preceding-sibling::header[1]/h2")[0].attrib["id"]

            volume["year"] = year
            volume["url"] = conference_link.attrib["href"]
            sleep(5)

    return scrape_data


def main():
    """
    Loads the scrape settings and scrapes each specified conference volume
    """

    parser = argparse.ArgumentParser(description="Scrape conference volumes based on settings file")
    parser.add_argument("--settings", default="scrape_settings.txt",
                        help="Path to the scrape settings file (default: scrape_settings.txt)")
    parser.add_argument("--out", default="out/",
                        help="Path to the output folder (default: out/)")
    args = parser.parse_args()
    SCRAPE_SETTINGS_PATH = args.settings
    OUTPUT_FOLDER = args.out

    to_scrape_volumes = parse_scrape_settings(SCRAPE_SETTINGS_PATH)
    to_scrape_volumes = search_volume_info(to_scrape_volumes)

    driver = create_driver()
    recognizer = sr.Recognizer()

    for volume in to_scrape_volumes:
         Volume(**volume, output_folder=OUTPUT_FOLDER, driver=driver, recognizer=recognizer).scrape()

    driver.quit()

if __name__ == "__main__":
    main()

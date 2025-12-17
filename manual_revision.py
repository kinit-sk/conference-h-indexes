import glob
import pandas as pd

SCRAPING_FOLDER = "out/"
columns = ["DOI", "conference_title", "conference", "citations", "year"]
csv_files = glob.glob(f"{SCRAPING_FOLDER}/*.csv")
for file in csv_files:
    df = pd.read_csv(file, usecols=columns)
    unprocessed = df[df["citations"] == -1]

    if not len(unprocessed):
        continue

    print(f"Found {len(unprocessed)} papers without citations for: {file}")

    for index, paper in unprocessed.iterrows():
        citations = input(f" {paper['conference_title']}\n Fill in the number of citations for the above paper title: ")
        if citations.isdigit():
            df.loc[index, "citations"] = int(citations)

    df.to_csv(file)
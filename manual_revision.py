import glob
import pandas as pd

from datetime import datetime

SCRAPING_FOLDER = "out/"
csv_files = glob.glob(f"{SCRAPING_FOLDER}/*.csv")
for file in csv_files:
    df = pd.read_csv(file)
    unprocessed = df[(df["citations"] == -1) | (df["citations"].isnull())]


    if len(unprocessed) < 1:
        continue

    print(f"Found {len(unprocessed)} papers without citations for: {file}")

    for index, paper in unprocessed.iterrows():
        citations = input(f" {paper['conference_title']}\n Fill in the number of citations for the above paper title: ")
        if citations.isdigit():
            df.loc[index, "citations"] = int(citations)
            df.loc[index, "retrieved_at"] = datetime.now()

    df.to_csv(file, index=False)
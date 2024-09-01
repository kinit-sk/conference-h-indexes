import pandas as pd


def calculate_h_index(citations):
    citation_count = len(citations)
    citations.sort(reverse=True)
    h_index = 0
    is_sufficient = True

    for i in range(1, citation_count + 1):
        for citation in citations[:i]:
            if citation < i:
                is_sufficient = False
                break

        if is_sufficient:
            h_index += 1
        else:
            break
    return h_index


df = pd.read_csv("raw_data.csv")[["DOI", "conference", "volume", "citations", "year"]]
filtered_df = df[df["DOI"] != -1][["conference", "volume", "citations", "year"]]
grouping = filtered_df.groupby(["conference", "volume", "year"], as_index=False )

h_index_df = grouping.agg(lambda citations: calculate_h_index(list(citations.values))).rename(columns={"citations": "h-index"})
h_index_df["number_of_papers"] = grouping.count()["citations"]
h_index_df["citations_per_paper_average"] = grouping.mean()["citations"]
h_index_df["type"] = h_index_df["volume"].apply(lambda volume: "2-Findings" if "finding" in volume.lower() else "1-Main")

h_index_df.to_csv("conferences_h_indices.csv", index=False)
print("H-index calculated and saved into conferences_h_indices.csv")
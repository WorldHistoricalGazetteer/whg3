import csv
import pandas as pd
from elasticsearch8 import Elasticsearch, helpers
from django.conf import settings

es = settings.ES_CONN
index_name = settings.ES_WHG

# Initialize an empty set to store unique close match pairs
close_match_pairs = set()

# Function to fetch the data from Elasticsearch and populate the set
def fetch_close_match_pairs():
    query = {
        "query": {
            "exists": {
                "field": "children"
            }
        }
    }

    # Scroll through all documents in the index with children
    scroll = helpers.scan(
        es,
        query=query,
        index=index_name,
        _source=["place_id", "children"],
        scroll="2m"
    )

    for doc in scroll:
        parent_id = doc["_source"]["place_id"]
        children = doc["_source"]["children"]
        # Add the parent-child pairs
        for child_id in children:
            close_match_pairs.add((parent_id, child_id))
        # Add the child-child pairs
        for i in range(len(children)):
            for j in range(i + 1, len(children)):
                close_match_pairs.add((children[i], children[j]))

# Fetch the data
fetch_close_match_pairs()

# Write the pairs to a CSV file
csv_filename = "close_matches.csv"
with open(csv_filename, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(["place_a_id", "place_b_id"])
    for pair in close_match_pairs:
        writer.writerow(pair)

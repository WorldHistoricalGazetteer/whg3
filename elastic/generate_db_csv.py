import csv
from datetime import datetime
import logging
logger = logging.getLogger(__name__)

# Input and output file names
input_csv_filename = "data/migration/close_matches.csv"
output_csv_filename = "data/migration/close_matches_for_db.csv"

# Today's date
today_date = '2024-05-31'

# Function to add additional fields and write to a new CSV file
def generate_db_csv(input_filename, output_filename):
    with open(input_filename, 'r') as infile, open(output_filename, 'w', newline='') as outfile:
        reader = csv.reader(infile)
        writer = csv.writer(outfile)

        # Write the header row
        writer.writerow(["basis", "created_at", "created_by_id", "place_a_id", "place_b_id", "task_id", "updated_at"])

        # Skip the input header
        next(reader)

        # Write the new rows with the additional fields
        for row in reader:
            place_a_id, place_b_id = row
            writer.writerow(['imported', today_date, 2, place_a_id, place_b_id, None, today_date])

# Generate the new CSV file
generate_db_csv(input_csv_filename, output_csv_filename)

logger.debug(f"New CSV file for database import has been written to {output_csv_filename}")

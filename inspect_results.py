import os
import pandas as pd

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
CSV_PATH = os.path.join(OUTPUT_DIR, "summary_inventory.csv")

if os.path.exists(CSV_PATH):
    df = pd.read_csv(CSV_PATH)
    print(f"Total satellite passes processed: {len(df)}")
    print("\n--- INVENTORY TABLE ---")
    print(df.to_string(index=False))
else:
    print("Summary inventory file not found yet.")

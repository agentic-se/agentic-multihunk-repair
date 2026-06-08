import pandas as pd

df = pd.read_parquet("./data/test-00000-of-00001.parquet")
df.to_json("swe_bench.json", orient="records", lines=True)

# populate_db.py
import sqlite3
import random
import pandas as pd
from datetime import datetime, timezone

# Streamlit アプリと同じ DB_PATH
DB_PATH = "ratings.db"

# pandas で停留所サンプルを作成（あるいは CSV から読み込み）
sample = pd.DataFrame([
    {"stop_id": "18_1", "stop_name": "岡山駅"},
    {"stop_id": "19_1", "stop_name": "岡山駅前"},
    {"stop_id": "20_1", "stop_name": "西川緑道公園前"},
    {"stop_id": "21_1", "stop_name": "柳川西"},
    {"stop_id": "22_1", "stop_name": "ＮＴＴ岡山前"},
    {"stop_id": "23_1", "stop_name": "両備前"},
    {"stop_id": "24_1", "stop_name": "農業会館前"},
    {"stop_id": "25_1", "stop_name": "柳町一丁目"},
    {"stop_id": "26_1", "stop_name": "田町二丁目"},
    {"stop_id": "27_1", "stop_name": "天満屋"},
])

# DB に接続して挿入
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

for _, row in sample.iterrows():
    c.execute(
        "INSERT INTO ratings (stop_id, has_step, has_ramp, assistance, created_at) VALUES (?, ?, ?, ?, ?)",
        (
          row["stop_id"],
          random.randint(0,1),
          random.randint(0,1),
          random.choice(["不要","やや必要","必要"]),
          datetime.now(timezone.utc).isoformat()
        )
    )

conn.commit()
conn.close()
print("サンプルデータを投入しました。")

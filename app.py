import os
import sqlite3
from datetime import datetime

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static

# ——————————————————————————
# 1. データベース初期化＆操作関数
# ——————————————————————————
DB_PATH = "ratings.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stop_id TEXT NOT NULL,
            has_step INTEGER NOT NULL,    -- 0: 段差なし, 1: 段差あり
            has_ramp INTEGER NOT NULL,    -- 0: スロープなし, 1: あり
            assistance TEXT NOT NULL,     -- '不要'/'やや必要'/'必要'
            created_at TEXT NOT NULL      -- ISO8601文字列
        )
    """)
    conn.commit()
    conn.close()

def insert_rating(stop_id, has_step, has_ramp, assistance):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO ratings (stop_id, has_step, has_ramp, assistance, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        stop_id,
        has_step,
        has_ramp,
        assistance,
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()

def load_ratings():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM ratings", conn)
    conn.close()
    return df

if not os.path.exists(DB_PATH):
    init_db()

# ——————————————————————————
# 2. 停留所データ読み込み
# ——————————————————————————
st.set_page_config(page_title="岡山市バリアフリー評価", layout="wide")

st.markdown("""
    <style>
      /* スマホ幅 (600px以下) で余白を狭く */
      @media (max-width: 600px) {
        .block-container {
          padding: 0.5rem !important;
          max-width: 100% !important;
        }
      }
      /* フォントを少し小さくして画面収まりを良く */
      @media (max-width: 600px) {
        body, .css-18e3th9 {
          font-size: 0.9rem !important;
        }
      }
    </style>
""", unsafe_allow_html=True)

st.title("🚌 岡山市内バス停留所バリアフリー評価")

# GTFSの stops.txt を読み込んで岡山市中心部を抽出
stops = pd.read_csv("ryobi_gtfs/stops.txt")
stops_ok = stops[
    (stops["stop_lat"].between(34.64, 34.68)) &
    (stops["stop_lon"].between(133.88, 133.94))
].reset_index(drop=True)

# 停留所名で重複を除く
unique_stops = stops_ok.drop_duplicates(subset=["stop_name"]).reset_index(drop=True)
stop_names = unique_stops["stop_name"].tolist()
stop_id_map = unique_stops.set_index("stop_name")["stop_id"].to_dict()

st.markdown("---")

# ——————————————————————————
# 3. 投稿フォーム
# ——————————————————————————
st.header("📝 バリアフリー評価を投稿する")
with st.form("rating_form", clear_on_submit=True):
    sel_stop = st.selectbox("■ 評価するバス停", stop_names)
    has_step = st.radio("段差はありますか？", ["あり", "なし"], horizontal=True)
    has_ramp = st.radio("スロープはありますか？", ["あり", "なし"], horizontal=True)
    assistance = st.select_slider("介助の必要度（主観）", ["不要", "やや必要", "必要"])
    submitted = st.form_submit_button("送信する")
    if submitted:
        insert_rating(
            stop_id=stop_id_map[sel_stop],
            has_step=1 if has_step == "あり" else 0,
            has_ramp=1 if has_ramp == "あり" else 0,
            assistance=assistance
        )
        st.success(f"「{sel_stop}」の評価を送信しました！")

# ——————————————————————————
# 4. フィルタ＆集計
# ——————————————————————————
st.header("🔍 絞り込み＆集計結果")
df = load_ratings()
if df.empty:
    st.info("まだ評価データが投稿されていません。")
else:
    # 停留所名をマージ
    df = pd.merge(df, unique_stops[["stop_id", "stop_name"]], on="stop_id", how="left")

    # 投稿ごとの段差率・スロープ率・介助度の集計
    agg = (
        df
        .groupby("stop_name")
        .agg(
            step_pct    = ("has_step", "mean"),
            ramp_pct    = ("has_ramp", "mean"),
            assist_mode = ("assistance", lambda x: x.mode()[0] if not x.mode().empty else "不要")
        )
        .reset_index()
    )

    # %を 4段階のカテゴリに変換
    def map_step(p):
        if p >= 0.75: return "高い"
        if p >= 0.50: return "中程度"
        if p >  0.00: return "低い"
        return "ない"

    def map_slope(p):
        if p >= 0.75: return "急"
        if p >= 0.50: return "やや急"
        if p >  0.00: return "なだらか"
        return "平坦"

    agg["step_level"]  = agg["step_pct"].apply(map_step)
    agg["slope_level"] = agg["ramp_pct"].apply(map_slope)
    agg["assistance"]  = agg["assist_mode"]

    # 絞り込みUI
    f_step   = st.multiselect("段差レベル",  ["ない","低い","中程度","高い"], default=["ない","低い","中程度","高い"])
    f_slope  = st.multiselect("スロープレベル",["平坦","なだらか","やや急","急"], default=["平坦","なだらか","やや急","急"])
    f_assist = st.multiselect("介助度",    ["不要","やや必要","必要"], default=["不要","やや必要","必要"])

    df_map = agg[
        agg["step_level"].isin(f_step) &
        agg["slope_level"].isin(f_slope) &
        agg["assistance"].isin(f_assist)
    ].copy()

    # 緯度経度をマージ
    df_map = pd.merge(
        df_map,
        unique_stops[["stop_name","stop_lat","stop_lon"]],
        on="stop_name",
        how="left"
    )

    st.write(f"絞り込み後の停留所数: **{len(df_map)}**")
    st.dataframe(df_map[["stop_name","step_level","slope_level","assistance"]]
                 .rename(columns={
                     "stop_name": "停留所",
                     "step_level": "段差レベル",
                     "slope_level": "スロープレベル",
                     "assistance": "介助度"
                 }))

    # ——————————————————————————
    # 5. 地図表示
    # ——————————————————————————
    st.header("🗺️ 停留所マップ")
    # 地図中心はフィルタ後の平均座標
    center = [df_map["stop_lat"].mean(), df_map["stop_lon"].mean()]
    m = folium.Map(location=center, zoom_start=13, tiles="OpenStreetMap")

    bounds = []
    for _, r in df_map.iterrows():
        lat, lon = r["stop_lat"], r["stop_lon"]
        bounds.append([lat, lon])

        tooltip_html = f"""
          <div style="line-height:1.2;">
            <strong>{r['stop_name']}</strong><br>
            段差レベル：{r['step_level']}<br>
            スロープレベル：{r['slope_level']}<br>
            介助度：{r['assistance']}
          </div>
        """
        folium.Marker(
            location=[lat, lon],
            tooltip=folium.Tooltip(tooltip_html, sticky=True, direction="right"),
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)

    # 全マーカーを含むようにズーム・パンを自動調整
    m.fit_bounds(bounds, padding=(30, 30))

    # Streamlit上に描画
    folium_static(m, width=800, height=500)

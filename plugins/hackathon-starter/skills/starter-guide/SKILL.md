---
description: >-
  Guides Claude when working on the farm_agent Python project: geocoding, Open-Meteo
  weather, Sentinel-2 NDVI via Google Earth Engine, optional JAXA Earth API (GSMaP /
  AMSR2 SMC), HTML dashboard styling (Sentinel blue / JAXA orange cards), CLI flags
  including --location/--crop for negative coordinates, and --llm-agent. Use when
  the user mentions farm_agent, crop dashboard, NDVI report, 圃場, AILecture, or
  agricultural monitoring pipeline.
---

# farm_agent 圃場ダッシュボード Skill

## 1 行で何の Skill か

**栽培・農業の現場が、住所（または緯度経度）と作物名だけで「気象＋衛星＋任意で JAXA」まで束ねた HTML ダッシュボードを得る手順を、リポジトリ上で迷わず進められるようにする。**

## トリガー（いつ読むか）

- `farm_agent`、圃場、NDVI、Sentinel、JAXA、GSMaP、土壌水分、`farm_agent.cli`、HTML レポート、AILecture などが出たとき
- ユーザーが「ダッシュボードを直したい」「CLI が動かない」「マイナス緯度でエラー」などと言ったとき

## リポジトリ上の位置（重要）

**本 Skill が入るプラグインフォルダだけが `plugin install` でコピーされる。** 実行用の Python 本体は同じ GitHub リポジトリの **`farm_agent/`** ディレクトリにある。作業時は **リポジトリルートをワークスペースに開き**、`farm_agent` サブディレクトリでコマンドを実行する。

## 入力と出力（体験の定義）

| 入力 | 出力 |
|------|------|
| 住所・地名、または `lat,lon` と作物名（CLI 引数） | ターミナル要約＋**`farm_agent/reports/latest.html`**（単一 HTML ダッシュボード） |
| `--llm-agent` + `OPENAI_API_KEY` | OpenAI ツールで取得順を自律決定したうえで同じ HTML |
| `--jaxa` または `FARM_AGENT_USE_JAXA=1`（jaxa-earth 導入時） | GSMaP 降水・AMSR2 SMC の補完が HTML の JAXA カードに反映 |

## エージェント向けルール

1. **作業ディレクトリ**: コマンドは `farm_agent/` で実行する（`python -m farm_agent.cli ...`）。
2. **南緯・西経**: 先頭が `-` の座標は `python -m farm_agent.cli --llm-agent --pretty --location="-34.60,-58.38" --crop soybean` のように **`--location` / `--crop`** を使うか、**すべてのフラグの後に ` -- `** を挟んでから位置引数を渡す（`--` の後ろに `--pretty` を書かない）。
3. **環境**: `farm_agent/.env`（`.env.example` をコピー）。`EARTHENGINE_PROJECT` は NDVI に必須。秘密を Skill や README に新規記載しない。
4. **UI の意図**: HTML は Sentinel セクションが**青系カード**、JAXA が**橙系カード**でデータソースが一目で分かる。崩さない。
5. **変更範囲**: 依頼にない大規模リファクタは避け、既存の命名・スタイルに合わせる。

## 主要ファイル（短縮マップ）

- `farm_agent/cli.py` — CLI
- `farm_agent/farm_agent/report_html.py` — ダッシュボード HTML
- `farm_agent/farm_agent/orchestrator.py` — 線形パイプライン
- `farm_agent/farm_agent/agents/autonomous_llm_agent.py` — `--llm-agent`
- `farm_agent/farm_agent/services/jaxa_supplement.py` — JAXA
- `farm_agent/README.md` — セットアップの詳細

## クイックコマンド例

```bash
cd farm_agent
pip install -r requirements.txt
python -m farm_agent.cli "茨城県つくば市" 米 --pretty
python -m farm_agent.cli --jaxa "36.0,140.1" とまと
python -m farm_agent.cli --llm-agent --pretty --location="-34.60,-58.38" --crop soybean
```

詳細はリポジトリ直下の **README.md** と **farm_agent/README.md** を参照する。

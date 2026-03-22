---
name: farm-agent-workflow
description: >-
  Maintains and extends the farm_agent Python package: CLI, HTML dashboard
  (Sentinel NDVI / JAXA supplement), geocoding, Open-Meteo, Google Earth Engine,
  optional jaxa-earth. Use when the user works on AILecture/farm_agent, crop
  dashboards, NDVI reports, JAXA GSMaP/SMC, or farm_agent.cli usage.
---

# farm_agent ワークフロー

## プロジェクトの位置

- ルート: `farm_agent/`（このリポジトリ直下）
- パッケージ: `farm_agent/farm_agent/`
- HTML 既定出力: `farm_agent/reports/latest.html`
- 環境: `farm_agent/.env`（`.env.example` をコピー）

## よく触るファイル

| 領域 | ファイル |
|------|----------|
| CLI | `farm_agent/cli.py` |
| HTML ダッシュボード | `farm_agent/report_html.py`（Sentinel 青カード `sentinel-data-card`、JAXA 橙 `jaxa-data-card`） |
| パイプライン | `farm_agent/orchestrator.py` |
| LLM ツール | `farm_agent/agents/autonomous_llm_agent.py` |
| JAXA | `farm_agent/services/jaxa_supplement.py` |
| 提案文 | `farm_agent/services/recommend.py` |

## CLI（実行は必ず `farm_agent` ディレクトリで）

```bash
cd farm_agent
python -m farm_agent.cli "住所または地名" 作物名
python -m farm_agent.cli --pretty "36.0,140.1" 米
python -m farm_agent.cli --jaxa "36.0,140.1" とまと
python -m farm_agent.cli --llm-agent --pretty --location="-34.60,-58.38" --crop soybean
```

**南緯・西経:** 先頭が `-` になる座標は `--location="lat,lon" --crop 名` か、すべてのフラグの**後**に ` -- ` を挟んで位置引数を渡す（`--` より後ろに `--pretty` 等を書かない）。

## 環境変数（詳細は `.env.example`）

- `EARTHENGINE_PROJECT` … NDVI（GEE）に必須
- `OPENAI_API_KEY` … `--llm-agent` に必須
- `FARM_AGENT_USE_JAXA` / `--jaxa` … JAXA 補完（`jaxa-earth` 要インストール）
- `FARM_AGENT_JAXA_THUMB` … JAXA ラスタ PNG 埋め込み（既定 1、matplotlib 利用）
- `FARM_AGENT_NO_BROWSER=1` … HTML 生成のみ

## エージェント向けルール

- 変更は依頼範囲に限定。ダッシュボードのデータソース別カード配色（青=Sentinel、橙=JAXA）を崩さない。
- 秘密（API キー）を README や Skill に書かない。
- 利用者向け説明は日本語で簡潔に。

## 提出・配布するとき

この Skill は **`farm_agent/.cursor/skills/farm-agent-workflow/`** にある。

- **フォルダごと zip** する、または **リポジトリに `.cursor/skills/` を含めて push** すれば提出可能。
- 受け取り側が Cursor で使う場合: プロジェクトを開くと **プロジェクト Skill** として読み込まれる（配置場所が `.cursor/skills/<名前>/SKILL.md` であること）。

個人の全プロジェクトで使う場合のみ、同じ構造を `~/.cursor/skills/farm-agent-workflow/` にコピーする（`skills-cursor` 内蔵スキルは触らない）。

# farm_agent

Claude Code 用プラグイン・marketplace の手順は、リポジトリ直下の **[../README.md](../README.md)** を参照してください。

圃場の候補地点と作物名から、気象・衛星 NDVI（Sentinel-2 / Google Earth Engine）・任意で JAXA Earth API（降水・土壌水分）などを集約し、**単一 HTML ダッシュボード**とテキスト要約を出力する Python パッケージです。

## できること

- **ジオコーディング**（住所・地名または `緯度,経度`）
- **過去の気象要約**（Open-Meteo）
- **NDVI**（GEE 上の Sentinel-2、代表点まわりのバッファ集計）
- **土壌水分プロキシ**（再解析ベース、NDVI が弱い場合の補助）
- **JAXA 補完**（GSMaP 日次降水・AMSR2 土壌水分、`jaxa-earth` 導入時）
- **ルールベースの管理提案**（参考文案）
- **`--llm-agent`**: OpenAI の function calling で取得順を自律決定（要 `OPENAI_API_KEY`）

## 必要環境

- Python 3.10 以上を想定（3.11 推奨）
- **Google Earth Engine**: NDVI 取得には GEE の認証と Cloud プロジェクト ID（`EARTHENGINE_PROJECT`）が必要です。初回は `earthengine authenticate` 等でログインしてください。
- **OpenAI**（任意）: `--llm-agent` を使うときは API キーが必要です。

## セットアップ

```bash
cd farm_agent
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

`.env.example` を `.env` にコピーし、キーやプロジェクト ID を設定します。

```bash
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
```

### JAXA Earth API（任意）

`FARM_AGENT_USE_JAXA=1` や CLI の `--jaxa` で使います。追加インストール例:

```bash
pip install --extra-index-url https://data.earth.jaxa.jp/api/python/repository/ jaxa-earth
```

HTML にラスタのプレビュー画像を埋め込む場合は **matplotlib** が必要です（`FARM_AGENT_JAXA_THUMB=1` が既定）。

## 使い方

既定では HTML を `reports/latest.html` に書き出し、ブラウザで開きます。

```bash
python -m farm_agent.cli "茨城県つくば市" 米
python -m farm_agent.cli "36.0,140.1" とまと --pretty
```

| オプション | 説明 |
|-----------|------|
| `-o FILE` / `--html FILE` | HTML の保存先 |
| `--no-html` | HTML を書かない |
| `--no-browser` | ブラウザを開かない |
| `--pretty` | ターミナル出力を Rich で整形 |
| `--jaxa` | Sentinel の強弱に関係なく JAXA を取得 |
| `--llm-agent` | OpenAI ツール自律モード（線形パイプラインと `--jaxa` は併用しません） |
| `--location` / `--crop` | 場所・作物を名前付きで指定（南緯・西経でも `=` 形式なら安全） |

**南緯・西経（先頭が `-`）のとき:** `argparse` がオプションと誤認しないよう、(1) **すべてのフラグを先に書き** ` -- ` の後に座標と作物、または (2) **`--location="-34.6,-58.38" --crop soybean`** のように `=` で渡す。詳細は `python -m farm_agent.cli -h` の末尾の例を参照。

ブラウザ起動を抑止する環境変数: `FARM_AGENT_NO_BROWSER=1`

## 環境変数

主要な項目は **`.env.example`** にコメント付きで載せています。例:

- `OPENAI_API_KEY` … `--llm-agent` 用
- `EARTHENGINE_PROJECT` … Earth Engine プロジェクト ID
- `FARM_AGENT_USE_JAXA` … パイプライン内での JAXA 補完
- `FARM_AGENT_JAXA_THUMB` … JAXA ラスタの PNG 埋め込み（`1` / `0`）
- `FARM_AGENT_LLM_DEMO_*` … LLM モードの動作確認用オプション（本番では通常オフ）

## レイアウト

- `farm_agent/` … パッケージ本体（CLI、オーケストレーション、HTML レポート、各サービス）
- `reports/` … 既定の HTML 出力先（`.gitignore` 対象推奨）
- `requirements.txt` … コア依存関係
- `.cursor/skills/farm-agent-workflow/` … Cursor 用 Agent Skill（`SKILL.md`）。講義・提出時はこのフォルダごと、またはリポジトリ丸ごと共有

## 注意

出力される提案や指標は**参考用**です。栽培判断は現地確認と専門家の意見を優先してください。各データソースの利用条件・クレジットは公式ドキュメントに従ってください。

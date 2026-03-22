# AILecture — farm_agent & Claude Code Plugin

## このリポジトリがすること（1 行）

**圃場の「場所＋作物」を入れると、気象・Sentinel-2 NDVI・（任意で）JAXA の降水・土壌水分までまとめた単一 HTML ダッシュボードを生成する Python ツールと、それを開発・実行するときに Claude Code が頼れる Skill プラグインを提供する。**

## 構成

| パス | 内容 |
|------|------|
| `farm_agent/` | **本体**（CLI、HTML レポート、GEE / Open-Meteo / JAXA など） |
| `.claude-plugin/marketplace.json` | Claude Code 用 **marketplace** 定義 |
| `plugins/hackathon-starter/` | **プラグイン 1 つ分**（`skills/starter-guide/SKILL.md` が核） |

> フォーク元が `plugins/hackathon-starter` のままでも提出可。中身は上記 Skill に差し替え済みです。

## Claude Code でのインストール（審査・第三者向け）

リポジトリを **公開**したあと、GitHub の `ユーザー名/リポジトリ名` に合わせて実行します。

```text
/plugin marketplace add <your-github-user>/<your-repo>
/plugin install farm-dashboard-plugin@ailecture-farm-marketplace
```

**提出前に直す場所**

- `.claude-plugin/marketplace.json` の `name`（例: `ailecture-farm-marketplace` を自分の識別しやすい名前に）
- 同ファイルと `plugins/hackathon-starter/.claude-plugin/plugin.json` の `owner` / `author`（`YOUR_GITHUB_USERNAME` 等）

marketplace 名は **`@` の右側**に使われます。プラグイン名は `farm-dashboard-plugin`（`marketplace.json` の `plugins[].name` と `plugin.json` の `name` と揃えてあります）。

## ローカルで marketplace を試す

```text
/plugin marketplace add /path/to/このリポジトリのルート
/plugin install farm-dashboard-plugin@ailecture-farm-marketplace
```

## farm_agent のセットアップと実行

詳細は **[farm_agent/README.md](farm_agent/README.md)** を参照。

**最短:**

```bash
cd farm_agent
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # 編集して EARTHENGINE_PROJECT などを設定
python -m farm_agent.cli "住所または地名" 作物名 --pretty
```

生成物: **`farm_agent/reports/latest.html`**（既定でブラウザが開く）

**入力 → 出力の対応**

- **入力**: 第 1 引数＝住所・地名または `緯度,経度`、第 2 引数＝作物名。オプションで `--jaxa` / `--llm-agent` / `--pretty` など。
- **出力**: 標準出力（または Rich）の要約 ＋ **HTML ダッシュボード**（気象、NDVI、地図、管理提案、条件により JAXA カード）。

**南緯・西経の例**

```bash
python -m farm_agent.cli --llm-agent --pretty --location="-34.60,-58.38" --crop soybean
```

## デモ動画・スクリーンショット

- **デモ動画（3 分以内）**: （提出時にここに YouTube または Loom 等の URL を貼る）
- **スクリーンショット**: `reports/latest.html` をブラウザで開いた画面（Sentinel 青カード / JAXA 橙カードが分かるとよい）

## ライセンス・免責

- 各データソース（OpenStreetMap、Open-Meteo、Google Earth Engine、JAXA 等）の利用条件に従ってください。
- 出力は参考情報です。栽培判断は現地確認と専門家の判断を優先してください。

## Plugin の制約（Claude Code）

プラグインインストール時にコピーされるのは **`plugins/hackathon-starter/` 以下**です。Python 本体は **`farm_agent/`** にあるため、**リポジトリ全体をクローン**してから CLI を実行してください。Skill はその前提でエージェントを導きます。

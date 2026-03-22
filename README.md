# agi-lab_farm_agent — 圃場ダッシュボード（farm_agent）提出用

フォーク元: [KaishuShito/agi-lab-skills-marketplace](https://github.com/KaishuShito/agi-lab-skills-marketplace)

## このリポジトリがすること（1 行）

**圃場の「場所＋作物」を入れると、気象・Sentinel-2 NDVI・（任意で）JAXA の降水・土壌水分までまとめた単一 HTML ダッシュボードを生成する Python ツールと、それを開発・実行するときに Claude Code が頼れる Skill プラグインを提供する。**

## 構成

| パス | 内容 |
|------|------|
| `farm_agent/` | **本体**（CLI、HTML レポート、GEE / Open-Meteo / JAXA など） |
| `.claude-plugin/marketplace.json` | Claude Code 用 **marketplace**（提出 plugin のみ） |
| `plugins/hackathon-starter/` | **farm-dashboard-plugin**（`skills/starter-guide/SKILL.md`） |

## Claude Code でのインストール

```text
/plugin marketplace add ayako0520/agi-lab_farm_agent
/plugin install farm-dashboard-plugin@agi-lab-farm-agent
```

**marketplace 名**は `.claude-plugin/marketplace.json` の `name`（`agi-lab-farm-agent`）です。変更した場合は `@` の右側も合わせてください。

**メール**: `marketplace.json` と `plugin.json` の `your-email@example.com` を公開してよいアドレスに置き換えてください。

## ローカルで marketplace を試す

```text
/plugin marketplace add /path/to/agi-lab_farm_agent
/plugin install farm-dashboard-plugin@agi-lab-farm-agent
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

**入力 → 出力**

- **入力**: 住所・地名または `緯度,経度`、作物名。オプションで `--jaxa` / `--llm-agent` / `--pretty` など。
- **出力**: ターミナル要約 ＋ **`farm_agent/reports/latest.html`**（気象、NDVI、地図、管理提案、条件により JAXA カード）。

**南緯・西経の例**

```bash
python -m farm_agent.cli --llm-agent --pretty --location="-34.60,-58.38" --crop soybean
```

## デモ動画・スクリーンショット

- **デモ動画（3 分以内）**: （提出時に URL を貼る）
- **スクリーンショット**: ブラウザで `latest.html` を表示（Sentinel 青カード / JAXA 橙カードが分かるとよい）

## Plugin の制約（Claude Code）

`plugin install` でコピーされるのは **各 plugin ディレクトリのみ**です。Python 本体は **`farm_agent/`** にあるため、**リポジトリ全体をクローン**してから CLI を実行してください。

## ライセンス

MIT（フォーク元に準拠）

## 免責

各データソースの利用条件に従ってください。出力は参考情報であり、栽培判断は現地確認と専門家の判断を優先してください。

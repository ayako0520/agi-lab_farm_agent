# シンプル時計（TypeScript）マニュアル

## できること
- ブラウザ上に現在時刻（`HH:MM:SS`）を表示
- 1秒ごとに自動更新

## 必要なもの
- Node.js / npm（インストール済みであること）

## ファイル構成（`AILecture/clock/`）
- `index.html`: 画面（`dist/clock.js` を読み込み）
- `clock.ts`: 時計ロジック（TypeScript）
- `tsconfig.json`: TypeScript のビルド設定
- `dist/clock.js`: ビルド生成物（自動生成）

## 1) 依存関係のインストール（初回だけ）
ターミナルで **`AILecture/clock` に移動してから** 次を実行します。

```bash
npm install
```

## 2) ビルド（TS → JS）

```bash
npm run build
```

成功すると `dist/clock.js` が生成されます。

## 3) 表示用サーバー起動
ES Modules の都合で、`index.html` を `file://` で直開きするより **ローカルサーバー経由**が確実です。

```bash
npm run start
```

## 4) ブラウザで開く
同じPCのブラウザなら、基本はこれが確実です。

- `http://127.0.0.1:5173/index.html`

（ネットワーク環境によっては、`http://10.x.x.x:5173` のようなアドレスは見えない場合があります）

## 5) サーバーを止める
`npm run start` を実行しているターミナルで次を押します。

- `Ctrl + C`

もし止まらない／ターミナルが閉じてしまった等で止められない場合は、次で **5173番ポートを使っているプロセス**を停止できます（PowerShell）。

```powershell
$pid = (Get-NetTCPConnection -LocalPort 5173 -State Listen | Select-Object -First 1 -ExpandProperty OwningProcess)
Stop-Process -Id $pid -Force
```

## よくあるトラブル
### `http://127.0.0.1:5173/index.html` が 404 になる
- `AILecture/clock` に `index.html` があるか確認してください。
- サーバーの起動ディレクトリが **`AILecture/clock`** になっているか確認してください（別フォルダで `npm run start` すると別の場所を配信します）。

### 画面は出るが時計が動かない
- 先に `npm run build` を実行して `dist/clock.js` が生成されているか確認してください。
- ブラウザの開発者ツール（Console）にエラーが出ていないか確認してください。


# 匿名Q&A（questionform）

FastAPI + SQLite で動作する簡易 Q&A（匿名投稿・投票・モデレーション）。

## セットアップ（ローカル）

1) Python を用意（3.9+ 推奨）。

2) 依存関係をインストール。

```
pip install -r questionform/requirements.txt
```

3) 管理トークンを設定（非必須ですが管理機能に必要）。

Windows (PowerShell):

```
$env:ADMIN_TOKEN = "任意の長いランダム文字列"
```

macOS/Linux (bash):

```
export ADMIN_TOKEN="任意の長いランダム文字列"
```

4) 実行。

```
uvicorn questionform.app:app --reload --host 0.0.0.0 --port 8000
```

ブラウザで `http://localhost:8000/` を開く。投影用は `http://localhost:8000/projector`。

API ドキュメント（自動生成）は `http://localhost:8000/docs`。

## 機能

- 投稿: `POST /api/questions` （本文 `text` 最大500字）
- 一覧: `GET /api/questions?order=new|top&include_hidden=false|true`
- 投票: `POST /api/questions/{id}/vote`
- 非表示: `POST /api/questions/{id}/hide`（管理）
- 再表示: `POST /api/questions/{id}/unhide`（管理）
- 削除: `DELETE /api/questions/{id}`（管理）

管理 API はヘッダに `X-Admin-Token: <ADMIN_TOKEN>` が必要です。

## データストア

- SQLite の単一ファイル `questionform/data.db` を自動作成。
- レコード: `id, text, votes, hidden, created_at(UTC ISO8601)`

## デプロイ（例: Render）

1) 本ディレクトリを GitHub リポジトリにプッシュ。

2) Render で “New Web Service” → リポジトリを選択。

- Build Command: `pip install -r questionform/requirements.txt`
- Start Command: `uvicorn questionform.app:app --host 0.0.0.0 --port $PORT`
- Environment → `ADMIN_TOKEN` を設定。

3) デプロイ URL を参加者に共有。

## 運用メモ

- 乱用対策: 必要に応じて投稿間隔の制限、NGワードフィルタを追加してください。
- 匿名性: IP などはホスティング側ログに残る可能性があります。告知文面で明示を推奨。
- バックアップ: `data.db` は単一ファイルなので定期コピーでバックアップできます。


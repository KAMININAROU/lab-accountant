<<<<<<< HEAD
# lab-accountant
This is a project for managing financial things for my laboratory.
=======
# 研究室業務委託報酬管理

PyQt5 で動く研究室向けの業務委託報酬・使用費目管理アプリです。

## 主要機能

- 人員管理
- 款項入力
- 個人明細
- 月次精算プレビュー・保存・確定
- 年度集計
- 税額計算
- Excel 出力
- 操作ログ表示
- 5分ごとの自動バックアップ
- JSTログ時刻表示
- 選択人員のExcel出力
- 月次精算行のパスワード付き削除
- 人員・案件・個人明細行のパスワード付き削除

## 試运行

```bash
cd /path/to/LabAccounting
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Debug

```bash
python -m py_compile main.py lab_accounting/**/*.py tools/*.py
python main.py
```

データベースは `lab_accounting.db` に保存されます。やり直す場合は、アプリを閉じてからこのファイルを退避または削除してください。

## バックアップ

通常の入力データは `lab_accounting.db` に即時保存され、アプリ起動時に自動で読み込まれます。

自動バックアップは5分ごとに `backups/` に作成されます。最新バックアップは `backups/lab_accounting_latest.db` です。

手動操作はアプリの `設定` ページで行います。

- `今すぐバックアップ`: その時点のデータベースを `backups/` に保存します。
- `バックアップを読み込む`: `.db` バックアップファイルを選択して復元します。復元前の現在データも `before_restore` として退避されます。

## 特殊ルール

- 月次精算の `支給日数` は `0.5` から `7` まで、`0.5` 刻みです。
- 月次精算の行削除は、表で行を選択して `選択行を削除` を押します。
- 人員管理の行削除は、表で行を選択して `選択行を削除` を押します。
- 案件入力の行削除は、表で行を選択して右クリックし、`選択行を削除` を選びます。複数行選択も可能です。
- 個人明細の行削除は、表で行を選択して `選択行を削除` を押します。
- パスワードはアプリ内部ではSHA-256ハッシュで照合します。
- 削除操作はログに保存されます。
- Excel出力では対象人員を複数選択できます。未選択の場合は全員出力します。
>>>>>>> master

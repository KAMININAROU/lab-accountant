<<<<<<< HEAD
# lab-accountant
This is a project for managing financial things for my laboratory.

# MacOS is Recommended
## It can be deployed on Windows but need some adjustments on virtual environments or python things, which are very complex.
## If you just want to download the app but not the codes, just go to the Release part and download the lab-acc.rar file.
=======================================================

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

## 試行(For MacOS)
### !!!! パスに漢字が入らないようにしてください。できれば簡単で！！！

cd /path/to/LabAccounting

python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

python main.py

## Debug(For MacOS)

python -m py_compile main.py lab_accounting/**/*.py tools/*.py

python .\main.py


## 試行(For Windows)
### VS code is highly recommended.
### !!!! パスに漢字が入らないようにしてください。できれば簡単で！！！
------------------------------------------
ダウンロード先のフォルダーを事前に作ってください。

vscodeのTerminalで以下のコマンドを実行：

python --version

もしエラーやpython not foundなどが出てきたら、pythonをインストールしてください。(インストール後、vscodeを再起動してください。)
------------------------------------------
cd (事前に作ったフォルダーのパス)

python -m venv .myvenv

.\.myvenv\Scripts\Activate.ps1

（うまく行ったら、(myvenv)という表記が現れる）

python -m pip install --upgrade pip

python -m pip install PyQt5 openpyxl

python .\main.py


### Trouble Shooting
### 1.
- ModuleNotFoundError: No module named 'PyQt5'
- ModuleNotFoundError: No module named 'openpyxl'
というエラーが出た場合、以下の命令を実行：

deactivate

Remove-Item -Recurse -Force .myvenv

python -m venv .myvenv

.\.myvenv\Scripts\Activate.ps1

python -m pip install --upgrade pip

python -m pip install PyQt5 openpyxl

python .\main.py

### 2.
- > python main.py qt.qpa.plugin: Could not find the Qt platform plugin "windows" in "" This application failed to start because no Qt platform plugin could be initialized. Reinstalling the application may fix this problem.

まず、myvenv という環境を作り直す。
deactivate

Remove-Item -Recurse -Force .myvenv

python -m venv .myvenv

.\.myvenv\Scripts\Activate.ps1

必要なＤＬＬファイルがあるかどうかをチェック：

Get-ChildItem -Recurse .\.venv\Lib\site-packages -Filter qwindows.dll
（これが出たら正解：Directory: D:\lab-acc\lab-accountant\.myvenv\Lib\site-packages\PyQt5\Qt5\plugins\platforms）

パスが出ても行かない場合：

$env:QT_QPA_PLATFORM_PLUGIN_PATH = (Resolve-Path ".\.myvenv\Lib\site-packages\PyQt5\Qt5\plugins\platforms").Path

python .\main.py


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
- 削除操作はログに保存されます。
- Excel出力では対象人員を複数選択できます。未選択の場合は全員出力します。
====================================================================
>>>>>>> master

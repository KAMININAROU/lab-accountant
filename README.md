# lab-accountant

研究室向けの業務委託報酬・使用費目管理アプリです。Python、PyQt5、SQLite、openpyxl で動作します。

## 主な機能

- 人員管理（カナ・備考・色・居住区分・日額）
- 案件入力と人／種類による検索
- 個人明細
- 月次精算の計算プレビュー、下書き保存、確定、削除
- 年度集計と月別集計
- 税額計算
- 人員情報・案件・月次精算明細・集計の Excel 出力
- 操作ログ
- SQLite バックアップと復元
- 起動中の Splash Screen

年度集計は、人員・案件・月次精算から計算する読み取り専用の結果です。年度集計画面から元データを削除することはできません。

## 試行（macOS）

パスに漢字を含まないフォルダーでの実行を推奨します。

```bash
cd /path/to/LabAccounting
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

## 試行（Windows）

```powershell
cd C:\path\to\LabAccounting
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python .\main.py
```

## Debug とテスト

構文確認:

```bash
python -m compileall -q main.py lab_accounting tools
```

自動テスト:

```bash
python -m unittest discover -s tests -v
```

画面を表示しない環境では、次のように実行できます。

```bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

## データベース移行

起動時に `lab_accounting.db` の構造を自動確認します。旧版データベースの場合は、人員、案件、月次精算、ログ、設定と既存 ID を保持したまま、次の移行を一度だけ実行します。

- 人員の独立した `memo` 列を追加
- 月次精算の「人員＋年度＋対象月」唯一制約を削除
- 検索用の通常索引を作成
- 外部キーと SQLite の整合性を確認

同じ移行は繰り返し実行してもデータを重複させません。旧版バックアップを復元した場合も、復元直後に同じ移行を実行します。

## 月次精算

- 同じ人の別月データはそれぞれ独立して保存されます。
- 同じ人・同じ月にも、補充分を別の精算として追加保存できます。
- 削除は `payment_id` 単位で行い、同月の別データには影響しません。
- 年度、対象月、人員、日数、計算モード、割合を変更すると古いプレビューは無効になります。
- 日数モードの手取額は、日額総額、支給日数、実効税率から自動計算されます。
- 支給日数は `0.5` から `7` まで、`0.5` 刻みです。

## バックアップ

通常データは `lab_accounting.db` に即時保存され、次回起動時に自動で読み込まれます。

初期設定では自動バックアップを 5 分ごとに作成し、`lab_accounting_auto_*.db` の最新 5 個だけを保持します。次のファイルは自動整理の対象外です。

- `lab_accounting_manual_*.db`
- `lab_accounting_before_restore_*.db`
- `lab_accounting_latest.db`
- ユーザーが追加したその他の `.db` ファイル

手動バックアップと復元はアプリの `設定` ページで行います。復元前には現在のデータベースを `before_restore` として保存し、復元後に移行と整合性チェックを実行します。

## 設定

`config/app_config.json` で次の項目を変更できます。

- アプリ名、バージョン、起動時の説明文
- 会計年度と年度開始月
- 居住者／非居住者税率
- 既定の日額総額
- Excel 出力先
- バックアップ先、間隔、保持数

旧設定ファイルに新しい項目がない場合は既定値を使用します。

## 削除とログ

人員、案件、個人明細、月次精算の削除には削除パスワードが必要です。人員を削除すると、その人に関連する案件と月次精算も削除されます。削除や人員情報の変更は操作ログに記録されます。

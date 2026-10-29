# HFT 策略圖鑑

已完成31個程式、325個策略的原始碼解說，涵蓋5,778筆有效參數；各程式盤點結果見 `PROGRESS.md`。網站以「已整理／待整理」區分維護進度，完成時只顯示總數，尚未完成時顯示已完成／總數。

直接以瀏覽器開啟 `index.html`，不必安裝前端套件或啟動伺服器。本機開啟仍可離線閱讀及收藏。

提供交易原理、進出場順序、部位管理、實作注意事項、自訂算例，以及依 C# `Category` 分組的完整參數。繼承參數直接合併；沒有基底類別頁、預設值、批次測試範圍及原始碼位置。未列入清單與已註解的策略統一標記「未在清單中」。

可搜尋、依程式／類型／清單狀態篩選，瀏覽參數索引、比較策略與匯出 CSV。

列表、卡片與策略內容皆可點「☆ 收藏／★ 已收藏」，側欄「我的收藏」集中瀏覽，也支援 `#favorites` 連結。在收藏清單取消時，本次瀏覽仍留著該列，可立即再按星號復原，離開後才會移出清單。

收藏儲存參考 [TestReview 的雲端標記實作](https://github.com/sibuzu/TestReview/blob/main/site/dist/mark-sync.js)：只有 `https://super.sibuzu.com` 使用 Netlify Blobs，其他網域、預覽入口與 `file://` 僅存目前瀏覽器，不發雲端請求。正式網域使用單一共用收藏清單；每個策略分開保存開／關標記，保留取消紀錄，避免舊裝置把已取消項目補回。首次同步會補入雲端尚無紀錄的本機收藏。

正式網域的變更先快取於本機及待送佇列，離線時顯示「收藏待同步」，恢復網路、頁面重新取得焦點、每分鐘或點同步狀態時重試。只有伺服器確認儲存後才顯示「收藏已同步」。這裡不新增登入系統，與參考專案一樣共用同一份雲端收藏。

## 部署雲端收藏

本目錄可作為獨立的網站文件 Git repo 根目錄；`netlify.toml`、`netlify/`、`package.json`、`package-lock.json` 與 `.gitignore` 都放在此層，不需要上層的 Node 或 Netlify 設定。以下命令均在本目錄執行，使用 Node 22.12 以上。

```powershell
npm ci
npm test
npm run build
```

在 Netlify 直接以此 repo 根目錄部署；建置命令為 `npm run build`，發布目錄為 `dist`，Functions 目錄為 `netlify/functions`。若暫時仍連接上層 hft repo，將 Netlify 的 Base directory 設為 `site`。建置只複製6個瀏覽器資產，不需要 C# 原始碼，也不發布內部盤點與撰寫程式。

將同一 Netlify 站點的正式網域設為 `super.sibuzu.com`，Functions 會使用該站點的 `hft-shared-favorites` Blobs store，不需把憑證寫入前端。只上傳靜態檔案不會啟用 Functions；尚未部署或雲端錯誤時會保留待同步狀態。

`npm test` 驗證網域隔離、API、跨裝置合併、取消紀錄及離線重試。實際網站部署狀態與端對端雲端寫入須在部署後另行確認。

介面參考 [TestReview](https://github.com/sibuzu/TestReview) 的灰綠配色、側欄、緊湊列表與同頁閱讀方式。「程式」對應其科目分類、「策略」對應其題目，保留交易研究用語。預設列表，可切換卡片；點選策略直接在原頁主區域閱讀，側欄列出同程式策略。點「回上頁」或使用瀏覽器返回，可保留搜尋、篩選、檢視方式及捲動位置。支援 `#strategy/<策略ID>` 連結，也相容舊的 `#strategy=<策略ID>`。

參數各 Category 與交易原理各大項可點標題展開／收合。「基本」參數預設收合，其餘預設展開；目前開啟期間會記住各策略的收合狀態，切換分頁不重設。搜尋參數或選擇 Category 時會暫時展開符合的分類，清除篩選後恢復原狀態。

## 更新資料

網站建置與閱讀使用已產生的 `data/`，不依賴上層專案。只有重新盤點策略時，才需要原始 hft checkout；目前盤點工具以本目錄的上層為 hft 根目錄，讀取其 `src/`。維持 `hft/site/` 配置時，在本目錄執行：

```powershell
python build_catalog.py
python verify_catalog.py
```

使用 Python 3.10 以上與標準函式庫。產生器自動盤點各程式 `.csproj` 的 `Compile` 項目，避免未編譯的同名類別混入。`EXCLUDED_PROGRAMS` 精確排除使用者指定的 SuperFinlab、SuperJack、SuperTrade、DavidTrade/UltraDavid、DeepIB、SuperIB、SuperJackLite、SuperDailyX、SuperOptionPlot、SuperOptionQuote；SuperInvETF與DavidTrade本身仍保留。

另以精確程式／類別ID排除4項經讀碼確認沒有獨立交易核心的支援類別，原因記錄於內部盤點清單；這些類別仍保留在繼承解析中。`verify_catalog.py` 獨立核對專案範圍、清單狀態、資料同步及參數說明覆蓋；全部整理完成時另執行 `python verify_catalog.py --require-complete`，並仍須核對交易解說與原始實作。

- `analysis/*.json`：逐程式人工閱讀交易實作後整理的原理與參數解說；`futures.json` 保留最先完成的兩個策略。程式行為變更後須重新核對，產生器不會自動重寫解說。
- `programs.json`：已核對的程式交易概況。
- `PROGRESS.md`：每次重建同步更新各程式的策略數、已完成及待整理數。
- `work/inventory.json`：內部盤點清單，供逐程式核對來源；原始碼位置不顯示於網頁。
- `data/catalog.json`：可供其他工具使用的結構化資料。
- `data/catalog.js`：網頁的離線資料，與 JSON 由同一次執行產生。
- `app.js`、`styles.css`、`index.html`：無建置步驟的網站。

參數資料由公開可寫入屬性合併，排除唯讀屬性、批次控制與明確績效結果。動態隱藏的設定也收錄；對實際不生效的項目，在參數解說註明。列舉選項來自同程式的 enum 定義。

內容解說以實作為準；原有 `Description` 可能過時，網頁優先顯示核對後的參數解說。自訂算例僅用來展示程式規則。

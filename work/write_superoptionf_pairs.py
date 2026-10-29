from pathlib import Path
import json
S=Path(__file__).resolve().parents[1];cat=json.loads((S/'data/catalog.json').read_text('utf-8-sig'));p=S/'analysis/SuperOptionF.json';out=json.loads(p.read_text('utf-8-sig')) if p.exists() else {}
base={'滑價Tick':'每腿每側固定滑價=此值×商品最小升降單位；逐腿損益扣兩側，不另算本地手續費或保證金成本。','價平計算方式':'先依call／put和P正負決定有號合約間距，再Round／Ceiling／Floor參考價。步長負時Ceiling／Floor的價格方向會反轉；另有商品歷史間距分支。','開始日期':'此字串供設定／匯出；實際執行用外部起日的年月篩合約月份，非按本欄逐筆裁切。','結束日期':'此字串供設定／匯出；核心用外部迄日年月為排除上界，合約月份>=迄月不做，不是含整個迄月。','權利金最低':'各腿帶正負進場權利金合計下界，買方負／賣方正；純數點數、尾X乘商品履約間距×合約乘數。只有最低<最高才篩，含等號。','權利金最高':'同有號權利金合計上界，不按腿張數加權也未扣滑價；最低>=最高完全不篩，兩個0因此不篩。','部位管理':'固定一口每腿1；固定金額>0，每腿獨立用金額萬×10000÷(該腿權利金×選擇權契約價值)再轉int，不保證各腿相同張數。','固定金額':'單位萬，逐腿按權利金配量而非組合淨權利金或保證金配量；正值太小可轉0張，固定金額<=0時回每腿1。','進場時間':'新倉第n天從前一合約最後資料日的本合約索引+N；結算前n天用本合約資料尾索引−N，都是資料交易日非曆日。','進場時間N':'相對上述索引的整數偏移，非HHmm；越界就略過該合約，不補附近日期。'}
cost='每腿損益=(有號入場+有號退出−兩側固定滑價)×張數，報表沒有再乘選擇權契約價值；該契約價值只用在資金換量，不能直接當成已換成貨幣損益。'
report='報表依加入順序逐腿累加已完成損益與DD，不做日內估值、也不先合併同組同到期腿再計DD。交易次數是腿紀錄數，買進成本是各腿權利金絕對值×張數之和，非保證金。'
settle='退出以商品結算表價格（找不到回退合約最後期貨open）和履約價計到期內含價值，call=max(結算−履約,0)、put=max(履約−結算,0)；不是最後選擇權報價撮合。'
def add(name,summary,family,entry,exit,me,ca,notes={}):
 iid='SuperOptionF/Stg'+name;ns=base|notes;out[iid]={'summary':summary,'family':family,'entry':entry,'exit':exit,'mechanics':me,'caveats':ca,'parameterNotes':{q['name']:ns[q['name']] for q in next(i for i in cat['items'] if i['id']==iid)['parameters']}}
for name in ['APT','APT3']:
 three=name=='APT3';nn={}
 for leg in (['P','Q','R'] if three else ['P','Q']):
  nn['權證動作'+leg]='第'+leg+'腿買／賣call或put，決定履約價外方向與權利金正負。'+('無則略過此腿，其餘啟用腿缺資料會取消整組。' if three else '任一腿合約或精確進場日資料缺少，整組取消。')
  nn['價外'+leg+'檔']='第'+leg+'腿相對期貨／ETF當日open的檔數，0價平、正價外、負價內，按有號履約格點與價平取整方式選合約。'
 ent=['每個合約期排定一個資料日，用期貨／ETF當日open當價平參考，按各腿動作與價外檔數選call／put，精確同日選擇權open成交。','新倉模式略過列表第一期，從前一期末資料日偏移N；結算前模式可從第一期尾倒數。只處理外部起月<=合約月份<外部迄月。','所有'+('啟用' if three else '兩')+'腿資料齊後，逐腿有號進場權利金相加，在最低<最高時篩含端點淨額區間，通過才整組加入。']
 ex=['沒有逐日停損、停利或動態換腿，每個原始腿一律按到期內含價值退出。',settle]
 me=[cost,report,'買腿進場價負、到期收回正，賣腿進場正、到期支付負。固定金額分別按每腿權利金算整張，可能變成不同張數的組合。']
 ca=['組合淨權利金濾網未按張數加權，固定額各腿張數又可不同，不能把通過的點數區間視為整組現金流限制。','缺合約、缺精確日期或結算參考為0會略過，沒有尋找下一日補進；到期用估值公式而非真實市價平倉。']
 if three:
  me.append('三腿加入前依P/Q、Q/R、P/R順序，把同類型反向腿的第二腿淨點數挪到第一腿出場欄；兩筆紀錄仍保留，各自還扣兩側滑價。')
  ca.append('這個MergeSpreadTrade不是提前平倉，也不要求履約相同／張數相同；若兩腿張數不同，挪點數後按各張數乘算可改變原本組合總損益。')
 add(name,('最多三個可選' if three else '兩個')+'選擇權買賣腿，在合約指定資料日建立並持有到期，按有號淨權利金篩選。','選擇權組合與到期損益',ent,ex,me,ca,nn)
p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('Wrote OptionF APT pair')

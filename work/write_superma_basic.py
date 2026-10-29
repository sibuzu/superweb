from pathlib import Path
import json
S=Path(__file__).resolve().parents[1];c=json.loads((S/'data/catalog.json').read_text('utf-8-sig'));p=S/'analysis/SuperMA.json';out=json.loads(p.read_text('utf-8-sig')) if p.exists() else {}
base={'滑價xTick':'純數乘商品最小升降單位，%按各自成交價換點數；FIFO配對進出兩側都扣，再乘口數及契約價值。','報價模式':'只開盤把OHLC全改open；只收盤把全改close；全部保留OHLC，由各策略核心決定觸價與成交。','開始交易時間':'本版核心未以此HHmm限制交易；真正載入／訊號時刻依策略資料與核心。','最後交易時間':'本版未讀此截止，不因到時自動平。','開始日期':'此字串主要供匯出設定；實際行情起日由外部傳入DoReadData後裁切，非核心另用此欄。','結束日期':'此字串供設定／匯出，實際讀取迄日由外部載入參數控制；各核心未保證末筆平。','部位管理':'固定一口1；固定金額除(行情open×契約價值)向下取整但至少1口，資金不足也會下一口。','固定金額':'固定名目換整口，不隨策略累計獲利複利；<=0仍被最小1口墊高。'}
cost='累計績效同一策略實例FIFO配對，扣兩側各自成交價滑價再乘數量×契約價值，DD只已實現。共用換約函式每次只平開1口，固定額若多口，實際換約紀錄量與策略總部位會不同。'
report='共用單筆執行欄位沒有同時乘總口數與契約價值；空單退出的單筆滑價還把退出價格本身直接加進去，與正確FIFO累計可顯著不同。應區分單筆欄位與總績效。'
def add(name,summary,family,entry,exit,me,ca,notes={}):
 iid='SuperMA/Stg'+name;ns=base|notes;out[iid]={'summary':summary,'family':family,'entry':entry,'exit':exit,'mechanics':me,'caveats':ca,'parameterNotes':{q['name']:ns[q['name']] for q in next(i for i in c['items'] if i['id']==iid)['parameters']}}
for name in ['SMS','SMSv2']:
 v2=name=='SMSv2';ent=['只做多，動量=目前open−N筆前open−兩者之間累積delta，不是百分比。日單位從完整日open序列先算，交易日05:30換日後第一筆分鐘才查；其他單位每根檢查。','空手且動量>=進場點就在本根open建倉；無足夠N筆以MinValue跳過，缺日期查不到日值則回0。']
 ex=['持多且動量嚴格<出場點時open平，其他根續持；沒有固定N天到期，也無資料末端強平。']
 if v2:ex=['只在同一動量訊號更新節點，先open<=已有移停線退，再open>=直停線退，才查動量<出場點。停利／移停後進WAITH，須動量先<出場點回空手，之後另根才可再買。','持倉open>=原啟移門檻後，用目前open減拉回距離建只上移的線；一般動量退出直接回NONE。沒有固定損、末筆強平。']
 ex.append('精確／對齊換約時持倉按原分鐘open平舊、open+delta接回，偏移成本及保護線；沒有日收強平。')
 notes={'持有長度':'N是動量端點資料距離，不是持有天數；目前open−N筆前open再扣中間換約delta，0成0動量。','長度單位':'日用05:30交易日日open動量、每交易日第一分鐘查；其他用所選聚合分鐘每根查，聚合從實際首根開始而非完全對齊時鐘。','進場點':'動量點數>=此值才多，含等號；不是%或跨越事件。','出場點':'動量嚴格<此點數才普通平；SMSv2也用此條件解除停利後等待。'}
 if v2:notes|={'直接停利p':'進場價加%或點數的門檻，只在動量更新節點查；已將OHLC覆open，成交max(open,Floor線)通常即open。','啟動移停p':'入場價加距離的原始啟移門檻，動量更新時open>=才推線。','移停拉回p':'以更新時open換距離，Round後線只上移；下一動量節點open到線才退，非每分鐘都查。'}
 add(name,'只做多的open端點動量，扣換約價差後決定進退'+('，停利後等動量回落重置。' if v2 else '。'),'端點動量與換約',ent,ex,[cost,report,'所有行情先克隆成OHLC=open，忽略實際盤中高低；日單位的SMSv2保護也只隨每日首次動量更新，不是全分鐘風控。' if v2 else 'OHLC全覆open，沒有價格風控；只按動量訊號進出。'],['TimeAlign的15分鐘模式卻以5分鐘取整，30／60以15／45分偏移，且資料聚合保留實際首根時戳，換約可能對齊不到而被略過。','Clear清紀錄卻不重設共用position／entryprice等欄位，重用相同實例回測可帶舊部位，不能只因local狀態回NONE就視為全新帳。','日值缺少回0而非缺值跳過，若門檻含0可新進；資料尾未平倉不按市價更新DD。'],notes)
notes={q['name']:'此類別只有版本宣告，未覆寫讀行情或交易核心；基底對應方法為空，此繼承欄位在本策略不產生行情／交易效果。' for q in next(i for i in c['items'] if i['id']=='SuperMA/StgQuote')['parameters']}
add('Quote','未實作行情載入與交易核心的保留策略項，單獨執行不建立任何買賣。','保留與未實作',['沒有訊號判斷或建倉方法；僅保留類別與版本。'],['沒有持倉風控、換約或末端退出核心。'],['基底DoReadData與DoBackTest均空，沒有依名稱自動接行情；這項仍按專案編譯與策略清單狀態保留。'],['參數清單是可設定的繼承欄位，但此類別未執行它們；不宜從停損、方向或固定金額欄位推測已有交易演算法。'],notes)
p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('Wrote MA SMS pair/Quote')

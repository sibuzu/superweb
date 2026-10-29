from pathlib import Path
import json
S=Path(__file__).resolve().parents[1];cat=json.loads((S/'data/catalog.json').read_text('utf8'));p=S/'analysis/SuperVIX.json';out=json.loads(p.read_text('utf8')) if p.exists() else {}
base={'滑價xTick':'每側固定點數=此值×全域商品TickSize；正常FIFO配對扣兩側，tag以x開頭的虛擬平開則用0滑價且不增普通交易次數，不再乘契約價值。','結算前n日換倉':'日線載入時每份合約先去尾n筆再串近月，按資料筆數非固定曆日；負n被當0，並不照Description負值作跨日新舊倉重疊。','口數策略':'只空或多一口將目標限±1；連續空在本項可按每次有效訊號再增加同向1，沒有資金或總量上限，換倉口數依各版本。','計算DD方式':'本項交易核心未讀此欄，DD由FIFO配對損益更新，不會因選每日而自動補虛擬平開。','策略方向':'此保留欄未參與本項核心判斷，方向由本策略固定的多／空或雙向規則決定。','開始日期':'核心按資料日日期篩訊號下界；一般日線入口先載完整歷史而非按參數裁切，指標可用起日前資料。','結束日期':'只限制訊號日期，下一根open執行未再查成交日；多數日線項沒有日期break後的強制清倉。'}
cost='同一策略實例的多個部位共用FIFO，不依symbol／子項ID分帳；總損益=（配對價差−兩側固定滑價）×配對口數，x虛擬配對滑價為0；不乘契約價值，DD只隨配對或明寫的虛擬平開更新。部分平倉助手的單筆profit按最後entryprice算全倉，分批加碼時可與FIFO總績效不同。'
ma='MA是含本日的ref_close現貨SMA；標準差按N−1樣本分母（N=1分母1），未滿窗均線0就跳過。'
def add(n,s,f,en,ex,me,ca,notes={}):
 iid='SuperVIX/Stg'+n;ns=base|notes;out[iid]={'summary':s,'family':f,'entry':en,'exit':ex,'mechanics':me,'caveats':ca,'parameterNotes':{p['name']:ns[p['name']] for p in next(i for i in cat['items'] if i['id']==iid)['parameters']}}
for n in ['均線以上空','布林通道','現貨布林通道']:
 bb=n!='均線以上空';spot=n=='現貨布林通道';nn={'MA':'現貨ref_close的含本日N筆簡單平均，並非期貨close均線；計到第N筆才有效。'}
 if bb:nn['STD']='現貨樣本標準差乘數，上線=MA+STD×σ；嚴格高於才空，回<=MA才全平，帶內續留。'
 en=['本日現貨ref_close嚴格高於'+('MA+樣本σ×STD' if bb else '本日現貨MA')+'時，只一口目標−1，連續模式目標=現有部位−1。']
 ex=['現貨'+('<=MA才目標0，MA與上線之間續留原空倉。' if bb else '<=MA即目標0。'),('同日ref_close' if spot else '下一資料筆期貨open')+'執行目標差額；session改變先本日'+('ref_close' if spot else '期貨close')+'退舊，再按保留目標重新建倉。']
 ca=['只處理到倒數第二筆，資料末端沒有額外平倉，日期越界break亦不補。','方向與每日DD保留欄不影響這個核心；只做空，不是類別Description所說只做多動量。']
 if spot:ca.append('紀錄symbol仍為當下期貨商品，但入出價格用現貨ref_close，同一收盤判訊號且成交；不是可把這個價格當真實期貨成交的執行模型。')
 else:ca.append('以現貨close發訊號、期貨下一open交易，中間價差和隔夜跳空會影響結果，不是直接買賣現貨均線。')
 ca.append('連續模式在換倉前已算舊口數再加1的目標，平舊後會重建該目標，而不是換約自動縮回1口。')
 add(n,('現貨高於均線' if not bb else '現貨突破布林上線')+'放空，'+('以同日現貨價記帳。' if spot else '在下一期貨開盤執行，回歸均線平倉。'),'VIX現貨訊號',en,ex,[cost,ma],ca,nn)
p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('Wrote VIX first3')

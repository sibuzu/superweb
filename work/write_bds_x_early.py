import json,runpy,copy
from pathlib import Path
S=Path(__file__).resolve().parents[1];data=json.loads((S/'data/catalog.json').read_text(encoding='utf8'))
n=runpy.run_path(str(S/'work/write_bds_early.py'))['base']
n.update({'進場模式':'決定新增BD線的日期：每日、每週、結算後第一個報價日，或結算前n個有資料日期；不是下單方向。','結算前n日':'在兩次結算之間的不同報價日期往回選n日，0對應最後結算日期；資料天數不足則取首日，尾端未見結算後資料可無法算出日期。','結算日動作':'有倉時換倉並平移全部保護價，或退出並停止；空手候選仍只平移，不因選停止而自動取消。','進場價格修正':'開啟時把整組基準／目標／保護價平移到觸發參考價；關閉時實際仍記open成交，但保護價按原目標價算。','跳空只進一條':'同根已有一條突破時直接停止其他已觸發候選；關閉可讓同根多條進場。','BD線開盤時間':'僅每日模式使用：當日第一筆HHmm>=此值嘗試建線。每週與結算模式不另限這個時間。','只在日開盤進場':'實際用新曆日首筆上保存的前一日末close作進場與固定停損比較；其他根通常無此參考值。成交價仍當筆open。','只在日開盤移停':'已有移停線時，用新曆日首筆保存的前一日末close檢查直停／回撤；移停啟動與線更新仍每根open處理。'})
p=S/'analysis/SuperBDS.json';res=json.loads(p.read_text(encoding='utf8'))
for name in ['StgBDSX','StgBDSXv2','StgBDSXv3','StgBDSXv4']:
 v=name!='StgBDSX';four=name.endswith('v4');three=name.endswith(('v3','v4'))
 a=copy.deepcopy(res['SuperBDS/StgBDSv2' if v else 'SuperBDS/StgBDS'])
 a['summary']='以每日／每週或結算相對日期畫BD基準，突破上下兩側建立一口多空部位，可選是否把參考價格修正到觸發報價。'+('此版可將進場與退出比較限於日界參考價。' if four else '每日畫線可再指定起始時刻。' if three else '另含淨部位上限、空手存續天數與持倉總停利。' if v else '')
 a['entry']=['畫線依模式選日期：每日首次、每週週次改變、結算後首個有資料日，或結算前n個有資料日期；週次採目前文化行事曆。'+('每日模式另等HHmm>=BD線開盤時間，其他模式不等該時刻。' if three else ''),'上下目標用基準±max(最少進場點,兩側各自距離)，按商品tick取整。空手先多後空，成交一律記當根open；可選修正整組參考價，否則保護仍由原目標價換算。']
 if v:a['entry'].append('容量用本根開始前的有號部位快照絕對值；跳空只進一條可選，達限制者停止。新曆日累加存續天數，只停止已超期空手候選。')
 a['exit']=[s.replace('結算事件將基準、目標及保護價按價差平移，在倉者另記平舊開新及成本。','結算事件有倉時可選平舊開新並平移，或出場並停止；空手者不論動作都只平移基準與目標。') for s in a['exit']]
 a['mechanics']=['先處理舊線再判新增日期；新線開價為當根open，濾網比較所有啟動基準的距離，成立則同根也接受單條交易檢查。', '每線固定一口；跳空修正僅改價格參考，不會改成交open，保護距離可能因此與實際成交價不同。']+([s for s in a['mechanics'] if 'KBAR' in s] if not four else ['此版移除ValidKBAR與OHLC覆寫，核心進出判斷仍直接使用open，KBAR欄位不再篩選。'])
 a['caveats']=[s for s in a['caveats'] if '不使用共用金額' not in s]+['每週只比較週次而非固定某星期幾；結算相對日期需前後資料與事件，資料不足時可能不建立線。','實作仍固定一口，未用共用金額轉口數；進場價格修正關閉時，風控不是以實際成交open為基準。']
 if four:
  a['entry'].append('只在日開盤進場開啟時，觸發參考其實是前一日最後close，僅新曆日第一根有寫入；第一個資料日沒有前日值時無法靠此模式進場。')
  a['exit'].insert(0,'只在日開盤移停開啟時，已有移停的直停／回撤用前日末close比較；尚無移停的固定停損卻跟隨只在日開盤進場開關。這些既有保護線分支的成交使用目前open；空單新移停線另有當根close檢查的例外。')
  a['exit'].append('空單刷新新移停線後，另以當根真實close>=新線判斷，符合就按新線價立即退出；此分支不受日開盤旗標控制。多單沒有相同的刷新後close立即退出分支。')
  a['caveats'].append('空單的刷新後close觸價與新線價成交是open一般規則的例外，不能當成全策略只看open。')
  a['caveats'].append('兩個日開盤開關不是都拿當日open當比較價，也不控制所有風控頻率：移停極值與線價仍每根open更新；固定停損使用的是進場開關。')
  nn=dict(n);nn['KBAR間隔ex']='此版單條交易函式未呼叫ValidKBAR，設定不改進出場頻率。';nn['開始交易時間']='此版未用KBAR篩選，也未用此欄位限制進場；日界參考採曆日切換。';nn['直停限價']='此版不因旗標讀high/low，直停比較open或日界參考值。'
 else:nn=dict(n)
 nn['BD線濾網點']='每次選定畫線日的報價open與啟動中基準距離小於此點數，放棄該次建線；日期標記已前移，不在同日等待價格離開後再試。'
 item=next(i for i in data['items'] if i['id']=='SuperBDS/'+name);a['parameterNotes']={pp['name']:nn[pp['name']] for pp in item['parameters']};res[item['id']]=a
p.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('Wrote',len(res),'SuperBDS explanations')

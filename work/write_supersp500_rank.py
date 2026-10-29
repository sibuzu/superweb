from pathlib import Path
import json,copy,runpy
x=runpy.run_path(str(Path(__file__).with_name('write_supersp500_basic.py')));S=x['S'];out=x['out'];src=x['src']
for name in ['DMS','DMSv2','DMSM','DMSR','RollYield','VRP']:
 v=copy.deepcopy(src['SuperCombo/Stg'+name]);v['mechanics'].append('本程式由7欄日CSV及拆息事件建立調整因子；介面市場選擇決定全域商品字典，與SuperCombo可按DataType串接期貨的資料入口不同。')
 v['caveats'].append('商品字典只載入有日CSV且沒有退市標記檔的商品，帶退市標記者整支排除，不會因回測日期較早而重新納入歷史樣本。')
 if name in ['DMSM','DMSR']:
  v['mechanics'].append('介面此項只列SP500Z市場；商品設定的range事件轉成含端點停用區間，InRange依訊號日判斷，區間內候選仍僅降分為0。')
 elif name=='DMS':v['mechanics'].append('介面提供SP500／VIX／Taiwan；候選仍由商品集合中查全域字典，並非自動選全市場所有股票。')
 elif name=='DMSv2':v['mechanics'].append('介面提供SP500／Taiwan；參考指數也要能在同一全域商品字典找到，未設定或找不到的行為依指數濾網分支。')
 else:v['mechanics'].append('介面此項只列VIX市場，但核心仍寫死XIV／VXX及各波動參考代碼，不會依當下選中的單一商品替換。')
 out['SuperSP500/Stg'+name]=v
(S/'analysis/SuperSP500.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
p=S/'programs.json';pr=json.loads(p.read_text('utf-8-sig'));pr['SuperSP500']='以7欄日CSV／拆息調整價進行單一商品持有、動量／均線／突破／ATR趨勢，及多商品正動量排名、指數濾網、SP500Z歷史區間排名、VXV/VIX期限結構與VIX對歷史實現波動的輪換；SDC只檢查資料。多數訊號在調整周期後下一開盤執行，排名系列保留既有量而非每次等權重配。現金費率每側手續費/200，DMS初始資金為每名額本金；月彙整、未滿窗、估值及資料對齊限制逐項說明。市場字典與有退市標記即整支排除決定歷史候選樣本，並非名稱所示僅固定交易S&P500。';p.write_text(json.dumps(pr,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('Wrote SP500 all12 overview')

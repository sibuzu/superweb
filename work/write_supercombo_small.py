import json
from pathlib import Path
S=Path(__file__).resolve().parents[1];cat=json.loads((S/'data/catalog.json').read_text(encoding='utf8'));p=S/'analysis/SuperCombo.json';out=json.loads(p.read_text(encoding='utf8')) if p.exists() else {}
base={'手續費':'百分比參數，買入扣價金×(1+此值/200)，賣出收價金×(1−此值/200)，所以每側費率是填值的一半；估口數另預留此值/100。','調整周期':'多數訊號只在本根到下根跨周期時才檢查，交易放下根開盤。每季看本根月為3倍數且跨月，每半年看6倍數且跨月；不是所有策略都有使用。','ATR長度':'此策略交易核心未用ATR計量或保護；繼承欄位Description的風險口數公式在此不生效。','初始資金':'Clear會以此重設現金與淨值；本策略由現金除價格向下取整數量，不使用商品每點價值。','流動資金':'執行中的現金帳；Clear覆寫成初始資金，每次買賣再更新，並非額外可獨立指定的本金。','資產淨值':'執行結果狀態，現金+有號部位×當次估價；Clear覆寫初始資金，不是進場濾網。'}
capital='共用現金帳逐筆買賣，數量為整數名目單位；每側成本按手續費/200。淨值與DD只在交易或P估價標記更新，並非完整每日／盤中市價曲線。'
period='只做多；本根收盤成立的訊號，須當次可調整且指標有效，才在下一根open×factor成交。持有期間不定期強制重買等權。'
def add(name,summary,family,entry,exit,mechanics,caveats,notes={}):
 iid='SuperCombo/Stg'+name;n=base|notes;out[iid]={'summary':summary,'family':family,'entry':entry,'exit':exit,'mechanics':mechanics,'caveats':caveats,'parameterNotes':{p['name']:n[p['name']] for p in next(i for i in cat['items'] if i['id']==iid)['parameters']}}
add('SDC','檢查價格調整因子與OHLC資料一致性的工具，沒有交易訊號。','資料檢查',['不建立買賣，從資料尾向前檢查每根。'],['沒有持倉，也沒有交易退出。'],['除權息比對兩組調整收盤，檢查開收是否落在高低範圍，以及同根open/close是否異常。','編入專案，但StgList註解，顯示未在清單中。'],['計delta時先除adj_close，即使關除權息也先算；值為0可除零。當日跳空檢查若開啟也直接除close。','檢查當日開收比，不是今天開盤對昨天收盤的隔夜跳空。資金與調整周期不影響檢查。'],{'除權息':'abs((adj_close2−adj_close)/adj_close)>0.001記不一致訊息；只記錄不修資料。','開高低收':'open或close高於high／低於low時記錄OHLC異常。','當日跳空':'同根open/close>2或<0.5時記錄異常，並非隔夜跳空比。','手續費':'沒有交易，不扣此成本；保留的共用欄位。','調整周期':'檢查每根資料，未使用調整周期。','ATR長度':'資料檢查未計算或使用ATR。','初始資金':'Clear重設帳戶狀態，但資料檢查本身不讀此值，也不換算任何交易數量。','流動資金':'Clear設成初始資金的共用狀態，資料檢查不進行交易或改變現金。','資產淨值':'Clear重設的共用狀態，本策略沒有持倉與績效估值邏輯。'})
add('JustHold','首筆開盤買入持有，跨月重算數量，合約變動平舊開新，資料末筆收盤退出。','持有',['第一根用open按floor(現金/價)買整數單位；不另預留手續費，可能使現金略負。','月份變更時用當日open全賣再重算整數量重買；若同根合約也變，先走換約分支。'],['末筆用close全部賣出；若中間合約變動，按當日close平舊、close+delta重買，紀錄時間多一分鐘。'],[capital,'換約若恰跨月才重算數量，但分母仍使用平舊的close，買新使用close+delta。其餘跨月直接平開，沒有獲利／損失風控。'],['只有一根資料時先進場分支，沒有到末筆平倉分支，會留下持倉。','沒有按調整周期選擇跨月頻率；是固定每次月份變動都平開。實際交易未使用factor，與其他動量策略的調整價格不同。'],{'商品':'透過全域商品字典選交易資料及商品識別；不是只改策略顯示文字。','調整周期':'本策略固定跨月平開，未使用此共用設定。','手續費':'每側按填值/200扣價金，但數量直接floor(現金/價格)未預留費用。'})
for name in ['SMS','TMA','TBO','TKern']:
 entry=[];ex=[];mech=[capital,period];ca=['均線／動量暖機由載入資料長度決定。末筆若落在執行日期內以close×factor平掉；未到訊號時維持空手／原持倉。','交易次數計每次買賣呼叫，P標記僅估值；換月或月末的P價更新也不等於保證每日DD已估。'];notes={}
 if name=='SMS':
  summary='比較今日收盤與N筆前調整到今日基準的收盤，正動量做多、負動量退場。';family='動量'
  entry=['CalcSM保存N筆前收盤×舊factor/今日factor；當今日close嚴格高於此參考且空手、周期可調整，就下一筆開盤買入。']
  ex=['今日close嚴格低於參考且有倉，在下一筆開盤賣出；相等維持，不設固定持有N天或每N天才退出。']
  notes={'動量長度':'比價回看N個資料列，不是入場後固定持有天數；少於N筆參考為0，不能進出。'}
 elif name=='TMA':
  summary='短均線高於長均線做多，短均線低於長均線回空手，按調整周期在下一開盤執行。';family='均線'
  entry=['FMA與SMA皆有效且短線>長線、空手時，下筆開盤投入可用現金。兩線由調整收盤均值換回當日factor價格基準。']
  ex=['短線<長線且有倉時，下筆開盤全退；兩線相等維持原狀，不建立空單。']
  notes={'FMA':'快速收盤簡單平均筆數，索引i<FMA時為0不交易；按factor統一前後基準。','SMA':'慢速收盤簡單平均筆數，與短線比大小；需有效並配合調整周期。'}
 elif name=='TBO':
  summary='收盤突破過去長窗最高價做多，跌破過去短窗最低價退出，訊號放到下一開盤成交。';family='區間突破'
  entry=['以不含本根的SBO根最高high建上軌，今日close嚴格突破上軌且空手時，下筆開盤買入。']
  ex=['以不含本根的FBO根最低low建下軌，今日close嚴格跌破下軌且持多時，下筆開盤全退。']
  notes={'FBO':'排除本根的短窗最低價，提供退出下軌；計算前先用factor統一歷史價格。','SBO':'排除本根的長窗最高價，提供進場上軌；不是用今日最高價碰線即買。'}
 else:
  summary='均線順多且收盤位於滾動窗最高收盤時做多，低於滾動最高收盤減N倍平均ATR時退出。';family='趨勢與ATR'
  entry=['短均線>長均線且今日close>=含本根SBO窗最高close、空手時，下一開盤買入；不是排除今日的high突破。']
  ex=['持多時每根計stop=SBO窗最高收盤−停損ATR×平均ATR，今日close嚴格低於stop且周期可調整，下一開盤全退。均線轉空本身不直接出。']
  notes={'SBO':'含本根的最近收盤最高窗，用同一滾動最高收盤作進場及停損參考。','FMA':'快收盤平均，只有進場需高於慢線，並非空頭交易訊號。','SMA':'慢收盤平均，與快線同時有效才允許周期調整。','停損ATR':'滾動窗最高收盤減平均ATR×此倍數為停止線；不是開倉以來最高價。','ATR長度':'當日含跳空真實範圍的簡單平均筆數，初期不足用已有筆數平均；只供停損線，不用來計口數。'}
  ca.append('停止線用滾動窗最高收盤及變動ATR，可隨最高值移出窗或ATR放大而放鬆，不是只朝有利方向推進的最高價追蹤。停損也受調整周期約束，不是每日必查成交。')
 add(name,summary,family,entry,ex,mech,ca,notes)
p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('Wrote 6 SuperCombo explanations')

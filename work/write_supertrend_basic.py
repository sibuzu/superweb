from pathlib import Path
import json
S=Path(__file__).resolve().parents[1];cat=json.loads((S/'data/catalog.json').read_text('utf8'));p=S/'analysis/SuperTrend.json';out=json.loads(p.read_text('utf8')) if p.exists() else {}
base={'滑價xTick':'純數×商品TickSize，尾%為各成交價百分比；FIFO損益扣入場與退出各側滑價，不另扣手續費、不再乘商品PointValue。','ATR長度':'計含跳空真實範圍的SMA，不足窗先用已有筆數平均；本策略只附ATR成交欄位，不用風險公式配量，實際固定1口。','操作方向':'多空都作／只多／只空限制訊號方向；各策略如何處理相反訊號依各核心，ETF專用分支可能不讀此值。','開始日期':'核心按日日期作訊號下界；正常介面先依起訖裁切後才算指標，暖機占起始區段。SMS2另會主動提早重載；其他版本只有另載前史並直接呼核心才可能起日前暖機。','結束日期':'核心用作訊號日期上界；下一筆open交易沒有再查成交日，資料載入外部另裁切，末端是否平倉依版本。'}
cost='共用FIFO按實際價差−入場滑價−退出滑價計已實現點數×口數，不再乘PointValue；核心DD只在配對退出更新；一般單次介面隨後以成交現金流、M／N記錄價格重算淨值與DD（仍不乘PointValue），並覆寫總績效／DD，交易次數與Gross欄未重算。總紀錄>2才補首末成交間、原無同時間戳的日close N；<=2不補，並非完整每日收盤曲線。批次入口未做這兩步重估，績效口徑可不同。'
roll='若本筆session與下一筆不同，先本close平舊，再按目標於下一open重進；訊號反手則下一open一次交易含平舊與開新，固定目標±1，不依ATR換口數。'
etf='ETF另走首個有效日open買1並持有，忽略操作方向和動量訊號；跨月下根open寫M0並更新單筆記帳進價，不改真實口數；循環跳出時索引的close退出。'
def add(name,summary,family,en,ex,me,ca,notes={}):
 iid='SuperTrend/Stg'+name;ns=base|notes;out[iid]={'summary':summary,'family':family,'entry':en,'exit':ex,'mechanics':me,'caveats':ca,'parameterNotes':{q['name']:ns[q['name']] for q in next(i for i in cat['items'] if i['id']==iid)['parameters']}}
for name in ['SMS','SMS2']:
 dynamic=name=='SMS2';en=['非ETF以本日close對N筆前close×舊delta／本delta的乘數校正端點，嚴格高則多、低則空，等號目標0；允許方向成立後下一筆open達到±1。'];ex=['等號或不允許的方向把目標改0，下一open平；session變更先本close退舊再次open按目標進。']
 ca=['ETF分支不是動量買賣，與類別Description只作多動量的文字不同；M估價會改單筆entryprice，核心FIFO仍保留原買價；介面另以含M的現金流估值覆寫總績效／DD，所以逐筆profit欄與總績效不能直接混讀。','ETF在迴圈因>結束日期break時，收尾用當下索引close，若資料還有更晚日期可在迄日後退出；只有1筆資料則不會首次買入。']
 nn={'動量長度':'端點比較回看N資料筆，不是均線；非ETF使用校正歷史close，ETF雖準備指標但不以它進退。','操作方向':'非ETF高於端點允許多、低於端點允許空，不允許側及相等都目標0；ETF分支固定買多且忽略此設定。'}
 if dynamic:
  en+=['先等候反向區域出現：close<SM才把買向設READY、close>SM才把賣向設READY；只有該向不再WAIT才能在回穿時進場，兩向旗標之後不重設。','回測先按初始長度算SM；每根持倉且目前長度<動量長度時長度+1，再重算本根端點，空手停止增長，退場也不回初始。']
  ex+=['非ETF即使PredictMode也在有效最後一筆close平，不再新進；若因日期先break或指標0提前略過最後根，沒有額外收尾補平。']
  nn|={'開始日期':'SMS2核心會把讀取起點主動提前初始長度×3/2整數曆日，算完SM後仍只處理>=本日期訊號，因此可在起日前暖機；不同於其他版本正常先裁切再算。','初始動量長度':'初次SM窗，並將資料讀取起點提前(此值×3/2整數計算)曆日；持倉時逐筆增加到目標，若本來較大不縮回。','動量長度':'動態窗口的增長目標，持倉每筆+1直到此值；空手不增長且退出不重設，並非每次入場由初始重走。'}
  ca+=['READY／ENTERED只有進程標記，退場未回WAIT；第一次需反向區域準備，以後不必每筆再滿足首次等待。']
 else:
  ex+=['非ETF最後根只有PredictMode=false才以close平；PredictMode=true不強平。指標0時先continue也可能跳掉末根平倉。']
  nn['結束日期']='ETF分支會以此檢訊號上界；非ETF的>結束日期break已註解，實際靠資料載入範圍限制，不可只靠此欄。'
 add(name,('動量先等反向準備、持倉逐步延長端點窗口後按收盤轉向；' if dynamic else '非ETF依收盤端點動量做多空，下一開盤執行；')+'ETF改走固定一口買入持有。','動量與趨勢',en,ex,[cost,roll,etf],ca,nn)
add('TMA','短收盤均線高於長線做多、低於做空或空手，相等退出，下一開盤執行。','均線與區間突破',['以close×delta先累加再除本根delta算含本根的快慢SMA；兩者非0且日期有效時，快>慢目標多1、快<慢目標空1，受方向允許。'],['不允許方向或快慢相等都目標0，下一open平；反向有效直接反手，session變更本close平後次open重進。','迴圈只到倒數第二筆，沒有最後close強平；結束日break也不補平。'],[cost,roll],['與只做多且均線相等續留的版本不同，本版相等會退出，並可真正建立空單。','均線需i>=各長度才非0，SMA窗口雖含本根但比通常N−1起算晚一筆暖機。'],{'FMA':'快SMA筆數，含本根close的delta乘數校正平均；i<FMA填0不交易。','SMA':'慢SMA筆數，與快線比大／小，相等目標0；必須兩均線有效。'})
add('TBO','收盤突破前期長高低帶進多空，依短期反側帶退出，次開執行並在session交界換約。','均線與區間突破',['長SBO窗排除本根的high／low經delta乘數校正，本close>=長高且舊非多優先目標多，否則<=長低且舊非空目標空，須該向允許。'],['未進長帶分支才檢持多close<=短低、持空close>=短高目標0；相反長帶可直接反手。','訊號下一open成交，session交界先本close平；最後close沒有收尾強平，僅處理到倒數第二根。'],[cost,roll],['方向限制只在長帶進場內層判斷，不是統一把不允許方向改0；若命中不允許側的長帶仍吃掉else-if，會跳過本應觸發的短帶退出。'],{'操作方向':'只在長帶新方向分支判斷允許；命中不允許的長帶也不往下查短帶平倉，不會自動把原倉改0。','FBO':'排除本根的前FBO筆low／high作多退／空退，含等號；只有未命中長帶分支才檢。','SBO':'排除本根的前SBO筆high／low作雙向入場，close>=／<=即成立，不只嚴格穿越。'})
add('TKern','雙均線方向配滾動最高／最低收盤進多空，以滾動收盤極值±平均ATR決定退出。','趨勢與ATR',['空手快MA>慢MA且close>=含本根SBO窗最高close可多，快<慢且close<=窗最低close可空，操作方向需允許；下一open建立固定1口。'],['持多close<滾動最高close−ATR倍數×平均ATR退，持空close>滾動最低close+ATR距離退，下一open執行；持倉不直接因MA反轉退出或反手。','session交界本close平舊，依保留目標次open再進；資料末根沒有強平，可能保留部位。'],[cost,roll,'停損極值是SBO滾動窗口，不是開倉以來的最佳收盤，ATR亦每日變動；線可隨窗口移出舊極值或波動變化而放寬。'],['註解聲稱按波動調口數，實際contract=1；ATR只供停止線與紀錄，沒有風險資金換量。'],{'SBO':'含本根SBO筆調整收盤極高／極低，用於空手突破及持倉停損，非排除今日的high／low。','FMA':'快收盤SMA，進場多需>慢、空需<慢；持倉後不再拿它作退出。','SMA':'慢收盤SMA，與快線及收盤極值都非0才處理本根。','停損ATR':'滾動窗收盤極值加減當日平均ATR×此倍數，close嚴格穿越才下一open退出；不是盤中觸線成交。','ATR長度':'乘數校正昨close後計true range的平均筆數，不足窗用已有均值；只供停止線，口數固定1。'})
p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('Wrote Trend initial5')

from pathlib import Path
import json
S=Path(__file__).resolve().parents[1];c=json.loads((S/'data/catalog.json').read_text('utf-8-sig'));out={}
base={'_固定金額萬':'每次建立一腿的名目額=此值×10000，按當根open換數量並向下取6位有效數字，不隨獲利複利、不預留成本。','_交易成本比':'每次買額外扣成交金額×此百分比，賣少收同百分比；平開／換約兩側也扣，非固定點數。','策略方向':'可只多／只空／雙向，四個訊號策略用此限制方向；BuyHold與持有固定時間核心直接DoBuy，忽略此欄。'}
cost='成交全部用當根open，每次固定名目換6位有效數字數量；紀錄依商品累計現金與淨量，成本按每筆名目百分比扣，不算利息或借券費。日末可加不交易的N紀錄，以當根close更新估值。'
report='損益與DD只在紀錄事件估值，不是每小時完整市價曲線；相鄰紀錄間隔<30分鐘先合併再計一組交易／DD，反手同時平開不一定算兩次。'
def add(name,summary,family,entry,exit,me,ca,notes={}):
 iid='SuperHour/Stg'+name;ns=base|notes;out[iid]={'summary':summary,'family':family,'entry':entry,'exit':exit,'mechanics':me,'caveats':ca,'parameterNotes':{p['name']:ns[p['name']] for p in next(i for i in c['items'] if i['id']==iid)['parameters']}}
add('BuyHold','第一根open按固定名目買入，持有到最後根open賣出，合約改變時平舊接新。','買入持有',['資料至少兩筆，第一根open直接建多一腿，不按策略方向選空。'],['最後根open全平；相鄰根合約不同時本根open平舊、下一根open以原數量買回，不重算等額。'],[cost,report],['單筆資料會先命中最後根分支而不進；第一根買完continue，所以若第一、第二根正好換約，該邊界未處理。','只有換約或日界時補估值；交易成本／換約成本外沒有其他持倉風控。'],{'策略方向':'核心固定DoBuy，設只空仍買多，此欄未生效。'})
add('持有固定時間','固定每N筆小時資料先平再買，重設名目數量，期間持多並處理換約。','固定週期持有',['從索引0起，每逢i%區間時數==0，先平全部再按目前open重建固定名目多；同方向也付平開兩側成本。'],['最後根先open全平，不再重建；週期之間若合約改變，本根open平舊、下一根open以原數量接回。'],[cost,report],['區間實為資料筆數，缺小時不補，因此不是絕對經過N小時；區間0會除零。','週期重建後continue，若恰同合約邊界則跳過換約處理；策略方向也完全未讀，始終做多。'],{'區間時數':'每此整數筆重開一次，需>0；索引0就建，多筆缺時間不補，不按時鐘計時。','策略方向':'核心每個週期直接DoBuy，設只空也買多，未使用此欄。'})
for name in ['簡單動能','簡單均線','布林通道','價格突破']:
 momentum=name=='簡單動能';ma=name=='簡單均線';bb=name=='布林通道';bo=name=='價格突破'
 if momentum:middle='N筆前open';band='該參考價×(1±突破比/100)';comp='>='
 elif ma:middle='前N筆open簡單均值（不含當根）';band='均值×(1±突破比/100)';comp='>='
 elif bb:middle='前N筆open簡單均值（不含當根）';band='均值±突破值×前N筆open標準差';comp='>='
 else:middle='前N筆open最高與最低的中點';band='前N筆open最高／最低，不含當根';comp='>'
 entry=['從索引N開始，參考中值='+middle+'，外帶='+band+'；現open'+comp+'上帶且允許多、原倉<=0就多，現open'+('<' if bo else '<=')+'下帶且允許空、原倉>=0就空。','任何方向訊號先平舊再以同根open按固定額開新，只有訊號狀態變化才重算數量；同向續持不每天加碼。']
 ex=['多單現open嚴格低中值／空單嚴格高中值平；反向外帶先於中值平判，所以允許反向時可直接平後反手。','一般回測資料末筆先open全平並break，不在最後根再新進；沒有其他固定損、停利或日平。']
 me=[cost,report,('價格突破另有合約邊界平舊／下一open原量接回；同根交易／換約未發生且跨日才加估值。' if bo else '此版本沒有換約處理，現貨／期貨合約價格變更可直接進入open指標；跨日先加close估值再處理本根訊號。')]
 ca=['區間按已載資料筆數；原始open不依delta還原，價格缺根或換約跳價可改訊號。指標以整段裁切後資料暖機，不另載前N筆歷史。']
 if bo:ca.append('DebugMode略過末筆強平後仍讀下一根合約，最後索引會越界；此例外屬debug分支，一般模式先break。')
 else:ca.append('DebugMode不執行末筆全平，可留下未平部位；一般模式則末筆open真平。日末估值close卻沿該根起始時間戳，和訊號open不在相同價位時點。')
 notes={'區間時數':'N筆原始小時行情窗口；需正整數。'+('作N筆前open端點，不是均線。' if momentum else 'TA函式結果多移一筆，當根指標使用截至前一根的N筆。')}
 if ma or momentum:notes['突破比']='以'+middle+'乘百分比建上下帶；到外帶可進，回中值另一側平，不是固定百分比止損。'
 if bb:notes['突破值']='上下帶共同的標準差倍率，不是百分比。中線為前N筆open的簡單平均。'
 add(name,('N筆端點動能' if momentum else 'N筆均線外帶' if ma else '布林外帶' if bb else '前N筆價格區間')+'突破做多空，回中線平，全部以當根open交易。','價格動量與通道',entry,ex,me,ca,notes)
(S/'analysis/SuperHour.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8');p=S/'programs.json';d=json.loads(p.read_text('utf-8-sig'));d['SuperHour']='原始小時open的買入持有、固定筆數重開、端點動能、簡單均線、布林與價格區間突破。每次固定名目、有效數字換量，回中值退出或反手；只有部分版本處理換約，估值是交易與日末紀錄事件，BuyHold及固定週期版本始終做多。';p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('Wrote SuperHour six/overview')

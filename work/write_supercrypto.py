import json,copy
from pathlib import Path
S=Path(__file__).resolve().parents[1];remote=json.loads((S/'analysis/RemoteCrypto.json').read_text(encoding='utf8'));cat=json.loads((S/'data/catalog.json').read_text(encoding='utf8'));out={}
n={'部位管理':'固定口數直接存子項下單數；槓桿模式以floor(資金淨值×槓桿倍數/(價格×每口幣單位))計量。BDS空手進場及平倉重算，TEST只建立子項時取一次。','固定口數':'固定模式每個內部單位對應的下單數，存於子項；不是全體所有線合計上限。','資金淨值':'設定時反推現金=淨值−總口數×目前價×每口幣量；BDS交易時再更新估值，非券商成交後實際帳戶權益。','槓桿倍數':'只在槓桿模式換算子項下單數，不是直接調交易所槓桿設定；沒有手續費、資金費或維持保證金風控。','BD線畫線日':'每天或指定星期：DayOfWeek對(enum值%7)比較。先消耗Start後唯一畫線旗標才查星期，不符星期也不留待別日再試。'}
for name in ['BDS','TEST']:
 a=copy.deepcopy(remote['RemoteCrypto/Stg'+name]);iid='SuperCrypto/Stg'+name;notes=a['parameterNotes'];notes.pop('下單口數');notes|=n
 if name=='BDS':
  a['summary']='指定星期與時間報價建BD基準，突破後多／空一個內部單位；以子項保存的固定或槓桿口數換算實際數量，停損可重進，直停／移停後停止。'
  a['entry'][0]='每次Start後HHmm精確等於畫線時間的第一筆，先標記已嘗試，再檢查近價濾網與指定星期；通過才建線，當根也檢查新子項。'
  a['entry'][2]='達目標先檢查有號淨內部部位上限，再平移基準並以當筆price記進場；內部一單位乘本子項下單數，不同線的實際量可不同。'
  a['mechanics'][1]='交易先更動本地部位、紀錄與現金，池用啟動子項的部位×下單數加總幣別淨差，再於實單模式送交易佇列；模擬price不是交易所成交回報。'
  a['mechanics'].append('BDS由空手入場、平倉後會依新淨值重算下單數；內部估值總口數卻包含同母全部子項而未過濾啟動，與池下單彙總範圍不同。')
  a['caveats'].append('槓桿量沒有價格／幣單位為0或淨值為負的防護；可能除零或得到零／負下單數。淨口數上限仍只管內部單位，不能限制各子項槓桿後總名目量。')
  notes['全部進場口數']='啟動子項內部有號部位的方向上限，0不限；未乘每項下單數，多空可互抵，不是實際名目量限制。'
 else:
  a['entry'][0]='產生交易／報價與交易時，只取第一個子項且須啟動；空手直接記+1，原多一內部單位直接記−2反成空一單位。'
  a['mechanics'][0]='測試直接呼叫DoTradeRecord，每筆量乘子項保存的下單數，並更新內部現金；不走BDS的策略作多／作空方法，因此不在每次進場重算口數或更新資金淨值。池仍依啟動幣別淨差送實單。'
  a['caveats'].append('啟動建立缺少的單一子項時CreateStgItem未傳價格，價格為0；若選槓桿模式會以0作分母。固定模式可建立，但之後調固定口數也不會自動覆寫已存在子項下單數。')
  notes['部位管理']='建立子項時可固定或槓桿計下單數，但TEST之後直接記交易、不再重算。新建子項啟動路徑未傳價，槓桿模式可能除以0。'
  notes['固定口數']='建立TEST子項時保存的乘數；之後每根反手繼續用子項保存值，修改母欄位不自動改舊子項。'
  notes['資金淨值']='可設定反推內部現金，但TEST只更動交易現金，不呼叫共用交易包裝的淨值更新；不能當成每報價刷新帳戶損益。'
 a['parameterNotes']={p['name']:notes[p['name']] for p in next(i for i in cat['items'] if i['id']==iid)['parameters']};out[iid]=a
(S/'analysis/SuperCrypto.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
p=S/'programs.json';v=json.loads(p.read_text(encoding='utf8'));v['SuperCrypto']='即時幣價BD突破狀態機與交替多空的管線測試，支援子項固定口數或槓桿淨值換算。畫線星期、Start單次旗標與TEST直接記錄路徑存在重要限制；內部模擬現金／交易紀錄與交易所真實成交分開解說。';p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('Wrote 2 SuperCrypto explanations')

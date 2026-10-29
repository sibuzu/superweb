from pathlib import Path
import json,re,copy,difflib
S=Path(__file__).resolve().parents[1];R=S.parent;cat=json.loads((S/'data/catalog.json').read_text('utf8'));src=json.loads((S/'analysis/SuperCombo.json').read_text('utf8'));p=S/'analysis/SuperSP500.json';out=json.loads(p.read_text('utf8')) if p.exists() else {}
def norm(s):
 s=re.sub(r'^using .*?;\s*','',s,flags=re.M);s=re.sub('Super(SP500|Combo)','PROGRAM',s);needle='public override enumMarket[] AvailMarket';a=s.find(needle)
 if a>=0:
  b=s.index('{',a);depth=1;j=b+1
  while depth:
   depth+=(s[j]=='{')-(s[j]=='}');j+=1
  s=s[:a]+s[j:]
 s=s.replace(', com.DataType)',')');s=re.sub(r'if\s*\(com.Symbol == "AMD" && ym == 201710\)\s*ym = ym;','',s)
 return re.sub(r'\s+','',s)
for name in ['SDC','SMS','TMA','TBO','TKern','DMS','DMSv2','DMSM','DMSR','RollYield','VRP']:
 a=(R/f'src/SuperSP500/Strategies/Stg{name}.cs').read_text('utf-8-sig');b=(R/f'src/SuperCombo/Strategies/Stg{name}.cs').read_text('utf-8-sig');assert norm(a)==norm(b),name
print('Proved 11 strategy bodies equal after market/read signature/no-op normalisation')
for name in ['SDC','SMS','TMA','TBO','TKern']:
 v=copy.deepcopy(src['SuperCombo/Stg'+name]);v['mechanics'].append('本程式以7欄日CSV及可選拆息事件載入，factor由調整收盤／拆息資料建立；不是SuperCombo依資料型別切換的期貨合約串接。')
 if name in ['TMA','TBO','TKern']:v['mechanics'].append('介面市場篩選提供SP500／Taiwan，交易核心仍使用當下所選商品資料。')
 if name=='SMS':v['mechanics'].append('介面市場篩選提供SP500／VIX／Taiwan；動量核心本身並不把商品限制為S&P500指數。')
 out['SuperSP500/Stg'+name]=v
notes=copy.deepcopy(src['SuperCombo/StgSMS']['parameterNotes']);notes.pop('動量長度');notes['調整周期']='此策略未讀調整周期；只在月份不同時寫open估價標記，不重配或重新買進。';notes['初始資金']='Clear設現金／淨值起點；第一筆量=floor(現金×(1−手續費/100)/(open×factor))，只初次配量。'
out['SuperSP500/StgBnH']={'summary':'首筆調整開盤投入整數量，跨月只更新估價，持有到最後調整收盤。','family':'持有','entry':['第一筆價格=open×factor，先按現金預留手續費/100再floor買入數量，先寫P估價再買；沒有方向或動量篩選。'],'exit':['資料末筆以close×factor賣出全部；中間不按月調張，也沒有停損或停利。'],'mechanics':['現金帳每側按價金×手續費/200扣費，並非填值全部在單側扣。初始估量預留率則是手續費/100。','只有跨月的中間資料筆才用open×factor寫P估價，不產生買賣；DD只在成交／P標記更新，不是完整每日close曲線。','介面可選SP500／SP500Z／VIX／Taiwan；名稱不表示固定綁定某一指數。日CSV及拆息調整因子決定實際調整價格。'],'caveats':['只有一筆資料會先進首筆if，不再進末筆else if，留下持倉；空資料則沒有任何買賣。','Description誤寫Split Dividend Check，實際交易核心是買入持有，與SDC檢查工具不同。'],'parameterNotes':notes}
p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('Wrote SP500 initial6')

#!/usr/bin/env python3
"""Fetch fresh public RSS news without credentials. Run locally or in GitHub Actions."""
import hashlib, json, os, re, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).parent
OUT=ROOT/'data'/'news.json'
NOW=datetime.now(timezone.utc)
QUERIES={
 'figma':'site:figma.com (Figma update OR release OR new features OR Config OR Make OR Dev Mode)',
 'ai':'site:openai.com OR site:anthropic.com OR site:blog.google AI model product launch design',
 'ux':'site:nngroup.com OR site:smashingmagazine.com OR site:design.google UX research service design trends',
 'events':'design conference OR Figma Config OR Apple event OR Adobe MAX OR Google I/O upcoming announcement',
 'tech':'(Apple OR Microsoft OR Google OR Adobe) product launch design technology',
}
FEEDS=[('figma','Figma / Google News',f'https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-US&gl=US&ceid=US:en') for k,q in QUERIES.items() if k=='figma']
FEEDS += [(k,'Google News',f'https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-US&gl=US&ceid=US:en') for k,q in QUERIES.items() if k!='figma']
FEEDS += [('tech','TechCrunch','https://techcrunch.com/feed/'),('ux','Smashing Magazine','https://www.smashingmagazine.com/feed/')]
UA='SignalDesignIntelligence/1.0 (RSS reader; personal research)'

def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.5'})
 with urllib.request.urlopen(req,timeout=22) as res:return res.read(2_500_000)

def clean(s):
 s=re.sub(r'<[^>]*>',' ',str(s or ''))
 return re.sub(r'\s+',' ',unescape(s)).strip()

def parse_date(s):
 try:
  d=parsedate_to_datetime(s)
  if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
  return d.astimezone(timezone.utc)
 except Exception:return None

def entries(raw,cat,source):
 root=ET.fromstring(raw)
 for item in root.findall('.//item'):
  title=clean(item.findtext('title'))
  url=(item.findtext('link') or '').strip()
  dt=parse_date(item.findtext('pubDate') or '')
  if not title or not url or not dt or dt>NOW+timedelta(hours=2) or dt<NOW-timedelta(days=10):continue
  desc=clean(item.findtext('description'))
  if len(desc)>450:desc=desc[:447]+'…'
  name=clean(item.findtext('source') or source)
  # Stable title signature handles re-issued RSS URLs.
  normal=re.sub(r'[^a-z0-9\u4e00-\u9fff]','',title.lower())
  ident=hashlib.sha256(normal.encode()).hexdigest()[:20]
  yield {'id':'rss_'+ident,'title':title[:220],'category':cat,'summary':desc,'url':url,'source':name,
         'date':dt.strftime('%Y-%m-%d'),'publishedAt':dt.isoformat(),'added':NOW.astimezone(ZoneInfo('Asia/Tokyo')).strftime('%Y-%m-%d'),'saved':False,'automatic':True}

# Transparent fallback when no AI API key is configured. This is rule-based,
# not a replacement for a fact-checked AI reading of full article text.
KEYS={
 'figma': [('Figma Make','原型与AI协同'),('Dev Mode','设计开发交付'),('plugin','插件生态'),('variables','设计变量'),('Config','产品发布'),('component','组件系统')],
 'ai':[('agent','AI Agent'),('model','模型能力'),('API','API集成'),('workflow','自动化流程'),('coding','AI编程'),('enterprise','企业落地')],
 'ux':[('research','用户研究'),('accessibility','无障碍设计'),('design system','设计系统'),('usability','可用性'),('service','服务设计'),('journey','用户旅程')],
 'events':[('conference','设计会议'),('launch','产品发布'),('event','行业活动')],
 'tech':[('privacy','隐私安全'),('interface','交互体验'),('platform','平台生态'),('AI','AI产品'),('product','产品策略')]
}
DOMAIN={'figma':('Figma工作流','评估是否能优化组件、原型或设计交付的日常步骤。'), 'ai':('AI应用','辨别新能力适合解决什么真实设计问题，并安排一次小规模试用。'), 'ux':('UX方法','对照当前项目，思考如何把相关方法用于调研、验证或设计决策。'), 'events':('行业活动','查看议程和发布内容，提取与你的职业方向直接相关的主题。'), 'tech':('产品趋势','观察产品定位、交互决策和用户价值能否迁移到你的项目。')}
def fallback_analysis(a):
 cat=a.get('category','tech');txt=(a.get('title','')+' '+a.get('summary','')).lower()
 kws=[label for phrase,label in KEYS.get(cat,[]) if phrase.lower() in txt]
 if not kws:kws=[DOMAIN.get(cat,DOMAIN['tech'])[0]]
 kws=list(dict.fromkeys(kws))[:4]
 # title/short summaries alone do not establish the full article's claims.
 score={'figma':3,'ai':2,'ux':3,'events':2,'tech':1}.get(cat,1)
 if any(x in txt for x in ['release','launch','new feature','update','figma make','accessibility','research','design system']):score=min(5,score+1)
 return {'keywords':kws,'learning':DOMAIN.get(cat,DOMAIN['tech'])[1], 'takeaway':'先阅读原文核对事实；重点关注：'+a.get('title','')[:100], 'priority':score,'analysisType':'规则初筛'}

def ai_enrich(records):
 key=os.environ.get('OPENAI_API_KEY','').strip()
 for a in records:a.update(fallback_analysis(a))
 if not key or not records:return
 model=os.environ.get('OPENAI_MODEL','gpt-4.1-mini')
 # Read RSS title + excerpt, not full articles; be explicit about this limit.
 for offset in range(0,len(records),12):
  batch=records[offset:offset+12]
  inp=[{'id':a['id'],'title':a['title'],'excerpt':a.get('summary',''),'category':a.get('category','')} for a in batch]
  prompt=('你是UI/UX、Service Design、HCD、Figma和AI工作流的研究助理。仅依据以下RSS标题和简介做中文简明分析；不得编造未出现的事实。'
          '为每一条生成：takeaway(中文不超过65字：是什么及为何值得关注)、learning(中文不超过70字：设计师可学什么或立即可做的验证)、'
          'keywords(2-4个具体中英关键词)、priority(1-5，5为必须关注)。弱相关条目评分1-2。'
          '返回严格JSON对象 {"items":[{"id":"...","takeaway":"...","learning":"...","keywords":["..."],"priority":3}]}。'
          '素材：'+json.dumps(inp,ensure_ascii=False))
  payload={'model':model,'messages':[{'role':'user','content':prompt}],'response_format':{'type':'json_object'},'temperature':0.2}
  req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=json.dumps(payload).encode('utf-8'),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
  try:
   with urllib.request.urlopen(req,timeout=75) as res:body=json.loads(res.read())
   parsed=json.loads(body['choices'][0]['message']['content'])
   mapped={x.get('id'):x for x in parsed.get('items',[]) if isinstance(x,dict)}
   for a in batch:
    x=mapped.get(a['id'])
    if not x:continue
    a['takeaway']=str(x.get('takeaway') or a['takeaway'])[:240]
    a['learning']=str(x.get('learning') or a['learning'])[:240]
    a['keywords']=[str(z)[:40] for z in x.get('keywords',[]) if isinstance(z,str)][:4] or a['keywords']
    try:a['priority']=max(1,min(5,int(x.get('priority',a['priority']))))
    except (ValueError,TypeError):pass
    a['analysisType']='AI基于RSS摘要'
  except Exception as ex:print('WARNING AI analysis failed, rule fallback retained:',str(ex)[:220])

def daily_archive(articles):
 # Create immutable date-oriented snapshots, but include an index of first-seen
 # date for all collected stories. Keep the daily file even if that day had no new items.
 folder=ROOT/'data'/'daily';folder.mkdir(parents=True,exist_ok=True)
 bydate={}
 for a in articles:
  date=a.get('added') or a.get('date')
  if re.fullmatch(r'\d{4}-\d{2}-\d{2}',date or ''):
   bydate.setdefault(date,[]).append(a['id'])
 day=NOW.astimezone(ZoneInfo('Asia/Tokyo')).strftime('%Y-%m-%d')
 bydate.setdefault(day,[])
 for date,ids in bydate.items():
  out=folder/(date+'.json')
  if not out.exists() or date==day:
   out.write_text(json.dumps({'date':date,'ids':sorted(set(ids)),'count':len(set(ids))},ensure_ascii=False,indent=2)+'\n')
 return len(bydate)

def main():
 old=[]
 if OUT.exists():
  try:old=json.loads(OUT.read_text()).get('articles',[])
  except Exception:pass
 existing={a['id']:a for a in old if a.get('id')}
 new_records=[]
 count=0
 for cat,src,url in FEEDS:
  try:
   rows=list(entries(get(url),cat,src))
   for item in rows:
    if item['id'] not in existing:existing[item['id']]=item;new_records.append(item);count+=1
   print(cat,src,len(rows))
  except Exception as ex:print('WARNING',cat,src,str(ex)[:250])
  time.sleep(.3)
 # Also enrich existing records from the first V2 run, so today's news gains analysis.
 pending=new_records+[a for a in existing.values() if 'keywords' not in a and a not in new_records]
 ai_enrich(pending)
 articles=sorted(existing.values(),key=lambda a:a.get('publishedAt',''),reverse=True)
 # No automatic pruning: preserve the complete historical archive.
 OUT.parent.mkdir(parents=True,exist_ok=True)
 archived_days=daily_archive(articles)
 obj={'updatedAt':NOW.isoformat(),'articles':articles,'status':'ok' if articles else 'empty','newCount':count,'sourcesChecked':len(FEEDS),'archivedDays':archived_days}
 OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
 print('Total:',len(articles),'New:',count)
 # Optional Lark webhook; do not require it for the website to work.
 webhook=os.environ.get('LARK_WEBHOOK_URL','').strip()
 if webhook and count:
  new_ids={a['id'] for a in articles if a['id'] not in {x.get('id') for x in old}}
  latest=[x for x in articles if x['id'] in new_ids][:8]
  body='📰 SIGNAL · 设计科技资讯更新\n\n'+'\n'.join(f'• [{x["category"]}] {x["title"]}\n{x["url"]}' for x in latest)
  payload=json.dumps({'msg_type':'text','content':{'text':body}}).encode()
  try:
   req=urllib.request.Request(webhook,data=payload,headers={'Content-Type':'application/json'},method='POST')
   with urllib.request.urlopen(req,timeout=20) as response:print('Lark:',response.status)
  except Exception as ex:print('WARNING Lark:',str(ex)[:200])

if __name__=='__main__':main()

#!/usr/bin/env python3
"""Fetch fresh public RSS news without credentials. Run locally or in GitHub Actions."""
import hashlib, json, os, re, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

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
         'date':dt.strftime('%Y-%m-%d'),'publishedAt':dt.isoformat(),'added':NOW.strftime('%Y-%m-%d'),'saved':False,'automatic':True}

def main():
 old=[]
 if OUT.exists():
  try:old=json.loads(OUT.read_text()).get('articles',[])
  except Exception:pass
 existing={a['id']:a for a in old if a.get('id') and a.get('automatic')}
 count=0
 for cat,src,url in FEEDS:
  try:
   rows=list(entries(get(url),cat,src))
   for item in rows:
    if item['id'] not in existing:existing[item['id']]=item;count+=1
   print(cat,src,len(rows))
  except Exception as ex:print('WARNING',cat,src,str(ex)[:250])
  time.sleep(.3)
 articles=sorted(existing.values(),key=lambda a:a.get('publishedAt',''),reverse=True)
 articles=[a for a in articles if a.get('publishedAt','') >= (NOW-timedelta(days=90)).isoformat()][:400]
 OUT.parent.mkdir(parents=True,exist_ok=True)
 obj={'updatedAt':NOW.isoformat(),'articles':articles,'status':'ok' if articles else 'empty','newCount':count,'sourcesChecked':len(FEEDS)}
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

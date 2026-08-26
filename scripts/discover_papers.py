#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, html, json, re, time
import urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path

ARXIV_API = "https://export.arxiv.org/api/query"
S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"
OR_API = "https://api2.openreview.net/notes"
ATOM = {"a": "http://www.w3.org/2005/Atom"}

def jload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def norm(s):
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def first_content_word(title):
    stop={"a","an","the","of","on","for","to","in","with","and","via","from","by","using"}
    for w in re.findall(r"[A-Za-z0-9]+", title):
        if w.lower() not in stop:
            return re.sub(r"[^A-Za-z0-9]", "", w).lower()
    return "paper"

def parse_date(s):
    if not s: return None
    s=s[:10]
    try: return dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    except: return None

def stable_id(p):
    if p.get("doi"): return "doi:"+p["doi"].lower()
    if p.get("arxiv_id"): return "arxiv:"+re.sub(r"v\d+$","",p["arxiv_id"])
    base=(p.get("title","")+"|"+";".join(p.get("authors",[])[:2])).lower()
    return "hash:"+hashlib.sha1(base.encode()).hexdigest()[:16]

def fetch_json(url, headers=None, timeout=30):
    req=urllib.request.Request(url, headers=headers or {"User-Agent":"paper-reading-workflow/2.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def fetch_arxiv(query,max_results):
    params={"search_query":query,"start":0,"max_results":max_results,"sortBy":"submittedDate","sortOrder":"descending"}
    req=urllib.request.Request(ARXIV_API+"?"+urllib.parse.urlencode(params),headers={"User-Agent":"paper-reading-workflow/2.0"})
    with urllib.request.urlopen(req,timeout=30) as r: data=r.read()
    root=ET.fromstring(data); out=[]
    for e in root.findall("a:entry",ATOM):
        abs_url=norm(e.findtext("a:id",default="",namespaces=ATOM))
        aid=abs_url.rstrip("/").split("/")[-1]
        authors=[norm(a.findtext("a:name",default="",namespaces=ATOM)) for a in e.findall("a:author",ATOM)]
        pdf=""
        for link in e.findall("a:link",ATOM):
            if link.attrib.get("title")=="pdf": pdf=link.attrib.get("href","")
        out.append({
            "source":"arXiv","arxiv_id":aid,"title":norm(e.findtext("a:title",default="",namespaces=ATOM)),
            "abstract":norm(e.findtext("a:summary",default="",namespaces=ATOM)),"authors":authors,
            "date":norm(e.findtext("a:published",default="",namespaces=ATOM))[:10],
            "updated":norm(e.findtext("a:updated",default="",namespaces=ATOM))[:10],
            "url":abs_url,"pdf":pdf,"venue":"","doi":""
        })
    return out

def fetch_semantic_scholar(keyword,limit):
    params={"query":keyword,"limit":min(limit,100),"fields":"title,abstract,authors,year,publicationDate,url,externalIds,venue"}
    data=fetch_json(S2_API+"?"+urllib.parse.urlencode(params))
    out=[]
    for x in data.get("data",[]):
        ids=x.get("externalIds") or {}
        aid=ids.get("ArXiv","")
        doi=ids.get("DOI","")
        out.append({
            "source":"Semantic Scholar","title":norm(x.get("title","")),"abstract":norm(x.get("abstract","")),
            "authors":[a.get("name","") for a in x.get("authors",[])],"date":x.get("publicationDate") or (str(x.get("year"))+"-01-01" if x.get("year") else ""),
            "url":x.get("url",""),"pdf":("https://arxiv.org/pdf/"+aid if aid else ""),"venue":norm(x.get("venue","")),
            "arxiv_id":aid,"doi":doi
        })
    return out

def fetch_openreview(venues,lookback_days):
    # Broad recent note fetch; filter client-side by venue text. OpenReview API schemas vary,
    # so this is intentionally defensive.
    cutoff=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=lookback_days)).timestamp()*1000
    params={"limit":1000,"sort":"tcdate:desc"}
    data=fetch_json(OR_API+"?"+urllib.parse.urlencode(params))
    out=[]
    for n in data.get("notes",[]):
        c=n.get("content") or {}
        def val(k):
            v=c.get(k,"")
            if isinstance(v,dict): v=v.get("value","")
            return v
        venue=" ".join(map(str,[val("venue"),val("venueid"),val("conference")]))
        if venues and not any(v.lower() in venue.lower() for v in venues): continue
        tc=n.get("tcdate") or n.get("cdate") or 0
        if tc and tc < cutoff: continue
        title=norm(val("title"))
        abstract=norm(val("abstract"))
        authors=val("authors") or []
        if isinstance(authors,str): authors=[authors]
        forum=n.get("forum") or n.get("id")
        out.append({
            "source":"OpenReview","title":title,"abstract":abstract,"authors":authors,
            "date":dt.datetime.fromtimestamp(tc/1000,dt.timezone.utc).strftime("%Y-%m-%d") if tc else "",
            "url":"https://openreview.net/forum?id="+str(forum),"pdf":"","venue":norm(venue),
            "arxiv_id":"","doi":""
        })
    return out

def score(p,cfg):
    text=(p.get("title","")+" "+p.get("abstract","")).lower()
    title=p.get("title","").lower()
    if any(k.lower() in text for k in cfg.get("exclude_keywords",[])): return -999,[],[]
    s=0; reasons=[]; projects=[]
    for t in cfg.get("topics",[]):
        hits=[]
        for kw in t.get("keywords",[]):
            k=kw.lower()
            if k in text:
                s += t.get("weight",1) * (2 if k in title else 1)
                hits.append(kw)
        if hits:
            reasons.append(f"{t['name']}: "+", ".join(hits[:3]))
            if t.get("project"): projects.append(t["project"])
    for kw,b in cfg.get("bonus_keywords",{}).items():
        if kw.lower() in text: s+=b
    venue=p.get("venue","")
    for v,b in cfg.get("venue_bonus",{}).items():
        if v.lower() in venue.lower(): s+=b; reasons.append("venue: "+v); break
    d=parse_date(p.get("date",""))
    if d:
        age=(dt.datetime.now(dt.timezone.utc)-d).days
        if age<=2: s+=2
        elif age<=7: s+=1
    return s,reasons,sorted(set(projects))

def priority(score,cfg):
    th=cfg.get("priority_thresholds",{})
    if score>=th.get("must_read",16): return "🔴"
    if score>=th.get("high",10): return "🟠"
    if score>=th.get("maybe",6): return "🟡"
    return "👀"

def bibkey(p):
    author=(p.get("authors") or ["anon"])[0]
    last=re.sub(r"[^A-Za-z0-9]","",author.split()[-1]).lower() or "anon"
    year=(p.get("date") or "0000")[:4]
    return f"{last}{year}{first_content_word(p.get('title','paper'))}"

def bibentry(p,key):
    title=p.get("title","").replace("{","").replace("}","")
    authors=" and ".join(p.get("authors") or [])
    year=(p.get("date") or "0000")[:4]
    fields=[f"  title = {{{title}}}", f"  author = {{{authors}}}", f"  year = {{{year}}}"]
    if p.get("doi"): fields.append(f"  doi = {{{p['doi']}}}")
    if p.get("url"): fields.append(f"  url = {{{p['url']}}}")
    if p.get("venue"): fields.append(f"  journal = {{{p['venue']}}}")
    return "@article{"+key+",\n"+",\n".join(fields)+"\n}\n"

def read_existing_queue(path):
    # Preserve user-managed fields for papers already in the queue.
    state={}
    if not Path(path).exists(): return state
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"): continue
        cells=[c.strip() for c in line.strip("|").split("|")]
        if len(cells)<9 or cells[0] in {"Priority","---"}: continue
        m=re.search(r"\((https?://[^)]+)\)",cells[3])
        if not m: continue
        state[m.group(1)]={"status":cells[1],"project":cells[6],"notes":cells[8]}
    return state

def render_queue(path,papers,cfg):
    old=read_existing_queue(path)
    lines=[
      "# Paper Reading Queue","",
      f"_Auto-refreshed {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · latest {cfg.get('lookback_days',14)} days_","",
      "## This Week — Must Read","",
      f"Top {cfg.get('must_read_n',5)} highest-priority papers are surfaced here; the full ranked queue follows.","",
      "| Priority | Status | Score | Paper | Date | Source | Project | BibTeX | Notes |",
      "|---|---|---:|---|---|---|---|---|---|"
    ]
    for p in papers[:cfg.get("must_read_n",5)]:
        lines.append(row(p,old))
    lines += ["","## Full Ranked Queue","",
      "| Priority | Status | Score | Paper | Date | Source | Project | BibTeX | Notes |",
      "|---|---|---:|---|---|---|---|---|---|"]
    for p in papers: lines.append(row(p,old))
    lines += ["","## Workflow","",
      "- `TODO` → not started","- `READING` → currently reading","- `DONE` → note finished","- `SKIP` → intentionally ignored","",
      "The refresh script preserves `Status`, `Project`, and `Notes` for papers already present in the queue.",""]
    Path(path).write_text("\n".join(lines),encoding="utf-8")

def row(p,old):
    st=old.get(p.get("url",""),{})
    status=st.get("status","TODO")
    project=st.get("project") or ", ".join(p.get("projects",[])[:2]) or "—"
    notes=st.get("notes","")
    paper=f"[{p['title'].replace('|','/').strip()}]({p.get('url','')})"
    return f"| {p['priority']} | {status} | {p['score']} | {paper} | {p.get('date','')} | {p.get('source','')} | {project} | `{p['bibkey']}` | {notes} |"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--config",default="config/paper_discovery.json")
    ap.add_argument("--queue",default="reading_queue.md")
    ap.add_argument("--seen",default="data/seen_papers.json")
    ap.add_argument("--include-seen",action="store_true")
    args=ap.parse_args()
    cfg=jload(args.config)
    cutoff=dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=cfg.get("lookback_days",14))
    papers=[]
    # arXiv
    if cfg["sources"]["arxiv"].get("enabled",True):
        cats=" OR ".join("cat:"+c for c in cfg.get("arxiv_categories",[]))
        papers+=fetch_arxiv(cats,cfg["sources"]["arxiv"].get("max_results",80))
    # Semantic Scholar: one query per topic name + strongest keyword to control traffic
    if cfg["sources"]["semantic_scholar"].get("enabled",True):
        limit=cfg["sources"]["semantic_scholar"].get("max_results",40)
        for t in cfg.get("topics",[]):
            q=t.get("keywords",[t["name"]])[0]
            try: papers+=fetch_semantic_scholar(q,limit)
            except Exception as e: print("WARNING Semantic Scholar",q,e)
            time.sleep(0.7)
    # OpenReview
    if cfg["sources"]["openreview"].get("enabled",True):
        try: papers+=fetch_openreview(cfg["sources"]["openreview"].get("venues",[]),cfg.get("lookback_days",14))
        except Exception as e: print("WARNING OpenReview",e)

    # dedupe
    uniq={}
    for p in papers:
        if not p.get("title"): continue
        d=parse_date(p.get("date",""))
        if d and d<cutoff: continue
        k=stable_id(p)
        if k not in uniq or len(p.get("abstract",""))>len(uniq[k].get("abstract","")): uniq[k]=p

    seen_path=Path(args.seen)
    seen=set()
    if seen_path.exists():
        try: seen=set(jload(seen_path).get("seen_ids",[]))
        except: pass

    ranked=[]
    for k,p in uniq.items():
        s,reasons,projects=score(p,cfg)
        if s<cfg.get("min_score",4): continue
        if (not args.include_seen) and k in seen: continue
        p["score"]=s; p["reasons"]=reasons; p["projects"]=projects
        p["priority"]=priority(s,cfg); p["bibkey"]=bibkey(p); p["_sid"]=k
        ranked.append(p)
    ranked.sort(key=lambda p:(p["score"],p.get("date","")),reverse=True)
    selected=ranked[:cfg.get("top_n",20)]

    render_queue(args.queue,selected,cfg)

    if cfg.get("bibtex",{}).get("enabled",True):
        out=Path(cfg["bibtex"].get("output_file","bib/discovered.bib"))
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text("\n".join(bibentry(p,p["bibkey"]) for p in selected),encoding="utf-8")

    seen.update(p["_sid"] for p in selected)
    seen_path.parent.mkdir(parents=True,exist_ok=True)
    seen_path.write_text(json.dumps({"seen_ids":sorted(seen)},indent=2),encoding="utf-8")
    print(f"Fetched {len(papers)} records, deduped to {len(uniq)}, selected {len(selected)}.")
    for p in selected: print(p["priority"],p["score"],p["date"],p["title"],"=>",p["bibkey"])

if __name__=="__main__":
    main()

#!/usr/bin/env python3
"""
v7 — proceedings-first literature tracker.

Conference membership comes ONLY from:
- official NeurIPS proceedings
- official PMLR conference volumes
- ICLR OpenReview Conference venues
- official SaTML accepted-paper pages

Semantic Scholar is used only for citation enrichment and top-journal discovery.
It is NOT used to decide conference membership.
"""
from __future__ import annotations
import html, json, os, re, time
import urllib.parse, urllib.request, urllib.error
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

CFG="config/paper_discovery.json"
S2_SEARCH="https://api.semanticscholar.org/graph/v1/paper/search"
OR_NOTES="https://api2.openreview.net/notes"

def load(): return json.loads(Path(CFG).read_text(encoding="utf-8"))
def clean(s): return re.sub(r"\s+"," ",html.unescape(s or "")).strip()

def http_text(url, timeout=45):
    req=urllib.request.Request(url,headers={"User-Agent":"paper-reading-workflow/7.0"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return r.read().decode("utf-8","replace")

def http_json(url, headers=None, timeout=45):
    h={"User-Agent":"paper-reading-workflow/7.0"}
    if headers: h.update(headers)
    req=urllib.request.Request(url,headers=h)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read())

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self._href=None; self._text=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self._href=dict(attrs).get("href"); self._text=[]
    def handle_data(self,data):
        if self._href is not None: self._text.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self._href is not None:
            self.links.append((self._href,clean(" ".join(self._text))))
            self._href=None; self._text=[]

class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.meta={}; self.title=""
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=="meta":
            key=d.get("name") or d.get("property")
            val=d.get("content")
            if key and val:
                self.meta.setdefault(key,[]).append(clean(val))
    def handle_data(self,data):
        pass

def parse_meta_page(url):
    txt=http_text(url)
    p=MetaParser(); p.feed(txt)
    m=p.meta
    def one(*keys):
        for k in keys:
            if m.get(k): return m[k][0]
        return ""
    return {
      "title":one("citation_title","dc.Title","og:title"),
      "authors":m.get("citation_author",[]),
      "abstract":one("description","citation_abstract","og:description"),
      "pdf":one("citation_pdf_url"),
      "doi":one("citation_doi"),
      "url":url
    }

def pmlr_volume(url, venue, year):
    txt=http_text(url); lp=LinkParser(); lp.feed(txt)
    links=[]
    for href,text in lp.links:
        full=urljoin(url,href)
        # PMLR paper landing pages are direct children like smith25a.html.
        if re.search(r"/v\d+/[^/]+\.html$", full) and not full.endswith("index.html"):
            links.append(full)
    out=[]; seen=set()
    for u in links:
        if u in seen: continue
        seen.add(u)
        try:
            p=parse_meta_page(u)
            if not p["title"]: continue
            p.update(venue=venue,year=int(year),kind="conference",source="PMLR")
            out.append(p)
        except Exception as e:
            print("WARN PMLR paper",u,type(e).__name__)
        time.sleep(0.03)
    return out

def neurips_volume(url, venue, year):
    txt=http_text(url); lp=LinkParser(); lp.feed(txt)
    links=[]
    for href,text in lp.links:
        full=urljoin(url,href)
        if ("Abstract-Conference.html" in full or "/paper/" in full and full.endswith(".html")):
            links.append(full)
    out=[]; seen=set()
    for u in links:
        if u in seen: continue
        seen.add(u)
        try:
            p=parse_meta_page(u)
            if not p["title"]: continue
            p.update(venue=venue,year=int(year),kind="conference",source="NeurIPS Proceedings")
            out.append(p)
        except Exception as e:
            print("WARN NeurIPS paper",u,type(e).__name__)
        time.sleep(0.03)
    return out

def orval(c,k):
    v=(c or {}).get(k,"")
    if isinstance(v,dict): return v.get("value","")
    return v

def iclr_venue(venue_id, venue, year):
    # OpenReview stores accepted conference papers with content.venueid.
    params={"content.venueid":venue_id,"limit":1000}
    data=http_json(OR_NOTES+"?"+urllib.parse.urlencode(params))
    out=[]
    for n in data.get("notes",[]):
        c=n.get("content") or {}
        title=clean(orval(c,"title"))
        if not title: continue
        authors=orval(c,"authors") or []
        if isinstance(authors,str): authors=[authors]
        abstract=clean(orval(c,"abstract"))
        forum=n.get("forum") or n.get("id")
        out.append({
          "title":title,"authors":authors,"abstract":abstract,
          "pdf":"https://openreview.net/pdf?id="+str(forum),
          "url":"https://openreview.net/forum?id="+str(forum),
          "doi":"","venue":venue,"year":int(year),"kind":"conference","source":"OpenReview"
        })
    return out

class SaTMLParser(HTMLParser):
    def __init__(self,base):
        super().__init__(); self.base=base; self.in_heading=False; self.heading_tag=None
        self.buf=[]; self.items=[]; self.current=None; self.in_p=False
    def handle_starttag(self,tag,attrs):
        if tag in ("h3","h4","h5"):
            self.in_heading=True; self.heading_tag=tag; self.buf=[]
        elif tag=="p":
            self.in_p=True; self.buf=[]
        elif tag=="a" and self.current is not None:
            href=dict(attrs).get("href","")
            text=dict(attrs).get("title","")
            if href:
                full=urljoin(self.base,href)
                if ".pdf" in href.lower(): self.current["pdf"]=full
                elif "arxiv.org" in href: self.current.setdefault("url",full)
    def handle_data(self,data):
        if self.in_heading or self.in_p: self.buf.append(data)
    def handle_endtag(self,tag):
        if self.in_heading and tag==self.heading_tag:
            txt=clean(" ".join(self.buf))
            # Conference section headings are short generic labels; paper headings are substantive.
            generic={"research papers","position papers","systematization of knowledge papers","sok papers","accepted papers"}
            if len(txt)>12 and txt.lower() not in generic:
                self.current={"title":txt,"authors":[],"abstract":"","pdf":"","url":""}
                self.items.append(self.current)
            self.in_heading=False; self.buf=[]
        elif self.in_p and tag=="p":
            txt=clean(" ".join(self.buf))
            if self.current and txt:
                if len(txt)>180 and not self.current["abstract"]:
                    self.current["abstract"]=txt
                elif not self.current["authors"] and len(txt)<300:
                    # Best-effort author line.
                    self.current["authors"]=[x.strip() for x in re.split(r",|;|\band\b",txt) if x.strip()]
            self.in_p=False; self.buf=[]

def satml_page(url,venue,year):
    txt=http_text(url)
    p=SaTMLParser(url); p.feed(txt)
    out=[]
    for x in p.items:
        x["url"]=x.get("url") or url+"#"+re.sub(r"[^a-z0-9]+","-",x["title"].lower()).strip("-")
        x.update(doi="",venue=venue,year=int(year),kind="conference",source="SaTML Accepted Papers")
        out.append(x)
    return out

def relevance(p,cfg):
    text=(p.get("title","")+" "+p.get("abstract","")).lower()
    title=p.get("title","").lower()
    score=0; why=[]; projects=[]
    for t in cfg["topics"]:
        hits=[k for k in t["core"] if k.lower() in text]
        if not hits: continue
        best=max(t["weight"]*(2 if k.lower() in title else 1) for k in hits)
        supp=[k for k in t.get("support",[]) if k.lower() in text]
        score+=best+min(4,len(supp))
        why.append(t["name"]+": "+", ".join(hits[:2]))
        projects.append(t["project"])
    for k,b in cfg.get("theory_bonus",{}).items():
        if k.lower() in text: score+=b
    return score,why,sorted(set(projects))

def s2_enrich(p):
    # Citation enrichment only. Never used for conference membership.
    key=os.environ.get("S2_API_KEY","").strip()
    headers={"User-Agent":"paper-reading-workflow/7.0"}
    if key: headers["x-api-key"]=key
    params={"query":p["title"],"limit":3,"fields":"title,citationCount,influentialCitationCount,externalIds,url"}
    try:
        data=http_json(S2_SEARCH+"?"+urllib.parse.urlencode(params),headers=headers)
    except Exception:
        return p
    target=set(re.findall(r"\w+",p["title"].lower()))
    best=None; bs=0
    for x in data.get("data",[]):
        s=len(target & set(re.findall(r"\w+",(x.get("title") or "").lower())))
        if s>bs: bs=s; best=x
    if best and bs>=max(4,int(len(target)*0.55)):
        p["citations"]=best.get("citationCount") or 0
        p["influential"]=best.get("influentialCitationCount") or 0
        ext=best.get("externalIds") or {}
        if not p.get("doi"): p["doi"]=ext.get("DOI") or ""
    return p

def priority(total,cfg):
    t=cfg["priority_thresholds"]
    if total>=t["red"]: return "🔴"
    if total>=t["orange"]: return "🟠"
    if total>=t["yellow"]: return "🟡"
    return "👀"

def bibkey(p):
    last="anon"
    if p.get("authors"):
        last=re.sub(r"[^A-Za-z0-9]","",p["authors"][0].split()[-1]).lower() or "anon"
    stop={"a","an","the","of","on","for","to","in","with","and","via","from","by","using"}
    words=[w.lower() for w in re.findall(r"[A-Za-z0-9]+",p["title"]) if w.lower() not in stop]
    return f"{last}{p['year']}{words[0] if words else 'paper'}"

def journal_search(journal,cfg):
    # Journals are the one place S2 is appropriate: venue filter + citation hard gate.
    key=os.environ.get("S2_API_KEY","").strip()
    headers={"User-Agent":"paper-reading-workflow/7.0"}
    if key: headers["x-api-key"]=key
    queries=["differential privacy","posterior sampling","synthetic data","missing data imputation","algorithmic fairness"]
    seen={}
    for q in queries:
        params={
          "query":q,"limit":100,
          "fields":"title,abstract,authors,year,publicationDate,venue,citationCount,influentialCitationCount,externalIds,url,openAccessPdf"
        }
        try:
            data=http_json(S2_SEARCH+"?"+urllib.parse.urlencode(params),headers=headers)
        except Exception as e:
            print("WARN journal",journal,q,type(e).__name__); continue
        for x in data.get("data",[]):
            if (x.get("venue") or "").lower()!=journal.lower(): continue
            if (x.get("citationCount") or 0)<cfg["journal_min_citations"]: continue
            y=x.get("year") or 0
            lo,hi=map(int,cfg["journal_year_range"].split("-"))
            if not (lo<=y<=hi): continue
            ext=x.get("externalIds") or {}
            doi=ext.get("DOI") or ""
            url=("https://doi.org/"+doi) if doi else (x.get("url") or "")
            p={
              "title":x.get("title") or "","abstract":x.get("abstract") or "",
              "authors":[a.get("name","") for a in (x.get("authors") or [])],
              "year":y,"venue":journal,"kind":"journal","source":"Semantic Scholar",
              "citations":x.get("citationCount") or 0,
              "influential":x.get("influentialCitationCount") or 0,
              "doi":doi,"url":url,
              "pdf":((x.get("openAccessPdf") or {}).get("url") or "")
            }
            rel,why,projects=relevance(p,cfg)
            if rel<cfg["min_relevance"]: continue
            p.update(relevance=rel,why=why,projects=projects)
            p["total"]=rel+10+min(8,p["citations"]//10)
            p["priority"]=priority(p["total"],cfg); p["bibkey"]=bibkey(p)
            seen[x.get("paperId") or doi or p["title"]]=p
        time.sleep(0.8)
    arr=list(seen.values())
    arr.sort(key=lambda p:(p["relevance"],p["citations"]),reverse=True)
    return arr[:cfg["journal_per_venue"]]

def bibtex(p):
    typ="inproceedings" if p["kind"]=="conference" else "article"
    fs=[
      f"  title = {{{p['title'].replace('{','').replace('}','')}}}",
      f"  author = {{{' and '.join(p.get('authors',[]))}}}",
      f"  year = {{{p['year']}}}",
      (f"  booktitle = {{{p['venue']}}}" if p["kind"]=="conference" else f"  journal = {{{p['venue']}}}"),
      f"  url = {{{p['url']}}}"
    ]
    if p.get("doi"): fs.append(f"  doi = {{{p['doi'].replace('https://doi.org/','')}}}")
    return "@"+typ+"{"+p["bibkey"]+",\n"+",\n".join(fs)+"\n}\n"

def row(p):
    why="; ".join(p.get("why",[]))
    return (
      f"| {p['priority']} | TODO | {p['relevance']} | {p.get('citations',0)} | "
      f"[{p['title'].replace('|','/')}]({p['url']}) | {p['venue']} | {p['year']} | "
      f"{', '.join(p.get('projects',[])) or '—'} | `{p['bibkey']}` | {why} | |"
    )

def main():
    cfg=load()
    all_conf=[]; notes=[]
    for conf in cfg["conferences"]:
        venue=conf["name"]
        bucket=[]
        for year,locator in conf["years"].items():
            try:
                if conf["type"]=="pmlr":
                    raw=pmlr_volume(locator,venue,year)
                elif conf["type"]=="neurips":
                    raw=neurips_volume(locator,venue,year)
                elif conf["type"]=="openreview":
                    raw=iclr_venue(locator,venue,year)
                elif conf["type"]=="satml":
                    raw=satml_page(locator,venue,year)
                else:
                    raw=[]
                print(venue,year,"official papers:",len(raw))
                for p in raw:
                    rel,why,projects=relevance(p,cfg)
                    if rel<cfg["min_relevance"]: continue
                    p.update(relevance=rel,why=why,projects=projects,citations=0,influential=0)
                    p=s2_enrich(p)
                    # Proceedings membership itself supplies the venue-quality gate.
                    p["total"]=rel+10+min(5,p.get("citations",0)//10)
                    p["priority"]=priority(p["total"],cfg); p["bibkey"]=bibkey(p)
                    bucket.append(p)
                    time.sleep(0.15)
            except Exception as e:
                notes.append(f"{venue} {year}: {type(e).__name__}: {e}")
        # per-venue ranking / quota prevents domination
        seen={}
        for p in bucket:
            key=(p.get("doi") or p["url"] or p["title"]).lower()
            if key not in seen or p["total"]>seen[key]["total"]: seen[key]=p
        arr=list(seen.values())
        arr.sort(key=lambda p:(p["relevance"],p.get("citations",0)),reverse=True)
        all_conf.extend(arr[:cfg["top_per_venue"]])
        print(venue,"selected:",min(len(arr),cfg["top_per_venue"]))

    journals=[]
    for j in cfg["top_journals"]:
        arr=journal_search(j,cfg)
        journals.extend(arr)
        print(j,"selected:",len(arr))

    lines=["# Paper Reading Queue","",
      "_Conference papers come directly from official proceedings / accepted-paper lists. No arXiv feed and no metadata-based venue guessing._","",
      "## Conference papers","",
      "| Priority | Status | Relevance | Citations | Paper | Venue | Year | Project | BibTeX | Why | Notes |",
      "|---|---|---:|---:|---|---|---:|---|---|---|---|"]
    for conf in cfg["conferences"]:
        arr=[p for p in all_conf if p["venue"]==conf["name"]]
        if not arr: continue
        lines.append(f"| **{conf['name']}** | | | | | | | | | | |")
        lines.extend(row(p) for p in arr)
    lines += ["","## Top journal papers — citation ≥ "+str(cfg["journal_min_citations"]),"",
      "| Priority | Status | Relevance | Citations | Paper | Venue | Year | Project | BibTeX | Why | Notes |",
      "|---|---|---:|---:|---|---|---:|---|---|---|---|"]
    for j in cfg["top_journals"]:
        arr=[p for p in journals if p["venue"]==j]
        if not arr: continue
        lines.append(f"| **{j}** | | | | | | | | | | |")
        lines.extend(row(p) for p in arr)
    if notes:
        lines += ["","## Fetch notes",""]+[f"- {n}" for n in notes]

    Path("reading_queue.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    Path("bib").mkdir(exist_ok=True)
    allp=all_conf+journals
    Path("bib/discovered.bib").write_text("\n".join(bibtex(p) for p in allp),encoding="utf-8")
    print("TOTAL",len(allp))

if __name__=="__main__":
    main()

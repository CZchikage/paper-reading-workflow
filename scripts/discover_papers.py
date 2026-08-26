#!/usr/bin/env python3
"""
v8 — fast proceedings-first tracker.

Speed strategy:
1. Parse official proceedings index.
2. Use the paper TITLE from that index as a broad prefilter.
3. Fetch landing pages only for title-prefiltered candidates, concurrently.
4. Apply full title+abstract relevance scoring.
5. Enrich citations only for final relevant candidates.

This avoids opening thousands of irrelevant paper pages.
"""
from __future__ import annotations
import html, json, os, re, time
import urllib.parse, urllib.request, urllib.error
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

CFG="config/paper_discovery.json"
S2_SEARCH="https://api.semanticscholar.org/graph/v1/paper/search"
OR_NOTES="https://api2.openreview.net/notes"

def load(): return json.loads(Path(CFG).read_text(encoding="utf-8"))
def clean(s): return re.sub(r"\s+"," ",html.unescape(s or "")).strip()

def http_text(url, timeout=35):
    req=urllib.request.Request(url,headers={"User-Agent":"paper-reading-workflow/8.0"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return r.read().decode("utf-8","replace")

def http_json(url, headers=None, timeout=35):
    h={"User-Agent":"paper-reading-workflow/8.0"}
    if headers: h.update(headers)
    req=urllib.request.Request(url,headers=h)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read())

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.href=None; self.buf=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.href=dict(attrs).get("href"); self.buf=[]
    def handle_data(self,data):
        if self.href is not None: self.buf.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.href is not None:
            self.links.append((self.href,clean(" ".join(self.buf))))
            self.href=None; self.buf=[]

class MetaParser(HTMLParser):
    def __init__(self): super().__init__(); self.meta={}
    def handle_starttag(self,tag,attrs):
        if tag!="meta": return
        d=dict(attrs); key=d.get("name") or d.get("property"); val=d.get("content")
        if key and val: self.meta.setdefault(key,[]).append(clean(val))

def parse_meta_page(url):
    p=MetaParser(); p.feed(http_text(url))
    m=p.meta
    def one(*ks):
        for k in ks:
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

def title_maybe_relevant(title,cfg):
    t=(title or "").lower()
    return any(k.lower() in t for k in cfg["fast_prefilter_keywords"])

def fetch_candidates_concurrently(items, venue, year, source, cfg):
    # items: [(url, title_from_index)]
    candidates=[(u,t) for u,t in items if title_maybe_relevant(t,cfg)]
    print(f"{venue} {year}: index={len(items)}, title-prefilter={len(candidates)}")
    out=[]
    with ThreadPoolExecutor(max_workers=cfg.get("max_workers",16)) as ex:
        futs={ex.submit(parse_meta_page,u):(u,t) for u,t in candidates}
        for fut in as_completed(futs):
            u,t=futs[fut]
            try:
                p=fut.result()
                if not p["title"]: p["title"]=t
                if not p["title"]: continue
                p.update(venue=venue,year=int(year),kind="conference",source=source)
                out.append(p)
            except Exception as e:
                print("WARN detail",venue,year,u,type(e).__name__)
    return out

def pmlr_volume(url, venue, year, cfg):
    lp=LinkParser(); lp.feed(http_text(url))
    seen={}; items=[]
    for href,text in lp.links:
        full=urljoin(url,href)
        if re.search(r"/v\d+/[^/]+\.html$",full) and not full.endswith("index.html"):
            if full not in seen:
                seen[full]=1; items.append((full,text))
    return fetch_candidates_concurrently(items,venue,year,"PMLR",cfg)

def neurips_volume(url, venue, year, cfg):
    lp=LinkParser(); lp.feed(http_text(url))
    seen={}; items=[]
    for href,text in lp.links:
        full=urljoin(url,href)
        if "Abstract-Conference.html" in full:
            if full not in seen:
                seen[full]=1; items.append((full,text))
    return fetch_candidates_concurrently(items,venue,year,"NeurIPS Proceedings",cfg)

def orval(c,k):
    v=(c or {}).get(k,"")
    return v.get("value","") if isinstance(v,dict) else v

def iclr_venue(venue_id,venue,year,cfg):
    """
    Crawl the public ICLR Conference group page instead of calling the OpenReview API.
    This avoids 403 errors from anonymous GitHub Actions requests.
    """
    group_url="https://openreview.net/group?id="+urllib.parse.quote(venue_id, safe="")
    txt=http_text(group_url)

    # OpenReview public pages embed forum links in rendered/serialized HTML.
    ids=[]
    for pat in [
        r'href=["\']https://openreview\.net/forum\?id=([^"\'&]+)',
        r'href=["\']/forum\?id=([^"\'&]+)',
        r'forum\?id=([A-Za-z0-9_-]+)'
    ]:
        ids.extend(re.findall(pat,txt))
    ids=list(dict.fromkeys(ids))

    # If the group page is client-rendered and forum ids are sparse, also inspect
    # visible links collected by the generic parser.
    lp=LinkParser(); lp.feed(txt)
    for href,label in lp.links:
        m=re.search(r'(?:https://openreview\.net)?/forum\?id=([^&]+)',href or "")
        if m: ids.append(m.group(1))
    ids=list(dict.fromkeys(ids))

    print(f"{venue} {year}: public group forum-links={len(ids)}")

    def parse_forum(fid):
        url="https://openreview.net/forum?id="+fid
        try:
            page=http_text(url)
        except Exception:
            return None

        # Public forum HTML generally contains metadata / JSON strings for title,
        # authors and abstract. Parse defensively.
        title=""
        abstract=""
        authors=[]

        # HTML meta first.
        mp=MetaParser(); mp.feed(page)
        m=mp.meta
        for k in ("citation_title","og:title"):
            if m.get(k):
                title=clean(m[k][0]); break
        authors=m.get("citation_author",[]) or authors
        for k in ("description","citation_abstract","og:description"):
            if m.get(k):
                abstract=clean(m[k][0]); break

        # Fallback to embedded JSON-like content.
        if not title:
            mm=re.search(r'"title"\s*:\s*(?:\{"value":)?\s*"((?:\\.|[^"])*)"',page)
            if mm:
                try: title=clean(json.loads('"'+mm.group(1)+'"'))
                except: title=clean(mm.group(1))
        if not abstract:
            mm=re.search(r'"abstract"\s*:\s*(?:\{"value":)?\s*"((?:\\.|[^"])*)"',page)
            if mm:
                try: abstract=clean(json.loads('"'+mm.group(1)+'"'))
                except: abstract=clean(mm.group(1))

        if not title or not title_maybe_relevant(title,cfg):
            return None

        return {
          "title":title,
          "authors":authors,
          "abstract":abstract,
          "pdf":"https://openreview.net/pdf?id="+fid,
          "url":url,
          "doi":"",
          "venue":venue,
          "year":int(year),
          "kind":"conference",
          "source":"OpenReview public HTML"
        }

    out=[]
    with ThreadPoolExecutor(max_workers=min(12,cfg.get("max_workers",16))) as ex:
        futs={ex.submit(parse_forum,fid):fid for fid in ids}
        for fut in as_completed(futs):
            try:
                p=fut.result()
                if p: out.append(p)
            except Exception:
                pass
    print(f"{venue} {year}: title-prefilter={len(out)}")
    return out

class SaTMLParser(HTMLParser):
    def __init__(self,base):
        super().__init__(); self.base=base; self.heading=False; self.htag=None; self.buf=[]
        self.items=[]; self.current=None; self.in_p=False
    def handle_starttag(self,tag,attrs):
        if tag in ("h3","h4","h5"):
            self.heading=True; self.htag=tag; self.buf=[]
        elif tag=="p": self.in_p=True; self.buf=[]
        elif tag=="a" and self.current:
            href=dict(attrs).get("href","")
            if href:
                full=urljoin(self.base,href)
                if ".pdf" in href.lower(): self.current["pdf"]=full
    def handle_data(self,d):
        if self.heading or self.in_p: self.buf.append(d)
    def handle_endtag(self,tag):
        if self.heading and tag==self.htag:
            txt=clean(" ".join(self.buf))
            generic={"research papers","position papers","systematization of knowledge papers","sok papers","accepted papers"}
            if len(txt)>12 and txt.lower() not in generic:
                self.current={"title":txt,"authors":[],"abstract":"","pdf":"","url":""}
                self.items.append(self.current)
            self.heading=False; self.buf=[]
        elif self.in_p and tag=="p":
            txt=clean(" ".join(self.buf))
            if self.current and txt:
                if len(txt)>180 and not self.current["abstract"]: self.current["abstract"]=txt
                elif not self.current["authors"] and len(txt)<300:
                    self.current["authors"]=[x.strip() for x in re.split(r",|;|\band\b",txt) if x.strip()]
            self.in_p=False; self.buf=[]

def satml_page(url,venue,year,cfg):
    p=SaTMLParser(url); p.feed(http_text(url))
    out=[]
    for x in p.items:
        if not title_maybe_relevant(x["title"],cfg): continue
        x["url"]=url+"#"+re.sub(r"[^a-z0-9]+","-",x["title"].lower()).strip("-")
        x.update(doi="",venue=venue,year=int(year),kind="conference",source="SaTML")
        out.append(x)
    print(f"{venue} {year}: page papers={len(p.items)}, title-prefilter={len(out)}")
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
    key=os.environ.get("S2_API_KEY","").strip()
    headers={"User-Agent":"paper-reading-workflow/8.0"}
    if key: headers["x-api-key"]=key
    params={"query":p["title"],"limit":3,"fields":"title,citationCount,influentialCitationCount,externalIds"}
    try: data=http_json(S2_SEARCH+"?"+urllib.parse.urlencode(params),headers=headers)
    except Exception: return p
    targ=set(re.findall(r"\w+",p["title"].lower()))
    best=None; bs=0
    for x in data.get("data",[]):
        s=len(targ & set(re.findall(r"\w+",(x.get("title") or "").lower())))
        if s>bs: bs=s; best=x
    if best and bs>=max(4,int(len(targ)*0.55)):
        p["citations"]=best.get("citationCount") or 0
        p["influential"]=best.get("influentialCitationCount") or 0
        if not p.get("doi"):
            p["doi"]=(best.get("externalIds") or {}).get("DOI") or ""
    return p

def priority(total,cfg):
    t=cfg["priority_thresholds"]
    if total>=t["red"]: return "🔴"
    if total>=t["orange"]: return "🟠"
    if total>=t["yellow"]: return "🟡"
    return "👀"

def bibkey(p):
    last="anon"
    if p.get("authors"): last=re.sub(r"[^A-Za-z0-9]","",p["authors"][0].split()[-1]).lower() or "anon"
    stop={"a","an","the","of","on","for","to","in","with","and","via","from","by","using"}
    ws=[w.lower() for w in re.findall(r"[A-Za-z0-9]+",p["title"]) if w.lower() not in stop]
    return f"{last}{p['year']}{ws[0] if ws else 'paper'}"

def bibtex(p):
    fs=[f"  title = {{{p['title'].replace('{','').replace('}','')}}}",
        f"  author = {{{' and '.join(p.get('authors',[]))}}}",
        f"  year = {{{p['year']}}}",
        f"  booktitle = {{{p['venue']}}}",
        f"  url = {{{p['url']}}}"]
    if p.get("doi"): fs.append(f"  doi = {{{p['doi'].replace('https://doi.org/','')}}}")
    return "@inproceedings{"+p["bibkey"]+",\n"+",\n".join(fs)+"\n}\n"

def row(p):
    return (f"| {p['priority']} | TODO | {p['relevance']} | {p.get('citations',0)} | "
            f"[{p['title'].replace('|','/')}]({p['url']}) | {p['venue']} | {p['year']} | "
            f"{', '.join(p.get('projects',[])) or '—'} | `{p['bibkey']}` | {'; '.join(p.get('why',[]))} | |")

def main():
    cfg=load(); all_conf=[]; notes=[]
    for conf in cfg["conferences"]:
        venue=conf["name"]; bucket=[]
        for year,locator in conf["years"].items():
            try:
                if conf["type"]=="pmlr": raw=pmlr_volume(locator,venue,year,cfg)
                elif conf["type"]=="neurips": raw=neurips_volume(locator,venue,year,cfg)
                elif conf["type"]=="openreview": raw=iclr_venue(locator,venue,year,cfg)
                elif conf["type"]=="satml": raw=satml_page(locator,venue,year,cfg)
                else: raw=[]
                relcand=[]
                for p in raw:
                    rel,why,projects=relevance(p,cfg)
                    if rel<cfg["min_relevance"]: continue
                    p.update(relevance=rel,why=why,projects=projects,citations=0,influential=0)
                    relcand.append(p)
                print(f"{venue} {year}: full-relevance={len(relcand)}")
                # enrich only relevant candidates, concurrently
                with ThreadPoolExecutor(max_workers=8) as ex:
                    enriched=list(ex.map(s2_enrich,relcand))
                for p in enriched:
                    p["total"]=p["relevance"]+10+min(5,p.get("citations",0)//10)
                    p["priority"]=priority(p["total"],cfg); p["bibkey"]=bibkey(p)
                    bucket.append(p)
            except Exception as e:
                notes.append(f"{venue} {year}: {type(e).__name__}: {e}")
        seen={}
        for p in bucket:
            k=(p.get("doi") or p["url"] or p["title"]).lower()
            if k not in seen or p["total"]>seen[k]["total"]: seen[k]=p
        arr=sorted(seen.values(),key=lambda p:(p["relevance"],p.get("citations",0)),reverse=True)
        all_conf.extend(arr[:cfg["top_per_venue"]])
        print(f"{venue}: selected={min(len(arr),cfg['top_per_venue'])}")

    lines=["# Paper Reading Queue","",
      "_Conference papers come directly from official proceedings / accepted-paper lists. Fast title-prefilter enabled._","",
      "## Conference papers","",
      "| Priority | Status | Relevance | Citations | Paper | Venue | Year | Project | BibTeX | Why | Notes |",
      "|---|---|---:|---:|---|---|---:|---|---|---|---|"]
    for conf in cfg["conferences"]:
        arr=[p for p in all_conf if p["venue"]==conf["name"]]
        if not arr: continue
        lines.append(f"| **{conf['name']}** | | | | | | | | | | |")
        lines.extend(row(p) for p in arr)
    if notes:
        lines += ["","## Fetch notes",""]+[f"- {n}" for n in notes]
    Path("reading_queue.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    Path("bib").mkdir(exist_ok=True)
    Path("bib/discovered.bib").write_text("\n".join(bibtex(p) for p in all_conf),encoding="utf-8")
    print("TOTAL",len(all_conf))

if __name__=="__main__":
    main()

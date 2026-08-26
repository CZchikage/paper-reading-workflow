#!/usr/bin/env python3
from __future__ import annotations
import html, json, re, urllib.parse, urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor

CFG="config/paper_discovery.json"
OA="https://api.openalex.org"

def cfg(): return json.loads(Path(CFG).read_text(encoding="utf-8"))

REGISTRY="data/paper_registry.json"

STATUS_TO_READ="🔴 To read"
STATUS_REVIEW_READY="🟡 Review ready"
STATUS_DONE="🟢 Done"

def stable_id(p):
    doi=(p.get("doi") or "").lower().replace("https://doi.org/","").strip()
    if doi:
        return "doi:"+doi
    url=(p.get("url") or "").strip().lower()
    if url:
        return "url:"+url
    title=re.sub(r"\W+"," ",(p.get("title") or "").lower()).strip()
    first=(p.get("authors") or [""])[0].lower().strip()
    year=str(p.get("year") or "")
    import hashlib
    return "hash:"+hashlib.sha1(f"{title}|{first}|{year}".encode()).hexdigest()[:20]

def load_registry():
    p=Path(REGISTRY)
    if not p.exists():
        return {}
    try:
        data=json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data,dict) and "papers" in data:
            return data["papers"]
        return data if isinstance(data,dict) else {}
    except Exception:
        return {}

def save_registry(reg):
    Path(REGISTRY).parent.mkdir(parents=True,exist_ok=True)
    payload={"version":1,"papers":reg}
    Path(REGISTRY).write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")

def parse_existing_queue(path="reading_queue.md"):
    """
    Preserve human-edited Status and Notes from the Markdown queue.
    Key by the paper URL, because it is directly recoverable from the table.
    """
    state={}
    p=Path(path)
    if not p.exists():
        return state
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"): continue
        cells=[x.strip() for x in line.strip("|").split("|")]
        if len(cells)<11: continue
        m=re.search(r"\((https?://[^)]+)\)",cells[4])
        if not m: continue
        status=cells[1]
        if status not in {STATUS_TO_READ,STATUS_REVIEW_READY,STATUS_DONE}:
            continue
        state[m.group(1).lower()]={"status":status,"notes":cells[-1]}
    return state

def sync_registry_from_queue(reg, queue_state):
    """Human edits in reading_queue.md win over the registry."""
    for pid,rec in reg.items():
        url=(rec.get("url") or "").lower()
        if url and url in queue_state:
            rec["status"]=queue_state[url]["status"]
            rec["notes"]=queue_state[url].get("notes","")
    return reg

def paper_from_registry(pid,rec):
    p=dict(rec)
    p["_pid"]=pid
    return p
def clean(s): return re.sub(r"\s+"," ",html.unescape(s or "")).strip()

def text(url):
    req=urllib.request.Request(url,headers={"User-Agent":"paper-reading-workflow/11.0"})
    with urllib.request.urlopen(req,timeout=40) as r:
        return r.read().decode("utf-8","replace")

def js(url):
    req=urllib.request.Request(url,headers={"User-Agent":"paper-reading-workflow/11.0"})
    with urllib.request.urlopen(req,timeout=40) as r:
        return json.loads(r.read())

def title_prefilter(title,c):
    t=(title or "").lower()
    return any(k in t for k in c["fast_prefilter_keywords"])

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.href=None; self.buf=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.href=dict(attrs).get("href"); self.buf=[]
    def handle_data(self,d):
        if self.href is not None: self.buf.append(d)
    def handle_endtag(self,tag):
        if tag=="a" and self.href is not None:
            self.links.append((self.href,clean(" ".join(self.buf))))
            self.href=None; self.buf=[]

class MetaParser(HTMLParser):
    def __init__(self): super().__init__(); self.meta={}
    def handle_starttag(self,tag,attrs):
        if tag!="meta": return
        d=dict(attrs); k=d.get("name") or d.get("property"); v=d.get("content")
        if k and v: self.meta.setdefault(k,[]).append(clean(v))

def meta_page(url):
    p=MetaParser(); p.feed(text(url)); m=p.meta
    def one(*ks):
        for k in ks:
            if m.get(k): return m[k][0]
        return ""
    return {"title":one("citation_title","dc.Title","og:title"),
            "authors":m.get("citation_author",[]),
            "abstract":one("description","citation_abstract","og:description"),
            "pdf":one("citation_pdf_url"),
            "doi":one("citation_doi"),
            "url":url}

class PMLRParser(HTMLParser):
    """Parse <div class=paper> blocks; title is in <p class=title>, not the abs link text."""
    def __init__(self,base):
        super().__init__(); self.base=base; self.in_paper=False; self.depth=0
        self.in_title=False; self.titlebuf=[]; self.current=None; self.items=[]
        self.link_href=None; self.link_buf=[]
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=="div":
            classes=(d.get("class") or "").split()
            if not self.in_paper and "paper" in classes:
                self.in_paper=True; self.depth=1
                self.current={"title":"","url":""}
                return
            elif self.in_paper:
                self.depth+=1
        if not self.in_paper: return
        if tag=="p" and "title" in (d.get("class") or "").split():
            self.in_title=True; self.titlebuf=[]
        elif tag=="a":
            self.link_href=d.get("href",""); self.link_buf=[]
    def handle_data(self,d):
        if self.in_title: self.titlebuf.append(d)
        if self.link_href is not None: self.link_buf.append(d)
    def handle_endtag(self,tag):
        if not self.in_paper: return
        if tag=="p" and self.in_title:
            self.current["title"]=clean(" ".join(self.titlebuf))
            self.in_title=False; self.titlebuf=[]
        elif tag=="a" and self.link_href is not None:
            label=clean(" ".join(self.link_buf)).lower()
            if label=="abs" and not self.current["url"]:
                self.current["url"]=urljoin(self.base,self.link_href)
            self.link_href=None; self.link_buf=[]
        elif tag=="div":
            self.depth-=1
            if self.depth==0:
                if self.current and self.current["title"] and self.current["url"]:
                    self.items.append(self.current)
                self.in_paper=False; self.current=None

def book_index(url,c):
    lp=LinkParser(); lp.feed(text(url)); out=[]; seen=set()
    for href,label in lp.links:
        full=urljoin(url,href)
        if not label or full in seen: continue
        if ("Abstract-Conference.html" in full or
            "Abstract-Main-Conference.html" in full or
            ("/paper_files/paper/" in full and full.endswith(".html"))):
            seen.add(full)
            out.append((full,label))
    return out

def pmlr_index(url,c):
    p=PMLRParser(url); p.feed(text(url))
    return [(x["url"],x["title"]) for x in p.items]

def satml_page(url,venue,year,c):
    # SaTML accepted pages contain title/author/abstract directly in the HTML.
    raw=text(url)
    # headings h4/h5 followed by text; use a forgiving HTML-to-text parser.
    class S(HTMLParser):
        def __init__(self):
            super().__init__(); self.h=False; self.ht=None; self.b=[]; self.p=False
            self.pb=[]; self.cur=None; self.items=[]
        def handle_starttag(self,tag,attrs):
            if tag in ("h3","h4","h5"):
                self.h=True; self.ht=tag; self.b=[]
            elif tag=="p": self.p=True; self.pb=[]
        def handle_data(self,d):
            if self.h: self.b.append(d)
            if self.p: self.pb.append(d)
        def handle_endtag(self,tag):
            if self.h and tag==self.ht:
                t=clean(" ".join(self.b))
                generic={"research papers","position papers","systematization of knowledge papers","sok papers","accepted papers"}
                if len(t)>12 and t.lower() not in generic:
                    self.cur={"title":t,"authors":[],"abstract":"","url":url,"pdf":"","doi":""}
                    self.items.append(self.cur)
                self.h=False
            elif self.p and tag=="p":
                s=clean(" ".join(self.pb))
                if self.cur and s:
                    if len(s)>180 and not self.cur["abstract"]: self.cur["abstract"]=s
                    elif not self.cur["authors"] and len(s)<300:
                        self.cur["authors"]=[x.strip() for x in re.split(r",|;|\band\b",s) if x.strip()]
                self.p=False
    p=S(); p.feed(raw)
    return [x for x in p.items if title_prefilter(x["title"],c)]

def relevance(p,c):
    full=(p.get("title","")+" "+p.get("abstract","")).lower()
    title=p.get("title","").lower(); score=0; why=[]; projects=[]
    for t in c["topics"]:
        hits=[k for k in t["core"] if k.lower() in full]
        if not hits: continue
        score+=max(t["weight"]*(2 if k.lower() in title else 1) for k in hits)
        score+=min(4,sum(k.lower() in full for k in t.get("support",[])))
        why.append(t["name"]+": "+", ".join(hits[:2])); projects.append(t["project"])
    for k,b in c["theory_bonus"].items():
        if k.lower() in full: score+=b
    return score,why,sorted(set(projects))

def priority(total,c):
    t=c["priority_thresholds"]
    return "🔴" if total>=t["red"] else "🟠" if total>=t["orange"] else "🟡" if total>=t["yellow"] else "👀"

def bibkey(p):
    last="anon"
    if p.get("authors"):
        last=re.sub(r"[^A-Za-z0-9]","",p["authors"][0].split()[-1]).lower() or "anon"
    words=[w.lower() for w in re.findall(r"[A-Za-z0-9]+",p["title"])
           if w.lower() not in {"a","an","the","of","on","for","to","in","with","and","via","from","by","using"}]
    return f"{last}{p['year']}{words[0] if words else 'paper'}"

def fetch_details(items,venue,year,c):
    cand=[(u,t) for u,t in items if title_prefilter(t,c)]
    print(f"{venue} {year}: index={len(items)}, title-prefilter={len(cand)}")
    def one(x):
        u,t=x
        try:
            p=meta_page(u)
            if not p["title"]: p["title"]=t
            p.update(venue=venue,year=int(year),kind="conference",citations=0)
            return p
        except Exception: return None
    with ThreadPoolExecutor(max_workers=16) as ex:
        return [p for p in ex.map(one,cand) if p]

def oa_abstract(inv):
    if not inv: return ""
    a=[]
    for w,poses in inv.items():
        for pos in poses:a.append((pos,w))
    return " ".join(w for _,w in sorted(a))

def journal_papers(j,c):
    issn="|".join(j["issn"])
    filt=(f"locations.source.issn:{issn},"
          f"from_publication_date:{c['journal_from_year']}-01-01,"
          f"cited_by_count:>{c['journal_min_citations']-1}")
    params={"filter":filt,"per-page":100,"sort":"cited_by_count:desc"}
    if c.get("openalex_mailto"): params["mailto"]=c["openalex_mailto"]
    data=js(OA+"/works?"+urllib.parse.urlencode(params))
    out=[]
    for w in data.get("results",[]):
        p={"title":w.get("title") or "",
           "abstract":oa_abstract(w.get("abstract_inverted_index")),
           "authors":[a.get("author",{}).get("display_name","") for a in w.get("authorships",[])],
           "year":w.get("publication_year"),"venue":j["name"],"kind":"journal",
           "citations":w.get("cited_by_count") or 0,
           "doi":w.get("doi") or "",
           "url":w.get("doi") or w.get("id") or ""}
        rel,why,projects=relevance(p,c)
        if rel<c["min_relevance"]: continue
        p.update(relevance=rel,why=why,projects=projects)
        p["total"]=rel+10+min(8,p["citations"]//10)
        p["priority"]=priority(p["total"],c); p["bibkey"]=bibkey(p)
        out.append(p)
    out.sort(key=lambda p:(p["relevance"],p["citations"]),reverse=True)
    return out[:c["journal_per_venue"]]

def bibtex(p):
    typ="inproceedings" if p["kind"]=="conference" else "article"
    venuefield="booktitle" if p["kind"]=="conference" else "journal"
    fs=[f"  title = {{{p['title'].replace('{','').replace('}','')}}}",
        f"  author = {{{' and '.join(p.get('authors',[]))}}}",
        f"  year = {{{p['year']}}}",
        f"  {venuefield} = {{{p['venue']}}}",
        f"  url = {{{p['url']}}}"]
    if p.get("doi"): fs.append(f"  doi = {{{p['doi'].replace('https://doi.org/','')}}}")
    return "@"+typ+"{"+p["bibkey"]+",\n"+",\n".join(fs)+"\n}\n"

def row(p):
    status=p.get("status",STATUS_TO_READ)
    notes=p.get("notes","")
    return (f"| {p['priority']} | {status} | {p['relevance']} | {p.get('citations',0)} | "
            f"[{p['title'].replace('|','/')}]({p['url']}) | {p['venue']} | {p['year']} | "
            f"{', '.join(p.get('projects',[])) or '—'} | `{p['bibkey']}` | {'; '.join(p.get('why',[]))} | {notes} |")

def merge_into_registry(reg, papers):
    """
    Never duplicate a previously seen paper.
    Existing status/notes are preserved; newly discovered papers start as To read.
    """
    for p in papers:
        pid=stable_id(p)
        p["_pid"]=pid
        if pid in reg:
            # Refresh bibliographic/ranking metadata but preserve workflow state.
            status=reg[pid].get("status",STATUS_TO_READ)
            notes=reg[pid].get("notes","")
            reg[pid].update({k:v for k,v in p.items() if k != "_pid"})
            reg[pid]["status"]=status
            reg[pid]["notes"]=notes
        else:
            rec={k:v for k,v in p.items() if k != "_pid"}
            rec["status"]=STATUS_TO_READ
            rec["notes"]=""
            reg[pid]=rec
    return reg

def active_sorted(reg,c):
    """
    The queue is a persistent tracker, not a weekly report.
    Show all tracked papers, with workflow status first and venue grouping later.
    """
    rank={STATUS_TO_READ:0,STATUS_REVIEW_READY:1,STATUS_DONE:2}
    arr=[paper_from_registry(pid,rec) for pid,rec in reg.items()]
    arr.sort(key=lambda p:(
        rank.get(p.get("status",STATUS_TO_READ),9),
        -int(p.get("relevance",0)),
        -int(p.get("citations",0)),
        str(p.get("venue","")),
        -int(p.get("year") or 0)
    ))
    return arr

def render_queue(reg,c,notes):
    papers=active_sorted(reg,c)
    confpapers=[p for p in papers if p.get("kind")=="conference"]
    journals=[p for p in papers if p.get("kind")=="journal"]

    lines=[
      "# Paper Reading Queue","",
      "_Stateful tracker. Previously seen papers are never re-added as duplicates._","",
      "**Status:** 🔴 To read · 🟡 Review ready · 🟢 Done","",
      "Workflow: discovery → 🔴 To read → deep-reading note generated → 🟡 Review ready → you review it → 🟢 Done","",
      "## Conference papers","",
      "| Priority | Status | Relevance | Citations | Paper | Venue | Year | Project | BibTeX | Why | Notes |",
      "|---|---|---:|---:|---|---|---:|---|---|---|---|"
    ]
    for conf in c["conferences"]:
        arr=[p for p in confpapers if p.get("venue")==conf["name"]]
        if arr:
            lines.append(f"| **{conf['name']}** | | | | | | | | | | |")
            lines.extend(row(p) for p in arr)

    lines += [
      "","## Top journal papers — citation ≥ 10","",
      "| Priority | Status | Relevance | Citations | Paper | Venue | Year | Project | BibTeX | Why | Notes |",
      "|---|---|---:|---:|---|---|---:|---|---|---|---|"
    ]
    for j in c["journals"]:
        arr=[p for p in journals if p.get("venue")==j["name"]]
        if arr:
            lines.append(f"| **{j['name']}** | | | | | | | | | | |")
            lines.extend(row(p) for p in arr)

    if notes:
        lines += ["","## Fetch notes",""]+[f"- {x}" for x in notes]

    Path("reading_queue.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

def render_bib(reg):
    papers=[paper_from_registry(pid,rec) for pid,rec in reg.items()]
    Path("bib").mkdir(exist_ok=True)
    Path("bib/discovered.bib").write_text(
        "\n".join(bibtex(p) for p in papers),
        encoding="utf-8"
    )

def main():
    c=cfg()
    reg=load_registry()

    # If the user manually changed statuses/notes in reading_queue.md, keep those edits.
    reg=sync_registry_from_queue(reg,parse_existing_queue())

    discovered=[]
    notes=[]

    # --- Verified conference sources ---
    for conf in c["conferences"]:
        bucket=[]
        for year,url in conf["years"].items():
            try:
                if conf["type"]=="book":
                    raw=fetch_details(book_index(url,c),conf["name"],year,c)
                elif conf["type"]=="pmlr":
                    raw=fetch_details(pmlr_index(url,c),conf["name"],year,c)
                else:
                    raw=satml_page(url,conf["name"],year,c)
                    for p in raw:
                        p.update(venue=conf["name"],year=int(year),kind="conference",citations=0)

                rels=[]
                for p in raw:
                    rel,why,projects=relevance(p,c)
                    if rel<c["min_relevance"]: continue
                    p.update(relevance=rel,why=why,projects=projects)
                    p["total"]=rel+10
                    p["priority"]=priority(p["total"],c)
                    p["bibkey"]=bibkey(p)
                    rels.append(p)

                print(f"{conf['name']} {year}: full-relevance={len(rels)}")
                bucket.extend(rels)
            except Exception as e:
                notes.append(f"{conf['name']} {year}: {type(e).__name__}: {e}")

        # Per-venue shortlist applies to NEW discovery candidates, not to the persistent registry.
        seen={}
        for p in bucket:
            k=stable_id(p)
            if k not in seen or p["total"]>seen[k]["total"]:
                seen[k]=p
        arr=sorted(seen.values(),key=lambda p:p["relevance"],reverse=True)[:c["top_per_venue"]]
        discovered.extend(arr)
        print(f"{conf['name']}: discovered shortlist={len(arr)}")

    # --- Verified journal ISSN filters + citation hard gate ---
    for j in c["journals"]:
        try:
            arr=journal_papers(j,c)
            discovered.extend(arr)
            print(f"{j['name']}: discovered shortlist={len(arr)}")
        except Exception as e:
            notes.append(f"{j['name']}: {type(e).__name__}: {e}")

    # Add only truly new papers; refresh metadata for old ones without resetting status.
    before=len(reg)
    reg=merge_into_registry(reg,discovered)
    after=len(reg)
    print(f"Registry: {before} existing + {after-before} new = {after} total")

    save_registry(reg)
    render_queue(reg,c,notes)
    render_bib(reg)

if __name__=="__main__":
    main()

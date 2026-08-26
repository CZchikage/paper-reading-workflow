#!/usr/bin/env python3
"""
v5 venue-balanced discovery.

Important design choices:
- No arXiv feed.
- No AAAI/KDD.
- Conference candidates are discovered by research query, then venue-validated.
- PMLR conferences are validated using raw source names where available.
- Each conference gets its own quota before global merging, so one venue cannot dominate.
- Journals must be whitelisted AND have >= configured citations.
"""
from __future__ import annotations
import html, json, re, time, urllib.parse, urllib.request
from pathlib import Path

API="https://api.openalex.org"

def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def norm(s): return re.sub(r"\s+"," ",html.unescape(s or "")).strip()

def get_json(path,params,cfg):
    if cfg["openalex"].get("mailto"): params["mailto"]=cfg["openalex"]["mailto"]
    url=API+path+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"User-Agent":"paper-reading-workflow/5.0"})
    with urllib.request.urlopen(req,timeout=40) as r: return json.loads(r.read())

def abstract(w):
    inv=w.get("abstract_inverted_index") or {}
    pairs=[]
    for word,poses in inv.items():
        for p in poses: pairs.append((p,word))
    return " ".join(w for _,w in sorted(pairs))

def venue_strings(w):
    vals=[]
    pl=w.get("primary_location") or {}
    locs=[pl]+(w.get("locations") or [])
    for loc in locs:
        if not loc: continue
        raw=loc.get("raw_source_name")
        if raw: vals.append(raw)
        src=loc.get("source") or {}
        if src.get("display_name"): vals.append(src["display_name"])
    # OpenAlex may expose venue-like information elsewhere too.
    for key in ("display_name","title"):
        if w.get(key): vals.append(w[key])
    return [norm(x) for x in vals if x]

def match_venue(w,venue):
    strings=[s.lower() for s in venue_strings(w)]
    for alias in venue["aliases"]:
        a=alias.lower()
        if any(a in s for s in strings):
            return True
    return False

def journal_match(w,journal):
    strings=[s.lower() for s in venue_strings(w)]
    return any(any(a.lower() in s for s in strings) for a in journal["aliases"])

def authors(w):
    return [a.get("author",{}).get("display_name","") for a in w.get("authorships",[]) if a.get("author")]

def to_paper(w,venue,kind):
    return {
      "id":w.get("id",""),
      "title":norm(w.get("title","")),
      "abstract":abstract(w),
      "authors":authors(w),
      "year":w.get("publication_year"),
      "date":w.get("publication_date") or "",
      "venue":venue,
      "kind":kind,
      "citations":w.get("cited_by_count") or 0,
      "doi":w.get("doi") or "",
      "url":w.get("doi") or w.get("id") or ""
    }

def relevance(p,cfg):
    text=(p["title"]+" "+p["abstract"]).lower()
    title=p["title"].lower()
    score=0; why=[]; projects=[]
    for t in cfg["topics"]:
        hits=[k for k in t["core_keywords"] if k.lower() in text]
        if not hits: continue
        best=max(t["weight"]*(2 if k.lower() in title else 1) for k in hits)
        supp=[k for k in t.get("support_keywords",[]) if k.lower() in text]
        score+=best+min(4,len(supp))
        why.append(t["name"]+": "+", ".join(hits[:2]))
        projects.append(t["project"])
    for k,b in cfg.get("theory_bonus",{}).items():
        if k.lower() in text: score+=b
    return score,why,sorted(set(projects))

def priority(total,cfg):
    t=cfg["priority_thresholds"]
    if total>=t["red"]: return "🔴"
    if total>=t["orange"]: return "🟠"
    if total>=t["yellow"]: return "🟡"
    return "👀"

def bibkey(p):
    last="anon"
    if p["authors"]:
        last=re.sub(r"[^A-Za-z0-9]","",p["authors"][0].split()[-1]).lower() or "anon"
    stop={"a","an","the","of","on","for","to","in","with","and","via","from","by","using"}
    ws=[w.lower() for w in re.findall(r"[A-Za-z0-9]+",p["title"]) if w.lower() not in stop]
    return f"{last}{p['year'] or '0000'}{ws[0] if ws else 'paper'}"

def discover_query(query,year,cfg):
    params={
      "search":query,
      "filter":f"publication_year:{year}",
      "per-page":cfg["openalex"]["per_page"],
      "sort":"cited_by_count:desc"
    }
    return get_json("/works",params,cfg).get("results",[])

def discover_conferences(cfg):
    buckets={v["name"]:{} for v in cfg["conference_venues"]}
    for year in cfg["conference_years"]:
        for topic in cfg["topics"]:
            for query in topic["queries"]:
                try:
                    works=discover_query(query,year,cfg)
                except Exception as e:
                    print("WARN query",query,year,type(e).__name__)
                    continue
                for w in works:
                    for venue in cfg["conference_venues"]:
                        if match_venue(w,venue):
                            p=to_paper(w,venue["name"],"conference")
                            rel,why,projects=relevance(p,cfg)
                            if rel<cfg["min_relevance"]: continue
                            p.update(relevance=rel,reasons=why,projects=projects)
                            # conference quality gate already passed; add venue priority + citations
                            cite_bonus=5 if p["citations"]>=30 else 3 if p["citations"]>=10 else 1 if p["citations"]>=3 else 0
                            p["total"]=rel+venue["priority"]+cite_bonus
                            p["priority"]=priority(p["total"],cfg)
                            p["bibkey"]=bibkey(p)
                            buckets[venue["name"]][p["id"]]=p
                time.sleep(0.12)

    selected=[]
    for venue in cfg["conference_venues"]:
        arr=list(buckets[venue["name"]].values())
        arr.sort(key=lambda p:(p["total"],p["relevance"],p["citations"]),reverse=True)
        arr=arr[:cfg["conference_per_venue"]]
        selected.extend(arr)
        print(f"{venue['name']}: {len(arr)} selected")
    return selected

def discover_journals(cfg):
    out=[]
    # Search by topic and then hard-filter journal + citation.
    seen={}
    for topic in cfg["topics"]:
        for query in topic["queries"]:
            params={
              "search":query,
              "filter":f"from_publication_date:{cfg['journal_from_year']}-01-01,cited_by_count:>{cfg['journal_min_citations']-1}",
              "per-page":cfg["openalex"]["per_page"],
              "sort":"cited_by_count:desc"
            }
            try: works=get_json("/works",params,cfg).get("results",[])
            except Exception as e:
                print("WARN journal query",query,type(e).__name__); continue
            for w in works:
                matched=None
                for j in cfg["top_journals"]:
                    if journal_match(w,j): matched=j["name"]; break
                if not matched: continue
                p=to_paper(w,matched,"journal")
                if p["citations"]<cfg["journal_min_citations"]: continue
                rel,why,projects=relevance(p,cfg)
                if rel<cfg["min_relevance"]: continue
                p.update(relevance=rel,reasons=why,projects=projects)
                cite_bonus=min(10,2+(p["citations"]//20))
                p["total"]=rel+10+cite_bonus
                p["priority"]=priority(p["total"],cfg)
                p["bibkey"]=bibkey(p)
                seen[p["id"]]=p
            time.sleep(0.12)

    # quota by journal
    for j in cfg["top_journals"]:
        arr=[p for p in seen.values() if p["venue"]==j["name"]]
        arr.sort(key=lambda p:(p["total"],p["citations"],p["relevance"]),reverse=True)
        out.extend(arr[:cfg["journal_per_venue"]])
        print(f"{j['name']}: {min(len(arr),cfg['journal_per_venue'])} selected")
    return out

def bibtex(p):
    typ="inproceedings" if p["kind"]=="conference" else "article"
    fields=[
      f"  title = {{{p['title'].replace('{','').replace('}','')}}}",
      f"  author = {{{' and '.join(p['authors'])}}}",
      f"  year = {{{p['year']}}}",
      (f"  booktitle = {{{p['venue']}}}" if p["kind"]=="conference" else f"  journal = {{{p['venue']}}}"),
      f"  url = {{{p['url']}}}"
    ]
    if p["doi"]: fields.append(f"  doi = {{{p['doi'].replace('https://doi.org/','')}}}")
    return "@"+typ+"{"+p["bibkey"]+",\n"+",\n".join(fields)+"\n}\n"

def load_state(path):
    st={}
    if not Path(path).exists(): return st
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"): continue
        cells=[x.strip() for x in line.strip("|").split("|")]
        if len(cells)<10: continue
        m=re.search(r"\((https?://[^)]+)\)",cells[4])
        if m: st[m.group(1)]={"status":cells[1],"notes":cells[-1]}
    return st

def row(p,st):
    old=st.get(p["url"],{})
    return (
      f"| {p['priority']} | {old.get('status','TODO')} | {p['relevance']} | {p['citations']} | "
      f"[{p['title'].replace('|','/')}]({p['url']}) | {p['venue']} | {p['year']} | "
      f"{', '.join(p['projects']) or '—'} | `{p['bibkey']}` | {'; '.join(p['reasons'])} | {old.get('notes','')} |"
    )

def render(papers,cfg):
    st=load_state("reading_queue.md")
    conf=[p for p in papers if p["kind"]=="conference"]
    jour=[p for p in papers if p["kind"]=="journal"]
    lines=[
      "# Paper Reading Queue","",
      "_Venue-balanced, quality-first. No arXiv feed; no AAAI/KDD._","",
      "## Top Conference Papers — 2025–2026","",
      "| Priority | Status | Relevance | Citations | Paper | Venue | Year | Project | BibTeX | Why | Notes |",
      "|---|---|---:|---:|---|---|---:|---|---|---|---|"
    ]
    # group conferences to make venue balance visible
    for v in cfg["conference_venues"]:
        arr=[p for p in conf if p["venue"]==v["name"]]
        if not arr: continue
        lines += [f"| **{v['name']}** |  |  |  |  |  |  |  |  |  |  |"]
        lines += [row(p,st) for p in arr]
    lines += [
      "","## Top Journal Papers — citation ≥ "+str(cfg["journal_min_citations"]),"",
      "| Priority | Status | Relevance | Citations | Paper | Venue | Year | Project | BibTeX | Why | Notes |",
      "|---|---|---:|---:|---|---|---:|---|---|---|---|"
    ]
    for j in cfg["top_journals"]:
        arr=[p for p in jour if p["venue"]==j["name"]]
        if not arr: continue
        lines += [f"| **{j['name']}** |  |  |  |  |  |  |  |  |  |  |"]
        lines += [row(p,st) for p in arr]
    Path("reading_queue.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

def main():
    cfg=load("config/paper_discovery.json")
    conf=discover_conferences(cfg)
    jour=discover_journals(cfg)

    # preserve venue balance. We don't globally truncate before each venue got its quota.
    papers=conf+jour
    render(papers,cfg)
    Path("bib").mkdir(exist_ok=True)
    Path("bib/discovered.bib").write_text("\n".join(bibtex(p) for p in papers),encoding="utf-8")
    print("Total:",len(papers))

if __name__=="__main__":
    main()

#!/usr/bin/env python3
"""
Quality-first paper tracker:
1) Past two years of papers from selected top conferences.
2) Selected top-journal papers with cited_by_count >= threshold.
3) Rank only after venue/citation quality gates.

Primary metadata source: OpenAlex.
No arXiv feed is queried.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.openalex.org"

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def get_json(url, mailto=""):
    headers={"User-Agent":"paper-reading-workflow/4.0"}
    if mailto:
        headers["User-Agent"] += f" (mailto:{mailto})"
    req=urllib.request.Request(url,headers=headers)
    with urllib.request.urlopen(req,timeout=40) as r:
        return json.loads(r.read())

def norm(s):
    return re.sub(r"\s+"," ",html.unescape(s or "")).strip()

def reconstruct_abstract(inv):
    if not inv: return ""
    pairs=[]
    for word, poss in inv.items():
        for pos in poss:
            pairs.append((pos,word))
    return " ".join(w for _,w in sorted(pairs))

def source_search(alias, mailto=""):
    params={"search":alias,"per-page":10}
    if mailto: params["mailto"]=mailto
    data=get_json(API+"/sources?"+urllib.parse.urlencode(params),mailto)
    return data.get("results",[])

def resolve_source(venue, mailto=""):
    candidates=[]
    for alias in venue["aliases"]:
        try:
            results=source_search(alias,mailto)
        except Exception:
            continue
        for s in results:
            name=(s.get("display_name") or "").lower()
            score=0
            if name==alias.lower(): score+=100
            if alias.lower() in name or name in alias.lower(): score+=30
            score += min(20, int((s.get("works_count") or 0)>100))
            candidates.append((score,s))
        time.sleep(0.15)
    if not candidates: return None
    candidates.sort(key=lambda x:x[0],reverse=True)
    return candidates[0][1]

def iter_works(source_id, filters, cfg):
    per=cfg["openalex"]["per_page"]
    max_pages=cfg["openalex"]["max_pages_per_venue"]
    mailto=cfg["openalex"].get("mailto","")
    cursor="*"
    pages=0
    while cursor and pages<max_pages:
        f=["primary_location.source.id:"+source_id]+filters
        params={"filter":",".join(f),"per-page":per,"cursor":cursor}
        if mailto: params["mailto"]=mailto
        data=get_json(API+"/works?"+urllib.parse.urlencode(params),mailto)
        for w in data.get("results",[]): yield w
        cursor=data.get("meta",{}).get("next_cursor")
        pages+=1
        time.sleep(0.15)

def doi_url(w):
    doi=w.get("doi") or ""
    return doi if doi.startswith("http") else (f"https://doi.org/{doi}" if doi else (w.get("id") or ""))

def authors(w):
    return [a.get("author",{}).get("display_name","") for a in w.get("authorships",[]) if a.get("author")]

def convert(w, venue_name, kind):
    loc=w.get("primary_location") or {}
    src=loc.get("source") or {}
    return {
      "openalex_id":w.get("id",""),
      "title":norm(w.get("title","")),
      "abstract":reconstruct_abstract(w.get("abstract_inverted_index")),
      "authors":authors(w),
      "year":w.get("publication_year"),
      "date":w.get("publication_date") or "",
      "venue":venue_name,
      "venue_raw":src.get("display_name") or "",
      "kind":kind,
      "citations":w.get("cited_by_count") or 0,
      "doi":w.get("doi") or "",
      "url":doi_url(w),
      "type":w.get("type") or "",
      "is_oa":((w.get("open_access") or {}).get("is_oa") or False)
    }

def relevance(p,cfg):
    text=(p["title"]+" "+p["abstract"]).lower()
    title=p["title"].lower()
    score=0; reasons=[]; projects=[]
    for t in cfg["topics"]:
        core=[k for k in t["core_keywords"] if k.lower() in text]
        supp=[k for k in t.get("support_keywords",[]) if k.lower() in text]
        if core:
            best=max(t["weight"]*(2 if k.lower() in title else 1) for k in core)
            score += best + min(4,len(supp))
            reasons.append(t["name"]+": "+", ".join(core[:2]))
            projects.append(t["project"])
    for kw,b in cfg.get("theory_bonus",{}).items():
        if kw.lower() in text: score+=b
    return score,reasons,sorted(set(projects))

def quality_score(p):
    # Venue is already a hard gate. Citations are additional ranking signal.
    q=0
    if p["kind"]=="conference":
        q=12
        if p["citations"]>=50: q+=6
        elif p["citations"]>=20: q+=4
        elif p["citations"]>=10: q+=3
        elif p["citations"]>=5: q+=1
    else:
        q=10
        if p["citations"]>=100: q+=8
        elif p["citations"]>=50: q+=6
        elif p["citations"]>=25: q+=4
        elif p["citations"]>=10: q+=2
    return q

def priority(total,cfg):
    th=cfg["priority"]
    if total>=th["red"]: return "🔴"
    if total>=th["orange"]: return "🟠"
    if total>=th["yellow"]: return "🟡"
    return "👀"

def bibkey(p):
    last="anon"
    if p["authors"]:
        last=re.sub(r"[^A-Za-z0-9]","",p["authors"][0].split()[-1]).lower() or "anon"
    stop={"a","an","the","of","on","for","to","in","with","and","via","from","by","using"}
    words=[w.lower() for w in re.findall(r"[A-Za-z0-9]+",p["title"]) if w.lower() not in stop]
    return f"{last}{p['year'] or '0000'}{words[0] if words else 'paper'}"

def bibtex(p):
    typ="inproceedings" if p["kind"]=="conference" else "article"
    fields=[
      f"  title = {{{p['title'].replace('{','').replace('}','')}}}",
      f"  author = {{{' and '.join(p['authors'])}}}",
      f"  year = {{{p['year']}}}",
    ]
    if p["kind"]=="conference":
        fields.append(f"  booktitle = {{{p['venue']}}}")
    else:
        fields.append(f"  journal = {{{p['venue']}}}")
    if p["doi"]:
        fields.append(f"  doi = {{{p['doi'].replace('https://doi.org/','')}}}")
    fields.append(f"  url = {{{p['url']}}}")
    return "@"+typ+"{"+p["bibkey"]+",\n"+",\n".join(fields)+"\n}\n"

def load_state(path):
    state={}
    if not Path(path).exists(): return state
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"): continue
        cells=[x.strip() for x in line.strip("|").split("|")]
        if len(cells)<11: continue
        m=re.search(r"\((https?://[^)]+)\)",cells[4])
        if m:
            state[m.group(1)]={"status":cells[1],"notes":cells[-1]}
    return state

def row(p,state):
    old=state.get(p["url"],{})
    why="; ".join(p["reasons"])
    return (
      f"| {p['priority']} | {old.get('status','TODO')} | {p['relevance']} | {p['citations']} | "
      f"[{p['title'].replace('|','/')}]({p['url']}) | {p['venue']} | {p['year']} | "
      f"{', '.join(p['projects']) or '—'} | `{p['bibkey']}` | {why} | {old.get('notes','')} |"
    )

def render(queue,papers,cfg,resolution_notes):
    state=load_state(queue)
    conf=[p for p in papers if p["kind"]=="conference"]
    journals=[p for p in papers if p["kind"]=="journal"]
    red=[p for p in papers if p["priority"]=="🔴"][:cfg["must_read_max"]]
    lines=[
      "# Paper Reading Queue","",
      "_Venue-first screening. No arXiv feed is used._","",
      "## Must Read",""
    ]
    if not red:
        lines += ["> No paper cleared the current Must Read threshold.",""]
    else:
        lines += [
          "| Priority | Status | Relevance | Citations | Paper | Venue | Year | Project | BibTeX | Why | Notes |",
          "|---|---|---:|---:|---|---|---:|---|---|---|---|"
        ]+[row(p,state) for p in red]+[""]
    lines += [
      "## Top Conference Papers — past two years","",
      "| Priority | Status | Relevance | Citations | Paper | Venue | Year | Project | BibTeX | Why | Notes |",
      "|---|---|---:|---:|---|---|---:|---|---|---|---|"
    ]+[row(p,state) for p in conf]+[
      "","## Top Journal Papers — citation ≥ "+str(cfg["journal_min_citations"]),"",
      "| Priority | Status | Relevance | Citations | Paper | Venue | Year | Project | BibTeX | Why | Notes |",
      "|---|---|---:|---:|---|---|---:|---|---|---|---|"
    ]+[row(p,state) for p in journals]
    if resolution_notes:
        lines += ["","## Source resolution notes",""]+[f"- {x}" for x in resolution_notes]
    Path(queue).write_text("\n".join(lines)+"\n",encoding="utf-8")

def main():
    cfg=load("config/paper_discovery.json")
    years=cfg["conference_years"]
    candidates=[]
    notes=[]

    # 1. Conferences: venue itself is the quality gate.
    for venue in cfg["conference_venues"]:
        src=resolve_source(venue,cfg["openalex"].get("mailto",""))
        if not src:
            notes.append(f"Could not resolve conference source: {venue['name']}")
            continue
        sid=src["id"].split("/")[-1]
        for year in years:
            filters=[f"publication_year:{year}"]
            count=0
            try:
                for w in iter_works(sid,filters,cfg):
                    p=convert(w,venue["name"],"conference")
                    rel,reasons,projects=relevance(p,cfg)
                    if rel<cfg["min_relevance"]: continue
                    p["relevance"]=rel;p["reasons"]=reasons;p["projects"]=projects
                    p["quality"]=quality_score(p);p["total"]=rel+p["quality"]
                    p["priority"]=priority(p["total"],cfg);p["bibkey"]=bibkey(p)
                    candidates.append(p); count+=1
            except Exception as e:
                notes.append(f"{venue['name']} {year}: {type(e).__name__}")
        time.sleep(0.2)

    # 2. Journals: top-journal membership + citation threshold are hard gates.
    for venue in cfg["top_journals"]:
        src=resolve_source(venue,cfg["openalex"].get("mailto",""))
        if not src:
            notes.append(f"Could not resolve journal source: {venue['name']}")
            continue
        sid=src["id"].split("/")[-1]
        filters=[
          f"from_publication_date:{cfg['journal_from_year']}-01-01",
          f"cited_by_count:>{cfg['journal_min_citations']-1}"
        ]
        try:
            for w in iter_works(sid,filters,cfg):
                p=convert(w,venue["name"],"journal")
                if p["citations"]<cfg["journal_min_citations"]: continue
                rel,reasons,projects=relevance(p,cfg)
                if rel<cfg["min_relevance"]: continue
                p["relevance"]=rel;p["reasons"]=reasons;p["projects"]=projects
                p["quality"]=quality_score(p);p["total"]=rel+p["quality"]
                p["priority"]=priority(p["total"],cfg);p["bibkey"]=bibkey(p)
                candidates.append(p)
        except Exception as e:
            notes.append(f"{venue['name']}: {type(e).__name__}")
        time.sleep(0.2)

    # dedupe DOI/OpenAlex id
    uniq={}
    for p in candidates:
        key=(p["doi"] or p["openalex_id"] or p["title"]).lower()
        if key not in uniq or p["total"]>uniq[key]["total"]:
            uniq[key]=p

    papers=list(uniq.values())
    # Conferences first, then journals; within each, relevance/quality/citations.
    conf=sorted([p for p in papers if p["kind"]=="conference"],
                key=lambda p:(p["total"],p["relevance"],p["citations"]),reverse=True)
    jour=sorted([p for p in papers if p["kind"]=="journal"],
                key=lambda p:(p["total"],p["citations"],p["relevance"]),reverse=True)
    selected=(conf+jour)[:cfg["top_n"]]

    render("reading_queue.md",selected,cfg,notes)

    Path("bib").mkdir(exist_ok=True)
    Path("bib/discovered.bib").write_text("\n".join(bibtex(p) for p in selected),encoding="utf-8")

    print(f"Conference matches: {len(conf)}; journal matches: {len(jour)}; selected: {len(selected)}")
    for p in selected:
        print(p["priority"],p["venue"],p["year"],"R",p["relevance"],"C",p["citations"],p["title"])

if __name__=="__main__":
    main()

#!/usr/bin/env python3
import json, re, sys
from pathlib import Path
if len(sys.argv)!=3: raise SystemExit(f"Usage: {sys.argv[0]} LOCAL.json PRODUCTION_TEST.json")
a=json.loads(Path(sys.argv[1]).read_text()); b=json.loads(Path(sys.argv[2]).read_text())
rows=[]
def add(level,item,x,y,why): rows.append((level,item,x,y,why))
for key in ("architecture","postgres_major","migration_head"):
    if a.get(key)!=b.get(key): add("BLOCKER",key,a.get(key),b.get(key),"must match")
for key in ("docker","compose","os"):
    if a.get(key)!=b.get(key): add("WARNING",key,a.get(key),b.get(key),"compatible versions require review")
def minor(v):
    nums=re.findall(r"\d+",str(v)); return tuple(nums[:2])
if minor(a.get("agent"))!=minor(b.get("agent")): add("BLOCKER","agent",a.get("agent"),b.get("agent"),"Agent major/minor behavior differs")
for svc in ("mesflow-app","mesflow-postgres","mesflow-deploy-agent"):
    ac=a.get("containers",{}).get(svc,{}); bc=b.get("containers",{}).get(svc,{})
    for field in ("restart","healthcheck","mounts"):
        av=ac.get(field); bv=bc.get(field)
        if field=="mounts":
            av=sorted(av or [],key=lambda x:(x.get("destination", ""),x.get("type", "")))
            bv=sorted(bv or [],key=lambda x:(x.get("destination", ""),x.get("type", "")))
        if av!=bv: add("BLOCKER",f"{svc}.{field}",av,bv,"deployment contract differs")
for key in ("host","locale","application_version","schema"):
    if a.get(key)!=b.get(key): add("EXPECTED DIFFERENCE",key,a.get(key),b.get(key),"allowed when contract and migration path are valid")
if a.get("qa")!=b.get("qa"): add("WARNING","qa",a.get("qa"),b.get("qa"),"same scenario source/profile behavior must be demonstrated")
for data,label in ((a,"DEV"),(b,"PRODUCTION TEST")):
    if data.get("timezone")!="Asia/Ho_Chi_Minh": add("WARNING",f"{label}.timezone",data.get("timezone"),"Asia/Ho_Chi_Minh","host differs from business timezone")
    for p,v in data.get("paths",{}).items():
        if not v.get("present"):
            if label=="DEV": add("BLOCKER",f"{label}.path","missing","required",f"required runtime persistence path: {p}")
            else: add("BLOCKER",f"{label}.path","required","missing",f"required runtime persistence path: {p}")
    for svc in ("mesflow-app","mesflow-postgres","mesflow-deploy-agent"):
        h=data.get("containers",{}).get(svc,{}).get("health")
        if h!="healthy":
            if label=="DEV": add("BLOCKER",f"{label}.{svc}.health",h,"healthy","promotion requires healthy service")
            else: add("BLOCKER",f"{label}.{svc}.health","healthy",h,"promotion requires healthy service")
    agent_payload=(data.get("health",{}).get("agent") or {}).get("payload") or {}
    qa_ok=bool((data.get("health",{}).get("qa") or {}).get("ok")) and bool((agent_payload.get("qa") or {}).get("online"))
    if not qa_ok:
        if label=="DEV": add("BLOCKER",f"{label}.qa.health","offline","online","QA connection required")
        else: add("BLOCKER",f"{label}.qa.health","online","offline","QA connection required")
order={"BLOCKER":0,"WARNING":1,"EXPECTED DIFFERENCE":2}
for row in sorted(rows,key=lambda x:(order[x[0]],x[1])): print(f"{row[0]:19} {row[1]}\n  DEV: {row[2]}\n  PRODUCTION TEST: {row[3]}\n  {row[4]}")
blockers=sum(x[0]=="BLOCKER" for x in rows); warnings=sum(x[0]=="WARNING" for x in rows)
print(f"\nSUMMARY BLOCKERS={blockers} WARNINGS={warnings} EXPECTED_DIFFERENCES={sum(x[0]=='EXPECTED DIFFERENCE' for x in rows)}")
print("READY FOR PROMOTION" if blockers==0 else "NOT READY FOR PROMOTION")
raise SystemExit(2 if blockers else 0)

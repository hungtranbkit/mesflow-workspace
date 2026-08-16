#!/usr/bin/env python3
"""Read-only MESFlow environment inventory. Values of environment variables are never emitted."""
from __future__ import annotations
import argparse, json, os, platform, re, shutil, socket, subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]

def run(*cmd: str, timeout: int = 8) -> str:
    try:
        return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""

def endpoint(url: str) -> dict:
    try:
        with urlopen(url, timeout=7) as response:
            raw=response.read(262144).decode("utf-8", "replace")
            try: payload=json.loads(raw)
            except json.JSONDecodeError: payload={}
            return {"ok": 200 <= response.status < 300, "status": response.status, "payload": payload}
    except Exception as exc:
        code=getattr(exc, "code", 0)
        return {"ok": False, "status": int(code or 0), "error": type(exc).__name__}

def docker_inspect(name: str) -> dict:
    raw=run("docker", "inspect", name)
    if not raw: return {"present": False}
    try: item=json.loads(raw)[0]
    except (ValueError, IndexError): return {"present": False}
    config=item.get("Config") or {}; state=item.get("State") or {}; host=item.get("HostConfig") or {}
    health=(state.get("Health") or {}).get("Status", "none")
    keys=sorted(x.split("=",1)[0] for x in config.get("Env") or [] if "=" in x)
    mounts=[{"destination":m.get("Destination"),"type":m.get("Type"),"rw":m.get("RW")} for m in item.get("Mounts") or []]
    networks=sorted(((item.get("NetworkSettings") or {}).get("Networks") or {}).keys())
    ports=[]
    for private, bindings in (((item.get("NetworkSettings") or {}).get("Ports")) or {}).items():
        for binding in bindings or []: ports.append(f"{binding.get('HostIp')}:{binding.get('HostPort')}->{private}")
    return {"present":True,"image":config.get("Image", ""),"running":bool(state.get("Running")),"health":health,
            "restart":(host.get("RestartPolicy") or {}).get("Name", ""),"env_keys":keys,"mounts":mounts,
            "networks":networks,"ports":sorted(ports),"healthcheck":(config.get("Healthcheck") or {}).get("Test", [])}

def env_metadata(path: Path) -> dict:
    if not path.exists(): return {"path":str(path),"present":False,"keys":[]}
    try:
        keys=sorted({line.split("=",1)[0].strip() for line in path.read_text(errors="replace").splitlines()
                     if line.strip() and not line.lstrip().startswith("#") and "=" in line})
    except PermissionError: keys=[]
    return {"path":str(path),"present":True,"mode":oct(path.stat().st_mode & 0o777)[2:],"keys":keys}

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("profile", choices=["local","production-test"]); ap.add_argument("--output")
    args=ap.parse_args()
    app=endpoint("http://127.0.0.1:8080/api/system/health")
    ready=endpoint("http://127.0.0.1:8080/api/system/ready")
    agent=endpoint("http://127.0.0.1:8090/health")
    qa=endpoint("http://127.0.0.1:8095/api/version")
    app_payload=app.get("payload") or {}; ready_payload=ready.get("payload") or {}; agent_payload=agent.get("payload") or {}
    containers={n:docker_inspect(n) for n in ("mesflow-app","mesflow-postgres","mesflow-deploy-agent","mesflow-qa-center","mesflow-testcenter","mesflow-nginx")}
    os_release={}
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if "=" in line:
                k,v=line.split("=",1); os_release[k]=v.strip('"')
    except OSError: pass
    compose=run("docker","compose","version","--short") or run("docker","compose","version")
    docker=run("docker","version","--format","{{.Server.Version}}")
    tz=run("timedatectl","show","-p","Timezone","--value") or os.environ.get("TZ", "unknown")
    env_path=Path("/opt/mesflow/.env")
    data={
      "format_version":1,"profile":args.profile,"generated_at":datetime.now(timezone.utc).isoformat(),"host":socket.gethostname(),
      "os":os_release.get("PRETTY_NAME", platform.platform()),"architecture":platform.machine(),"docker":docker or "NOT_AVAILABLE",
      "compose":compose or "NOT_AVAILABLE","timezone":tz or "unknown","locale":os.environ.get("LC_ALL") or os.environ.get("LANG", "unknown"),
      "postgres":str(app_payload.get("postgres_version") or "NOT_VERIFIED"),"postgres_major":str(app_payload.get("postgres_version") or "").split(".")[0] or "NOT_VERIFIED",
      "application_version":str(app_payload.get("version") or ready_payload.get("version") or "NOT_VERIFIED"),
      "schema":str(app_payload.get("schema_version") or ready_payload.get("schema_version") or "NOT_VERIFIED"),
      "migration_head":str(ready_payload.get("migration_head") or "NOT_VERIFIED"),
      "agent":str(agent_payload.get("agent_version") or "NOT_VERIFIED"),
      "qa":str((qa.get("payload") or {}).get("version") or agent_payload.get("qa",{}).get("version") or "NOT_VERIFIED"),
      "services":[k for k,v in containers.items() if v.get("present")],"containers":containers,
      "networks":sorted(run("docker","network","ls","--format","{{.Name}}").splitlines()),
      "volumes":sorted(run("docker","volume","ls","--format","{{.Name}}").splitlines()),
      "health":{"application":app,"ready":ready,"agent":agent,"qa":qa},"env":env_metadata(env_path),
      "paths":{str(p):{"present":p.exists(),"mode":oct(p.stat().st_mode & 0o777)[2:] if p.exists() else None}
               for p in map(Path,["/opt/mesflow/runtime","/opt/mesflow/runtime/tutorials","/opt/mesflow/runtime/tutorials/esp-kiosk","/opt/mesflow/runtime/backups"])},
      "disk_available_bytes":shutil.disk_usage("/").free,
    }
    rendered=json.dumps(data,ensure_ascii=False,indent=2)+"\n"
    if args.output: Path(args.output).parent.mkdir(parents=True,exist_ok=True); Path(args.output).write_text(rendered)
    else: print(rendered,end="")
    return 0
if __name__ == "__main__": raise SystemExit(main())

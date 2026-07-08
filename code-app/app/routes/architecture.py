import os
import re
from collections import defaultdict
from fastapi import APIRouter, HTTPException
from app.services.storage import get_vectorstore

router = APIRouter(prefix="/architecture", tags=["Architecture"])

_EXCLUDE = (
    "node_modules", "package-lock", ".git", "__pycache__",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".woff", ".ttf", ".eot", ".otf",
)


def _is_relevant(path: str) -> bool:
    p = path.lower()
    return not any(x in p for x in _EXCLUDE)


_ROUTE_PATTERNS = [
    re.compile(r"(?:router|app|server|route)\s*\.\s*(?:get|post|put|patch|delete|options)\s*\(\s*[\"']([^\"']+)[\"']", re.DOTALL),
    re.compile(r"(?:router|app|server)\.route\s*\(\s*[\"']([^\"']+)[\"']\s*\)", re.DOTALL),
    re.compile(r"(?:app|server|router|express)\s*\.\s*use\s*\(\s*[\"']([^\"']+)[\"']", re.DOTALL),
    re.compile(r"@\w+\.(?:get|post|put|patch|delete)\s*\(\s*[\"']([^\"']+)[\"']"),
    re.compile(r"@route\s*\(\s*[\"']([^\"']+)[\"']"),
    re.compile(r"(?:path|re_path|url)\s*\(\s*[\"']([^\"']+)[\"']"),
    re.compile(r"<Route\s+[^>]*path\s*=\s*[\"']([^\"']+)[\"']", re.DOTALL),
    re.compile(r"path\s*:\s*[\"']([^\"']+)[\"']"),
]

_IMPORT_PATTERNS = [
    re.compile(r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]', re.DOTALL),
    re.compile(r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)', re.DOTALL),
    re.compile(r'from\s+(\S+)\s+import', re.DOTALL),
    re.compile(r'import\s+(\S+)', re.DOTALL),
]

_ENDPOINT_DOMAIN = [
    (r"login|signin|auth|register|signup|logout|forgot|reset|verify|token|refresh|session|oauth|sso", "auth"),
    (r"search|browse|explore|discover|feed|trending|catalog|query|suggest|autocomplete", "search"),
    (r"post|create|upload|submit|publish|share|article|blog|listing|item|product|draft|listing", "content"),
    (r"like|unlike|comment|reply|follow|unfollow|friend|react|vote|rate|rating|review|feedback", "social"),
    (r"favorite|save|bookmark|wishlist|cart|bag|basket|collect|watchlist", "saved"),
    (r"order|checkout|purchase|confirm|cancel|subscribe|subscription|renew|refund|return", "orders"),
    (r"payment|pay|stripe|invoice|billing|wallet|balance|credit|debit|charge|receipt|payout", "payments"),
    (r"notif|alert|activity|notification|announcement|broadcast", "notifications"),
    (r"message|chat|inbox|conversation|dm|mail|email|sms|thread|direct", "messaging"),
    (r"track|delivery|ship|status|health|ping|heartbeat|monitor|log|audit", "status"),
    (r"profile|account|user|setting|preference|avatar|password|me", "profile"),
    (r"admin|dashboard|manage|analytics|moderat|panel|console|super|backoffice", "admin"),
    (r"address|location|shipping|billing|city|state|zip|geo|map|coordinates", "address"),
    (r"upload|image|video|gallery|photo|asset|attachment|media|file|document|thumbnail", "media"),
    (r"report|flag|ban|block|mute|appeal|complaint|spam|abuse|violation", "moderation"),
    (r"tag|category|topic|genre|label|collection|taxonomy|group", "tags"),
    (r"invite|referral|share|promo|coupon|discount|offer|reward|point|badge|achievement|score|level|gamif", "promo"),
    (r"event|calendar|schedule|meetup|appointment|booking|reservation", "events"),
    (r"api.doc|swagger|openapi|graphql|docs|schema|spec", "api"),
    (r"export|import|backup|restore|migrate|sync|archive|clone", "transfer"),
    (r"webhook|cron|hook|callback|job|task|worker|queue|scheduler", "jobs"),
    (r"translate|locale|i18n|l10n|language|localization", "i18n"),
    (r"template|theme|layout|widget|component|block|section", "ui"),
    (r"search|filter|sort|paginate", "search"),
]

_DOMAIN_LABELS = {
    "auth": "Auth",
    "search": "Search",
    "content": "Content",
    "social": "Social",
    "saved": "Saved",
    "orders": "Orders",
    "payments": "Payments",
    "notifications": "Notifications",
    "messaging": "Messaging",
    "status": "Status",
    "profile": "Profile",
    "admin": "Admin",
    "address": "Address",
    "media": "Media",
    "moderation": "Moderation",
    "tags": "Tags",
    "promo": "Promo",
    "events": "Events",
    "api": "API",
    "transfer": "Transfer",
    "jobs": "Jobs",
    "i18n": "i18n",
    "ui": "UI",
}

_SEP = " \u00b7 "

_DOMAIN_ORDER = [
    "auth", "search", "content", "social", "saved", "tags",
    "orders", "payments", "promo",
    "notifications", "messaging",
    "media", "events", "status", "profile", "admin", "moderation",
    "address", "api", "transfer", "jobs", "i18n", "ui",
]

_FRONTEND_EXT = {".jsx", ".tsx", ".html"}
_FRONTEND_HINTS = ("page", "screen", "component", "view")
_BACKEND_HINTS = ("route", "api", "controller", "handler", "service", "model", "middleware")


def _sanitize_label(text: str) -> str:
    s = text.replace('"', "'")
    for ch in ("(", ")", "<", ">", "{", "}", "[", "]", "|", "\\", "`"):
        s = s.replace(ch, "")
    s = s.replace("\r\n", " \u00b7 ").replace("\n", " \u00b7 ").replace("\r", " \u00b7 ")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:160]


def _shorten_route(r: str) -> str:
    parts = [p for p in r.split("/") if p and not p.startswith(":")]
    if not parts:
        return "/"
    short = "/" + parts[-1]
    return short[:30]


def _classify(path: str) -> str:
    for pattern, domain in _ENDPOINT_DOMAIN:
        if re.search(pattern, path, re.IGNORECASE):
            return domain
    return None


def _assign_layer(path: str, is_frontend_path: bool, is_route_file: bool) -> str:
    p = path.lower()
    ext_match = any(p.endswith(e) for e in _FRONTEND_EXT)
    is_frontend = ext_match or any(x in p for x in _FRONTEND_HINTS)
    is_backend = any(x in p for x in _BACKEND_HINTS) or p.endswith((".py", ".js", ".ts"))
    if is_frontend:
        return "frontend"
    if is_backend:
        return "backend"
    return "backend"


def _find_domain_in_path(import_path: str) -> str:
    name = import_path.lower().replace("/", ".").replace("\\", ".")
    for pattern, domain in _ENDPOINT_DOMAIN:
        if re.search(pattern, name, re.IGNORECASE):
            return domain
    return None


def _detect_dependency_edges(domain_files: dict) -> list:
    edges = set()
    for src_domain, file_infos in domain_files.items():
        for finfo in file_infos:
            content = finfo.get("content") or ""
            for pat in _IMPORT_PATTERNS:
                for match in pat.findall(content):
                    imp = match.strip()
                    tgt = _find_domain_in_path(imp)
                    if tgt and tgt != src_domain:
                        edges.add((tgt, src_domain))
    return list(edges)


def _detect_stack(files_contents: dict) -> dict:
    stack = {"frontend": set(), "backend": set(), "database": set(), "other": set()}
    for path, combined in files_contents.items():
        p = path.lower()
        content = " ".join(combined).lower() if combined else ""

        if "package.json" in p:
            if '"react"' in content: stack["frontend"].add("React")
            if '"next"' in content: stack["frontend"].add("Next.js")
            if '"vue"' in content: stack["frontend"].add("Vue")
            if '"angular"' in content: stack["frontend"].add("Angular")
            if '"express"' in content: stack["backend"].add("Express")
            if '"mongoose"' in content: stack["database"].add("MongoDB")
            if '"mongodb"' in content: stack["database"].add("MongoDB")
            if '"pg"' in content or '"postgres"' in content: stack["database"].add("PostgreSQL")
            if '"redis"' in content: stack["database"].add("Redis")
            if '"prisma"' in content: stack["database"].add("Prisma")
            if '"sequelize"' in content or '"typeorm"' in content: stack["database"].add("SQL")
            if '"firebase"' in content: stack["database"].add("Firebase")
            if '"stripe"' in content: stack["other"].add("Stripe")

        if "requirements.txt" in p:
            if "django" in content: stack["backend"].add("Django")
            if "flask" in content: stack["backend"].add("Flask")
            if "fastapi" in content: stack["backend"].add("FastAPI")
            if "psycopg2" in content: stack["database"].add("PostgreSQL")
            if "pymongo" in content: stack["database"].add("MongoDB")
            if "redis" in content: stack["database"].add("Redis")

        if any(x in p for x in ("docker-compose",)):
            if "mongo" in content: stack["database"].add("MongoDB")
            if "postgres" in content: stack["database"].add("PostgreSQL")
            if "redis" in content: stack["database"].add("Redis")

    return {k: sorted(v) for k, v in stack.items() if v}


def _build_file_tree_architecture(doc_ids, vs, stack):
    seen_paths = {}
    for doc_id in doc_ids:
        try:
            doc = vs.docstore.get(doc_id)
        except Exception:
            continue
        if not doc or not hasattr(doc, "metadata"):
            continue
        path = doc.metadata.get("path") or doc.metadata.get("filename")
        if not path:
            continue
        content = doc.page_content or ""
        if path not in seen_paths:
            seen_paths[path] = content

    root_dirs = {}
    for path in seen_paths:
        parts = path.replace("\\", "/").split("/")
        root = parts[0] if len(parts) > 1 else "/"
        if root not in root_dirs:
            root_dirs[root] = {"files": [], "imports": set()}
        root_dirs[root]["files"].append(path)

        content = seen_paths.get(path, "").lower()
        for m in re.finditer(r'(?:import|from)\s+(\S+)', content):
            imp = m.group(1).split(".")[0]
            if imp in root_dirs and imp != root:
                root_dirs[root]["imports"].add(imp)

    all_roots = sorted(root_dirs.keys())
    node_count = 0
    lines = ["graph LR"]

    nodes = {}
    for root in all_roots:
        nid = f"N{node_count}"
        node_count += 1
        fcount = len(root_dirs[root]["files"])
        label = f"{root if root != '/' else 'root'} ({fcount})"
        lines.append(f'    {nid}["{label}"]')
        style = "fill:#0d1d0d,stroke:#34d399,stroke-width:2px" if root in ("frontend", "src", "/") else "fill:#0d0d1d,stroke:#6366f1,stroke-width:2px"
        lines.append(f'    style {nid} {style}')
        nodes[root] = nid

    for root, info in root_dirs.items():
        for dep in info["imports"]:
            if dep in nodes:
                lines.append(f'  {nodes[root]} --> {nodes[dep]}')

    ext_items = stack.get("database", []) + stack.get("other", [])
    ext_nodes = {}
    if ext_items:
        lines.append("  subgraph External")
        for item in ext_items:
            eid = f"E_{item[:6].lower()}"
            lines.append(f'    {eid}[("{item}")]')
            ext_nodes[item] = eid
            lines.append(f'    style {eid} fill:#111122,stroke:#f59e0b,stroke-width:2px')
        lines.append("  end")

    for root, info in root_dirs.items():
        if root in nodes and ext_nodes:
            lines.append(f'  {nodes[root]} --> {next(iter(ext_nodes.values()))}')

    return {
        "mermaid": "\n".join(lines),
        "module_graph": {r: len(root_dirs[r]["files"]) for r in all_roots},
        "layers": {"filesystem": all_roots},
        "entry_points": all_roots[:1],
        "tech": {k: v for k, v in stack.items() if v},
        "modules_found": len(all_roots),
        "dependencies": sum(len(v["imports"]) for v in root_dirs.values()),
    }


@router.post("/clear")
def clear_index():
    from app.services.storage import clear_vectorstore, get_vectorstore
    vs = get_vectorstore()
    count = vs.num_docs if vs and hasattr(vs, "num_docs") else 0
    clear_vectorstore()
    return {"cleared": True, "vectors_removed": count}


@router.post("/debug")
def debug_vectorstore():
    from app.services.storage import get_vectorstore
    vs = get_vectorstore()
    if not vs:
        return {"error": "no vectorstore"}
    return {
        "has_docstore": hasattr(vs, "docstore"),
        "docstore_type": type(vs.docstore).__name__ if hasattr(vs, "docstore") else None,
        "docstore_len": len(vs.docstore) if hasattr(vs, "docstore") else 0,
        "has_index_map": hasattr(vs, "index_to_docstore_id"),
        "index_len": len(vs.index_to_docstore_id) if hasattr(vs, "index_to_docstore_id") else 0,
        "bm25_docs": vs.bm25.num_docs if hasattr(vs, "bm25") else 0,
        "faiss_ntotal": vs.faiss.index.ntotal if hasattr(vs, 'faiss') and hasattr(vs.faiss, 'index') else 0,
    }


@router.post("/generate")
def generate_architecture():
    try:
        vs = get_vectorstore()
        if not vs or not hasattr(vs, "docstore"):
            raise HTTPException(status_code=400, detail="No vectorstore available")

        endpoints = []
        route_file_count = 0
        config_files = {}

        try:
            docstore_size = len(vs.docstore) if vs.docstore else 0
            faiss_size = len(vs.index_to_docstore_id) if hasattr(vs, 'index_to_docstore_id') else 0
            bm25_size = len(vs.bm25.index_to_docstore_id) if hasattr(vs, 'bm25') and hasattr(vs.bm25, 'index_to_docstore_id') else 0
            print(f"[ARCH] docstore={docstore_size} faiss_idx={faiss_size} bm25_idx={bm25_size}")

            doc_ids = list(vs.docstore.keys()) if vs.docstore else list(vs.index_to_docstore_id.values())
            print(f"[ARCH] doc_ids count={len(doc_ids)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read vectorstore index: {e}")

        for doc_id in doc_ids:
            try:
                doc = vs.docstore.get(doc_id)
            except Exception:
                continue
            if not doc or not hasattr(doc, "metadata"):
                continue
            path = doc.metadata.get("path") or doc.metadata.get("filename")
            if not path:
                continue

            content = doc.page_content or ""
            p = path.lower()

            if any(x in p for x in ("package.json", "requirements.txt", "docker-compose")):
                if path not in config_files:
                    config_files[path] = []
                config_files[path].append(content)

            if not _is_relevant(path):
                continue

            is_route_file = any(x in p for x in ("route", "api", "controller", "handler"))
            has_frontend = p.endswith((".jsx", ".tsx")) or any(x in p for x in ("page", "screen", "component"))

            for pattern in _ROUTE_PATTERNS:
                matches = pattern.findall(content)
                for m in matches:
                    endpoints.append((m, _classify(m), is_route_file, path, has_frontend))

            if is_route_file:
                route_file_count += 1

            if has_frontend:
                domain = _classify(path) or _classify(path.replace("-", "/").replace("_", "/"))
                if domain:
                    endpoints.append((path, domain, False, path, True))

        stack = _detect_stack(config_files)

        if not endpoints and not route_file_count:
            return _build_file_tree_architecture(doc_ids, vs, stack)

        domain_info = defaultdict(lambda: {"routes": [], "files": [], "layer": None})
        for ep, domain, is_route, fpath, is_fe in endpoints:
            if domain:
                domain_info[domain]["routes"].append(ep)
                fe = is_fe and not is_route
                if fe:
                    if domain_info[domain]["layer"] != "backend":
                        domain_info[domain]["layer"] = "frontend"
                else:
                    domain_info[domain]["layer"] = "backend"
                domain_info[domain]["files"].append({"path": fpath, "content": None})

        if not domain_info:
            raise HTTPException(status_code=400, detail="Could not identify any functional module")

        file_paths_by_domain = {}
        for d, info in domain_info.items():
            file_paths_by_domain[d] = [f["path"] for f in info["files"]]

        for doc_id in doc_ids:
            try:
                doc = vs.docstore.get(doc_id)
            except Exception:
                continue
            if not doc or not hasattr(doc, "metadata"):
                continue
            path = doc.metadata.get("path") or doc.metadata.get("filename")
            if not path:
                continue
            for domain, paths in file_paths_by_domain.items():
                if path in paths:
                    for f in domain_info[domain]["files"]:
                        if f["path"] == path and f["content"] is None:
                            f["content"] = doc.page_content or ""
                            break
                    break

        domain_files = {}
        for domain, info in domain_info.items():
            domain_files[domain] = info["files"]

        dep_edges = _detect_dependency_edges(domain_files)

        all_domains = sorted(domain_info.keys(), key=lambda d: (_DOMAIN_ORDER.index(d) if d in _DOMAIN_ORDER else 999))

        fe_domains = [d for d in all_domains if domain_info[d]["layer"] == "frontend"]
        be_domains = [d for d in all_domains if domain_info[d]["layer"] != "frontend"]

        entry_domains = set(fe_domains)
        for src, tgt in dep_edges:
            entry_domains.discard(tgt)

        lines = ["graph LR"]
        node_count = 0

        def mk_node(label):
            nonlocal node_count
            nid = f"N{node_count}"
            node_count += 1
            return nid, label

        fe_items = []
        for d in fe_domains:
            title = _DOMAIN_LABELS.get(d, d.replace("_", " ").title())
            routes = sorted(set(domain_info[d]["routes"]))[:2]
            rstr = _SEP.join(_shorten_route(r) for r in routes) if routes else ""
            label = _sanitize_label(f"{title} {_SEP}{rstr}" if rstr else title)
            fe_items.append((d, label))

        be_items = []
        for d in be_domains:
            title = _DOMAIN_LABELS.get(d, d.replace("_", " ").title())
            routes = sorted(set(domain_info[d]["routes"]))[:2]
            rstr = _SEP.join(r for r in routes) if routes else ""
            label = _sanitize_label(f"{title} {_SEP}{rstr}" if rstr else title)
            be_items.append((d, label))

        ext_items = stack.get("database", []) + stack.get("other", [])

        fe_nodes = {}
        if fe_items:
            lines.append("  subgraph Frontend")
            for d, label in fe_items:
                nid = f"N{node_count}"
                node_count += 1
                lines.append(f'    {nid}["{label}"]')
                fe_nodes[d] = nid
                lines.append(f'    style {nid} fill:#0d1d0d,stroke:#34d399,stroke-width:2px')
            lines.append("  end")

        be_nodes = {}
        if be_items:
            lines.append("  subgraph Backend")
            for d, label in be_items:
                nid = f"N{node_count}"
                node_count += 1
                lines.append(f'    {nid}["{label}"]')
                be_nodes[d] = nid
                lines.append(f'    style {nid} fill:#0d0d1d,stroke:#6366f1,stroke-width:2px')
            lines.append("  end")

        ext_nodes = {}
        if ext_items:
            lines.append("  subgraph External")
            for item in ext_items:
                eid = f"E_{item[:6].lower()}"
                elabel = _sanitize_label(item)
                lines.append(f'    {eid}[("{elabel}")]')
                ext_nodes[item] = eid
                lines.append(f'    style {eid} fill:#111122,stroke:#f59e0b,stroke-width:2px')
            lines.append("  end")

        for src, tgt in dep_edges:
            s_nid = fe_nodes.get(src) or be_nodes.get(src)
            t_nid = fe_nodes.get(tgt) or be_nodes.get(tgt)
            if s_nid and t_nid:
                lines.append(f'  {s_nid} --> {t_nid}')

        for fd, fnid in fe_nodes.items():
            if be_nodes:
                target = next(iter(be_nodes.values()))
                lines.append(f'  {fnid} -.-> {target}')

        for bd, bnid in be_nodes.items():
            if ext_nodes:
                first_ext = next(iter(ext_nodes.values()))
                lines.append(f'  {bnid} --> {first_ext}')

        return {
            "mermaid": "\n".join(lines),
            "module_graph": {d: len(domain_info[d]["routes"]) for d in all_domains},
            "layers": {layer: [d for d in all_domains if domain_info[d]["layer"] == layer] for layer in ("frontend", "backend")},
            "entry_points": list(entry_domains),
            "tech": {k: v for k, v in stack.items() if v},
            "modules_found": len(all_domains),
            "dependencies": len(dep_edges),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Architecture generation failed: {e}")

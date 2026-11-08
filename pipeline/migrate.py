import json,os,re,sys,gzip,glob,html,subprocess,hashlib,time,collections
from concurrent.futures import ThreadPoolExecutor
REPO="tomkerem/NAC.MAAGAR"
PREFIX=sys.argv[1]; TAG=sys.argv[2]; OUT=sys.argv[3]; LIMIT=int(sys.argv[4]) if len(sys.argv)>4 else 10**9
MANI=os.environ.get("MANIFEST","manifest/part*.json.gz")
try:
    import pillow_heif; pillow_heif.register_heif_opener()
except Exception: pass
rows=[]
for _f in sorted(glob.glob(MANI)): rows+=json.load(gzip.open(_f,"rt",encoding="utf-8"))
_drop=set(json.load(open("manifest/drop.json"))) if os.path.exists("manifest/drop.json") else set()
rows=[r for r in rows if r["id"] not in _drop]
BIG=2048000
NOACC=set(json.load(open("manifest/noaccess.json"))) if os.path.exists("manifest/noaccess.json") else set()
UNRES=json.load(open("manifest/shortcuts_unres.json")) if os.path.exists("manifest/shortcuts_unres.json") else {}
HAVE=set(open("/tmp/assets.txt").read().split()) if os.path.exists("/tmp/assets.txt") else set()
A=os.path.join(OUT,"archive"); AA=os.path.join(A,"a"); os.makedirs(AA,exist_ok=True)
REL=os.path.join(OUT,"_release"); os.makedirs(REL,exist_ok=True)
CAT={"מדיה וצ׳ופרים":"media","גלופות וסמלים":"glupot","קטלוג השבט":"catalog","פנאטיות":"fanatia","הדרכה":"hadracha","מחנאות":"machanot","ג׳ינגלים":"jingles"}
def ext_of(name,mime):
    e=os.path.splitext(name)[1].lower().lstrip(".")
    return re.sub(r'[^a-z0-9]','',e)[:5] or {"image/jpeg":"jpg","video/mp4":"mp4"}.get(mime,"bin")
# folder ids: stable slug from path
def slug(path): return "f"+hashlib.md5(path.encode()).hexdigest()[:10]
idpath={r["id"]:r["path"] for r in rows}
if PREFIX.startswith("="):
    PREFIX=PREFIX[1:]; sel=[r for r in rows if r["path"].rsplit("/",1)[0]==PREFIX][:LIMIT]
else:
    sel=[r for r in rows if r["path"].startswith(PREFIX)][:LIMIT]
# all folders on the way (to build tree)
folders=set(["/"]) 
children=collections.defaultdict(list)
for r in rows:
    if r["mime"]=="application/vnd.google-apps.folder": folders.add(r["path"])
for r in rows:
    parent=r["path"].rsplit("/",1)[0] or "/"
    children[parent].append(r)
selids={r["id"] for r in sel}
site=lambda r: ("a/%s.%s"%(r["id"],ext_of(r["path"].rsplit("/",1)[1],r["mime"])))
fails=[];stats=collections.Counter()
def dl(url,dest,tries=4):
    for t in range(tries):
        p=subprocess.run(["curl","-sL","--fail","-m","900","-o",dest,url],capture_output=True)
        if p.returncode==0 and os.path.getsize(dest)>0:
            with open(dest,"rb") as f: head=f.read(200)
            if head.lstrip()[:15].lower().startswith(b"<!doctype html") and not dest.endswith(".html"):
                pass_ = False
            else: pass_=True
            if pass_: return True
        time.sleep(2*(t+1))
    return False
def gdl(i,dest): return dl("https://drive.usercontent.google.com/download?id=%s&export=download&confirm=t"%i,dest)
LINKRE=re.compile(r'https?://(?:drive|docs)\.google\.com/[^"\'\s<>)]*')
def rewrite_links(s,hrefprefix=""):
    def sub(m):
        u=html.unescape(m.group(0)); m2=re.search(r'/d/([\w-]{20,})|[?&]id=([\w-]{20,})|/folders/([\w-]{20,})',u)
        if m2:
            i=next(g for g in m2.groups() if g)
            if i in idpath:
                p=idpath[i]; r=next((x for x in rows if x["id"]==i),None)
                if r["mime"]=="application/vnd.google-apps.folder": return hrefprefix+slug(p)+".html"
                if r["mime"]=="application/vnd.google-apps.document": return hrefprefix+"a/%s.html"%i
                return hrefprefix+site(r) if not (r["mime"].startswith(("video/","audio/")) or int(r["size"])>BIG) else rel_url(r)
        stats["drive_links_left"]+=1
        return m.group(0)
    return LINKRE.sub(sub,s)
TAGMAP={}
for _f in glob.glob(os.path.join(A,"tags-*.json")):
    TAGMAP.update(json.load(open(_f)))
def rel_url(r): return "https://github.com/%s/releases/download/%s/%s"%(REPO,TAGMAP.get(r["id"],TAG),os.path.basename(site(r)))
CSS="""body{margin:0;background:#000;color:#fff;font-family:Arial,sans-serif;direction:rtl;text-align:center;padding:20px}
h1{color:red;font-size:26px}h2{color:red}a{color:#fff}.bar a{display:inline-block;border:2px solid red;border-radius:8px;padding:8px 16px;color:red;text-decoration:none;margin:4px}
.card{border:2px solid red;border-radius:12px;background:#111;max-width:700px;margin:12px auto;padding:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;max-width:1000px;margin:12px auto}.grid img{width:100%;height:150px;object-fit:cover;border-radius:8px;border:1px solid red;display:block}
video,audio{max-width:100%}.doc{background:#fff;color:#000;text-align:right;max-width:800px;margin:16px auto;padding:20px;border-radius:8px}.doc *{max-width:100%}
.sub{font-size:13px;color:#aaa}"""
BGCSS="""body{background:#000 url('../bg-%(c)s.jpg') center/cover no-repeat fixed}h1,h2{text-shadow:0 0 6px #000,0 0 3px #000}.card,.grid img{background:rgba(17,17,17,.93)}@media(max-width:600px){body{padding-top:155px;background:linear-gradient(to bottom,rgba(0,0,0,0) 62%%,#000 98%%),url('../bg-%(c)s.jpg') top center/100%% auto no-repeat,#000}}"""
def page(title,body,back,bg=None):
    st=CSS+(BGCSS%{"c":bg} if bg else "")
    return '<!DOCTYPE html><html lang="he" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title><style>%s</style></head><body><div class="bar">%s</div><h1>%s</h1>%s</body></html>'%(html.escape(title),st,back,html.escape(title),body)
def name_of(p): return p.rsplit("/",1)[-1]
# process files
def proc(r):
    p=r["path"];n=name_of(p);m=r["mime"];i=r["id"]
    try:
        if i in NOACC: return
        if m=="application/vnd.google-apps.folder" or m=="application/vnd.google-apps.shortcut": return
        dest=os.path.join(AA,os.path.basename(site(r)))
        if m.startswith("image/"):
            if os.path.exists(os.path.join(AA,i+".jpg")): return
            tmp=dest+".src";
            if not gdl(i,tmp): fails.append(p);return
            from PIL import Image,ImageOps
            try:
                im=ImageOps.exif_transpose(Image.open(tmp)).convert("RGB");im.thumbnail((1000,1000))
                dest=os.path.join(AA,i+".jpg");im.save(dest,quality=62,optimize=True);stats["img"]+=1
            except Exception as e:
                fails.append(p+" (image decode: %s)"%type(e).__name__)
            os.remove(tmp)
        elif m.startswith(("video/","audio/")):
            d=os.path.join(REL,os.path.basename(site(r)))
            if os.path.basename(d) in HAVE: return
            if gdl(i,d): stats["release_files"]+=1
            else: fails.append(p)
        elif m=="application/vnd.google-apps.document":
            d=os.path.join(AA,i+".html")
            if os.path.exists(d): return
            tmp=d+".src"
            if not dl("https://docs.google.com/document/d/%s/export?format=html"%i,tmp): fails.append(p);return
            s=open(tmp,errors="ignore").read();os.remove(tmp)
            mm=re.search(r"<style[^>]*>(.*?)</style>",s,re.S);st=mm.group(1) if mm else ""
            body=re.search(r"<body[^>]*>(.*)</body>",s,re.S).group(1)
            body=rewrite_links(body,"")
            body=re.sub(r'https://www\.google\.com/url\?q=([^&"]+)[^"]*',lambda x:__import__("urllib.parse").parse.unquote(x.group(1)),body)
            open(d,"w").write(page(n,'<div class="doc"><style>%s</style>%s</div>'%(st,body),'<a href="%s.html">חזרה</a>'%slug(p.rsplit("/",1)[0] or "/")));stats["docs"]+=1
        else:
            if int(r["size"])>BIG:
                d=os.path.join(REL,os.path.basename(site(r)))
                if os.path.basename(d) in HAVE: return
                if gdl(i,d): stats["release_files"]+=1
                else: fails.append(p)
            else:
                if os.path.exists(dest): return
                if gdl(i,dest): stats["files"]+=1
                else: fails.append(p)
    except Exception as e: fails.append(p+" (%s)"%e)
files=[r for r in sel if r["mime"] not in("application/vnd.google-apps.folder",)]
with ThreadPoolExecutor(6) as ex: list(ex.map(proc,files))
for r in sel:
    if os.path.exists(os.path.join(REL,os.path.basename(site(r)))): TAGMAP[r["id"]]=TAG
json.dump({r["id"]:TAG for r in sel if os.path.exists(os.path.join(REL,os.path.basename(site(r))))},open(os.path.join(A,"tags-%s.json"%re.sub(r"[^A-Za-z0-9_-]","",TAG)),"w"))
# folder pages: only for folders on selected subtree and its ancestors
def has_sel(fp):
    return any(r["path"].startswith(fp+"/") or r["path"]==fp for r in sel) or PREFIX.startswith(fp+"/") or fp=="/"
for fp in sorted(folders):
    if not (fp=="/" or fp.startswith(PREFIX) or PREFIX.startswith(fp+"/") ): continue
    kids=children.get(fp,[]);body="";imgs=[];sub=[]
    for k in sorted(kids,key=lambda x:x["path"]):
        n=name_of(k["path"]);m=k["mime"]
        if m=="application/vnd.google-apps.folder":
            if True: sub.append('<div class="card"><a href="%s.html">📁 %s</a></div>'%(slug(k["path"]),html.escape(n)))
            continue
        ex=lambda e: os.path.exists(os.path.join(AA,k["id"]+e))
        fn=os.path.exists
        if m.startswith("image/"):
            if os.path.exists(os.path.join(AA,k["id"]+".jpg")): imgs.append('<a href="a/%s.jpg"><img loading="lazy" src="a/%s.jpg" alt="%s"></a>'%(k["id"],k["id"],html.escape(n)))
        elif m.startswith("video/"):
            if k["path"] in fails: continue
            body+='<div class="card"><div>%s</div><video controls preload="none" playsinline src="%s"></video></div>'%(html.escape(n),rel_url(k))
        elif m.startswith("audio/"):
            if k["path"] in fails: continue
            body+='<div class="card"><div>%s</div><audio controls preload="none" src="%s"></audio></div>'%(html.escape(n),rel_url(k))
        elif m=="application/vnd.google-apps.document":
            if not ex(".html"): continue
            body+='<div class="card"><a href="a/%s.html">📄 %s</a></div>'%(k["id"],html.escape(n))
        elif m=="application/vnd.google-apps.shortcut":
            _u=UNRES.get(k["id"])
            body+=('<div class="card sub">⚠ לא הועתק (אין גישה לתיקייה): <a href="%s" target="_blank">%s ↗</a></div>'%(_u,html.escape(n))) if _u else ('<div class="card sub">קיצור דרך: %s</div>'%html.escape(n))
        elif k["id"] in NOACC:
            body+='<div class="card sub">🔒 לא הועתק (הקובץ חסום במקור): %s</div>'%html.escape(n)
        else:
            if int(k["size"])<=BIG and not os.path.exists(os.path.join(AA,os.path.basename(site(k)))): continue
            href=rel_url(k) if int(k["size"])>BIG else "a/"+os.path.basename(site(k))
            body+='<div class="card"><a href="%s">⬇ %s</a><div class="sub">%.1f MB</div></div>'%(href,html.escape(n),k["size"]/1e6)
    if imgs: body+='<div class="grid">%s</div>'%"".join(imgs)
    title=name_of(fp) if fp!="/" else "הארכיון"
    back='<a href="../index.html">מאגר הנשיא</a>'
    parent=fp.rsplit("/",1)[0] or "/"
    if fp!="/" and parent!="/": back+='<a href="%s.html">⬆ %s</a>'%(slug(parent),html.escape(name_of(parent)))
    elif fp!="/": back+='<a href="f_root.html">הארכיון</a>'
    open(os.path.join(A,("f_root" if fp=="/" else slug(fp))+".html"),"w").write(page(title,"".join(sub)+body,back,CAT.get(fp.split("/")[1]) if fp!="/" else None))
json.dump({"stats":stats,"fails":fails},open(os.path.join(OUT,"report.json"),"w"),ensure_ascii=False,indent=1)
print(dict(stats),"fails",len(fails))

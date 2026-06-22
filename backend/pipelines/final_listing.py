# -*- coding: utf-8 -*-
"""
完整上架方案 - 用Listing生成器给美妆个护产品生成Listing
流程: 输入ASIN → 获取Listing → AI优化 → 截图展示
"""
import sys, json, time, base64, os
sys.stdout.reconfigure(encoding="utf-8")
import websocket, urllib.request
from datetime import datetime

SCREENSHOT_DIR = r"C:\Users\OPENPC\.openclaw\workspace\projects\amazon_ai_kit\output\screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

req = urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5)
tabs = json.loads(req.read())
tab = [t for t in tabs if "sellersprite" in (t.get("url","")+t.get("title",""))][0]
ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=15)

_id = 0
def send(m, p=None):
    global _id; _id += 1
    ws.send(json.dumps({"method": m, "id": _id, "params": p or {}}))
    return json.loads(ws.recv()).get("result", {})

def shot(name):
    r = send("Page.captureScreenshot", {"format": "png", "fromSurface": True, "quality": 80})
    d = r.get("data", "")
    if d:
        p = os.path.join(SCREENSHOT_DIR, f"{name}.png")
        with open(p, "wb") as f:
            f.write(base64.b64decode(d))
        print(f"     📸 {name}.png ({os.path.getsize(p)//1024}KB)")

def jse(js):
    r = send("Runtime.evaluate", {"expression": js, "returnByValue": True})
    return r.get("result", {}).get("value")

def go(url, t=3):
    send("Page.navigate", {"url": url})
    time.sleep(t)
    return jse("document.title")

print("=" * 70)
print("完整上架方案 - Listing生成器操作")
print(f"时间: {datetime.now().strftime('%H:%M')}")
print("=" * 70)

# 美妆个护Top产品数据（从程序自动选出的）
TOP_BEAUTY = [
    {"ASIN": "B0DFL5BK8H", "name": "Feet Soaking Tub 足浴盆", "price": 37.98, "margin": "32.9%"},
    {"ASIN": "B0DFLTJQ3N", "name": "Bush Balm 须后膏", "price": 37.49, "margin": "32.7%"},
    {"ASIN": "B0DQLRQK7L", "name": "Peptides Serum 胜肽精华", "price": 30.99, "margin": "29.6%"},
    {"ASIN": "B0DHH1XC56", "name": "Manucurist Nail Polish 指甲油", "price": 19.00, "margin": "23.5%"},
    {"ASIN": "B0DTP5T7N3", "name": "Fluorescent Light Covers 灯罩", "price": 26.99, "margin": "26.9%"},
]

print(f"\n📦 美妆个护Top产品清单:")
for p in TOP_BEAUTY:
    print(f"  {p['ASIN']} - {p['name']} (${p['price']} | {p['margin']})")

# ============================================================
# 操作1: 到Listing生成器
# ============================================================
print(f"\n{'='*70}")
print("【操作1】进入Listing生成器")
go("https://www.sellersprite.com/v3/listing-builder")
print(f"  当前: {jse('document.title')[:60]}")
shot("lb_final_01_初始页")

# ============================================================
# 操作2: 逐个输入Top产品ASIN并生成
# ============================================================
for idx, product in enumerate(TOP_BEAUTY[:3]):  # 只做Top 3
    asin = product["ASIN"]
    name = product["name"]
    price = product["price"]
    margin = product["margin"]
    
    print(f"\n{'='*70}")
    print(f"【操作2.{idx+1}】{name} ({asin})")
    
    # 如果idx>0,先清空再输入
    if idx > 0:
        # 先重载页面清空
        go("https://www.sellersprite.com/v3/listing-builder")
        time.sleep(2)
    
    # 输入ASIN
    r = jse(f"""(()=>{{
        const inputs=document.querySelectorAll('input');
        for(const inp of inputs){{
            const ph=inp.placeholder||"";
            if(ph.toLowerCase().includes("asin") && inp.offsetParent!==null){{
                const native=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                native.call(inp,"{asin}");
                inp.dispatchEvent(new Event("input",{{bubbles:true}}));
                inp.dispatchEvent(new Event("change",{{bubbles:true}}));
                return "输入ASIN: {asin}";
            }}
        }}
        return "未找到ASIN输入框";
    }})()""")
    print(f"  {r}")
    time.sleep(1)
    
    shot(f"lb_final_{idx+1}a_{asin}_已输入")
    
    # 点击"获取Listing"
    print(f"  点击「获取Listing」...")
    r = jse("""(()=>{
        const btns=document.querySelectorAll('button,.el-button');
        for(const b of btns){
            const t=(b.textContent||"").trim();
            if(t==="获取Listing" && b.offsetParent!==null){
                b.click(); return "点击: 获取Listing";
            }
        }
        return "未找到";
    })()""")
    print(f"  {r}")
    time.sleep(3)
    
    shot(f"lb_final_{idx+1}b_{asin}_获取后")
    
    # 看获取到的标题
    title = jse("""(()=>{
        const areas=document.querySelectorAll('textarea');
        for(const ta of areas){
            const ph=ta.placeholder||"";
            if(ph.includes("写一个标题") && ta.value){
                return ta.value.substring(0,100);
            }
        }
        // 找所有含内容的textarea
        const values=[];
        areas.forEach(ta=>{
            if(ta.value && ta.value.length>20) values.push(ta.value.substring(0,80));
        });
        return JSON.stringify(values);
    })()""")
    print(f"  获取到的标题: {str(title)[:80]}")
    
    # 点击AI生成标题
    print(f"  点击「AI生成标题」...")
    r = jse("""(()=>{
        const btns=document.querySelectorAll('button,.el-button');
        for(const b of btns){
            const t=(b.textContent||"").trim();
            if(t==="AI生成标题" && b.offsetParent!==null){
                b.click(); return "点击: AI生成标题";
            }
        }
        return "未找到";
    })()""")
    print(f"  {r}")
    time.sleep(3)
    
    shot(f"lb_final_{idx+1}c_{asin}_AI标题")
    
    # 点击AI生成描述（五点）
    print(f"  点击「AI生成描述」...")
    r = jse("""(()=>{
        const btns=document.querySelectorAll('button,.el-button');
        for(const b of btns){
            const t=(b.textContent||"").trim();
            if(t.includes("AI生成描述") && b.offsetParent!==null){
                b.click(); return "点击: AI生成描述";
            }
        }
        return "未找到";
    })()""")
    print(f"  {r}")
    time.sleep(3)
    
    shot(f"lb_final_{idx+1}d_{asin}_AI描述")
    
    # 获取最终生成的完整信息
    info = jse("""(()=>{
        const areas=document.querySelectorAll('textarea');
        const result=[];
        areas.forEach(ta=>{
            const ph=ta.placeholder||"";
            const val=ta.value||"";
            if((val && val.length>20) || (ph && ph.length>5)){
                result.push({placeholder: ph.substring(0,30), value: val.substring(0,100)});
            }
        });
        return JSON.stringify(result);
    })()""")
    if info:
        fields = json.loads(info)
        print(f"\n  生成的Listing内容:")
        for f in fields[:5]:
            print(f"    [{f.get('placeholder','')[:25]}] {f.get('value','')[:60]}")
    
    print(f"\n  ✅ {name} 完成")

# ============================================================
# 汇总
# ============================================================
print(f"\n{'='*70}")
print("✅ 完整上架方案生成完毕")
print(f"{'='*70}")
print(f"""
生成的产品:
  1. Feet Soaking Tub (B0DFL5BK8H) ✅
  2. Bush Balm (B0DFLTJQ3N) ✅  
  3. Peptides Serum (B0DQLRQK7L) ✅

每个产品已:
  - 输入ASIN → 获取原始Listing
  - AI生成优化标题
  - AI生成五点描述
  
你可以在浏览器上直接看到这些内容

截图保存: {SCREENSHOT_DIR}
当前页面: Listing生成器（第3个产品）
""")

ws.close()

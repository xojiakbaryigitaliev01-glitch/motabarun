# 📁 FAYL: main.py  →  asosiy papkada (bot.py, db.py yoniga). Server shu fayldan ishga tushadi.
import hashlib
import hmac
import html
import json
import os
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl

from aiogram.types import MenuButtonWebApp, Update, WebAppInfo
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
from bot import BASE, BOT_TOKEN, bot, dp

HERE = os.path.dirname(os.path.abspath(__file__))
SECRET = os.getenv("WEBHOOK_SECRET", "motabar_secret_2026")
GROUP_ID = int(os.getenv("GROUP_ID", "0") or 0)


@asynccontextmanager
async def lifespan(app):
    await db.init()
    if BASE:
        await bot.set_webhook(f"{BASE}/webhook", secret_token=SECRET, drop_pending_updates=True)
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="🛒 Do'kon", web_app=WebAppInfo(url=BASE)))
    yield
    await bot.session.close()


app = FastAPI(lifespan=lifespan)
os.makedirs(f"{HERE}/static/img", exist_ok=True)
app.mount("/img", StaticFiles(directory=f"{HERE}/static/img"), name="img")


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"ok": True}


@app.get("/")
async def index():
    return FileResponse(f"{HERE}/static/index.html", headers={"Cache-Control": "no-cache"})


@app.post("/webhook")
async def webhook(req: Request, x_telegram_bot_api_secret_token: str = Header(None)):
    if x_telegram_bot_api_secret_token != SECRET:
        raise HTTPException(403)
    await dp.feed_update(bot, Update.model_validate(await req.json(), context={"bot": bot}))
    return {"ok": True}


@app.get("/api/config")
async def config():
    g = os.getenv
    return {"operator": g("OPERATOR", "optom_unchi"), "channel": g("CHANNEL", "motabar_andijon"),
            "instagram": g("INSTAGRAM", "motabar_unmarkazi"), "lat": g("LAT", "40.830129"), "lon": g("LON", "72.352841")}


@app.get("/api/products")
async def products():
    return [{"id": p["id"], "name": p["name"], "cat": p["cat"], "price": p["price"], "descr": p["descr"],
             "weight": p.get("weight") or "50 kg",
             "img": f"/api/img/{p['id']}?v={p['photo'][-8:]}" if p["photo"] else (p.get("img") or "")} for p in await db.products()]


_cache = {}


@app.get("/api/img/{pid}")
async def img(pid: int):
    p = await db.get(pid)
    if not p or not p["photo"]:
        raise HTTPException(404)
    if p["photo"] not in _cache:
        f = await bot.get_file(p["photo"])
        _cache[p["photo"]] = (await bot.download_file(f.file_path)).read()
    return Response(_cache[p["photo"]], media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


def check_init(init_data: str):
    """Telegram initData imzosini tekshiradi (soxta zakazlardan himoya)."""
    try:
        d = dict(parse_qsl(init_data, keep_blank_values=True))
        h = d.pop("hash", "")
        s = "\n".join(f"{k}={v}" for k, v in sorted(d.items()))
        key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        if hmac.compare_digest(hmac.new(key, s.encode(), hashlib.sha256).hexdigest(), h):
            return json.loads(d["user"])
    except Exception:
        pass
    return None


class Item(BaseModel):
    id: int
    qty: int


class Order(BaseModel):
    initData: str = ""
    name: str
    phone: str
    address: str
    comment: str = ""
    items: list[Item]


@app.post("/api/order")
async def order(o: Order):
    u = check_init(o.initData)
    if not u:
        raise HTTPException(401, "Iltimos, do'konni Telegram bot orqali oching")
    if not GROUP_ID:
        raise HTTPException(500, "GROUP_ID sozlanmagan (admin bilan bog'laning)")
    prods = {p["id"]: p for p in await db.by_ids([i.id for i in o.items])}
    lines, total, snap = [], 0, []
    for i in o.items:
        p = prods.get(i.id)
        if not p or not 0 < i.qty <= 1000:
            continue
        s = p["price"] * i.qty
        total += s
        snap.append({"id": p["id"], "name": p["name"], "qty": i.qty, "price": p["price"]})
        lines.append(f"• <b>{html.escape(p['name'])}</b> ({html.escape(p['cat'])}, {html.escape(p.get('weight') or '50 kg')}) × {i.qty} = {s:,} so'm".replace(",", " "))
    if not lines:
        raise HTTPException(400, "Savat bo'sh yoki mahsulotlar topilmadi")
    e = html.escape
    oid = await db.new_order(u["id"], {"name": o.name, "phone": o.phone, "address": o.address, "items": snap}, total)
    who = f'<a href="tg://user?id={u["id"]}">{e(u.get("first_name", "Mijoz"))}</a>' + (f' (@{u["username"]})' if u.get("username") else "")
    text = (f"🛒 <b>YANGI ZAKAZ №{oid}</b>\n\n👤 {e(o.name)}\n💬 {who}\n📞 {e(o.phone)}\n📍 {e(o.address)}\n"
            + (f"📝 {e(o.comment)}\n" if o.comment.strip() else "") + "\n" + "\n".join(lines)
            + f"\n\n💰 <b>Jami: {total:,} so'm</b>".replace(",", " "))
    try:
        await bot.send_message(GROUP_ID, text)
    except Exception:
        raise HTTPException(500, "Zakazni guruhga yuborib bo'lmadi. Bot guruhda borligini tekshiring")
    try:
        await bot.send_message(u["id"], f"✅ <b>Zakaz №{oid} qabul qilindi!</b>\nJami: {total:,} so'm\nOperator tez orada bog'lanadi.".replace(",", " "))
    except Exception:
        pass
    return {"ok": True, "order_id": oid, "total": total}

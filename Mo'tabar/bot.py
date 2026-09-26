# 📁 FAYL: bot.py  →  asosiy papkaga (main.py yoniga)
# Telegram bot: /start, /id va ADMIN PANEL (un qo'shish, o'chirish, narx o'zgartirish).
import os
import re
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (InlineKeyboardButton as IB, InlineKeyboardMarkup as IM, KeyboardButton,
                           ReplyKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo)
import db

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMINS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}
BASE = (os.getenv("BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
admin = Router()
user = Router()
admin.message.filter(F.from_user.id.in_(ADMINS))
admin.callback_query.filter(F.from_user.id.in_(ADMINS))


class Add(StatesGroup):
    name = State()
    cat = State()
    price = State()
    weight = State()
    descr = State()
    photo = State()


class Price(StatesGroup):
    val = State()


def num(t):
    d = re.sub(r"\D", "", t or "")
    return int(d) if d else 0


def menu():
    return IM(inline_keyboard=[
        [IB(text="➕ Un qo'shish", callback_data="add")],
        [IB(text="🗑 Un o'chirish", callback_data="list:del"), IB(text="💰 Narxni o'zgartirish", callback_data="list:price")],
        [IB(text="📊 Statistika", callback_data="stats")],
    ])


# ---------------- ODDIY FOYDALANUVCHI ----------------
@user.message(Command("start"))
async def start(m):
    kb = IM(inline_keyboard=[[IB(text="🛒 Do'konni ochish", web_app=WebAppInfo(url=BASE))]])
    await m.answer("🌾 <b>Mo'tabar Un Markazi</b>ga xush kelibsiz!\n\nSifatli un — to'g'ridan-to'g'ri ombordan. "
                   "Katalogni ochish uchun tugmani bosing 👇", reply_markup=kb)
    if m.from_user.id in ADMINS:
        await m.answer("👑 Siz adminsiz. Boshqaruv: /admin")


@user.message(Command("id"))
async def get_id(m):
    await m.answer(f"👤 Sizning ID: <code>{m.from_user.id}</code>\n💬 Chat ID: <code>{m.chat.id}</code>")


# ---------------- ADMIN ----------------
@admin.message(Command("admin"))
async def admin_menu(m, state: FSMContext):
    await state.clear()
    await m.answer("🛠 <b>Admin panel</b>", reply_markup=menu())


@admin.message(Command("seed"))
async def seed_cmd(m):
    await db.seed()
    await m.answer("✅ Boshlang'ich unlar qo'shildi/yangilandi.", reply_markup=menu())


@admin.message(Command("cancel"))
async def cancel(m, state: FSMContext):
    await state.clear()
    await m.answer("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    await m.answer("🛠 <b>Admin panel</b>", reply_markup=menu())


@admin.callback_query(F.data == "add")
async def add_start(c, state: FSMContext):
    await state.set_state(Add.name)
    await c.message.answer("1/5 ✏️ Un nomini yozing (masalan: <b>MO'TABAR</b>)\n\nBekor qilish: /cancel")
    await c.answer()


@admin.message(Add.name, F.text)
async def add_name(m, state: FSMContext):
    await state.update_data(name=m.text.strip())
    cats = await db.cats()
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x)] for x in cats], resize_keyboard=True,
                             one_time_keyboard=True) if cats else None
    await state.set_state(Add.cat)
    await m.answer("2/5 🏷 Un <b>navini</b> yozing (masalan: <b>1-navli un</b>).\nMavjud navni tanlang yoki yangisini yozing — "
                   "yangi nav katalogda avtomatik paydo bo'ladi.", reply_markup=kb)


@admin.message(Add.cat, F.text)
async def add_cat(m, state: FSMContext):
    await state.update_data(cat=m.text.strip())
    await state.set_state(Add.price)
    await m.answer("3/5 💰 50 kg qop narxini yozing (faqat raqam, masalan: <b>295000</b>)", reply_markup=ReplyKeyboardRemove())


@admin.message(Add.price, F.text)
async def add_price(m, state: FSMContext):
    p = num(m.text)
    if p < 1:
        return await m.answer("⚠️ Narxni raqam bilan yozing. Masalan: 295000")
    await state.update_data(price=p)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="50 kg"), KeyboardButton(text="25 kg")],
                                       [KeyboardButton(text="1 kg")]], resize_keyboard=True, one_time_keyboard=True)
    await state.set_state(Add.weight)
    await m.answer("4/6 ⚖️ Qop og'irligini yozing yoki tanlang (masalan: <b>50 kg</b>)", reply_markup=kb)


@admin.message(Add.weight, F.text)
async def add_weight(m, state: FSMContext):
    await state.update_data(weight=m.text.strip())
    await state.set_state(Add.descr)
    await m.answer("5/6 📝 Qisqa tavsif yozing (o'tkazib yuborish uchun <b>-</b> yuboring)", reply_markup=ReplyKeyboardRemove())


@admin.message(Add.descr, F.text)
async def add_descr(m, state: FSMContext):
    await state.update_data(descr="" if m.text.strip() == "-" else m.text.strip())
    await state.set_state(Add.photo)
    await m.answer("6/6 🖼 Un rasmini yuboring (o'tkazib yuborish uchun <b>-</b> yuboring)")


async def finish(m, state, photo):
    d = await state.get_data()
    pid = await db.add(d["name"], d["cat"], d["price"], d.get("weight", "50 kg"), d.get("descr", ""), photo)
    await state.clear()
    await m.answer(f"✅ <b>{d['name']}</b> qo'shildi! (№{pid})\n{d['cat']} • {d['weight']} • {d['price']:,} so'm".replace(",", " "), reply_markup=menu())


@admin.message(Add.photo, F.photo)
async def add_photo(m, state: FSMContext):
    await finish(m, state, m.photo[-1].file_id)


@admin.message(Add.photo, F.text == "-")
async def add_nophoto(m, state: FSMContext):
    await finish(m, state, "")


@admin.callback_query(F.data.startswith("list:"))
async def lst(c):
    mode = c.data.split(":")[1]
    ps = await db.products()
    if not ps:
        await c.message.answer("Hozircha un yo'q.", reply_markup=menu())
        return await c.answer()
    icon = "🗑" if mode == "del" else "💰"
    kb = IM(inline_keyboard=[[IB(text=f"{icon} {p['name']} • {p['cat']} • {p['weight']} • {p['price']:,}".replace(",", " "),
                                 callback_data=f"{mode}:{p['id']}")] for p in ps])
    await c.message.answer("Tanlang:", reply_markup=kb)
    await c.answer()


@admin.callback_query(F.data.startswith("del:"))
async def ask_del(c):
    pid = int(c.data.split(":")[1])
    kb = IM(inline_keyboard=[[IB(text="✅ Ha, o'chirish", callback_data=f"delok:{pid}"), IB(text="↩️ Yo'q", callback_data="x")]])
    await c.message.answer("Rostdan o'chirilsinmi?", reply_markup=kb)
    await c.answer()


@admin.callback_query(F.data.startswith("delok:"))
async def do_del(c):
    await db.delete(int(c.data.split(":")[1]))
    await c.message.edit_text("🗑 O'chirildi. Do'konda darhol yo'qoladi.", reply_markup=menu())
    await c.answer()


@admin.callback_query(F.data == "x")
async def close(c):
    await c.message.delete()
    await c.answer()


@admin.callback_query(F.data.startswith("price:"))
async def ask_price(c, state: FSMContext):
    await state.set_state(Price.val)
    await state.update_data(pid=int(c.data.split(":")[1]))
    await c.message.answer("💰 Yangi narxni yozing (masalan: 300000). Bekor qilish: /cancel")
    await c.answer()


@admin.message(Price.val, F.text)
async def set_price(m, state: FSMContext):
    p = num(m.text)
    if p < 1:
        return await m.answer("⚠️ Narxni raqam bilan yozing.")
    d = await state.get_data()
    await db.set_price(d["pid"], p)
    await state.clear()
    await m.answer("✅ Narx yangilandi.", reply_markup=menu())


@admin.callback_query(F.data == "stats")
async def stats(c):
    s = await db.stats()
    await c.message.answer(f"📊 Jami zakazlar: <b>{s['n']}</b>\n📅 Bugun: <b>{s['today']}</b>\n💰 Jami summa: <b>{int(s['s']):,} so'm</b>".replace(",", " "))
    await c.answer()


dp.include_router(admin)
dp.include_router(user)

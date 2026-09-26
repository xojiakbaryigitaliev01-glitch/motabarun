# 📁 FAYL: db.py  →  asosiy papkaga (main.py yoniga)
# Ma'lumotlar bazasi (Neon Postgres). Render'ning fayl tizimi vaqtinchalik, shuning uchun tashqi baza ishlatamiz.
import os
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

DSN = os.environ["DATABASE_URL"]


async def q(sql, args=(), fetch=None):
    async with await psycopg.AsyncConnection.connect(DSN, row_factory=dict_row, autocommit=True) as c:
        cur = await c.execute(sql, args)
        if fetch == "all":
            return await cur.fetchall()
        if fetch == "one":
            return await cur.fetchone()


# Boshlang'ich unlar. Format: (nomi, navi, narxi, tavsif, rasm fayli static/img ichida)
SEED = [
    ("MO'TABAR", "1-navli un", 295000, "50 kg", "Qozog'istonda ishlab chiqarilgan 1-navli yuqori sifatli un", "motabar 1s.jpg"),
    ("MO'TABAR", "2-navli un", 250000, "50 kg", "Qozog'istonda ishlab chiqarilgan 2-navli ishonchli un", "motabar 2s.jpg"),
    ("QADIMGI-NAV", "Qadimgi-nav", 130000, "50 kg", "An'anaviy usulda tayyorlangan qadimgi nav un", "corner.jpg"),
    ("ADMIRAL", "1-navli un", 280000, "50 kg", "Yuqori navli premium un", "motabar vs.jpg"),
]


async def seed():
    """Boshlang'ich unlarni qo'shadi (bor bo'lsa faqat rasmi va og'irligini yangilaydi)."""
    for n, c, pr, w, d, im in reversed(SEED):  # birinchisi eng tepada chiqishi uchun oxirida qo'shiladi
        r = await q("SELECT id FROM products WHERE name=%s AND cat=%s", (n, c), "one")
        if r:
            await q("UPDATE products SET img=%s, weight=%s WHERE id=%s", (im, w, r["id"]))
        else:
            await q("INSERT INTO products(name,cat,price,weight,descr,img) VALUES(%s,%s,%s,%s,%s,%s)", (n, c, pr, w, d, im))


async def init():
    await q("""CREATE TABLE IF NOT EXISTS products(
        id SERIAL PRIMARY KEY, name TEXT NOT NULL, cat TEXT NOT NULL, price INT NOT NULL,
        descr TEXT DEFAULT '', photo TEXT DEFAULT '', created TIMESTAMP DEFAULT now())""")
    await q("ALTER TABLE products ADD COLUMN IF NOT EXISTS img TEXT DEFAULT ''")
    await q("ALTER TABLE products ADD COLUMN IF NOT EXISTS weight TEXT DEFAULT '50 kg'")
    if (await q("SELECT COUNT(*) AS n FROM products", fetch="one"))["n"] == 0:
        await seed()
    await q("""CREATE TABLE IF NOT EXISTS orders(
        id SERIAL PRIMARY KEY, uid BIGINT, data JSONB, total BIGINT, created TIMESTAMP DEFAULT now())""")


async def products():  # eng yangisi tepada
    return await q("SELECT * FROM products ORDER BY id DESC", fetch="all")


async def by_ids(ids):
    return await q("SELECT * FROM products WHERE id = ANY(%s)", (list(ids),), "all")


async def cats():
    r = await q("SELECT DISTINCT cat FROM products ORDER BY cat", fetch="all")
    return [x["cat"] for x in r]


async def add(name, cat, price, weight, descr, photo):
    r = await q("INSERT INTO products(name,cat,price,weight,descr,photo) VALUES(%s,%s,%s,%s,%s,%s) RETURNING id",
                (name, cat, price, weight, descr, photo), "one")
    return r["id"]


async def delete(pid):
    await q("DELETE FROM products WHERE id=%s", (pid,))


async def set_price(pid, price):
    await q("UPDATE products SET price=%s WHERE id=%s", (price, pid))


async def get(pid):
    return await q("SELECT * FROM products WHERE id=%s", (pid,), "one")


async def new_order(uid, data, total):
    r = await q("INSERT INTO orders(uid,data,total) VALUES(%s,%s,%s) RETURNING id", (uid, Json(data), total), "one")
    return r["id"]


async def stats():
    return await q("""SELECT COUNT(*) AS n, COALESCE(SUM(total),0) AS s,
        COUNT(*) FILTER (WHERE created::date = now()::date) AS today FROM orders""", fetch="one")

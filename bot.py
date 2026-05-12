import asyncio
import os
import logging
import aiosqlite
from collections import defaultdict
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

FLAGS = {
    "Moldova": "🇲🇩", "Serbia": "🇷🇸", "Greece": "🇬🇷", "Hungary": "🇭🇺",
    "Spain": "🇪🇸", "Ireland": "🇮🇪", "Finland": "🇫🇮", "Croatia": "🇭🇷",
    "Estonia": "🇪🇪", "Germany": "🇩🇪", "Lithuania": "🇱🇹", "Portugal": "🇵🇹",
    "San Marino": "🇸🇲", "Poland": "🇵🇱", "Montenegro": "🇲🇪", "Bulgaria": "🇧🇬",
    "Azerbaijan": "🇦🇿", "Romania": "🇷🇴", "Luxembourg": "🇱🇺", "Czechia": "🇨🇿",
    "Armenia": "🇦🇲", "Switzerland": "🇨🇭", "Cyprus": "🇨🇾", "Latvia": "🇱🇻",
    "Denmark": "🇩🇰", "Australia": "🇦🇺", "Ukraine": "🇺🇦", "Albania": "🇦🇱",
    "Malta": "🇲🇹", "Norway": "🇳🇴",
}

def get_flag(country_full_name):
    country_name = country_full_name.split(" - ")[0].strip()
    return FLAGS.get(country_name, "🏳️")

class Voting(StatesGroup):
    choosing_list = State()
    choosing_country = State()
    entering_name = State()
    entering_performance = State()
    entering_singing = State()
    entering_overall = State()

async def init_db():
    async with aiosqlite.connect("scoreboard.db") as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS lists (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            locked INTEGER NOT NULL DEFAULT 0
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS countries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id TEXT NOT NULL,
            full_name TEXT NOT NULL,
            FOREIGN KEY(list_id) REFERENCES lists(id)
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS scores (
            username TEXT NOT NULL,
            country_id INTEGER NOT NULL,
            performance INTEGER NOT NULL,
            singing INTEGER NOT NULL,
            overall INTEGER NOT NULL,
            UNIQUE(username, country_id),
            FOREIGN KEY(country_id) REFERENCES countries(id)
        )''')
        cursor = await db.execute("SELECT COUNT(*) FROM lists")
        count = (await cursor.fetchone())[0]
        if count == 0:
            await db.execute("INSERT INTO lists (id, name, locked) VALUES ('semi1','First Semi-Final',0)")
            await db.execute("INSERT INTO lists (id, name, locked) VALUES ('semi2','Second Semi-Final',0)")
            await db.execute("INSERT INTO lists (id, name, locked) VALUES ('final','Final',1)")

            semi1 = [
                "Moldova - Viva, Moldova!",
                "Serbia - My System",
                "Greece - Andromeda",
                "Hungary - Ferto",
                "Spain - Rosa",
                "Ireland - On Replay",
                "Finland - Liekinheitin",
                "Croatia - Nova Zora",
                "Estonia - To Epic To Be True",
                "Germany - Michelle",
                "Lithuania - Dancing on the Ice",
                "Portugal - Sólo Quiero Más",
                "San Marino - Superstar",
                "Poland - Pray",
                "Montenegro - Kraj mene",
            ]
            for c in semi1:
                await db.execute("INSERT INTO countries (list_id, full_name) VALUES ('semi1',?)", (c,))

            semi2 = [
                "Bulgaria - DARA - BANGARANGA",
                "Azerbaijan - JIVA - JUST GO",
                "Romania - ALEXANDRA CĂPITĂNESCU - CHOKE ME",
                "Luxembourg - EVA MARIJA - MOTHER NATURE",
                "Czechia - DANIEL ZIZKA - CROSSROADS",
                "Armenia - SIMON - PALOMA RUMBA",
                "Switzerland - VERONICA FUSARO - ALICE",
                "Cyprus - ANTIGONI - JALLA",
                "Latvia - ATVARA - ĒNĀ",
                "Denmark - SØREN TORPEGAARD LUND - FØR VI GÅR HJEM",
                "Australia - DELTA GOODREM - ECLIPSE",
                "Ukraine - LELEKA - RIDNYM",
                "Albania - ALIS - NÄN",
                "Malta - AIDAN - BELLA",
                "Norway - JONAS LOVV - YA YA YA",
            ]
            for c in semi2:
                await db.execute("INSERT INTO countries (list_id, full_name) VALUES ('semi2',?)", (c,))
        await db.commit()

async def get_unlocked_lists():
    async with aiosqlite.connect("scoreboard.db") as db:
        cursor = await db.execute("SELECT id, name FROM lists WHERE locked=0")
        return await cursor.fetchall()

async def get_countries_of_list(list_id):
    async with aiosqlite.connect("scoreboard.db") as db:
        cursor = await db.execute("SELECT id, full_name FROM countries WHERE list_id=?", (list_id,))
        return await cursor.fetchall()

def split_text(text, max_len=4000):
    parts = []
    while len(text) > max_len:
        split_at = text.rfind('\n', 0, max_len)
        if split_at == -1:
            split_at = max_len
        parts.append(text[:split_at])
        text = text[split_at:].lstrip('\n')
    parts.append(text)
    return parts

async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    admin_sessions = set()

    # ══════════════════════════════════════════════
    # АДМИН-КОМАНДЫ (до всех остальных обработчиков)
    # ══════════════════════════════════════════════

    def is_admin(user_id):
        return user_id in admin_sessions

    @dp.message(Command("admin_logout"))
    async def admin_logout(message: Message):
        if message.from_user.id in admin_sessions:
            admin_sessions.discard(message.from_user.id)
            await message.answer("👋 Вы вышли из режима администратора.")
        else:
            await message.answer("❌ Вы не входили как администратор.")

    @dp.message(Command("lock"))
    async def lock_list(message: Message):
        if not is_admin(message.from_user.id):
            await message.answer("⛔ Сначала войдите как администратор (отправьте пароль).")
            return
        try:
            parts = message.text.split()
            if len(parts) != 2:
                raise ValueError
            list_id = parts[1]
            if list_id not in ('semi1', 'semi2', 'final'):
                raise ValueError
            async with aiosqlite.connect("scoreboard.db") as db:
                await db.execute("UPDATE lists SET locked=1 WHERE id=?", (list_id,))
                await db.commit()
            names = {"semi1": "First Semi-Final", "semi2": "Second Semi-Final", "final": "Final"}
            await message.answer(f"🔒 Список «{names.get(list_id, list_id)}» заблокирован.")
        except:
            await message.answer("⚠️ Используйте: /lock semi1")

    @dp.message(Command("unlock"))
    async def unlock_list(message: Message):
        if not is_admin(message.from_user.id):
            await message.answer("⛔ Сначала войдите как администратор (отправьте пароль).")
            return
        try:
            parts = message.text.split()
            if len(parts) != 2:
                raise ValueError
            list_id = parts[1]
            if list_id not in ('semi1', 'semi2', 'final'):
                raise ValueError
            async with aiosqlite.connect("scoreboard.db") as db:
                await db.execute("UPDATE lists SET locked=0 WHERE id=?", (list_id,))
                await db.commit()
            names = {"semi1": "First Semi-Final", "semi2": "Second Semi-Final", "final": "Final"}
            await message.answer(f"🔓 Список «{names.get(list_id, list_id)}» разблокирован.")
        except:
            await message.answer("⚠️ Используйте: /unlock semi1")

    @dp.message(Command("del_user"))
    async def delete_user_scores(message: Message):
        if not is_admin(message.from_user.id):
            await message.answer("⛔ Сначала войдите как администратор.")
            return
        try:
            parts = message.text.split(" ", 1)
            if len(parts) < 2:
                raise ValueError
            username = parts[1].strip()
            if not username:
                raise ValueError
            async with aiosqlite.connect("scoreboard.db") as db:
                cursor = await db.execute("DELETE FROM scores WHERE username=?", (username,))
                deleted = cursor.rowcount
                await db.commit()
            if deleted > 0:
                await message.answer(f"🗑️ Удалено {deleted} оценок пользователя {username}")
            else:
                await message.answer(f"❌ Пользователь {username} не найден.")
        except:
            await message.answer("⚠️ Используйте: /del_user Alex")

    @dp.message(Command("del_country"))
    async def delete_country_scores(message: Message):
        if not is_admin(message.from_user.id):
            await message.answer("⛔ Сначала войдите как администратор.")
            return
        try:
            parts = message.text.split(" ", 1)
            if len(parts) < 2:
                raise ValueError
            country_name = parts[1].strip()
            if not country_name:
                raise ValueError
            async with aiosqlite.connect("scoreboard.db") as db:
                cursor = await db.execute(
                    "SELECT id, full_name FROM countries WHERE full_name LIKE ?",
                    (f"%{country_name}%",)
                )
                countries = await cursor.fetchall()
                if not countries:
                    await message.answer(f"❌ Страна '{country_name}' не найдена.")
                    return
                total_deleted = 0
                for country_id, full_name in countries:
                    cursor = await db.execute("DELETE FROM scores WHERE country_id=?", (country_id,))
                    total_deleted += cursor.rowcount
                await db.commit()
            await message.answer(f"🗑️ Удалено {total_deleted} оценок для '{country_name}'")
        except:
            await message.answer("⚠️ Используйте: /del_country Moldova")

    @dp.message(Command("del_all"))
    async def delete_all_scores(message: Message):
        if not is_admin(message.from_user.id):
            await message.answer("⛔ Сначала войдите как администратор.")
            return
        try:
            async with aiosqlite.connect("scoreboard.db") as db:
                cursor = await db.execute("SELECT COUNT(*) FROM scores")
                count = (await cursor.fetchone())[0]
                await db.execute("DELETE FROM scores")
                await db.commit()
            await message.answer(f"🗑️ Удалены ВСЕ оценки ({count} шт.).")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")

    @dp.message(Command("reset_db"))
    async def reset_database(message: Message):
        if not is_admin(message.from_user.id):
            await message.answer("⛔ Сначала войдите как администратор.")
            return
        try:
            if "confirm" not in message.text:
                await message.answer(
                    "⚠️ ВНИМАНИЕ! Это удалит ВСЕ оценки и списки.\n"
                    "Для подтверждения: /reset_db confirm"
                )
                return
            async with aiosqlite.connect("scoreboard.db") as db:
                await db.execute("DROP TABLE IF EXISTS scores")
                await db.execute("DROP TABLE IF EXISTS countries")
                await db.execute("DROP TABLE IF EXISTS lists")
                await db.commit()
            await init_db()
            await message.answer("🔄 База данных полностью сброшена и пересоздана.")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")

    # ══════════════════════════════════════════════
    # ГЛАВНОЕ МЕНЮ
    # ══════════════════════════════════════════════

    @dp.message(Command("start"))
    async def cmd_start(message: Message, state: FSMContext):
        await state.clear()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎤 Голосовать", callback_data="menu_vote")],
            [InlineKeyboardButton(text="📊 Все оценки", callback_data="menu_scores")],
            [InlineKeyboardButton(text="🏆 Топ-10", callback_data="menu_top10")],
            [InlineKeyboardButton(text="🔑 Администрирование", callback_data="menu_admin")]
        ])
        await message.answer(
            "🎶 Добро пожаловать на <b>Eurovision 2026 Scorecard</b>!\n\n"
            "📋 <i>First Semi-Final</i> — 15 песен\n"
            "📋 <i>Second Semi-Final</i> — 15 песен\n"
            "🏆 <i>Final</i> — появится позже\n\n"
            "Выберите действие:",
            parse_mode="HTML", reply_markup=kb
        )

    @dp.message(Command("cancel"))
    @dp.message(F.text.lower() == "отмена")
    async def cmd_cancel(message: Message, state: FSMContext):
        await state.clear()
        await message.answer("❌ Действие отменено.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_start")]
        ]))

    @dp.callback_query(F.data == "menu_start")
    async def back_to_start(call: CallbackQuery, state: FSMContext):
        await state.clear()
        await cmd_start(call.message, state)
        await call.answer()

    # ══════════════════════════════════════════════
    # ГОЛОСОВАНИЕ
    # ══════════════════════════════════════════════

    @dp.callback_query(F.data == "menu_vote")
    async def start_vote(call: CallbackQuery, state: FSMContext):
        await state.clear()
        unlocked = await get_unlocked_lists()
        if not unlocked:
            await call.message.edit_text("🔒 Все списки заблокированы.")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"votelist_{list_id}")] for list_id, name in unlocked
        ] + [[InlineKeyboardButton(text="❌ Отмена", callback_data="menu_start")]])
        await call.message.edit_text("📋 Выберите список:", reply_markup=kb)
        await state.set_state(Voting.choosing_list)
        await call.answer()

    @dp.callback_query(F.data.startswith("votelist_"), Voting.choosing_list)
    async def list_chosen(call: CallbackQuery, state: FSMContext):
        list_id = call.data.split("_", 1)[1]
        await state.update_data(list_id=list_id)
        countries = await get_countries_of_list(list_id)
        buttons = []
        for cid, name in countries:
            flag = get_flag(name)
            if " - " in name:
                parts = name.split(" - ", 1)
                display = f"{flag} {parts[0]} — {parts[1]}"
            else:
                display = f"{flag} {name}"
            buttons.append([InlineKeyboardButton(text=display, callback_data=f"country_{cid}")])
        buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_vote")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await call.message.edit_text("🎤 Выберите страну и песню:", reply_markup=kb)
        await state.set_state(Voting.choosing_country)
        await call.answer()

    @dp.callback_query(F.data.startswith("country_"), Voting.choosing_country)
    async def country_chosen(call: CallbackQuery, state: FSMContext):
        country_id = int(call.data.split("_")[1])
        await state.update_data(country_id=country_id)
        async with aiosqlite.connect("scoreboard.db") as db:
            cursor = await db.execute("SELECT full_name FROM countries WHERE id=?", (country_id,))
            row = await cursor.fetchone()
            country_name = row[0] if row else "?"
            flag = get_flag(country_name)
        await state.update_data(country_display=f"{flag} {country_name}")
        if " - " in country_name:
            parts = country_name.split(" - ", 1)
            display = f"{flag} <b>{parts[0]}</b> — {parts[1]}"
        else:
            display = f"{flag} <b>{country_name}</b>"
        await call.message.edit_text(f"👤 Введите ваше имя (никнейм) для оценки:\n\n{display}",
                                     parse_mode="HTML")
        await state.set_state(Voting.entering_name)
        await call.answer()

    @dp.message(Voting.entering_name)
    async def name_entered(message: Message, state: FSMContext):
        name = message.text.strip()
        if not name:
            await message.answer("⚠️ Имя не может быть пустым. Введите снова:")
            return
        await state.update_data(username=name)
        data = await state.get_data()
        await message.answer(f"⭐ Оценка за <b>Stage/Выступление</b> (1–12):\n{data.get('country_display', '')}",
                             parse_mode="HTML")
        await state.set_state(Voting.entering_performance)

    @dp.message(Voting.entering_performance)
    async def perf_entered(message: Message, state: FSMContext):
        try:
            p = int(message.text)
            if 1 <= p <= 12:
                await state.update_data(performance=p)
                await message.answer("🎵 Оценка за <b>Vocal/Исполнение</b> (1–12):", parse_mode="HTML")
                await state.set_state(Voting.entering_singing)
            else:
                raise ValueError
        except:
            await message.answer("⚠️ Введите целое число от 1 до 12:")

    @dp.message(Voting.entering_singing)
    async def sing_entered(message: Message, state: FSMContext):
        try:
            s = int(message.text)
            if 1 <= s <= 12:
                await state.update_data(singing=s)
                await message.answer("🌟 <b>Total/Общая</b> оценка (1–12):", parse_mode="HTML")
                await state.set_state(Voting.entering_overall)
            else:
                raise ValueError
        except:
            await message.answer("⚠️ Введите целое число от 1 до 12:")

    @dp.message(Voting.entering_overall)
    async def overall_entered(message: Message, state: FSMContext):
        try:
            o = int(message.text)
            if 1 <= o <= 12:
                data = await state.get_data()
                async with aiosqlite.connect("scoreboard.db") as db:
                    await db.execute('''INSERT INTO scores (username, country_id, performance, singing, overall)
                                        VALUES (?,?,?,?,?)
                                        ON CONFLICT(username, country_id) DO UPDATE SET
                                        performance=excluded.performance,
                                        singing=excluded.singing,
                                        overall=excluded.overall''',
                                     (data['username'], data['country_id'], data['performance'],
                                      data['singing'], o))
                    await db.commit()
                await message.answer(
                    f"✅ Оценка сохранена!\n\n{data.get('country_display', '')}\n"
                    f"🎭 Stage: {data['performance']} | 🎵 Vocal: {data['singing']} | 🌟 Total: {o}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🎤 Оценить ещё", callback_data="menu_vote")],
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_start")]
                    ])
                )
                await state.clear()
            else:
                raise ValueError
        except:
            await message.answer("⚠️ Введите целое число от 1 до 12:")

    # ══════════════════════════════════════════════
    # ВСЕ ОЦЕНКИ
    # ══════════════════════════════════════════════

    @dp.callback_query(F.data == "menu_scores")
    async def show_scores(call: CallbackQuery):
        await call.message.edit_text("⏳ Загружаю оценки...")
        async with aiosqlite.connect("scoreboard.db") as db:
            cursor = await db.execute('''SELECT l.name as list_name, c.full_name, s.username,
                                        s.performance, s.singing, s.overall
                                        FROM scores s
                                        JOIN countries c ON s.country_id=c.id
                                        JOIN lists l ON c.list_id=l.id''')
            rows = await cursor.fetchall()

        if not rows:
            await call.message.edit_text("📭 Пока нет ни одной оценки.",
                                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                             [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_start")]
                                         ]))
            return

        grouped = defaultdict(dict)
        for list_name, country, username, p, s, o in rows:
            grouped[(list_name, country)][username] = (p, s, o)

        country_stats = []
        for (list_name, country), users in grouped.items():
            avg_overall = sum(v[2] for v in users.values()) / len(users)
            flag = get_flag(country)
            country_stats.append((list_name, flag, country, users, avg_overall))

        country_stats.sort(key=lambda x: x[4], reverse=True)

        lines = ["📊 <b>ВСЕ ОЦЕНКИ</b> (сортировка по среднему баллу)\n"]
        current_list = None
        for list_name, flag, country, users, avg in country_stats:
            if list_name != current_list:
                current_list = list_name
                lines.append(f"\n▸ <i>{list_name}</i>")
            parts_country = country.split(" - ", 1) if " - " in country else (country, "")
            country_short = parts_country[0]
            song = parts_country[1] if len(parts_country) > 1 else ""
            lines.append(f"\n{flag} <b>{country_short}</b> – {song}  (ср. балл: {avg:.1f})")
            for user, (p, s, o) in sorted(users.items()):
                lines.append(f"    {user}: Stage {p} | Vocal {s} | Total {o}")

        full_text = "\n".join(lines)

        parts = split_text(full_text, 4000)
        for i, part in enumerate(parts):
            if i == 0:
                await call.message.edit_text(part, parse_mode="HTML")
            else:
                await call.message.answer(part, parse_mode="HTML")

        await call.message.answer("─" * 20, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_start")]
        ]))
        await call.answer()

    # ══════════════════════════════════════════════
    # ТОП-10
    # ══════════════════════════════════════════════

    @dp.callback_query(F.data == "menu_top10")
    async def show_top10(call: CallbackQuery):
        async with aiosqlite.connect("scoreboard.db") as db:
            cursor = await db.execute('''SELECT l.name as list_name, c.full_name, AVG(s.overall) as avg_overall,
                                        COUNT(*) as votes
                                        FROM scores s
                                        JOIN countries c ON s.country_id=c.id
                                        JOIN lists l ON c.list_id=l.id
                                        GROUP BY c.id
                                        ORDER BY avg_overall DESC
                                        LIMIT 10''')
            top = await cursor.fetchall()

        if not top:
            await call.message.edit_text("📭 Пока нет оценок для рейтинга.",
                                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                             [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_start")]
                                         ]))
            return

        lines = ["🏆 <b>ТОП-10 СТРАН</b> (по средней общей оценке)\n"]
        medals = ["🥇", "🥈", "🥉"] + ["  "] * 7
        for i, (list_name, country, avg, votes) in enumerate(top):
            flag = get_flag(country)
            parts_country = country.split(" - ", 1) if " - " in country else (country, "")
            country_short = parts_country[0]
            song = parts_country[1] if len(parts_country) > 1 else ""
            lines.append(f"{medals[i]}{i+1}. {flag} <b>{country_short}</b> – {song}")
            lines.append(f"     {list_name} | ср. балл: {avg:.2f} | оценок: {votes}\n")

        full_text = "\n".join(lines)
        await call.message.edit_text(full_text, parse_mode="HTML",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                         [InlineKeyboardButton(text="📊 Все оценки", callback_data="menu_scores")],
                                         [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu_start")]
                                     ]))
        await call.answer()

    # ══════════════════════════════════════════════
    # ВХОД В АДМИНКУ (самый последний @dp.message)
    # ══════════════════════════════════════════════

    @dp.callback_query(F.data == "menu_admin")
    async def admin_prompt(call: CallbackQuery, state: FSMContext):
        await state.clear()
        await call.message.edit_text("🔐 Введите пароль администратора:")
        await call.answer()

    @dp.message()
    async def admin_login_handler(message: Message, state: FSMContext):
      
        if message.text and message.text.strip() == ADMIN_PASSWORD:
            await state.clear()
            admin_sessions.add(message.from_user.id)
            await message.answer(
                "✅ Вы вошли как администратор.\n\n"
                "<b>Доступные команды:</b>\n"
                "/lock semi1 | semi2 | final\n"
                "/unlock semi1 | semi2 | final\n"
                "/del_user имя\n"
                "/del_country страна\n"
                "/del_all\n"
                "/reset_db confirm\n"
                "/admin_logout",
                parse_mode="HTML"
            )

    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

import os
import json
import time
import sqlite3
from collections import defaultdict
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "euro2026")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

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

# ─── Telegram API helpers ───
def send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    r = requests.post(f"{API_URL}/sendMessage", json=data)
    return r.json()

def edit_message(chat_id, message_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    r = requests.post(f"{API_URL}/editMessageText", json=data)
    return r.json()

def answer_callback(callback_id):
    requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": callback_id})

def inline_button(text, callback_data):
    return {"text": text, "callback_data": callback_data}

def inline_keyboard(buttons):
    return {"inline_keyboard": buttons}

# ─── Database ───
def init_db():
    with sqlite3.connect("scoreboard.db") as db:
        db.execute('''CREATE TABLE IF NOT EXISTS lists (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            locked INTEGER NOT NULL DEFAULT 0
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS countries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id TEXT NOT NULL,
            full_name TEXT NOT NULL,
            FOREIGN KEY(list_id) REFERENCES lists(id)
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS scores (
            username TEXT NOT NULL,
            country_id INTEGER NOT NULL,
            performance INTEGER NOT NULL,
            singing INTEGER NOT NULL,
            overall INTEGER NOT NULL,
            UNIQUE(username, country_id),
            FOREIGN KEY(country_id) REFERENCES countries(id)
        )''')
        cursor = db.execute("SELECT COUNT(*) FROM lists")
        count = cursor.fetchone()[0]
        if count == 0:
            db.execute("INSERT INTO lists (id, name, locked) VALUES ('semi1','First Semi-Final',0)")
            db.execute("INSERT INTO lists (id, name, locked) VALUES ('semi2','Second Semi-Final',0)")
            db.execute("INSERT INTO lists (id, name, locked) VALUES ('final','Final',1)")
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
                db.execute("INSERT INTO countries (list_id, full_name) VALUES ('semi1',?)", (c,))
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
                db.execute("INSERT INTO countries (list_id, full_name) VALUES ('semi2',?)", (c,))
        db.commit()

def get_unlocked_lists():
    with sqlite3.connect("scoreboard.db") as db:
        cursor = db.execute("SELECT id, name FROM lists WHERE locked=0")
        return cursor.fetchall()

def get_countries_of_list(list_id):
    with sqlite3.connect("scoreboard.db") as db:
        cursor = db.execute("SELECT id, full_name FROM countries WHERE list_id=?", (list_id,))
        return cursor.fetchall()

def get_country_by_id(country_id):
    with sqlite3.connect("scoreboard.db") as db:
        cursor = db.execute("SELECT full_name FROM countries WHERE id=?", (country_id,))
        row = cursor.fetchone()
        return row[0] if row else "?"

# ─── User states ───
user_states = {}
admin_sessions = set()

# ─── Main bot logic ───
def process_update(update):
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")
        user_id = msg["from"]["id"]

        # Команды
        if text == "/start":
            user_states.pop(user_id, None)
            kb = inline_keyboard([
                [inline_button("🎤 Голосовать", "menu_vote")],
                [inline_button("📊 Все оценки", "menu_scores")],
                [inline_button("🏆 Топ-10", "menu_top10")],
                [inline_button("🔑 Администрирование", "menu_admin")]
            ])
            send_message(chat_id, "🎶 Добро пожаловать на Eurovision 2026 Scorecard!\n\n📋 First Semi-Final — 15 песен\n📋 Second Semi-Final — 15 песен\n\nВыберите действие:", kb)

        elif text == "/admin_logout":
            admin_sessions.discard(user_id)
            send_message(chat_id, "👋 Вы вышли из режима администратора.")

        elif text.startswith("/lock "):
            if user_id not in admin_sessions:
                send_message(chat_id, "⛔ Сначала войдите как администратор.")
                return
            try:
                list_id = text.split()[1]
                if list_id in ('semi1', 'semi2', 'final'):
                    with sqlite3.connect("scoreboard.db") as db:
                        db.execute("UPDATE lists SET locked=1 WHERE id=?", (list_id,))
                        db.commit()
                    names = {"semi1": "First Semi-Final", "semi2": "Second Semi-Final", "final": "Final"}
                    send_message(chat_id, f"🔒 Список «{names[list_id]}» заблокирован.")
                else:
                    send_message(chat_id, "⚠️ Используйте: /lock semi1")
            except:
                send_message(chat_id, "⚠️ Используйте: /lock semi1")

        elif text.startswith("/unlock "):
            if user_id not in admin_sessions:
                send_message(chat_id, "⛔ Сначала войдите как администратор.")
                return
            try:
                list_id = text.split()[1]
                if list_id in ('semi1', 'semi2', 'final'):
                    with sqlite3.connect("scoreboard.db") as db:
                        db.execute("UPDATE lists SET locked=0 WHERE id=?", (list_id,))
                        db.commit()
                    names = {"semi1": "First Semi-Final", "semi2": "Second Semi-Final", "final": "Final"}
                    send_message(chat_id, f"🔓 Список «{names[list_id]}» разблокирован.")
                else:
                    send_message(chat_id, "⚠️ Используйте: /unlock semi1")
            except:
                send_message(chat_id, "⚠️ Используйте: /unlock semi1")

        elif text.startswith("/del_user "):
            if user_id not in admin_sessions:
                send_message(chat_id, "⛔ Сначала войдите как администратор.")
                return
            try:
                username = text.split(" ", 1)[1].strip()
                with sqlite3.connect("scoreboard.db") as db:
                    cursor = db.execute("DELETE FROM scores WHERE username=?", (username,))
                    deleted = cursor.rowcount
                    db.commit()
                if deleted > 0:
                    send_message(chat_id, f"🗑️ Удалено {deleted} оценок пользователя {username}")
                else:
                    send_message(chat_id, f"❌ Пользователь {username} не найден.")
            except:
                send_message(chat_id, "⚠️ Используйте: /del_user Alex")

        elif text.startswith("/del_country "):
            if user_id not in admin_sessions:
                send_message(chat_id, "⛔ Сначала войдите как администратор.")
                return
            try:
                country_name = text.split(" ", 1)[1].strip()
                with sqlite3.connect("scoreboard.db") as db:
                    cursor = db.execute("SELECT id FROM countries WHERE full_name LIKE ?", (f"%{country_name}%",))
                    countries = cursor.fetchall()
                    total = 0
                    for (cid,) in countries:
                        cur = db.execute("DELETE FROM scores WHERE country_id=?", (cid,))
                        total += cur.rowcount
                    db.commit()
                if total > 0:
                    send_message(chat_id, f"🗑️ Удалено {total} оценок для '{country_name}'")
                else:
                    send_message(chat_id, f"❌ Страна '{country_name}' не найдена.")
            except:
                send_message(chat_id, "⚠️ Используйте: /del_country Moldova")

        elif text == "/del_all":
            if user_id not in admin_sessions:
                send_message(chat_id, "⛔ Сначала войдите как администратор.")
                return
            with sqlite3.connect("scoreboard.db") as db:
                cursor = db.execute("SELECT COUNT(*) FROM scores")
                count = cursor.fetchone()[0]
                db.execute("DELETE FROM scores")
                db.commit()
            send_message(chat_id, f"🗑️ Удалены ВСЕ оценки ({count} шт.).")

        elif text.startswith("/reset_db"):
            if user_id not in admin_sessions:
                send_message(chat_id, "⛔ Сначала войдите как администратор.")
                return
            if "confirm" not in text:
                send_message(chat_id, "⚠️ ВНИМАНИЕ! Это удалит ВСЕ оценки и списки.\nДля подтверждения: /reset_db confirm")
                return
            with sqlite3.connect("scoreboard.db") as db:
                db.execute("DROP TABLE IF EXISTS scores")
                db.execute("DROP TABLE IF EXISTS countries")
                db.execute("DROP TABLE IF EXISTS lists")
                db.commit()
            init_db()
            send_message(chat_id, "🔄 База данных полностью сброшена и пересоздана.")

        else:
            state = user_states.get(user_id, {}).get("state")
            if state == "waiting_password":
                if text.strip() == ADMIN_PASSWORD:
                    admin_sessions.add(user_id)
                    user_states.pop(user_id)
                    send_message(chat_id, "✅ Вы вошли как администратор.\n\n/lock semi1 | semi2 | final\n/unlock semi1 | semi2 | final\n/del_user имя\n/del_country страна\n/del_all\n/reset_db confirm\n/admin_logout")
                else:
                    send_message(chat_id, "❌ Неверный пароль.")
            elif state == "entering_name":
                user_states[user_id]["data"]["username"] = text.strip()
                user_states[user_id]["state"] = "entering_performance"
                send_message(chat_id, "⭐ Оценка за Stage/Выступление (1-12):")
            elif state == "entering_performance":
                try:
                    p = int(text)
                    if 1 <= p <= 12:
                        user_states[user_id]["data"]["performance"] = p
                        user_states[user_id]["state"] = "entering_singing"
                        send_message(chat_id, "🎵 Оценка за Vocal/Исполнение (1-12):")
                    else:
                        send_message(chat_id, "⚠️ Введите число от 1 до 12:")
                except:
                    send_message(chat_id, "⚠️ Введите целое число от 1 до 12:")
            elif state == "entering_singing":
                try:
                    s = int(text)
                    if 1 <= s <= 12:
                        user_states[user_id]["data"]["singing"] = s
                        user_states[user_id]["state"] = "entering_overall"
                        send_message(chat_id, "🌟 Total/Общая оценка (1-12):")
                    else:
                        send_message(chat_id, "⚠️ Введите число от 1 до 12:")
                except:
                    send_message(chat_id, "⚠️ Введите целое число от 1 до 12:")
            elif state == "entering_overall":
                try:
                    o = int(text)
                    if 1 <= o <= 12:
                        data = user_states[user_id]["data"]
                        with sqlite3.connect("scoreboard.db") as db:
                            db.execute('''INSERT INTO scores (username, country_id, performance, singing, overall)
                                          VALUES (?,?,?,?,?)
                                          ON CONFLICT(username, country_id) DO UPDATE SET
                                          performance=excluded.performance,
                                          singing=excluded.singing,
                                          overall=excluded.overall''',
                                       (data['username'], data['country_id'], data['performance'], data['singing'], o))
                            db.commit()
                        country_name = get_country_by_id(data['country_id'])
                        flag = get_flag(country_name)
                        kb = inline_keyboard([
                            [inline_button("🎤 Оценить ещё", "menu_vote")],
                            [inline_button("🏠 Главное меню", "menu_start")]
                        ])
                        send_message(chat_id, f"✅ Оценка сохранена!\n\n{flag} {country_name}\n🎭 Stage: {data['performance']} | 🎵 Vocal: {data['singing']} | 🌟 Total: {o}", kb)
                        user_states.pop(user_id)
                    else:
                        send_message(chat_id, "⚠️ Введите число от 1 до 12:")
                except:
                    send_message(chat_id, "⚠️ Введите целое число от 1 до 12:")

    elif "callback_query" in update:
        cb = update["callback_query"]
        user_id = cb["from"]["id"]
        chat_id = cb["message"]["chat"]["id"]
        msg_id = cb["message"]["message_id"]
        data = cb["data"]
        answer_callback(cb["id"])

        if data == "menu_start":
            user_states.pop(user_id, None)
            kb = inline_keyboard([
                [inline_button("🎤 Голосовать", "menu_vote")],
                [inline_button("📊 Все оценки", "menu_scores")],
                [inline_button("🏆 Топ-10", "menu_top10")],
                [inline_button("🔑 Администрирование", "menu_admin")]
            ])
            edit_message(chat_id, msg_id, "🎶 Eurovision 2026 Scorecard\n\nВыберите действие:", kb)

        elif data == "menu_vote":
            unlocked = get_unlocked_lists()
            if not unlocked:
                edit_message(chat_id, msg_id, "🔒 Все списки заблокированы.")
                return
            buttons = [[inline_button(name, f"votelist_{lid}")] for lid, name in unlocked]
            buttons.append([inline_button("❌ Отмена", "menu_start")])
            edit_message(chat_id, msg_id, "📋 Выберите список:", inline_keyboard(buttons))

        elif data.startswith("votelist_"):
            list_id = data.split("_", 1)[1]
            countries = get_countries_of_list(list_id)
            buttons = []
            for cid, name in countries:
                flag = get_flag(name)
                if " - " in name:
                    parts = name.split(" - ", 1)
                    display = f"{flag} {parts[0]} — {parts[1]}"
                else:
                    display = f"{flag} {name}"
                buttons.append([inline_button(display, f"country_{cid}")])
            buttons.append([inline_button("⬅️ Назад", "menu_vote")])
            edit_message(chat_id, msg_id, "🎤 Выберите страну и песню:", inline_keyboard(buttons))

        elif data.startswith("country_"):
            country_id = int(data.split("_")[1])
            country_name = get_country_by_id(country_id)
            flag = get_flag(country_name)
            if " - " in country_name:
                parts = country_name.split(" - ", 1)
                display = f"{flag} {parts[0]} — {parts[1]}"
            else:
                display = f"{flag} {country_name}"
            edit_message(chat_id, msg_id, f"👤 Введите ваше имя для оценки:\n\n{display}")
            user_states[user_id] = {"state": "entering_name", "data": {"country_id": country_id, "country_display": f"{flag} {country_name}"}}

        elif data == "menu_admin":
            user_states[user_id] = {"state": "waiting_password", "data": {}}
            edit_message(chat_id, msg_id, "🔐 Введите пароль администратора:")

        elif data == "menu_scores":
            with sqlite3.connect("scoreboard.db") as db:
                cursor = db.execute('''SELECT l.name as list_name, c.full_name, s.username,
                                      s.performance, s.singing, s.overall
                                      FROM scores s
                                      JOIN countries c ON s.country_id=c.id
                                      JOIN lists l ON c.list_id=l.id''')
                rows = cursor.fetchall()
            if not rows:
                edit_message(chat_id, msg_id, "📭 Пока нет ни одной оценки.", inline_keyboard([[inline_button("🏠 Главное меню", "menu_start")]]))
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

            lines = ["📊 ВСЕ ОЦЕНКИ\n"]
            current_list = None
            for list_name, flag, country, users, avg in country_stats:
                if list_name != current_list:
                    current_list = list_name
                    lines.append(f"\n▸ {list_name}")
                parts = country.split(" - ", 1)
                short = parts[0]
                song = parts[1] if len(parts) > 1 else ""
                lines.append(f"\n{flag} {short} – {song}  (ср. балл: {avg:.1f})")
                for user, (p, s, o) in sorted(users.items()):
                    lines.append(f"    {user}: Stage {p} | Vocal {s} | Total {o}")

            full_text = "\n".join(lines)
            if len(full_text) > 4000:
                full_text = full_text[:4000] + "\n\n... (показаны не все)"
            
            kb = inline_keyboard([[inline_button("🏠 Главное меню", "menu_start")]])
            edit_message(chat_id, msg_id, full_text, kb)

        elif data == "menu_top10":
            with sqlite3.connect("scoreboard.db") as db:
                cursor = db.execute('''SELECT l.name as list_name, c.full_name, AVG(s.overall) as avg_overall,
                                      COUNT(*) as votes
                                      FROM scores s
                                      JOIN countries c ON s.country_id=c.id
                                      JOIN lists l ON c.list_id=l.id
                                      GROUP BY c.id
                                      ORDER BY avg_overall DESC
                                      LIMIT 10''')
                top = cursor.fetchall()
            if not top:
                edit_message(chat_id, msg_id, "📭 Пока нет оценок для рейтинга.", inline_keyboard([[inline_button("🏠 Главное меню", "menu_start")]]))
                return
            lines = ["🏆 ТОП-10 СТРАН\n"]
            medals = ["🥇", "🥈", "🥉"] + ["  "] * 7
            for i, (list_name, country, avg, votes) in enumerate(top):
                flag = get_flag(country)
                parts = country.split(" - ", 1)
                short = parts[0]
                song = parts[1] if len(parts) > 1 else ""
                lines.append(f"{medals[i]}{i+1}. {flag} {short} – {song}")
                lines.append(f"     {list_name} | ср. балл: {avg:.2f} | оценок: {votes}\n")
            full_text = "\n".join(lines)
            kb = inline_keyboard([
                [inline_button("📊 Все оценки", "menu_scores")],
                [inline_button("🏠 Главное меню", "menu_start")]
            ])
            edit_message(chat_id, msg_id, full_text, kb)

# ─── Polling ───
def main():
    init_db()
    print("Bot started!")
    offset = 0
    while True:
        try:
            r = requests.get(f"{API_URL}/getUpdates", params={"offset": offset, "timeout": 30})
            updates = r.json().get("result", [])
            for upd in updates:
                process_update(upd)
                offset = upd["update_id"] + 1
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()

import json
import logging
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    ChatMemberHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8523446298"))
DATA_FILE = "data.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "users": set(data.get("users", [])),
                "channels": {int(k): v for k, v in data.get("channels", {}).items()},
                "groups": {int(k): v for k, v in data.get("groups", {}).items()},
                "sent_count": data.get("sent_count", 0),
                "failed_count": data.get("failed_count", 0),
                "welcome_text": data.get(
                    "welcome_text",
                    "أهلاً بك معنا في المجموعة! نتمنى لك وقتاً ممتعاً. 🌹",
                ),
                "start_text": data.get(
                    "start_text",
                    "أهلاً بك في البوت! استخدم اللوحة للتحكم.",
                ),
                "notifications": data.get("notifications", True),
            }
        except Exception as e:
            logging.error("خطأ أثناء قراءة الملف: %s", e)

    return {
        "users": set(),
        "channels": {},
        "groups": {},
        "sent_count": 0,
        "failed_count": 0,
        "welcome_text": "أهلاً بك معنا في المجموعة! نتمنى لك وقتاً ممتعاً. 🌹",
        "start_text": "أهلاً بك في البوت! استخدم اللوحة للتحكم.",
        "notifications": True,
    }

db = load_data()

def save_data():
    try:
        data_to_save = {
            "users": list(db["users"]),
            "channels": db["channels"],
            "groups": db["groups"],
            "sent_count": db["sent_count"],
            "failed_count": db["failed_count"],
            "welcome_text": db["welcome_text"],
            "start_text": db["start_text"],
            "notifications": db["notifications"],
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error("خطأ أثناء كتابة الملف: %s", e)

def get_main_panel_keyboard():
    notif_status = "🔔 مفعّلة" if db["notifications"] else "🔕 معطّلة"
    keyboard = [
        [InlineKeyboardButton("📋 القنوات والكروبات المربوطة", callback_data="select_chats_menu")],
        [InlineKeyboardButton("💬 تعديل رسالة الترحيب", callback_data="set_welcome")],
        [InlineKeyboardButton("📢 إرسال إذاعة", callback_data="start_broadcast")],
        [InlineKeyboardButton("👋 تعديل رسالة الستارت", callback_data="set_start")],
        [InlineKeyboardButton(f"الإشعارات: {notif_status}", callback_data="toggle_notif")],
        [InlineKeyboardButton("👥 قاعدة البيانات", callback_data="database")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("🗑️ مسح البيانات", callback_data="clear_db")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_main_panel_text():
    return (
        "📨 <b>لوحة تحكم البوت</b>\n"
        "───────────────────\n"
        f"📢 <b>القنوات المربوطة :</b> {len(db['channels'])}\n"
        f"👁️ <b>الكروبات المربوطة :</b> {len(db['groups'])}\n"
        f"👥 <b>المستخدمين :</b> {len(db['users'])}\n"
        f"✅ <b>رسائل مرسلة :</b> {db['sent_count']}\n"
        f"❌ <b>رسائل فاشلة :</b> {db['failed_count']}\n"
        "───────────────────"
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.message:
        return

    if user.id not in db["users"]:
        db["users"].add(user.id)
        save_data()

    if user.id == ADMIN_ID:
        await update.message.reply_text(
            get_main_panel_text(),
            reply_markup=get_main_panel_keyboard(),
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(db["start_text"])

async def auto_track_my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if not result:
        return

    chat = result.chat
    new_status = result.new_chat_member.status

    if new_status in ["administrator", "member"]:
        if chat.type == "channel":
            db["channels"][chat.id] = chat.title or "قناة"
            msg = (
                f"✅ <b>تم التعرف على قناة جديدة وحفظها:</b>\n"
                f"📌 {chat.title}\n🆔 <code>{chat.id}</code>"
            )
        elif chat.type in ["group", "supergroup"]:
            db["groups"][chat.id] = chat.title or "كروب"
            msg = (
                f"✅ <b>تم التعرف على كروب جديد وحفظه:</b>\n"
                f"📌 {chat.title}\n🆔 <code>{chat.id}</code>"
            )
        else:
            return

        save_data()
        if db["notifications"]:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID, text=msg, parse_mode="HTML"
                )
            except Exception:
                pass

    elif new_status in ["left", "kicked"]:
        db["channels"].pop(chat.id, None)
        db["groups"].pop(chat.id, None)
        save_data()

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return

    chat = result.chat
    new_status = result.new_chat_member.status
    old_status = result.old_chat_member.status

    if old_status in ["left", "kicked", "restricted"] and new_status in ["member", "administrator"]:
        user = result.new_chat_member.user

        if user.is_bot:
            return

        db["users"].add(user.id)
        if chat.type in ["group", "supergroup"]:
            db["groups"][chat.id] = chat.title or "كروب"
        save_data()

        try:
            welcome_msg = (
                f"أهلاً بك يا <a href='tg://user?id={user.id}'>{user.first_name}</a> "
                f"في المجموعـة! 🌹\n\n{db['welcome_text']}"
            )
            await context.bot.send_message(
                chat_id=chat.id,
                text=welcome_msg,
                parse_mode="HTML",
            )
            db["sent_count"] += 1
            save_data()
        except Exception as e:
            db["failed_count"] += 1
            save_data()
            logging.error("خطأ في إرسال الترحيب المباشر: %s", e)

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    join_request = update.chat_join_request
    if not join_request:
        return

    user = join_request.from_user
    chat = join_request.chat

    if chat.type == "channel":
        db["channels"][chat.id] = chat.title or "قناة"
    elif chat.type in ["group", "supergroup"]:
        db["groups"][chat.id] = chat.title or "كروب"

    try:
        await join_request.approve()
    except Exception as e:
        logging.error("فشل قبول طلب الانضمام: %s", e)
        return

    db["users"].add(user.id)
    save_data()

    try:
        await context.bot.send_message(chat_id=user.id, text=db["welcome_text"])
        db["sent_count"] += 1
        save_data()
    except Exception as e:
        db["failed_count"] += 1
        save_data()
        logging.error("تعذر إرسال الخاص: %s", e)

async def admin_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        return

    data = query.data

    if data in ["back_to_main", "stats"]:
        context.user_data.clear()
        await query.edit_message_text(
            get_main_panel_text(),
            reply_markup=get_main_panel_keyboard(),
            parse_mode="HTML",
        )

    elif data == "select_chats_menu":
        kbd = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 القنوات المربوطة", callback_data="view_channels")],
            [InlineKeyboardButton("👁️ الكروبات المربوطة", callback_data="view_groups")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")],
        ])
        await query.edit_message_text(
            "📋 <b>المحادثات المربوطة بالبوت:</b>",
            reply_markup=kbd,
            parse_mode="HTML",
        )

    elif data == "view_channels":
        kbd = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="select_chats_menu")]
        ])
        channels_list = (
            "\n".join(
                f"• <b>{title}</b> | <code>{c_id}</code>"
                for c_id, title in db["channels"].items()
            )
            if db["channels"]
            else "لا يوجد قنوات مربوطة حالياً."
        )
        await query.edit_message_text(
            f"📢 <b>القنوات المربوطة ({len(db['channels'])}):</b>\n\n{channels_list}",
            reply_markup=kbd,
            parse_mode="HTML",
        )

    elif data == "view_groups":
        kbd = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="select_chats_menu")]
        ])
        groups_list = (
            "\n".join(
                f"• <b>{title}</b> | <code>{g_id}</code>"
                for g_id, title in db["groups"].items()
            )
            if db["groups"]
            else "لا يوجد كروبات مربوطة حالياً."
        )
        await query.edit_message_text(
            f"👁️ <b>الكروبات المربوطة ({len(db['groups'])}):</b>\n\n{groups_list}",
            reply_markup=kbd,
            parse_mode="HTML",
        )

    elif data == "set_welcome":
        context.user_data["state"] = "waiting_for_welcome"
        kbd = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 إلغاء", callback_data="back_to_main")]
        ])
        await query.edit_message_text(
            f"💬 <b>نص الترحيب الحالي:</b>\n\n"
            f"<code>{db['welcome_text']}</code>\n\n"
            "أرسل النص الجديد للترحيب الآن:",
            reply_markup=kbd,
            parse_mode="HTML",
        )

    elif data == "set_start":
        context.user_data["state"] = "waiting_for_start"
        kbd = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 إلغاء", callback_data="back_to_main")]
        ])
        await query.edit_message_text(
            f"👋 <b>نص الستارت الحالي:</b>\n\n"
            f"<code>{db['start_text']}</code>\n\n"
            "أرسل النص الجديد للستارت الآن:",
            reply_markup=kbd,
            parse_mode="HTML",
        )

    elif data == "start_broadcast":
        context.user_data["state"] = "waiting_for_broadcast"
        kbd = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 إلغاء", callback_data="back_to_main")]
        ])
        await query.edit_message_text(
            "📢 <b>قسم الإذاعة العامة</b>\n\n"
            "أرسل الآن الرسالة التي تريد إرسالها لجميع الأعضاء:",
            reply_markup=kbd,
            parse_mode="HTML",
        )

    elif data == "toggle_notif":
        db["notifications"] = not db["notifications"]
        save_data()
        await query.edit_message_text(
            get_main_panel_text(),
            reply_markup=get_main_panel_keyboard(),
            parse_mode="HTML",
        )

    elif data == "database":
        kbd = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
        ])
        await query.edit_message_text(
            f"👥 <b>قاعدة البيانات</b>\n\n"
            f"إجمالي الأعضاء المسجلين: <code>{len(db['users'])}</code>",
            reply_markup=kbd,
            parse_mode="HTML",
        )

    elif data == "clear_db":
        db["users"].clear()
        db["channels"].clear()
        db["groups"].clear()
        db["sent_count"] = 0
        db["failed_count"] = 0
        save_data()
        kbd = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")]
        ])
        await query.edit_message_text(
            "🗑️ <b>تم مسح كافة البيانات والإحصائيات وتحديث الملف بنجاح!</b>",
            reply_markup=kbd,
            parse_mode="HTML",
        )

async def handle_admin_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.effective_user.id != ADMIN_ID:
        return

    state = context.user_data.get("state")

    if state == "waiting_for_welcome":
        db["welcome_text"] = update.message.text
        context.user_data["state"] = None
        save_data()
        await update.message.reply_text("✅ تم تحديث نص الترحيب وحفظه!")
        await update.message.reply_text(
            get_main_panel_text(),
            reply_markup=get_main_panel_keyboard(),
            parse_mode="HTML",
        )

    elif state == "waiting_for_start":
        db["start_text"] = update.message.text
        context.user_data["state"] = None
        save_data()
        await update.message.reply_text("✅ تم تحديث نص الستارت وحفظه!")
        await update.message.reply_text(
            get_main_panel_text(),
            reply_markup=get_main_panel_keyboard(),
            parse_mode="HTML",
        )

    elif state == "waiting_for_broadcast":
        context.user_data["state"] = None
        text_to_send = update.message.text
        success, fail = 0, 0

        for uid in list(db["users"]):
            try:
                await context.bot.send_message(chat_id=uid, text=text_to_send)
                success += 1
            except Exception:
                fail += 1

        db["sent_count"] += success
        db["failed_count"] += fail
        save_data()

        await update.message.reply_text(
            f"📢 <b>اكتملت الإذاعة!</b>\n\n"
            f"✅ تم الإرسال: {success}\n❌ فشل الإرسال: {fail}",
            parse_mode="HTML",
        )
        await update.message.reply_text(
            get_main_panel_text(),
            reply_markup=get_main_panel_keyboard(),
            parse_mode="HTML",
        )

def main():
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("ضع BOT_TOKEN في متغير البيئة BOT_TOKEN قبل التشغيل.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("panel", start_command))
    app.add_handler(CallbackQueryHandler(admin_button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_inputs))
    app.add_handler(
        ChatMemberHandler(auto_track_my_status, ChatMemberHandler.MY_CHAT_MEMBER)
    )
    app.add_handler(
        ChatMemberHandler(welcome_new_member, ChatMemberHandler.CHAT_MEMBER)
    )
    app.add_handler(ChatJoinRequestHandler(handle_join_request))

    print("البوت يعمل ونظام التخزين في ملف JSON مفعل بنجاح...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

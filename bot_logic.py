# bot_logic.py
# language: Python, runtime: Vercel Serverless (Python 3.12), target: bot logic module
import io
import html
import json
import logging
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler,
)

# ═══════════ EDIT THESE TWO LINES ═══════════
BOT_TOKEN = "8426186448:AAHE4dkzYCaSkYdRuik83VXIlRx7eBk-96E"     # from @BotFather
API_BASE  = "https://bdeeinedu.vercel.app/api/eiin.php" # public URL to your eiin.php
# ════════════════════════════════════════════

TIMEOUT   = 30
PAGE_SIZE = 6
ASK_EIIN, ASK_SEARCH = range(2)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("eiin-bot")


# ───────── helpers ─────────
def pick(obj, *keys, default="N/A"):
    for k in keys:
        v = obj.get(k) if isinstance(obj, dict) else None
        if v not in (None, "", 0, "0", "N/A", "null", "None"):
            return v
    return default


async def fetch_eiin(eiin: str) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(API_BASE, params={"eiin": eiin})
        r.raise_for_status()
        return r.json()


def heads_of(payload):
    return (payload.get("headInfo") or {}).get("data") or []


def emps_of(payload):
    content = (((payload.get("employeeList") or {}).get("data") or {}).get("content")) or []
    return content if isinstance(content, list) else []


# ───────── card formatting ─────────
def head_card(h):
    name   = pick(h, "name", "empName", "employeeName", "fullName")
    desig  = pick(h, "designation", "designationName", "designation_name", "role")
    eid    = pick(h, "id", "empRefId", "empId")
    mobile = pick(h, "mobile", "mobileNo", "phone", "contactNo")
    email  = pick(h, "email", "emailId", "emailAddress")
    img    = h.get("image") or ""
    lines = [
        "🏛 <b>Head / Principal</b>",
        "",
        f"👤 <b>{html.escape(str(name))}</b>",
        f"🆔 <code>{html.escape(str(eid))}</code>",
        f"🏷 {html.escape(str(desig))}",
    ]
    if mobile != "N/A": lines.append(f"📞 {html.escape(str(mobile))}")
    if email  != "N/A": lines.append(f"📧 {html.escape(str(email))}")
    return "\n".join(lines), img


def emp_card(e):
    name   = pick(e, "name", "empName", "employeeName", "fullName")
    desig  = pick(e, "designation", "designationName", "designation_name")
    eid    = pick(e, "id", "empRefId", "empId")
    mobile = pick(e, "mobile", "mobileNo", "phone", "contactNo")
    email  = pick(e, "email", "emailId", "emailAddress")
    img    = e.get("image") or ""
    lines = [
        f"👤 <b>{html.escape(str(name))}</b>",
        f"🆔 <code>{html.escape(str(eid))}</code>",
        f"🏷 {html.escape(str(desig))}",
    ]
    if mobile != "N/A": lines.append(f"📞 {html.escape(str(mobile))}")
    if email  != "N/A": lines.append(f"📧 {html.escape(str(email))}")
    return "\n".join(lines), img


# ───────── keyboards ─────────
def main_menu(eiin, total_emps):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Head / Principal", callback_data=f"head:{eiin}")],
        [InlineKeyboardButton(f"👥 Employee List ({total_emps})", callback_data=f"list:{eiin}:0")],
        [InlineKeyboardButton("🔎 Search Employee", callback_data=f"search:{eiin}")],
        [InlineKeyboardButton("📄 Raw JSON", callback_data=f"raw:{eiin}")],
        [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh:{eiin}")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")],
    ])


def emp_list_kb(eiin, emps, page):
    start = page * PAGE_SIZE
    chunk = emps[start:start + PAGE_SIZE]
    kb = []
    for i, e in enumerate(chunk):
        idx   = start + i
        name  = pick(e, "name", "empName", "employeeName", "fullName")
        desig = pick(e, "designation", "designationName", "designation_name")
        label = f"👤 {name}" + (f" · {desig}" if desig != "N/A" else "")
        if len(label) > 60: label = label[:57] + "..."
        kb.append([InlineKeyboardButton(label, callback_data=f"emp:{eiin}:{idx}")])

    total_pages = max(1, (len(emps) + PAGE_SIZE - 1) // PAGE_SIZE)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"list:{eiin}:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1} / {total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"list:{eiin}:{page+1}"))
    if nav: kb.append(nav)
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data=f"menu:{eiin}")])
    return InlineKeyboardMarkup(kb)


# ───────── media senders ─────────
async def send_media(bot, chat_id, text, img, keyboard=None):
    if img:
        try:
            return await bot.send_photo(
                chat_id=chat_id, photo=img, caption=text,
                parse_mode=ParseMode.HTML, reply_markup=keyboard,
            )
        except Exception as e:
            log.warning("photo fail: %s", e)
            text = f"{text}\n\n🖼 <a href=\"{html.escape(img, quote=True)}\">View Photo</a>"
    return await bot.send_message(
        chat_id=chat_id, text=text,
        parse_mode=ParseMode.HTML, reply_markup=keyboard,
    )


# ───────── /start & about ─────────
WELCOME = (
    "🎓 <b>EMIS EIIN Lookup Bot</b>\n"
    "\n"
    "Lookup any school/college by EIIN.\n"
    "View <b>Head / Principal</b> and full <b>Employee List</b>.\n"
    "\n"
    "Commands:\n"
    "• <code>/eiin 123456</code> — quick lookup\n"
    "• <code>/start</code> — menu\n"
    "• <code>/cancel</code> — abort\n"
)


def start_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Enter EIIN", callback_data="ask_eiin")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME, parse_mode=ParseMode.HTML, reply_markup=start_kb())


async def home_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(WELCOME, parse_mode=ParseMode.HTML, reply_markup=start_kb())


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    text = (
        "ℹ️ <b>About</b>\n\n"
        "Data source: <code>apps.emis.gov.bd</code>\n"
        "Backend: <code>eiin.php</code>\n"
        "Interface: Telegram Bot (async, Vercel webhook)\n\n"
        "👨‍💻 Developer: @SHAKIB2016\n"
        "📡 Telegram: @SHAKIB2016"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="home")]])
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# ───────── EIIN flow ─────────
async def prompt_eiin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        "📝 Send the <b>EIIN</b> (digits only). Example: <code>104532</code>",
        parse_mode=ParseMode.HTML, reply_markup=ForceReply(selective=True),
    )
    return ASK_EIIN


async def prompt_eiin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args and args[0].isdigit():
        await show_main_menu(update.effective_message, context, args[0])
        return ConversationHandler.END
    await update.message.reply_text(
        "📝 Send the <b>EIIN</b> (digits only).",
        parse_mode=ParseMode.HTML, reply_markup=ForceReply(selective=True),
    )
    return ASK_EIIN


async def show_main_menu(msg, context, eiin: str):
    wait = await msg.reply_text("⏳ Fetching…")
    try:
        payload = await fetch_eiin(eiin)
    except Exception as e:
        await wait.edit_text(f"❌ Fetch failed: <code>{html.escape(str(e))}</code>",
                             parse_mode=ParseMode.HTML)
        return
    context.user_data["payload"] = payload
    context.user_data["eiin"]    = eiin
    emps = emps_of(payload)
    text = (
        f"🏫 <b>EIIN: {html.escape(eiin)}</b>\n"
        f"👥 Employees: <b>{len(emps)}</b>\n"
        f"👤 Head records: <b>{len(heads_of(payload))}</b>\n"
    )
    await wait.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu(eiin, len(emps)))


async def handle_eiin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text.isdigit():
        await update.message.reply_text("❌ EIIN must be digits only. Try again.")
        return ASK_EIIN
    await show_main_menu(update.message, context, text)
    return ConversationHandler.END


# ───────── main menu interactions ─────────
async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    eiin = q.data.split(":", 1)[1]
    payload = context.user_data.get("payload")
    if not payload or context.user_data.get("eiin") != eiin:
        try:
            payload = await fetch_eiin(eiin)
            context.user_data["payload"] = payload
            context.user_data["eiin"]    = eiin
        except Exception as e:
            await q.edit_message_text(f"❌ <code>{html.escape(str(e))}</code>",
                                      parse_mode=ParseMode.HTML)
            return
    emps = emps_of(payload)
    text = (
        f"🏫 <b>EIIN: {html.escape(eiin)}</b>\n"
        f"👥 Employees: <b>{len(emps)}</b>\n"
        f"👤 Head records: <b>{len(heads_of(payload))}</b>\n"
    )
    await q.edit_message_text(text, parse_mode=ParseMode.HTML,
                              reply_markup=main_menu(eiin, len(emps)))


async def refresh_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Refreshing…")
    eiin = q.data.split(":", 1)[1]
    try:
        payload = await fetch_eiin(eiin)
        context.user_data["payload"] = payload
        context.user_data["eiin"]    = eiin
    except Exception as e:
        await q.edit_message_text(f"❌ <code>{html.escape(str(e))}</code>",
                                  parse_mode=ParseMode.HTML)
        return
    emps = emps_of(payload)
    text = (
        f"🏫 <b>EIIN: {html.escape(eiin)}</b>\n"
        f"👥 Employees: <b>{len(emps)}</b>\n"
        f"👤 Head records: <b>{len(heads_of(payload))}</b>\n"
    )
    await q.edit_message_text(text, parse_mode=ParseMode.HTML,
                              reply_markup=main_menu(eiin, len(emps)))


# ───────── head view ─────────
async def head_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    eiin = q.data.split(":", 1)[1]
    payload = context.user_data.get("payload")
    if not payload:
        try:
            payload = await fetch_eiin(eiin)
            context.user_data["payload"] = payload
        except Exception as e:
            await q.edit_message_text(f"❌ <code>{html.escape(str(e))}</code>",
                                      parse_mode=ParseMode.HTML)
            return
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=f"menunew:{eiin}")]])
    heads = heads_of(payload)
    if not heads:
        await q.edit_message_text("ℹ️ No head / principal records found.", reply_markup=back_kb)
        return
    try:
        await q.message.delete()
    except Exception:
        pass
    for h in heads:
        text, img = head_card(h)
        await send_media(context.bot, q.message.chat_id, text, img, back_kb)


# ───────── employee list ─────────
async def list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, eiin, page_s = q.data.split(":")
    page = int(page_s)
    payload = context.user_data.get("payload")
    if not payload:
        try:
            payload = await fetch_eiin(eiin)
            context.user_data["payload"] = payload
        except Exception as e:
            await q.edit_message_text(f"❌ <code>{html.escape(str(e))}</code>",
                                      parse_mode=ParseMode.HTML)
            return
    emps = emps_of(payload)
    if not emps:
        await q.edit_message_text(
            "ℹ️ No employees found.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=f"menu:{eiin}")]]),
        )
        return
    text = (
        f"👥 <b>Employee List</b> — EIIN <code>{html.escape(eiin)}</code>\n"
        f"Total: <b>{len(emps)}</b>\n\nTap a name to view details."
    )
    await q.edit_message_text(text, parse_mode=ParseMode.HTML,
                              reply_markup=emp_list_kb(eiin, emps, page))


async def listnew_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, eiin, page_s = q.data.split(":")
    page = int(page_s)
    try:
        await q.message.delete()
    except Exception:
        pass
    payload = context.user_data.get("payload")
    emps = emps_of(payload) if payload else []
    text = (
        f"👥 <b>Employee List</b> — EIIN <code>{html.escape(eiin)}</code>\n"
        f"Total: <b>{len(emps)}</b>\n\nTap a name to view details."
    )
    await context.bot.send_message(
        chat_id=q.message.chat_id, text=text,
        parse_mode=ParseMode.HTML, reply_markup=emp_list_kb(eiin, emps, page),
    )


async def emp_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, eiin, idx_s = q.data.split(":")
    idx = int(idx_s)
    payload = context.user_data.get("payload")
    if not payload:
        await q.answer("Reload list first.", show_alert=True)
        return
    emps = emps_of(payload)
    if idx >= len(emps):
        await q.answer("Not found.", show_alert=True)
        return
    page = idx // PAGE_SIZE
    text, img = emp_card(emps[idx])
    back_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to list", callback_data=f"listnew:{eiin}:{page}")],
        [InlineKeyboardButton("🏠 Menu", callback_data=f"menunew:{eiin}")],
    ])
    await send_media(context.bot, q.message.chat_id, text, img, back_kb)


# ───────── menunew (rebuild menu) ─────────
async def menunew_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    eiin = q.data.split(":", 1)[1]
    try:
        await q.message.delete()
    except Exception:
        pass
    payload = context.user_data.get("payload")
    emps = emps_of(payload) if payload else []
    text = (
        f"🏫 <b>EIIN: {html.escape(eiin)}</b>\n"
        f"👥 Employees: <b>{len(emps)}</b>\n"
        f"👤 Head records: <b>{len(heads_of(payload)) if payload else 0}</b>\n"
    )
    await context.bot.send_message(
        chat_id=q.message.chat_id, text=text,
        parse_mode=ParseMode.HTML, reply_markup=main_menu(eiin, len(emps)),
    )


# ───────── search ─────────
async def prompt_search_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    eiin = q.data.split(":", 1)[1]
    context.user_data["search_eiin"] = eiin
    await q.message.reply_text(
        "🔎 <b>Search employee</b>\nSend a name or part of a name.",
        parse_mode=ParseMode.HTML, reply_markup=ForceReply(selective=True),
    )
    return ASK_SEARCH


async def handle_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    eiin = context.user_data.get("search_eiin")
    query = (update.message.text or "").strip().lower()
    if not eiin or not query:
        await update.message.reply_text("Empty search. Try again.")
        return ConversationHandler.END
    payload = context.user_data.get("payload")
    if not payload or context.user_data.get("eiin") != eiin:
        try:
            payload = await fetch_eiin(eiin)
            context.user_data["payload"] = payload
            context.user_data["eiin"]    = eiin
        except Exception as e:
            await update.message.reply_text(f"❌ <code>{html.escape(str(e))}</code>",
                                            parse_mode=ParseMode.HTML)
            return ConversationHandler.END
    emps = emps_of(payload)
    matches = []
    for i, e in enumerate(emps):
        nm = str(pick(e, "name", "empName", "employeeName", "fullName")).lower()
        dg = str(pick(e, "designation", "designationName", "designation_name")).lower()
        if query in nm or query in dg:
            matches.append((i, e))
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=f"menu:{eiin}")]])
    if not matches:
        await update.message.reply_text(
            f"😕 No match for “{html.escape(query)}”.", reply_markup=back_kb)
        return ConversationHandler.END
    kb = []
    for i, e in matches[:20]:
        nm = pick(e, "name", "empName", "employeeName", "fullName")
        dg = pick(e, "designation", "designationName", "designation_name")
        label = f"👤 {nm}" + (f" · {dg}" if dg != "N/A" else "")
        if len(label) > 60: label = label[:57] + "..."
        kb.append([InlineKeyboardButton(label, callback_data=f"emp:{eiin}:{i}")])
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data=f"menu:{eiin}")])
    await update.message.reply_text(
        f"🔎 <b>{len(matches)}</b> match(es) for “{html.escape(query)}”.",
        parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb),
    )
    return ConversationHandler.END


# ───────── raw JSON ─────────
async def raw_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    eiin = q.data.split(":", 1)[1]
    payload = context.user_data.get("payload")
    if not payload:
        await q.answer("Fetch first.", show_alert=True)
        return
    buf = io.BytesIO(json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"))
    buf.name = f"eiin_{eiin}.json"
    await context.bot.send_document(chat_id=q.message.chat_id, document=buf)


# ───────── misc ─────────
async def noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


async def error_handler(update, context):
    log.exception("handler error", exc_info=context.error)


# ───────── application factory ─────────
def build_application() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("eiin", prompt_eiin_cmd),
            CallbackQueryHandler(prompt_eiin_cb,  pattern=r"^ask_eiin$"),
            CallbackQueryHandler(prompt_search_cb, pattern=r"^search:"),
        ],
        states={
            ASK_EIIN:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_eiin_input)],
            ASK_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(home_cb,    pattern=r"^home$"))
    app.add_handler(CallbackQueryHandler(about,      pattern=r"^about$"))
    app.add_handler(CallbackQueryHandler(menu_cb,    pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(menunew_cb, pattern=r"^menunew:"))
    app.add_handler(CallbackQueryHandler(head_cb,    pattern=r"^head:"))
    app.add_handler(CallbackQueryHandler(list_cb,    pattern=r"^list:"))
    app.add_handler(CallbackQueryHandler(listnew_cb, pattern=r"^listnew:"))
    app.add_handler(CallbackQueryHandler(emp_cb,     pattern=r"^emp:"))
    app.add_handler(CallbackQueryHandler(refresh_cb, pattern=r"^refresh:"))
    app.add_handler(CallbackQueryHandler(raw_cb,     pattern=r"^raw:"))
    app.add_handler(CallbackQueryHandler(noop,       pattern=r"^noop$"))
    app.add_error_handler(error_handler)

    return app

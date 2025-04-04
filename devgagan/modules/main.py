import time
import random
import string
import asyncio
from pyrogram import filters, Client
from devgagan import app
from config import API_ID, API_HASH, FREEMIUM_LIMIT, PREMIUM_LIMIT, OWNER_ID
from devgagan.core.get_func import get_msg
from devgagan.core.func import *
from devgagan.core.mongo import db
from devgagan.modules.shrink import is_user_verified
from pyrogram.errors import FloodWait, UserNotParticipant
from datetime import datetime, timedelta
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
async def generate_random_name(length=8):
    return ''.join(random.choices(string.ascii_lowercase, k=length))
users_loop = {}
interval_set = {}
batch_mode = {}
async def check_interval(user_id, freecheck):
    if freecheck != 1 or await is_user_verified(user_id):
        return True, None
    now = datetime.now()
    if user_id in interval_set:
        cooldown_end = interval_set[user_id]
        if now < cooldown_end:
            remaining_time = (cooldown_end - now).seconds // 60
            return False, f"Please wait {remaining_time} minute(s) before sending another link. Alternatively, purchase premium for instant access.\n\n> Hey 👋 You can use /token to use the bot free for 3 hours without any time limit."
        else:
            del interval_set[user_id]
    return True, None
async def set_interval(user_id, interval_minutes=5):
    now = datetime.now()
    interval_set[user_id] = now + timedelta(minutes=interval_minutes)
@app.on_message(filters.regex(r'https?://(?:www\.)?t\.me/(?:c/)?([^\s/]+)/(\d+)'))
async def single_link(_, message):
    user_id = message.chat.id
    if user_id in batch_mode:
        return
    if users_loop.get(user_id, False):
        await message.reply(
            "لديك عملية جارية بالفعل. يرجى الانتظار حتى تنتهي أو إلغاؤها باستخدام /cancel."
        )
        return
    freecheck = await chk_user(message, user_id)
    if freecheck == 1 and FREEMIUM_LIMIT == 0 and user_id not in OWNER_ID:
        await message.reply("الخدمة المجانية غير متاحة حاليًا. قم بالترقية إلى الإصدار المميز للوصول.")
        return
    can_proceed, response_message = await check_interval(user_id, freecheck)
    if not can_proceed:
        await message.reply(response_message)
        return
    users_loop[user_id] = True
    link = get_link(message.text)
    userbot = None
    try:
        join = await subscribe(_, message)
        if join == 1:
            users_loop[user_id] = False
            return
        msg = await message.reply("Processing...")
        is_bot_channel_member = False
        channel_username = None
        message_id_link = None

        if 't.me/c/' in link or 't.me/b/' in link:
            parts = link.split("/")
            if 't.me/b/' not in link:
                channel_username = parts[parts.index('c') + 1]
                message_id_link = parts[-1]
            else:
                channel_username = parts[-2]
                message_id_link = parts[-1]
            try:
                # Check if bot is a member of the channel
                await app.get_chat_member(f'@{channel_username}', app.me.id)
                is_bot_channel_member = True
            except UserNotParticipant:
                is_bot_channel_member = False
            except Exception as e:
                is_bot_channel_member = False # Assume not a member in case of other errors
                print(f"Error checking bot membership: {e}")


        if 't.me/' in link and 't.me/+' not in link and 't.me/c/' not in link and 't.me/b/' not in link:
            await get_msg(app, user_id, msg.id, link, 0, message, is_bot_channel_member=False) # Always False for direct links
            await set_interval(user_id, interval_minutes=5)
            return
        data = await db.get_data(user_id)
        if data and data.get("session"):
            session = data.get("session")
            try:
                device = 'Vivo Y20'
                session_name = await generate_random_name()
                userbot = Client(session_name, api_id=API_ID, api_hash=API_HASH, device_model=device, session_string=session)
                await userbot.start()
            except:
                users_loop[user_id] = False
                return await msg.edit_text("انتهت صلاحية تسجيل الدخول /login مرة أخرى...")
        else:
            users_loop[user_id] = False
            await msg.edit_text("تسجيل الدخول في البوت أولاً...")
            return
        try:
            if 't.me/+' in link:
                q = await userbot_join(userbot, link)
                await msg.edit_text(q)
            elif 't.me/c/' in link or 't.me/b/' in link:
                client_to_use = app if is_bot_channel_member else userbot
                await get_msg(client_to_use, user_id, msg.id, link, 0, message, is_bot_channel_member=is_bot_channel_member)
                await set_interval(user_id, interval_minutes=5)
            else:
                await msg.edit_text("تنسيق الرابط غير صالح.")
        except Exception as e:
            await msg.edit_text(f"الرابط: `{link}`\n\n**خطأ:** {str(e)}")
    except FloodWait as fw:
        await msg.edit_text(f'حاول مرة أخرى بعد {fw.x} ثانية بسبب الفيضان من تيليجرام.')
    except Exception as e:
        await msg.edit_text(f"الرابط: `{link}`\n\n**خطأ:** {str(e)}")
    finally:
        if userbot and userbot.is_connected:
            await userbot.stop()
        users_loop[user_id] = False
@app.on_message(filters.command("batch"))
async def batch_link(_, message):
    user_id = message.chat.id
    if users_loop.get(user_id, False):
        await app.send_message(
            message.chat.id,
            "لديك بالفعل عملية دفعية قيد التشغيل. يرجى الانتظار حتى تكتمل العملية الحالية قبل بدء عملية جديدة."
        )
        return
    freecheck = await chk_user(message, user_id)
    if freecheck == 1 and FREEMIUM_LIMIT == 0 and user_id not in OWNER_ID:
        await message.reply("الخدمة المجانية غير متاحة حاليًا. قم بالترقية إلى الإصدار المميز للوصول.")
        return
    toker = await is_user_verified(user_id)
    if toker:
        max_batch_size = (FREEMIUM_LIMIT + 20)
        freecheck = 0
    else:
        freecheck = await chk_user(message, user_id)
        if freecheck == 1:
            max_batch_size = FREEMIUM_LIMIT
        else:
            max_batch_size = PREMIUM_LIMIT

    while True:
        start = await app.ask(message.chat.id, text="يرجى إرسال رابط البداية.")
        start_id = start.text.strip()
        s = start_id.split("/")[-1]
        try:
            cs = int(s)
            break
        except ValueError:
            await app.send_message(message.chat.id, "رابط غير صالح. يرجى الإرسال مرة أخرى...")
    while True:
        num_messages = await app.ask(message.chat.id, text="كم عدد الرسائل التي تريد معالجتها؟")
        try:
            cl = int(num_messages.text.strip())
            if cl <= 0 or cl > max_batch_size:
                raise ValueError(f"يجب أن يكون عدد الرسائل بين 1 و {max_batch_size}.")
            break
        except ValueError as e:
            await app.send_message(message.chat.id, f"رقم غير صالح: {e}. يرجى إدخال رقم صالح مرة أخرى...")
    can_proceed, response_message = await check_interval(user_id, freecheck)
    if not can_proceed:
        await message.reply(response_message)
        return
    join_button = InlineKeyboardButton("Join Channel", url="https://t.me/romm207")
    keyboard = InlineKeyboardMarkup([[join_button]])
    pin_msg = await app.send_message(
        user_id,
        "بدأت عملية الدفع ⚡\n__معالجة: 0/{cl}__\n\n**__مدعوم من @X_XF8__**",
        reply_markup=keyboard
    )
    try:
        await pin_msg.pin()
    except Exception as e:
        await pin_msg.pin(both_sides=True)
    users_loop[user_id] = True
    try:
        for i in range(cs, cs + cl):
            if user_id in users_loop and users_loop[user_id]:
                try:
                    x = start_id.split('/')
                    y = x[:-1]
                    result = '/'.join(y)
                    url = f"{result}/{i}"
                    link = get_link(url)
                    if 't.me/' in link and 't.me/b/' not in link and 't.me/c' not in link:
                        msg = await app.send_message(message.chat.id, f"معالجة الرابط {url}...")
                        await get_msg(None, user_id, msg.id, link, 0, message)
                        await pin_msg.edit_text(
                        f"بدأت عملية الدفع ⚡\n__معالجة: {i - cs + 1}/{cl}__\n\n**__مدعوم من @X_XF8__**",
                        reply_markup=keyboard
                        )
                        await asyncio.sleep(5)
                except Exception as e:
                    print(f"خطأ في معالجة الرابط {url}: {e}")
                    continue
        if not any(prefix in start_id for prefix in ['t.me/c/', 't.me/b/']):
            await set_interval(user_id, interval_minutes=20)
            await app.send_message(message.chat.id, "اكتملت الدفعة بنجاح! 🎉")
            await pin_msg.edit_text(
                        f"اكتملت عملية الدفع لـ {cl} رسالة استمتع 🌝\n\n**__مدعوم من @X_XF8__**",
                        reply_markup=keyboard
            )
            return
        data = await db.get_data(user_id)
        if data and data.get("session"):
            session = data.get("session")
            device = 'Vivo Y20'
            session_name = await generate_random_name()
            userbot = Client(
                session_name,
                api_id=API_ID,
                api_hash=API_HASH,
                device_model=device,
                session_string=session
            )
            await userbot.start()
        else:
            await app.send_message(message.chat.id, "تسجيل الدخول في البوت أولاً...")
            return
        try:
            for i in range(cs, cs + cl):
                if user_id in users_loop and users_loop[user_id]:
                    try:
                        x = start_id.split('/')
                        y = x[:-1]
                        result = '/'.join(y)
                        url = f"{result}/{i}"
                        link = get_link(url)
                        if 't.me/b/' in link or 't.me/c/' in link:
                            msg = await app.send_message(message.chat.id, f"معالجة الرابط {url}...")
                            await get_msg(userbot, user_id, msg.id, link, 0, message)
                            sleep_msg = await app.send_message(
                                message.chat.id,
                                "النوم لمدة 5 ثوانٍ لتجنب الفيضان..."
                            )
                            await asyncio.sleep(2)
                            await pin_msg.edit_text(
                            f"بدأت عملية الدفع ⚡\n__معالجة: {i - cs + 1}/{cl}__\n\n**__مدعوم من @X_XF8__**",
                            reply_markup=keyboard
                            )
                            await asyncio.sleep(10)
                            await sleep_msg.delete()
                    except Exception as e:
                        print(f"خطأ في معالجة الرابط {url}: {e}")
                        continue
        finally:
            if userbot.is_connected:
                await userbot.stop()
        await app.send_message(message.chat.id, "اكتملت الدفعة بنجاح! 🎉")
        await set_interval(user_id, interval_minutes=20)
        await pin_msg.edit_text(
                        f"اكتملت الدفعة لـ {cl} رسالة ⚡\n\n**__مدعوم من @X_XF8__**",
                        reply_markup=keyboard
        )
    except FloodWait as fw:
        await app.send_message(
            message.chat.id,
            f"حاول مرة أخرى بعد {fw.x} ثانية بسبب الفيضان من تيليجرام."
        )
    except Exception as e:
        await app.send_message(message.chat.id, f"خطأ: {str(e)}")
    finally:
        users_loop.pop(user_id, None)
@app.on_message(filters.command("cancel"))
async def stop_batch(_, message):
    user_id = message.chat.id
    if user_id in users_loop and users_loop[user_id]:
        users_loop[user_id] = False
        await app.send_message(
            message.chat.id,
            "تم إيقاف المعالجة الدفعية بنجاح. يمكنك بدء دفعة جديدة الآن إذا كنت تريد ذلك."
        )
    elif user_id in users_loop and not users_loop[user_id]:
        await app.send_message(
            message.chat.id,
            "تم إيقاف العملية الدفعية بالفعل. لا توجد دفعة نشطة للإلغاء."
        )
    else:
        await app.send_message(
            message.chat.id,
            "لا توجد معالجة دفعية نشطة قيد التشغيل للإلغاء."
        )

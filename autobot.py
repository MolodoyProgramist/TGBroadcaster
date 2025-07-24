import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

# === Конфигурация ===
BOT_TOKEN = '7720559426:AAF35_mJcDWGdhRNPVX3kdvk_5adsEvQG2k'
API_ID = 23603493
API_HASH = '6de7be83325747a28538fa478faa60f1'
ADMIN_ID = 6080202170

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# === FSM состояния ===
class Broadcast(StatesGroup):
    waiting_for_text = State()
    waiting_for_count = State()
    waiting_for_chat = State()

class Analyze(StatesGroup):
    waiting_for_chat = State()

# === Кнопки ===
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="Анализ чата")]
    ],
    resize_keyboard=True
)

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Отмена")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# === /start ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Выбери действие:", reply_markup=main_kb)

# === 📢 Рассылка ===
@dp.message(lambda msg: msg.text == "📢 Рассылка")
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Только админ может использовать эту функцию.")
        return
    await message.answer("✏️ Введи текст сообщения:", reply_markup=cancel_kb)
    await state.set_state(Broadcast.waiting_for_text)

@dp.message(Broadcast.waiting_for_text)
async def get_broadcast_text(message: types.Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Рассылка отменена.", reply_markup=main_kb)
        return

    await state.update_data(text=message.text)
    await message.answer("🔢 Сколько раз отправить?", reply_markup=cancel_kb)
    await state.set_state(Broadcast.waiting_for_count)

@dp.message(Broadcast.waiting_for_count)
async def get_broadcast_count(message: types.Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Рассылка отменена.", reply_markup=main_kb)
        return

    if not message.text.isdigit():
        await message.answer("⚠️ Введи число.", reply_markup=cancel_kb)
        return
    await state.update_data(count=int(message.text))
    await message.answer("🔗 Введи ссылку на чат (@chatname):", reply_markup=cancel_kb)
    await state.set_state(Broadcast.waiting_for_chat)

@dp.message(Broadcast.waiting_for_chat)
async def run_broadcast(message: types.Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("❌ Рассылка отменена.", reply_markup=main_kb)
        return

    data = await state.get_data()
    text = data["text"]
    count = data["count"]
    chat = message.text.strip()

    if not chat.startswith("@"):
        await message.answer("⚠️ Ссылка должна начинаться с @.", reply_markup=cancel_kb)
        return

    await message.answer(f"🚀 Рассылка в {chat} началась...", reply_markup=main_kb)

    client = TelegramClient("user_session", API_ID, API_HASH)

    try:
        await client.start()
    except SessionPasswordNeededError:
        await message.answer("🔐 Включена двухфакторка. Войди вручную.")
        await state.clear()
        return

    try:
        entity = await client.get_entity(chat)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        await client.disconnect()
        await state.clear()
        return

    success, fail = 0, 0
    for i in range(count):
        try:
            await client.send_message(entity, text)
            success += 1
        except Exception:
            fail += 1
        await asyncio.sleep(1.5)

    await client.disconnect()
    await message.answer(f"✅ Успешно: {success}\n❌ Ошибок: {fail}", reply_markup=main_kb)
    await state.clear()

# === Анализ чата ===
@dp.message(lambda msg: msg.text == "Анализ чата")
async def analyze_chat_request(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Только админ может использовать эту функцию.")
        return
    await message.answer("📥 Введи ссылку на чат (@chatname):")
    await state.set_state(Analyze.waiting_for_chat)

@dp.message(Analyze.waiting_for_chat)
async def analyze_chat(message: types.Message, state: FSMContext):
    chat = message.text.strip()
    if not chat.startswith("@"):
        await message.answer("⚠️ Ссылка должна начинаться с @.")
        return

    await message.answer("⏳ Сбор участников...")

    client = TelegramClient("user_session", API_ID, API_HASH)

    try:
        await client.start()
    except SessionPasswordNeededError:
        await message.answer("🔐 Включена двухфакторка.")
        await state.clear()
        return

    try:
        entity = await client.get_entity(chat)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        await client.disconnect()
        await state.clear()
        return

    participants = []
    try:
        async for user in client.iter_participants(entity):
            participants.append(user)
    except Exception as e:
        await message.answer(f"❌ Ошибка при сборе: {e}")
        await client.disconnect()
        await state.clear()
        return

    filename = f"users_{entity.id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        for user in participants:
            uname = f"@{user.username}" if user.username else "NoUsername"
            name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            f.write(f"{uname} | {name} | ID: {user.id}\n")

    await client.disconnect()
    await message.answer_document(types.FSInputFile(filename), caption="✅ Участники сохранены.")
    os.remove(filename)
    await state.clear()

# === Запуск ===
async def main():
    print("✅ Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

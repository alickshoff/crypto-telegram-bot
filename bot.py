import logging
import requests
import socket
import matplotlib.pyplot as plt
from io import BytesIO

import nest_asyncio
nest_asyncio.apply()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, JobQueue

# === Настройки ===
TOKEN = "7286598622:AAEOSZH4FK1Uh5wufaqVRzYBgBq8Y2ZQ_Hw"

# === Логирование ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# === Проверка интернет-соединения ===
def is_internet_available():
    try:
        socket.create_connection(("www.google.com", 80))
        return True
    except OSError:
        return False


# === Команда /start — главное меню с кнопками ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 RSI анализ", callback_data="rsi")],
        [InlineKeyboardButton("💰 Текущая цена", callback_data="price")],
        [InlineKeyboardButton("🎯 Пример точки входа", callback_data="entry")],
        [InlineKeyboardButton("💧 Оценка ликвидности", callback_data="liquidity")],
        [InlineKeyboardButton("📈 Недельный прогноз", callback_data="forecast")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)


# === Обработка нажатий на кнопки ===
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "rsi":
        await rsi_handler(query, context)
    elif query.data == "price":
        await price_handler(query, context)
    elif query.data == "entry":
        await entry_handler(query, context)
    elif query.data == "liquidity":
        await liquidity_handler(query, context)
    elif query.data == "forecast":
        await forecast_handler(query, context)
    elif query.data == "back":
        # Возврат в главное меню
        keyboard = [
            [InlineKeyboardButton("📊 RSI анализ", callback_data="rsi")],
            [InlineKeyboardButton("💰 Текущая цена", callback_data="price")],
            [InlineKeyboardButton("🎯 Пример точки входа", callback_data="entry")],
            [InlineKeyboardButton("💧 Оценка ликвидности", callback_data="liquidity")],
            [InlineKeyboardButton("📈 Недельный прогноз", callback_data="forecast")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите действие:", reply_markup=reply_markup)


# === Функция расчёта RSI ===
def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return []

    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period if sum(losses[:period]) > 0 else 1e-10

    rsi_values = [50.0] * len(prices)  # Заполняем заглушкой
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        rsi_values[i] = rsi

    return rsi_values


# === Отправка графика RSI ===
async def send_rsi_chart(chat_id, context):
    url = "https://min-api.cryptocompare.com/data/v2/histominute "
    params = {
        "fsym": "BTC",
        "tsym": "USD",
        "limit": 100,
        "aggregate": 5
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")

        data = response.json().get("Data", {}).get("Data", [])
        closes = [float(item["close"]) for item in data]
        rsi_values = calculate_rsi(closes)

        # Строим график
        plt.figure(figsize=(10, 4))
        plt.plot(rsi_values, label="RSI")
        plt.axhline(30, color="red", linestyle="--", alpha=0.3)
        plt.axhline(70, color="green", linestyle="--", alpha=0.3)
        plt.title("RSI для BTC/USD")
        plt.xlabel("Периоды")
        plt.ylabel("Значение RSI")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()

        # Сохраняем график в байты
        img_byte_arr = BytesIO()
        plt.savefig(img_byte_arr, format='png')
        plt.close()
        img_byte_arr.seek(0)

        # Отправляем как изображение
        await context.bot.send_photo(chat_id=chat_id, photo=InputFile(img_byte_arr, filename="rsi.png"))

    except Exception as e:
        logging.error(f"Ошибка при построении графика RSI: {e}")
        await context.bot.send_message(chat_id=chat_id, text="⚠️ Не удалось построить график RSI.")


# === Обработчики для каждой кнопки ===
async def rsi_handler(query, context):
    chat_id = query.message.chat_id
    await send_rsi_chart(chat_id, context)


async def price_handler(query, context):
    if not is_internet_available():
        text = "🌐 Нет интернета."
    else:
        try:
            url = "https://min-api.cryptocompare.com/data/price "
            params = {"fsym": "BTC", "tsyms": "USD"}
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")

            price = response.json().get("USD", None)
            if not price:
                raise Exception("Нет данных")

            text = f"💰 BTC/USDT: ${price:.2f}"
        except Exception as e:
            logging.error(f"Ошибка в цене: {e}")
            text = "💰 BTC/USDT: $62,000 (данные недоступны)"

    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup)


# === Другие обработчики ===
async def entry_handler(query, context):
    text = "🎯 Пример точки входа: $63,000"
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup)


async def liquidity_handler(query, context):
    text = "💧 Ликвидность по BTC/USDT высокая."
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup)


async def forecast_handler(query, context):
    text = "📈 Прогноз на неделю: ожидается рост до $65,000"
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup)


# === Автообновление цены BTC/USDT ===
async def auto_update_price(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id

    try:
        url = "https://min-api.cryptocompare.com/data/price "
        params = {"fsym": "BTC", "tsyms": "USD"}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")

        price = response.json().get("USD", None)
        if not price:
            raise Exception("Нет данных")

        message = f"🔄 BTC/USDT: ${price:.2f} (автообновление)"
        await context.bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        logging.error(f"Ошибка автообновления: {e}")
        await context.bot.send_message(chat_id=chat_id, text="🔄 Не удалось обновить цену BTC/USDT")


# === Команда /subscribe — включить автообновление цен ===
async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    await context.bot.send_message(chat_id=chat_id, text="✅ Включено автообновление цен BTC/USDT (каждые 5 минут)")
    context.job_queue.run_repeating(auto_update_price, interval=300, chat_id=chat_id)


# === Команда /unsubscribe — отключить автообновление цен ===
async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs:
        job.schedule_removal()
    await context.bot.send_message(chat_id=chat_id, text="❌ Автообновление цен отключено.")


# === Запуск бота с поддержкой графиков и автообновления ===
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))

    # Кнопки
    app.add_handler(CallbackQueryHandler(button_click))

    # Автообновление цен
    await app.initialize()

    print("Бот запущен...")
    await app.run_polling()


# === Точка входа ===
if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
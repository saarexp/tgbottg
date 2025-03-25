from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from jinja2 import Template
import os
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

user_state = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("📦 POSTNL", callback_data="vervoerder_postnl"),
            InlineKeyboardButton("🚚 DHL", callback_data="vervoerder_dhl")
        ],
        [
            InlineKeyboardButton("💡 Doe een suggestie voor nieuwe verzendbewijzen", url="https://t.me/gasgevenn")
        ]
    ]
    with open("img/welkom.png", "rb") as img:
        await update.message.reply_photo(
            photo=img,
            caption="Welkom bij de verzendbewijs generator! Kies een verzenddienst of doe een suggestie:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if user_id not in user_state:
        user_state[user_id] = {}

    if data == "terug_naar_start":
        await query.answer()
        await query.message.delete()
        await context.bot.send_message(chat_id=user_id, text="/start")
        return

    if data.startswith("vervoerder_"):
        vervoerder = data.split("_")[1]
        user_state[user_id]["vervoerder"] = vervoerder

        if vervoerder == "postnl":
            bericht = "Je hebt POSTNL gekozen. 🧾\n🏢 Wat is de naam van het bedrijf waar het pakket naartoe wordt verzonden? (Bijv. Amazon)"
            afbeelding = "img/pnl.png"
        else:
            bericht = "Je hebt DHL gekozen. 📛\n👤 Wat is je voor- en achternaam? (Bijv. Jan Jansen)"
            afbeelding = "img/dhl.png"

        with open(afbeelding, "rb") as img:
            await query.message.reply_photo(photo=img, caption=bericht)

        await query.message.delete()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    if user_id not in user_state or "vervoerder" not in user_state[user_id]:
        await update.message.reply_text("Typ /start om te beginnen.")
        return

    state = user_state[user_id]
    vervoerder = state.get("vervoerder")

    if vervoerder == "postnl":
        if "bedrijf" not in state:
            state["bedrijf"] = text
            await update.message.reply_text("📍 Wat is de straat van het bedrijf? (Bijv. Herengracht 1)")
        elif "straat" not in state:
            state["straat"] = text
            await update.message.reply_text("📮 Wat is de postcode van de ontvangen? (Bijv. 1022VX)")
        elif "postcode" not in state:
            state["postcode"] = text
            await update.message.reply_text("🏙️ Welke stad woont de ontvanger? (Bijv. Amsterdam)")
        elif "stad" not in state:
            state["stad"] = text
            await update.message.reply_text("🌍 Wat is het land van bestemming? (Bijv. Nederland)")
        elif "land" not in state:
            state["land"] = text
            await update.message.reply_text("🔍 Wat is je Track & Trace code? (Bijv. PNL23834HSDHH)")
        elif "track" not in state:
            state["track"] = text
            await generate_image(update, context, state)
            user_state.pop(user_id)

    elif vervoerder == "dhl":
        if "naam" not in state:
            state["naam"] = text
            await update.message.reply_text("🔍 Wat is je Track & Trace code? (Bijv. JVG36283V3Y73G)")
        elif "track" not in state:
            state["track"] = text
            await update.message.reply_text("🏢 Wat is de naam van het bedrijf waar het pakket naartoe wordt verzonden? (Bijv. Amazon)")
        elif "bedrijf" not in state:
            state["bedrijf"] = text
            await update.message.reply_text("📅 Wat is de datum van inlevering? (Bijv. Maandag 24 maart)")
        elif "datum" not in state:
            state["datum"] = text
            await update.message.reply_text("⏰ Wat is de tijd van inlevering? (Bijv. 14.22)")
        elif "tijd" not in state:
            state["tijd"] = text
            await update.message.reply_text("🏪 Wat is de naam van het pakketpunt? (Bijv. Bruna Amsterdam)")
        elif "pakketpunt" not in state:
            state["pakketpunt"] = text
            await update.message.reply_text("📍 Wat is het adres van het pakketpunt? (Bijv. Breestraat 22)")
        elif "adres" not in state:
            state["adres"] = text
            await update.message.reply_text("🗺️ Wat is de postcode en stad? (Bijv. 1044BX Amsterdam)")
        elif "postcode_stad" not in state:
            state["postcode_stad"] = text
            await generate_image(update, context, state)
            user_state.pop(user_id)

def load_template(vervoerder):
    path = f"template/template_{vervoerder}.html"
    if not os.path.exists(path):
        return Template("""
            <html>
                <body>
                    <h1>{{ vervoerder|upper }}</h1>
                    {% for key, value in kwargs.items() %}
                        <p>{{ key }}: {{ value }}</p>
                    {% endfor %}
                </body>
            </html>
        """)
    with open(path, "r", encoding="utf-8") as f:
        return Template(f.read())

async def html_to_image_playwright(html_str, output_path):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html_str)
        await page.screenshot(path=output_path, full_page=True)
        await browser.close()

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE, data):
    template = load_template(data["vervoerder"])
    rendered = template.render(**data)

    os.makedirs("verzendbewijzen", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    naam_segment = data.get("naam", data.get("bedrijf", "onbekend")).replace(" ", "_")
    filename = f"verzendbewijzen/{data['vervoerder']}_{naam_segment}_{timestamp}.png"

    await html_to_image_playwright(rendered, filename)

    if not os.path.exists(filename):
        await update.message.reply_text("❌ Afbeelding kon niet worden gegenereerd.")
        return

    knop = [[InlineKeyboardButton("🔁 Terug naar start", callback_data="terug_naar_start")]]
    await update.message.reply_text("📸 Screenshot is klaar:")
    with open(filename, "rb") as img:
        await update.message.reply_photo(photo=img, reply_markup=InlineKeyboardMarkup(knop))

def main():
    app = ApplicationBuilder().token("7586502264:AAECp98W53wZdG4pgmiUPtRpevylKAPNNT8").build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot draait...")
    app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())

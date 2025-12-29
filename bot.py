import os
import hashlib
import logging
import aiosqlite
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_FILE = "duplicates.db"

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ================= DATABASE =================
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                chat_id INTEGER,
                content_hash TEXT,
                PRIMARY KEY (chat_id, content_hash)
            )
        """)
        await db.commit()

# ================= HASH FUNCTIONS =================
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

async def generate_message_hash(message) -> str | None:
    if message.text:
        return sha256(message.text.encode())

    if message.photo:
        file = await message.photo[-1].get_file()
        content = await file.download_as_bytearray()
        return sha256(content)

    if message.video:
        file = await message.video.get_file()
        content = await file.download_as_bytearray()
        return sha256(content)

    if message.document:
        file = await message.document.get_file()
        content = await file.download_as_bytearray()
        return sha256(content)

    if message.audio:
        file = await message.audio.get_file()
        content = await file.download_as_bytearray()
        return sha256(content)

    return None

# ================= HANDLER =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.channel_post
    if not message:
        return

    chat_id = message.chat_id
    msg_hash = await generate_message_hash(message)

    if not msg_hash:
        return

    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "SELECT 1 FROM messages WHERE chat_id = ? AND content_hash = ?",
            (chat_id, msg_hash)
        )
        exists = await cursor.fetchone()

        if exists:
            try:
                await message.delete()
                logging.info(f"Mensagem duplicada deletada no chat {chat_id}")
            except Exception as e:
                logging.error(f"Erro ao deletar mensagem: {e}")
            return

        await db.execute(
            "INSERT INTO messages (chat_id, content_hash) VALUES (?, ?)",
            (chat_id, msg_hash)
        )
        await db.commit()

# ================= MAIN =================
async def main():
    await init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(
        MessageHandler(
            filters.ALL,
            handle_message
        )
    )

    logging.info("🤖 Bot anti-duplicados iniciado...")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from app.config import settings
from app.services.ollama_client import summarize_chat, generate_creative

_scheduler: AsyncIOScheduler | None = None


async def job_daily_summary(bot: Bot):
    if not settings.primary_chat_id:
        return
    text = await summarize_chat()
    await bot.send_message(chat_id=settings.primary_chat_id, message_thread_id=settings.summary_topic_id, text=text, disable_web_page_preview=True)


async def job_creative(bot: Bot):
    if not settings.primary_chat_id:
        return
    text = await generate_creative()
    await bot.send_message(chat_id=settings.primary_chat_id, message_thread_id=settings.creative_topic_id, text=text, disable_web_page_preview=True)


async def setup_scheduler(bot: Bot):
    global _scheduler
    if _scheduler:
        return
    tz = pytz.timezone(settings.timezone)
    _scheduler = AsyncIOScheduler(timezone=tz)
    _scheduler.add_job(job_daily_summary, CronTrigger(hour=8, minute=0), args=[bot], id="daily_summary")
    _scheduler.add_job(job_creative, CronTrigger(hour=20, minute=0), args=[bot], id="creative")
    _scheduler.start()

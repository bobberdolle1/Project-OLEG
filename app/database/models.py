from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, Integer, String, DateTime, Boolean, ForeignKey, Text, UniqueConstraint, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(16), default='active', index=True) # active, left
    strikes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default='active', index=True) # active, left

    game: Mapped["GameStat"] = relationship(back_populates="user", uselist=False)
    user_achievements: Mapped[list["UserAchievement"]] = relationship(back_populates="user")
    user_quests: Mapped[list["UserQuest"]] = relationship(back_populates="user")
    guild_memberships: Mapped[list["GuildMember"]] = relationship(back_populates="user")
    question_history: Mapped[list["UserQuestionHistory"]] = relationship(back_populates="user")
    warnings: Mapped[list["Warning"]] = relationship(back_populates="user")
    quotes: Mapped[list["Quote"]] = relationship(back_populates="user")
    admin_roles: Mapped[list["Admin"]] = relationship(back_populates="user")
    blacklist_entries: Mapped[list["Blacklist"]] = relationship(back_populates="user")
    private_chat: Mapped["PrivateChat"] = relationship(back_populates="user", uselist=False)


class MessageLog(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64))
    text: Mapped[Optional[str]] = mapped_column(Text)
    has_link: Mapped[bool] = mapped_column(Boolean, default=False)
    links: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # '\n' separated
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class GameStat(Base):
    __tablename__ = "game_stats"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String(64))

    size_cm: Mapped[int] = mapped_column(Integer, default=0)
    next_grow_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pvp_wins: Mapped[int] = mapped_column(Integer, default=0)
    grow_count: Mapped[int] = mapped_column(Integer, default=0)
    casino_jackpots: Mapped[int] = mapped_column(Integer, default=0)
    reputation: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[User] = relationship(back_populates="game")


class Wallet(Base):
    __tablename__ = "wallets"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)


class Achievement(Base):
    __tablename__ = "achievements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)

    users: Mapped[list["UserAchievement"]] = relationship(back_populates="achievement")


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    achievement_id: Mapped[int] = mapped_column(ForeignKey("achievements.id"), primary_key=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="user_achievements")
    achievement: Mapped["Achievement"] = relationship(back_populates="users")


class TradeOffer(Base):
    __tablename__ = "trade_offers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    item_type: Mapped[str] = mapped_column(String(64))
    item_quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(64), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    seller: Mapped["User"] = relationship(foreign_keys=[seller_user_id])


class Auction(Base):
    __tablename__ = "auctions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    item_type: Mapped[str] = mapped_column(String(64))
    item_quantity: Mapped[int] = mapped_column(Integer)
    start_price: Mapped[int] = mapped_column(Integer)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(64), default="active")
    current_highest_bid_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bids.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    seller: Mapped["User"] = relationship(foreign_keys=[seller_user_id])
    bids: Mapped[list["Bid"]] = relationship(back_populates="auction")
    current_highest_bid: Mapped[Optional["Bid"]] = relationship(foreign_keys=[current_highest_bid_id], post_update=True)


class Bid(Base):
    __tablename__ = "bids"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id"))
    bidder_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    auction: Mapped["Auction"] = relationship(back_populates="bids")
    bidder: Mapped["User"] = relationship(foreign_keys=[bidder_user_id])


class Quest(Base):
    __tablename__ = "quests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    reward_type: Mapped[str] = mapped_column(String(64))
    reward_amount: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64))
    target_value: Mapped[int] = mapped_column(Integer)

    users_quests: Mapped[list["UserQuest"]] = relationship(back_populates="quest")


class UserQuest(Base):
    __tablename__ = "user_quests"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id"), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="user_quests")
    quest: Mapped["Quest"] = relationship(back_populates="users_quests")


class Guild(Base):
    __tablename__ = "guilds"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner: Mapped["User"] = relationship(foreign_keys=[owner_user_id])
    members: Mapped[list["GuildMember"]] = relationship(back_populates="guild")


class GuildMember(Base):
    __tablename__ = "guild_members"
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    role: Mapped[str] = mapped_column(String(64), default="member")

    guild: Mapped["Guild"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="guild_memberships")


class TeamWar(Base):
    __tablename__ = "team_wars"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    declarer_guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"))
    defender_guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="declared")
    winner_guild_id: Mapped[Optional[int]] = mapped_column(ForeignKey("guilds.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    declarer_guild: Mapped["Guild"] = relationship(foreign_keys=[declarer_guild_id])
    defender_guild: Mapped["Guild"] = relationship(foreign_keys=[defender_guild_id])
    winner_guild: Mapped[Optional["Guild"]] = relationship(foreign_keys=[winner_guild_id])
    participants: Mapped[list["TeamWarParticipant"]] = relationship(back_populates="team_war")


class TeamWarParticipant(Base):
    __tablename__ = "team_war_participants"
    team_war_id: Mapped[int] = mapped_column(ForeignKey("team_wars.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id")) # Guild at the time of participation
    score: Mapped[int] = mapped_column(Integer, default=0)
    kills: Mapped[int] = mapped_column(Integer, default=0)
    deaths: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    team_war: Mapped["TeamWar"] = relationship(back_populates="participants")
    user: Mapped["User"] = relationship() # One-way relationship
    guild: Mapped["Guild"] = relationship() # One-way relationship


class DuoTeam(Base):
    __tablename__ = "duo_teams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user1_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user2_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user1: Mapped["User"] = relationship(foreign_keys=[user1_id])
    user2: Mapped["User"] = relationship(foreign_keys=[user2_id])
    stats: Mapped["DuoStat"] = relationship(back_populates="duo_team", uselist=False)

    __table_args__ = (
        UniqueConstraint('user1_id', 'user2_id', name='_user1_user2_uc'),
        CheckConstraint('user1_id < user2_id', name='_user1_lt_user2_cc')
    )


class DuoStat(Base):
    __tablename__ = "duo_stats"
    duo_team_id: Mapped[int] = mapped_column(ForeignKey("duo_teams.id"), primary_key=True)
    rating: Mapped[int] = mapped_column(Integer, default=1000) # Initial ELO rating
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    
    duo_team: Mapped["DuoTeam"] = relationship(back_populates="stats")


class GlobalStats(Base):
    __tablename__ = "global_stats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(DateTime, unique=True, index=True) # Date for the stats
    period_type: Mapped[str] = mapped_column(String(64)) # "daily", "weekly", "monthly"

    total_pvp_wins: Mapped[int] = mapped_column(Integer, default=0)
    pvp_wins_delta: Mapped[int] = mapped_column(Integer, default=0)

    total_grow_count: Mapped[int] = mapped_column(Integer, default=0)
    grow_count_delta: Mapped[int] = mapped_column(Integer, default=0)

    total_casino_jackpots: Mapped[int] = mapped_column(Integer, default=0)
    casino_jackpots_delta: Mapped[int] = mapped_column(Integer, default=0)

    total_reputation: Mapped[int] = mapped_column(Integer, default=0)
    reputation_delta: Mapped[int] = mapped_column(Integer, default=0)


class UserQuestionHistory(Base):
    __tablename__ = "user_question_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    asked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="question_history")


class SpamPattern(Base):
    __tablename__ = "spam_patterns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pattern: Mapped[str] = mapped_column(String(255), unique=True)
    is_regex: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Warning(Base):
    __tablename__ = "warnings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    moderator_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="warnings")

class ToxicityConfig(Base):
    __tablename__ = "toxicity_configs"
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    threshold: Mapped[int] = mapped_column(Integer, default=75) # 0-100
    action: Mapped[str] = mapped_column(String(64), default="warn") # "warn", "delete", "mute"
    mute_duration: Mapped[int] = mapped_column(Integer, default=5) # in minutes


class ToxicityConfig(Base):
    __tablename__ = "toxicity_configs"
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    threshold: Mapped[float] = mapped_column(Float, default=0.8) # Toxicity score threshold
    action: Mapped[str] = mapped_column(String(64), default="warn") # "warn", "delete", "mute"
    mute_duration: Mapped[int] = mapped_column(Integer, default=5) # in minutes
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ToxicityLog(Base):
    __tablename__ = "toxicity_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    message_text: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float)
    category: Mapped[Optional[str]] = mapped_column(String(128))
    action_taken: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Quote(Base):
    __tablename__ = "quotes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    username: Mapped[str] = mapped_column(String(64))
    image_data: Mapped[bytes] = mapped_column(Text)  # Изображение цитаты в байтах
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Комментарий Олега
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    is_golden_fund: Mapped[bool] = mapped_column(Boolean, default=False)  # В "золотом фонде" или нет
    is_sticker: Mapped[bool] = mapped_column(Boolean, default=False)  # Является ли стикером
    sticker_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # ID файла стикера в Telegram
    telegram_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # ID чата в Telegram
    telegram_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # ID сообщения в Telegram
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user: Mapped["User"] = relationship(back_populates="quotes")


class ModerationConfig(Base):
    __tablename__ = "moderation_configs"
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mode: Mapped[str] = mapped_column(String(20), default="normal")  # light, normal, dictatorship
    enabled_features: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON строка с настройками
    banned_words: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON строка с запрещенными словами
    flood_threshold: Mapped[int] = mapped_column(Integer, default=5)  # Порог флуда
    spam_link_protection: Mapped[bool] = mapped_column(Boolean, default=True)
    swear_filter: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_warn_threshold: Mapped[int] = mapped_column(Integer, default=3)  # Порог для авто-варнов
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatConfig(Base):
    __tablename__ = "chat_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    chat_name: Mapped[str] = mapped_column(String(255))
    chat_type: Mapped[str] = mapped_column(String(20), default="main")  # 'main' или 'auxiliary'
    moderation_mode: Mapped[str] = mapped_column(String(20), default="normal")  # 'light', 'normal', 'dictatorship'
    dailysummary_topic_id: Mapped[int] = mapped_column(Integer, default=1)
    memes_topic_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    system_prompt_override: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Переопределение системного промпта для чата
    welcome_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Сообщение приветствия
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связь с пользователем (владельцем чата)
    owner_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(String(20), default="moderator")  # 'owner', 'moderator'
    added_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Кто добавил
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связь с пользователем
    user: Mapped["User"] = relationship(back_populates="admin_roles")


class Blacklist(Base):
    __tablename__ = "blacklist"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Если NULL, то глобальный бан
    reason: Mapped[str] = mapped_column(Text)
    added_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="blacklist_entries")


class PrivateChat(Base):
    __tablename__ = "private_chats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    message_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON для хранения контекста
    last_interaction: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    toxicity_level: Mapped[float] = mapped_column(Float, default=0.0)  # Уровень токсичности пользователя
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)  # Заблокирован ли пользователь

    user: Mapped["User"] = relationship(back_populates="private_chat")
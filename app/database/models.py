from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import BigInteger, Integer, String, DateTime, Boolean, ForeignKey, Text, UniqueConstraint, CheckConstraint, func, Float, LargeBinary, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base
from app.utils import utc_now


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    status: Mapped[str] = mapped_column(String(16), default='active', index=True)  # active, left
    strikes: Mapped[int] = mapped_column(Integer, default=0)
    # Fortress Update: Global reputation score
    reputation_score: Mapped[int] = mapped_column(Integer, default=1000)

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
    topic_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)  # ID топика в форуме
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class GameStat(Base):
    __tablename__ = "game_stats"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String(64))

    size_cm: Mapped[int] = mapped_column(Integer, default=0)
    next_grow_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pvp_wins: Mapped[int] = mapped_column(Integer, default=0)
    pvp_losses: Mapped[int] = mapped_column(Integer, default=0)  # PP battle losses
    grow_count: Mapped[int] = mapped_column(Integer, default=0)
    casino_jackpots: Mapped[int] = mapped_column(Integer, default=0)
    reputation: Mapped[int] = mapped_column(Integer, default=0)
    # Fortress Update: ELO and League system
    elo_rating: Mapped[int] = mapped_column(Integer, default=1000)
    league: Mapped[str] = mapped_column(String(20), default='scrap')  # scrap, silicon, quantum, elite
    season_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    # Grand Casino v7.0: Growth history for sparkline (Requirements 7.4)
    # Stores last 7 days of growth data as JSON: [{"date": "2025-12-08", "size": 50, "change": 5}, ...]
    grow_history: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)

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
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    seller: Mapped["User"] = relationship(foreign_keys=[seller_user_id])
    bids: Mapped[list["Bid"]] = relationship(back_populates="auction", foreign_keys="[Bid.auction_id]")
    current_highest_bid: Mapped[Optional["Bid"]] = relationship(foreign_keys=[current_highest_bid_id], post_update=True)


class Bid(Base):
    __tablename__ = "bids"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id"))
    bidder_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    auction: Mapped["Auction"] = relationship(back_populates="bids", foreign_keys=[auction_id])
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
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="user_quests")
    quest: Mapped["Quest"] = relationship(back_populates="users_quests")


class Guild(Base):
    __tablename__ = "guilds"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    owner: Mapped["User"] = relationship(foreign_keys=[owner_user_id])
    members: Mapped[list["GuildMember"]] = relationship(back_populates="guild")


class GuildMember(Base):
    __tablename__ = "guild_members"
    guild_id: Mapped[int] = mapped_column(ForeignKey("guilds.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

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
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    team_war: Mapped["TeamWar"] = relationship(back_populates="participants")
    user: Mapped["User"] = relationship() # One-way relationship
    guild: Mapped["Guild"] = relationship() # One-way relationship


class DuoTeam(Base):
    __tablename__ = "duo_teams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user1_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user2_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

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
    asked_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    user: Mapped["User"] = relationship(back_populates="question_history")


class SpamPattern(Base):
    __tablename__ = "spam_patterns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pattern: Mapped[str] = mapped_column(String(255), unique=True)
    is_regex: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

class Warning(Base):
    __tablename__ = "warnings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    moderator_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    user: Mapped["User"] = relationship(back_populates="warnings")

class ToxicityConfig(Base):
    __tablename__ = "toxicity_configs"
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    threshold: Mapped[int] = mapped_column(Integer, default=75) # 0-100
    action: Mapped[str] = mapped_column(String(64), default="warn") # "warn", "delete", "mute"
    mute_duration: Mapped[int] = mapped_column(Integer, default=5) # in minutes





class ToxicityLog(Base):
    __tablename__ = "toxicity_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    message_text: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float)
    category: Mapped[Optional[str]] = mapped_column(String(128))
    action_taken: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Quote(Base):
    __tablename__ = "quotes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    username: Mapped[str] = mapped_column(String(64))
    image_data: Mapped[bytes] = mapped_column(LargeBinary)  # Изображение цитаты в байтах
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Комментарий Олега
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    dislikes_count: Mapped[int] = mapped_column(Integer, default=0)  # Счётчик дизлайков
    is_golden_fund: Mapped[bool] = mapped_column(Boolean, default=False)  # В "золотом фонде" или нет
    is_sticker: Mapped[bool] = mapped_column(Boolean, default=False)  # Является ли стикером
    sticker_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # ID файла стикера в Telegram
    telegram_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # ID чата в Telegram
    telegram_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # ID сообщения в Telegram
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    # Fortress Update: Link to sticker pack
    sticker_pack_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sticker_packs.id"), nullable=True)

    user: Mapped["User"] = relationship(back_populates="quotes")
    sticker_pack: Mapped[Optional["StickerPack"]] = relationship(back_populates="quotes")
    votes: Mapped[list["QuoteVote"]] = relationship(back_populates="quote", cascade="all, delete-orphan")


class QuoteVote(Base):
    """Голоса за цитаты (лайки/дизлайки)."""
    __tablename__ = "quote_votes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)  # Telegram user ID
    vote_type: Mapped[str] = mapped_column(String(10))  # "like" или "dislike"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    
    quote: Mapped["Quote"] = relationship(back_populates="votes")
    
    __table_args__ = (
        # Один голос на пользователя на цитату
        {"sqlite_autoincrement": True},
    )


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
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True) # Telegram Chat ID
    title: Mapped[str] = mapped_column(String(255))
    is_forum: Mapped[bool] = mapped_column(Boolean, default=False)

    summary_topic_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    creative_topic_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active_topic_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Топик где бот активен
    auto_reply_chance: Mapped[float] = mapped_column(Float, default=0.0)  # Шанс автоответа (0.0-1.0)
    
    moderation_mode: Mapped[str] = mapped_column(String(20), default="normal")

    owner_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    # Fortress Update: DEFCON level and owner notifications
    defcon_level: Mapped[int] = mapped_column(Integer, default=1)  # 1=Peaceful, 2=Strict, 3=Martial Law
    owner_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_user_id"), index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(String(20), default="moderator")  # 'owner', 'moderator'
    added_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Кто добавил
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    # Связь с пользователем
    user: Mapped["User"] = relationship(back_populates="admin_roles", foreign_keys=[user_id])


class Blacklist(Base):
    __tablename__ = "blacklist"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_user_id"), index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Если NULL, то глобальный бан
    reason: Mapped[str] = mapped_column(Text)
    added_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    user: Mapped["User"] = relationship(back_populates="blacklist_entries", foreign_keys=[user_id])


class PrivateChat(Base):
    __tablename__ = "private_chats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_user_id"), unique=True, index=True)
    message_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON для хранения контекста
    last_interaction: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    toxicity_level: Mapped[float] = mapped_column(Float, default=0.0)  # Уровень токсичности пользователя
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)  # Заблокирован ли пользователь

    user: Mapped["User"] = relationship(back_populates="private_chat", foreign_keys=[user_id])


class PendingVerification(Base):
    """Ожидающие верификации новых пользователей (Welcome 2.0)."""
    __tablename__ = "pending_verifications"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    welcome_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # ID сообщения с кнопкой
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)  # Когда истекает время на верификацию
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_kicked: Mapped[bool] = mapped_column(Boolean, default=False)


class GameChallenge(Base):
    """Вызов на PvP игру (Requirements 8.1, 8.2, 8.3, 8.4)."""
    __tablename__ = "game_challenges"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    challenger_id: Mapped[int] = mapped_column(BigInteger, index=True)
    target_id: Mapped[int] = mapped_column(BigInteger, index=True)
    game_type: Mapped[str] = mapped_column(String(32))  # pvp, roulette, coinflip
    bet_amount: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending, accepted, expired, cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)  # Timeout handling


class UserBalance(Base):
    """Баланс пользователя для игр (Requirements 10.1, 10.5)."""
    __tablename__ = "user_balances"
    
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    balance: Mapped[int] = mapped_column(Integer, default=100)  # Стартовый баланс
    total_won: Mapped[int] = mapped_column(Integer, default=0)
    total_lost: Mapped[int] = mapped_column(Integer, default=0)


# ============================================================================
# FORTRESS UPDATE v6.0 - New Models
# ============================================================================


class CitadelConfig(Base):
    """DEFCON protection configuration per chat (Requirement 1.1)."""
    __tablename__ = "citadel_configs"
    
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    defcon_level: Mapped[int] = mapped_column(Integer, default=1)  # 1=Peaceful, 2=Strict, 3=Martial Law
    raid_mode_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    anti_spam_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    profanity_filter_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    sticker_limit: Mapped[int] = mapped_column(Integer, default=0)  # 0 = disabled
    forward_block_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    new_user_restriction_hours: Mapped[int] = mapped_column(Integer, default=24)
    hard_captcha_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    gif_patrol_enabled: Mapped[bool] = mapped_column(Boolean, default=False)  # GIF moderation (work in progress)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class UserReputation(Base):
    """User reputation score per chat (Requirement 4.1)."""
    __tablename__ = "user_reputations"
    
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    score: Mapped[int] = mapped_column(Integer, default=1000)
    is_read_only: Mapped[bool] = mapped_column(Boolean, default=False)
    last_change_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class ReputationHistory(Base):
    """Reputation change history (Requirement 4.8)."""
    __tablename__ = "reputation_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    change_amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class Tournament(Base):
    """Tournament tracking (Requirement 10.1)."""
    __tablename__ = "tournaments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(20), index=True)  # daily, weekly, grand_cup
    start_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default='active', index=True)  # active, completed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    
    scores: Mapped[list["TournamentScore"]] = relationship(back_populates="tournament", cascade="all, delete-orphan")


class TournamentScore(Base):
    """Tournament scores per user per discipline (Requirement 10.1)."""
    __tablename__ = "tournament_scores"
    
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    discipline: Mapped[str] = mapped_column(String(20), primary_key=True)  # grow, pvp, roulette
    score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    
    tournament: Mapped["Tournament"] = relationship(back_populates="scores")


class UserElo(Base):
    """User ELO ratings for league system (Requirement 11.1)."""
    __tablename__ = "user_elo"
    
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    elo: Mapped[int] = mapped_column(Integer, default=1000, index=True)
    league: Mapped[str] = mapped_column(String(20), default='scrap', index=True)  # scrap, silicon, quantum, elite
    season_wins: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class NotificationConfig(Base):
    """Owner notification settings per chat (Requirement 15.8)."""
    __tablename__ = "notification_configs"
    
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    raid_alert: Mapped[bool] = mapped_column(Boolean, default=True)
    ban_notification: Mapped[bool] = mapped_column(Boolean, default=True)
    toxicity_warning: Mapped[bool] = mapped_column(Boolean, default=True)
    defcon_recommendation: Mapped[bool] = mapped_column(Boolean, default=True)
    repeated_violator: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_tips: Mapped[bool] = mapped_column(Boolean, default=True)


class StickerPack(Base):
    """Sticker pack management per chat (Requirement 8.1)."""
    __tablename__ = "sticker_packs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    pack_name: Mapped[str] = mapped_column(String(64), unique=True)
    pack_title: Mapped[str] = mapped_column(String(64))
    sticker_count: Mapped[int] = mapped_column(Integer, default=0)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    owner_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Telegram user ID who created the pack
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    
    quotes: Mapped[list["Quote"]] = relationship(back_populates="sticker_pack")


class SecurityBlacklist(Base):
    """Security blacklist for abuse prevention (Requirement 17.7)."""
    __tablename__ = "security_blacklist"
    
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reason: Mapped[str] = mapped_column(Text)
    blacklisted_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)


class RateLimit(Base):
    """Rate limit tracking (fallback when Redis unavailable) (Requirement 17.2)."""
    __tablename__ = "rate_limits"
    
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)


class DailiesConfig(Base):
    """
    Dailies configuration per chat (Requirements 13.4, 13.5).
    
    Stores settings for daily scheduled messages including:
    - Morning summary enabled/disabled
    - Evening quote enabled/disabled
    - Evening stats enabled/disabled
    """
    __tablename__ = "dailies_configs"
    
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    summary_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # Morning summary
    quote_enabled: Mapped[bool] = mapped_column(Boolean, default=True)    # Evening quote
    stats_enabled: Mapped[bool] = mapped_column(Boolean, default=True)    # Evening stats
    summary_time_hour: Mapped[int] = mapped_column(Integer, default=9)    # 09:00 Moscow
    quote_time_hour: Mapped[int] = mapped_column(Integer, default=21)     # 21:00 Moscow
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class BotConfig(Base):
    """
    Bot behavior configuration per chat.
    
    Controls auto-reply chance and feature toggles.
    """
    __tablename__ = "bot_configs"
    
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    
    # Автоответ (0-100%)
    auto_reply_chance: Mapped[int] = mapped_column(Integer, default=5)  # 5% по умолчанию
    
    # Функции бота
    quotes_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # /q команда
    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=True)   # Распознавание голоса
    vision_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # Анализ картинок
    games_enabled: Mapped[bool] = mapped_column(Boolean, default=True)   # Игровые команды
    
    # Время на принятие вызова в PvP/ПП (в секундах)
    pvp_accept_timeout: Mapped[int] = mapped_column(Integer, default=60)  # 60 секунд по умолчанию
    
    # Персона бота: "oleg" (дерзкий) или "dude" (расслабленный The Dude)
    persona: Mapped[str] = mapped_column(String(20), default="oleg")
    
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


# ============================================================================
# SHIELD & ECONOMY v6.5 - New Models
# ============================================================================


class UserEnergy(Base):
    """
    Personal energy system for LLM request limiting (Requirements 1.1, 1.2, 1.3, 1.4).
    
    Each user has an energy counter (0-3) that decrements on rapid requests.
    When energy reaches 0, user enters cooldown period.
    Energy resets after 60 seconds of inactivity.
    """
    __tablename__ = "user_energy"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    energy: Mapped[int] = mapped_column(Integer, default=3)  # 0-3, starts at 3
    last_request: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cooldown_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'chat_id', name='uq_user_chat_energy'),
    )


class ChatRateLimitConfig(Base):
    """
    Global chat rate limit configuration (Requirements 2.1, 2.3).
    
    Configures the maximum LLM requests per minute for each chat.
    Default limit is 20 requests per minute.
    """
    __tablename__ = "chat_rate_limit_config"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    llm_requests_per_minute: Mapped[int] = mapped_column(Integer, default=20)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ProtectionProfileConfig(Base):
    """
    Protection profile configuration per chat (Requirements 10.1, 10.2, 10.3, 10.4).
    
    Stores the selected protection profile and custom settings.
    Profiles: standard, strict, bunker, custom
    """
    __tablename__ = "protection_profile_config"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    profile: Mapped[str] = mapped_column(String(20), default="standard")  # standard, strict, bunker, custom
    
    # Custom settings (used when profile="custom" or to override defaults)
    anti_spam_links: Mapped[bool] = mapped_column(Boolean, default=True)
    captcha_type: Mapped[str] = mapped_column(String(10), default="button")  # button, hard
    profanity_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    neural_ad_filter: Mapped[bool] = mapped_column(Boolean, default=False)
    block_forwards: Mapped[bool] = mapped_column(Boolean, default=False)
    sticker_limit: Mapped[int] = mapped_column(Integer, default=0)  # 0 = unlimited
    mute_newcomers: Mapped[bool] = mapped_column(Boolean, default=False)
    block_media_non_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    aggressive_profanity: Mapped[bool] = mapped_column(Boolean, default=False)
    
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SilentBan(Base):
    """
    Silent ban tracking for suspicious users (Requirements 9.4, 9.5).
    
    Users under silent ban have their messages deleted without notification.
    They can be unbanned by passing a captcha challenge.
    """
    __tablename__ = "silent_bans"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    captcha_answer: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Expected answer for unban
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'chat_id', name='uq_user_chat_silent_ban'),
    )


# ============================================================================
# GAMES v7.5 - New Models for Economy and Inventory
# ============================================================================


class CockfightStats(Base):
    """
    Cockfight statistics per user (v7.5).
    
    Tracks cockfight wins, losses, and owned roosters.
    """
    __tablename__ = "cockfight_stats"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    total_earnings: Mapped[int] = mapped_column(Integer, default=0)
    owned_roosters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of rooster types
    
    __table_args__ = (
        UniqueConstraint('user_id', 'chat_id', name='uq_user_chat_cockfight'),
    )


class GameHistory(Base):
    """
    Game history for tracking all game results (v7.5).
    
    Stores history of all games played for statistics and leaderboards.
    """
    __tablename__ = "game_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    game_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    bet_amount: Mapped[int] = mapped_column(Integer, default=0)
    result_amount: Mapped[int] = mapped_column(Integer, default=0)  # Positive = win, negative = loss
    won: Mapped[bool] = mapped_column(Boolean, default=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON with game-specific details
    played_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


# ============================================================================
# INVENTORY & FISHING SYSTEM v7.5.1
# ============================================================================


class UserInventory(Base):
    """
    User inventory for items from lootboxes and shop.
    
    Stores items like fishing rods, lucky charms, shields, etc.
    """
    __tablename__ = "user_inventory"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    equipped: Mapped[bool] = mapped_column(Boolean, default=False)
    item_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON for item-specific data
    acquired_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'chat_id', 'item_type', name='uq_user_chat_item'),
    )


class FishingStats(Base):
    """
    Fishing statistics per user.
    
    Tracks fish caught by rarity, total earnings, equipped rod, etc.
    """
    __tablename__ = "fishing_stats"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    
    # Fish caught by rarity
    trash_caught: Mapped[int] = mapped_column(Integer, default=0)
    common_caught: Mapped[int] = mapped_column(Integer, default=0)
    uncommon_caught: Mapped[int] = mapped_column(Integer, default=0)
    rare_caught: Mapped[int] = mapped_column(Integer, default=0)
    epic_caught: Mapped[int] = mapped_column(Integer, default=0)
    legendary_caught: Mapped[int] = mapped_column(Integer, default=0)
    
    # Totals
    total_casts: Mapped[int] = mapped_column(Integer, default=0)
    total_earnings: Mapped[int] = mapped_column(Integer, default=0)
    biggest_catch_value: Mapped[int] = mapped_column(Integer, default=0)
    biggest_catch_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Equipped rod (item_type from inventory)
    equipped_rod: Mapped[str] = mapped_column(String(64), default="basic_rod")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'chat_id', name='uq_user_chat_fishing'),
    )


# ============================================================================
# SDOC INTEGRATION - Олег как резидент Steam Deck OC
# ============================================================================


class GroupAdmin(Base):
    """
    Админы/приписочники группы SDOC.
    
    Синхронизируется с Telegram API getChatAdministrators.
    Олег знает их по именам и может упоминать в разговоре.
    """
    __tablename__ = "group_admins"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # Кастомный титул в группе
    role: Mapped[str] = mapped_column(String(20), default="administrator")  # creator, administrator
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    
    __table_args__ = (
        UniqueConstraint('chat_id', 'user_id', name='uq_chat_admin'),
    )


class GroupMeme(Base):
    """
    Локальные мемы и приколы группы.
    
    Олег собирает их из чата и может использовать в разговоре.
    Примеры: "Синица с яйцами", "Иваново", местные шутки.
    """
    __tablename__ = "group_memes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    meme_type: Mapped[str] = mapped_column(String(32), index=True)  # quote, joke, reference, nickname
    content: Mapped[str] = mapped_column(Text)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Контекст/объяснение
    author_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Кто автор
    author_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)  # Сколько раз Олег использовал
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    
    __table_args__ = (
        UniqueConstraint('chat_id', 'content', name='uq_chat_meme_content'),
    )


class SDOCTopic(Base):
    """
    Топики группы SDOC.
    
    Олег знает структуру группы и может направлять людей в нужные топики.
    """
    __tablename__ = "sdoc_topics"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, index=True)  # message_thread_id
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(32), default="general")  # tech, fun, trade, meta
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON список ключевых слов
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    __table_args__ = (
        UniqueConstraint('chat_id', 'topic_id', name='uq_chat_topic'),
    )

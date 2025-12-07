# Design Document: Oleg Commands Fix

## Overview

Исправление и улучшение ключевых функций бота Олег:
1. Починка админ-панели `/admin` в личных сообщениях
2. Реализация TTS голосовых ответов через Silero TTS
3. Настройка разных команд в меню "/" для групп и ЛС
4. Контекстно-зависимый `/help`

## Architecture

```mermaid
graph TB
    subgraph "Command Layer"
        ADMIN[/admin Handler]
        SAY[/say Handler]
        HELP[/help Handler]
    end
    
    subgraph "Services"
        TTS[TTS Service<br/>Silero Model]
        PANEL[Admin Panel Service]
    end
    
    subgraph "Bot Setup"
        SCOPE[Command Scope Manager]
        STARTUP[Bot Startup]
    end
    
    ADMIN --> PANEL
    SAY --> TTS
    HELP --> |context check| HELP
    STARTUP --> SCOPE
    SCOPE --> |register| GROUP_CMDS[Group Commands]
    SCOPE --> |register| PRIVATE_CMDS[Private Commands]
```

## Components and Interfaces

### 1. TTS Service (app/services/tts.py)

Обновление существующего сервиса для использования Silero TTS:

```python
class TTSService:
    async def _generate_audio(self, text: str) -> Optional[bytes]:
        """Generate audio using Silero TTS model."""
        
    async def _load_model(self) -> bool:
        """Lazy load Silero TTS model on first use."""
        
    def _convert_to_ogg(self, audio_tensor: torch.Tensor, sample_rate: int) -> bytes:
        """Convert audio tensor to OGG format for Telegram."""
```

### 2. Help Handler (app/handlers/help.py)

Разделение help на контексты:

```python
HELP_TEXT_GROUP = """..."""  # Команды для групп
HELP_TEXT_PRIVATE = """..."""  # Команды для ЛС

@router.message(Command("help"))
async def cmd_help(msg: Message):
    if msg.chat.type == 'private':
        # Show private help
    else:
        # Show group help
```

### 3. Command Scope Manager (app/services/command_scope.py)

Новый модуль для регистрации команд:

```python
GROUP_COMMANDS = [
    BotCommand("help", "Справка по командам"),
    BotCommand("games", "Гайд по играм"),
    BotCommand("grow", "Увеличить размер"),
    # ...
]

PRIVATE_COMMANDS = [
    BotCommand("help", "Справка по командам"),
    BotCommand("admin", "Админ-панель"),
    BotCommand("reset", "Сбросить контекст"),
    # ...
]

async def setup_commands(bot: Bot):
    """Register command scopes for different chat types."""
```

## Data Models

### TTSResult (existing)

```python
@dataclass
class TTSResult:
    audio_data: bytes      # OGG audio bytes
    duration_seconds: float
    format: str            # "ogg"
    original_text: str
    was_truncated: bool
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Admin panel shows owner chats
*For any* user ID and set of chats, the admin panel SHALL display exactly those chats where the user is the owner.
**Validates: Requirements 1.1**

### Property 2: TTS fallback on unavailability
*For any* text input, when TTS service returns None, the response SHALL contain the text with "🔊" prefix and "(голосом Олега)" marker.
**Validates: Requirements 2.2**

### Property 3: Text truncation preserves limit
*For any* text longer than 500 characters, the truncated output SHALL have length ≤ 500 and end with "...и так далее".
**Validates: Requirements 2.3**

### Property 4: Help context differentiation
*For any* help request, the response content SHALL differ based on chat type (private vs group), with private help containing "admin" and group help containing game commands.
**Validates: Requirements 4.1, 4.2**

### Property 5: TTS produces valid OGG
*For any* successful TTS generation, the output audio_data SHALL be valid OGG format (starts with "OggS" magic bytes).
**Validates: Requirements 5.2**

## Error Handling

| Scenario | Handling |
|----------|----------|
| TTS model load failure | Log error, set `_is_available = False`, return None |
| TTS generation failure | Fall back to text with voice emoji prefix |
| Admin panel - no owner chats | Show "no chats available" message |
| /say without text | Show usage instructions |
| Command scope registration failure | Log warning, continue with defaults |

## Testing Strategy

### Property-Based Testing

Используем **Hypothesis** для Python:

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=501))
def test_truncation_preserves_limit(text):
    """Property 3: Text truncation preserves limit"""
    result, was_truncated = tts_service.truncate_text(text)
    assert len(result) <= 500
    assert result.endswith("...и так далее")
```

### Unit Tests

- Test admin panel ownership verification
- Test help text selection by chat type
- Test command scope registration
- Test TTS OGG format validation

### Integration Tests

- End-to-end /admin flow in private chat
- End-to-end /say with actual TTS generation
- Command menu visibility in different contexts

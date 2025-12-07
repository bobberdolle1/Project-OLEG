# Implementation Plan

- [x] 1. Implement TTS with Silero model





  - [x] 1.1 Update TTS service to load Silero model lazily


    - Add `_load_model()` method with torch.hub.load for silero_tts
    - Add model caching to avoid reloading
    - Handle model load failures gracefully
    - _Requirements: 5.1, 5.3_
  - [x] 1.2 Implement audio generation with Silero


    - Update `_generate_audio()` to use loaded model
    - Generate audio tensor from text
    - _Requirements: 2.1, 5.1_
  - [x] 1.3 Implement OGG conversion for Telegram


    - Add `_convert_to_ogg()` method using soundfile/pydub
    - Ensure output is compatible with Telegram voice messages
    - _Requirements: 5.2_
  - [x] 1.4 Write property test for TTS truncation


    - **Property 3: Text truncation preserves limit**
    - **Validates: Requirements 2.3**
  - [x] 1.5 Write property test for OGG format


    - **Property 5: TTS produces valid OGG**
    - **Validates: Requirements 5.2**

- [x] 2. Implement context-aware /help command





  - [x] 2.1 Create separate help texts for group and private chats


    - Define `HELP_TEXT_GROUP` with game/moderation commands
    - Define `HELP_TEXT_PRIVATE` with admin/reset commands
    - _Requirements: 4.1, 4.2_

  - [x] 2.2 Update help handler to check chat type

    - Add chat type detection in `cmd_help()`
    - Return appropriate help text based on context
    - _Requirements: 4.1, 4.2_
  - [x] 2.3 Write property test for help context differentiation


    - **Property 4: Help context differentiation**
    - **Validates: Requirements 4.1, 4.2**


- [x] 3. Implement command scope registration




  - [x] 3.1 Create command scope manager module


    - Create `app/services/command_scope.py`
    - Define `GROUP_COMMANDS` list with group-relevant commands
    - Define `PRIVATE_COMMANDS` list with private-relevant commands
    - _Requirements: 3.1, 3.2_

  - [x] 3.2 Implement setup_commands function
    - Use `bot.set_my_commands()` with `BotCommandScopeAllPrivateChats`
    - Use `bot.set_my_commands()` with `BotCommandScopeAllGroupChats`
    - _Requirements: 3.3_
  - [x] 3.3 Integrate command setup into bot startup


    - Call `setup_commands()` in `on_startup()` in main.py
    - _Requirements: 3.3_

- [x] 4. Verify and fix admin panel in private messages






  - [x] 4.1 Debug and fix admin panel handler

    - Verify `/admin` works in private chat
    - Ensure owner chat list is correctly fetched
    - Fix any issues with inline keyboard generation
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 4.2 Write property test for admin panel ownership

    - **Property 1: Admin panel shows owner chats**
    - **Validates: Requirements 1.1**


- [x] 5. Checkpoint - Ensure all tests pass




  - Ensure all tests pass, ask the user if questions arise.

- [-] 6. Final integration and commit




  - [x] 6.1 Test all commands manually

    - Test /admin in private chat
    - Test /say with text
    - Test /help in both contexts
    - Verify command menu in "/" shows correct commands
  - [-] 6.2 Create commit with all changes

    - Stage all modified files
    - Create descriptive commit message

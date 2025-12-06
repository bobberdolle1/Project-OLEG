# Implementation Plan: OLEG v6.0 Fortress Update

- [x] 1. Database migrations and models





  - [x] 1.1 Create Alembic migration for new tables (citadel_configs, user_reputations, reputation_history, tournaments, tournament_scores, user_elo, notification_configs, sticker_packs, security_blacklist)


    - Add all new tables as defined in design document
    - Add foreign key constraints and indexes
    - _Requirements: 1.1, 4.1, 10.1, 11.1, 15.8, 17.7_

  - [x] 1.2 Update existing models (User, GameStat, Quote, Chat) with new fields

    - Add reputation_score to users
    - Add elo_rating, league, season_multiplier to game_stats
    - Add sticker_pack_id to quotes
    - Add defcon_level, owner_notifications_enabled to chats
    - _Requirements: 4.1, 11.1, 8.4, 1.1_

  - [x] 1.3 Create SQLAlchemy model classes for new tables

    - CitadelConfig, UserReputation, ReputationHistory, Tournament, TournamentScore, UserElo, NotificationConfig, StickerPack, SecurityBlacklist
    - _Requirements: All_

- [x] 2. Security foundation



  - [x] 2.1 Implement SecurityService with input sanitization


    - Create sanitize_input() for SQL injection, XSS, command injection
    - Create validate_callback_data() and sign_callback_data() with HMAC
    - Create verify_callback_signature()
    - _Requirements: 17.1, 17.3, 17.12_

  - [x] 2.2 Write property tests for security sanitization

    - **Property 36: Input sanitization**
    - **Validates: Requirements 17.1**
  - [x] 2.3 Write property tests for callback signature


    - **Property 38: Callback signature verification**
    - **Validates: Requirements 17.12**
  - [x] 2.4 Implement rate limiting in SecurityService

    - Create check_rate_limit() with 30 msg/min threshold
    - Create blacklist_user() and detect_abuse_pattern()
    - _Requirements: 17.2, 17.7_

  - [x] 2.5 Write property tests for rate limiting

    - **Property 37: Rate limiting enforcement**
    - **Validates: Requirements 17.2**
  - [x] 2.6 Implement file validation

    - Create validate_file() with type and size checks (max 20MB)
    - _Requirements: 17.4_

  - [x] 2.7 Write property tests for file validation

    - **Property 39: File validation**
    - **Validates: Requirements 17.4**
  - [x] 2.8 Implement error message sanitization

    - Create generic error responses without internal details
    - _Requirements: 17.9_

  - [x] 2.9 Write property tests for error sanitization

    - **Property 40: Error message sanitization**
    - **Validates: Requirements 17.9**
  - [x] 2.10 Implement access control

    - Create verify_admin_realtime() using Telegram API
    - Create access control checks for private data
    - _Requirements: 17.6, 17.10_

  - [x] 2.11 Write property tests for access control


    - **Property 41: Access control enforcement**
    - **Validates: Requirements 17.10**

- [x] 3. Checkpoint - Ensure all tests pass





  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Citadel System (DEFCON Protection)



  - [x] 4.1 Implement CitadelService with DEFCON levels


    - Create DEFCONLevel enum and CitadelConfig dataclass
    - Implement get_config(), set_defcon(), is_new_user()
    - Default DEFCON 1 for new chats
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.7_

  - [x] 4.2 Write property tests for DEFCON initialization

    - **Property 1: Default DEFCON initialization**
    - **Validates: Requirements 1.1**

  - [x] 4.3 Write property tests for DEFCON feature consistency
    - **Property 2: DEFCON feature consistency**
    - **Validates: Requirements 1.2, 1.3, 1.4**
  - [x] 4.4 Implement raid detection and activation

    - Create check_raid_condition() with 5 joins/60s threshold
    - Create activate_raid_mode() with 15 minute duration
    - _Requirements: 1.5, 1.6_

  - [x] 4.5 Write property tests for raid mode
    - **Property 3: Raid mode activation threshold**
    - **Property 4: Raid mode restrictions**
    - **Validates: Requirements 1.5, 1.6**
  - [x] 4.6 Create DEFCON middleware filter


    - Integrate with existing middleware stack
    - Apply restrictions based on current DEFCON level
    - _Requirements: 1.2, 1.3, 1.4_
  - [x] 4.7 Implement "олег defcon" command handler



    - Parse command, validate admin, change level
    - _Requirements: 1.7_

- [x] 5. Reputation System





  - [x] 5.1 Implement ReputationService


    - Create ReputationChange enum with deltas
    - Implement get_reputation(), modify_reputation(), initialize_user()
    - Implement check_read_only_status() with 200/300 thresholds
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x] 5.2 Write property tests for reputation initialization

    - **Property 5: Reputation initialization**
    - **Validates: Requirements 4.1**

  - [x] 5.3 Write property tests for reputation deltas

    - **Property 6: Reputation change deltas**
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6**

  - [x] 5.4 Write property tests for read-only threshold

    - **Property 7: Read-only threshold**
    - **Validates: Requirements 4.7**
  - [x] 5.5 Integrate reputation with moderation actions


    - Hook into warn, mute, delete message handlers
    - _Requirements: 4.2, 4.3, 4.4_

  - [x] 5.6 Integrate reputation with positive actions

    - Hook into reaction handlers for "thank you"
    - Hook into tournament win handlers
    - _Requirements: 4.5, 4.6_

- [x] 6. Checkpoint - Ensure all tests pass





  - Ensure all tests pass, ask the user if questions arise.


- [x] 7. Neuro-Moderation System


  - [x] 7.1 Enhance ToxicityAnalyzer with structured response


    - Update analyze_toxicity() to return ToxicityResult dataclass
    - Add category detection (insult, hate_speech, threat, spam)
    - Add confidence level and sarcasm detection
    - _Requirements: 2.1, 2.3_

  - [x] 7.2 Write property tests for toxicity result structure

    - **Property 9: Toxicity result structure**
    - **Validates: Requirements 2.3**

  - [x] 7.3 Implement DEFCON-aware action mapping
    - Create get_action_for_score() with DEFCON-based actions
    - _Requirements: 2.2_

  - [x] 7.4 Write property tests for toxicity action mapping
    - **Property 8: Toxicity action mapping**

    - **Validates: Requirements 2.2**
  - [x] 7.5 Implement toxicity incident logging

    - Create log_incident() to store in toxicity_logs
    - _Requirements: 2.4_
  - [x] 7.6 Write property tests for incident logging
    - **Property 10: Toxicity incident logging**
    - **Validates: Requirements 2.4**
  - [x] 7.7 Update ToxicityFilterMiddleware



    - Integrate with CitadelService for DEFCON level
    - Integrate with ReputationService for score updates
    - _Requirements: 2.2, 4.4_



- [x] 8. GIF Patrol System



  - [x] 8.1 Implement GIFPatrolService


    - Create extract_frames() to get 3 frames from GIF
    - Integrate with existing vision pipeline
    - _Requirements: 3.1, 3.2, 3.6_
  - [x] 8.2 Write property tests for frame extraction


    - **Property 11: Frame extraction count**
    - **Validates: Requirements 3.1**
  - [x] 8.3 Implement GIF analysis handler


    - Create handler for GIF/animation messages
    - Queue analysis to worker or process inline
    - _Requirements: 3.3, 3.4, 3.5_
  - [x] 8.4 Implement fallback for unavailable vision model


    - Queue for later analysis, allow temporarily
    - _Requirements: 3.5_


- [x] 9. Checkpoint - Ensure all tests pass




  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. TTS Service





  - [x] 10.1 Implement TTSService


    - Create generate_voice() with text truncation at 500 chars
    - Create should_auto_voice() with 0.1% probability
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

  - [x] 10.2 Write property tests for text truncation

    - **Property 12: Text truncation**
    - **Validates: Requirements 5.5**


  - [x] 10.3 Write property tests for auto-voice probability
    - **Property 13: Auto-voice probability**
    - **Validates: Requirements 5.2**
  - [x] 10.4 Implement /say command handler


    - Parse text, generate voice, send as voice note
    - _Requirements: 5.1_


  - [x] 10.5 Implement TTS fallback
    - Fall back to text on service unavailability

    - _Requirements: 5.4_
  - [x] 10.6 Integrate auto-voice into response generation

    - Add 0.1% chance check before sending text responses
    - _Requirements: 5.2_


- [x] 11. Summarizer Service


  - [x] 11.1 Implement SummarizerService


    - Create summarize() with 2-sentence limit
    - Create fetch_article() for URL content
    - Create is_too_short check for < 100 chars
    - _Requirements: 6.1, 6.3, 6.5_

  - [x] 11.2 Write property tests for summary sentence limit

    - **Property 14: Summary sentence limit**
    - **Validates: Requirements 6.1**

  - [x] 11.3 Write property tests for short content rejection
    - **Property 15: Short content rejection**
    - **Validates: Requirements 6.5**

  - [x] 11.4 Write property tests for URL detection
    - **Property 16: URL detection**
    - **Validates: Requirements 6.3**
  - [x] 11.5 Implement /tl;dr and /summary command handlers



    - Parse reply, summarize content, offer voice option
    - _Requirements: 6.1, 6.2, 6.4_


- [x] 12. Checkpoint - Ensure all tests pass




  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Quote Generator Enhancement



  - [x] 13.1 Enhance QuoteGeneratorService


    - Update render_quote() with gradient backgrounds and themes
    - Implement render_quote_chain() with max 10 messages
    - Implement render_roast_quote() with LLM comment
    - Output WebP format, max 512x512
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_


  - [x] 13.2 Write property tests for quote chain limit
    - **Property 17: Quote chain limit**

    - **Validates: Requirements 7.3**
  - [x] 13.3 Write property tests for image dimensions

    - **Property 18: Quote image dimensions**
    - **Validates: Requirements 7.5**

  - [x] 13.4 Write property tests for quote persistence

    - **Property 19: Quote persistence**
    - **Validates: Requirements 7.6**

  - [x] 13.5 Update /q command handler


    - Support /q, /q [N], /q * modes
    - Store quote in database after creation
    - _Requirements: 7.1, 7.3, 7.4, 7.6_

- [x] 14. Sticker Pack System





  - [x] 14.1 Implement StickerPackService


    - Create get_current_pack(), add_sticker(), remove_sticker()
    - Create create_new_pack() and rotate_pack_if_needed()
    - Auto-rotate at 120 stickers
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 14.2 Write property tests for pack rotation

    - **Property 20: Pack rotation threshold**
    - **Validates: Requirements 8.2**
  - [x] 14.3 Write property tests for sticker record update


    - **Property 21: Sticker record update**
    - **Validates: Requirements 8.4**
  - [x] 14.4 Implement /qs and /qd command handlers


    - /qs to add quote to pack
    - /qd for admin to remove sticker
    - _Requirements: 8.1, 8.5_

- [x] 15. Golden Fund System





  - [x] 15.1 Implement GoldenFundService


    - Create check_and_promote() with 5 reaction threshold
    - Create search_relevant_quote() using ChromaDB RAG
    - Create should_respond_with_quote() with 5% probability
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  - [x] 15.2 Write property tests for golden promotion


    - **Property 22: Golden promotion threshold**
    - **Validates: Requirements 9.1**
  - [x] 15.3 Write property tests for golden search probability

    - **Property 23: Golden search probability**
    - **Validates: Requirements 9.2**
  - [x] 15.4 Integrate Golden Fund with response generation


    - Add 5% chance to search and respond with quote sticker
    - _Requirements: 9.2, 9.3_
  - [x] 15.5 Implement Golden Fund notification


    - Notify chat when quote enters Golden Fund
    - _Requirements: 9.5_


- [x] 16. Checkpoint - Ensure all tests pass




  - Ensure all tests pass, ask the user if questions arise.


- [x] 17. League System (ELO)


  - [x] 17.1 Implement LeagueService


    - Create League enum with thresholds
    - Implement get_status(), update_elo(), get_league_for_elo()
    - Implement ELO formula with K=32
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.6, 11.7_


  - [x] 17.2 Write property tests for initial ELO and league
    - **Property 24: Initial ELO and league**

    - **Validates: Requirements 11.1**
  - [x] 17.3 Write property tests for league promotion thresholds

    - **Property 25: League promotion thresholds**
    - **Validates: Requirements 11.2, 11.3, 11.4**
  - [x] 17.4 Write property tests for ELO calculation
    - **Property 26: ELO calculation correctness**
    - **Validates: Requirements 11.6**

  - [x] 17.5 Integrate ELO with PvP games

    - Update ELO after PvP matches
    - _Requirements: 11.6_

  - [x] 17.6 Update /profile to show league info


    - Display league, ELO, progress to next league
    - _Requirements: 11.7_

- [x] 18. Tournament System






  - [x] 18.1 Implement TournamentService

    - Create TournamentType and TournamentDiscipline enums
    - Implement start_tournament(), end_tournament(), update_score()
    - Implement get_standings()
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 18.2 Write property tests for winner count

    - **Property 27: Tournament winner count**
    - **Validates: Requirements 10.4**

  - [x] 18.3 Write property tests for achievement recording
    - **Property 28: Tournament achievement recording**
    - **Validates: Requirements 10.6**
  - [x] 18.4 Implement tournament scheduler jobs


    - Daily at 00:00 UTC, Weekly on Monday, Monthly on 1st
    - _Requirements: 10.1, 10.2, 10.3_

  - [x] 18.5 Implement /tournament command handler

    - Show current standings
    - _Requirements: 10.5_


  - [x] 18.6 Integrate tournament scoring with game handlers
    - Update scores on /grow, /pvp, /roulette
    - _Requirements: 10.1_

- [x] 19. Checkpoint - Ensure all tests pass





  - Ensure all tests pass, ask the user if questions arise.

- [x] 20. Alive UI System




  - [x] 20.1 Implement AliveUIService

    - Create phrase pools for different categories
    - Implement start_status(), update_status(), finish_status()
    - Implement get_random_phrase()
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

  - [x] 20.2 Write property tests for status timing

    - **Property 29: Status message timing**
    - **Validates: Requirements 12.1**

  - [x] 20.3 Write property tests for update interval
    - **Property 30: Status update interval**

    - **Validates: Requirements 12.2**
  - [x] 20.4 Write property tests for category phrases
    - **Property 31: Category-specific phrases**

    - **Validates: Requirements 12.3, 12.4**
  - [x] 20.5 Write property tests for status cleanup
    - **Property 32: Status cleanup**
    - **Validates: Requirements 12.5**
  - [x] 20.6 Integrate Alive UI with long-running handlers



    - Add status messages to TTS, quote rendering, GIF analysis
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_


- [x] 21. Dailies System




  - [x] 21.1 Implement DailiesService


    - Create daily summary generator
    - Create daily quote selector (Golden Fund or generated)
    - Create daily stats aggregator
    - _Requirements: 13.1, 13.2, 13.3_

  - [x] 21.2 Write property tests for settings respect

    - **Property 33: Daily message respect settings**
    - **Validates: Requirements 13.4**

  - [x] 21.3 Write property tests for skip on no activity

    - **Property 34: Skip summary on no activity**
    - **Validates: Requirements 13.5**
  - [x] 21.4 Implement scheduler jobs for dailies


    - 09:00 Moscow: summary
    - 21:00 Moscow: quote and stats
    - _Requirements: 13.1, 13.2, 13.3_

  - [x] 21.5 Implement chat-specific settings for dailies

    - Respect enabled/disabled settings per chat
    - _Requirements: 13.4, 13.5_


- [x] 22. Notification System








  - [x] 22.1 Implement NotificationService


    - Create NotificationType enum and NotificationConfig
    - Implement notify_owner(), get_config(), toggle_notification()
    - Implement generate_tips()
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 15.8_

  - [x] 22.2 Write property tests for default notifications

    - **Property 35: Default notifications enabled**
    - **Validates: Requirements 15.8**
  - [x] 22.3 Integrate notifications with moderation events


    - Raid mode notifications integrated in antiraid.py
    - Ban notifications integrated in moderation.py
    - _Requirements: 15.1, 15.2_
  - [x] 22.4 Integrate toxicity warning notifications


    - Add toxicity increase detection to toxicity_filter middleware
    - Call check_toxicity_increase() periodically or on incidents
    - _Requirements: 15.3_
  - [x] 22.5 Implement /советы and /tips command handlers


    - Create handler for /советы and /tips commands
    - Call generate_tips() and format response
    - _Requirements: 15.7_

- [x] 23. Checkpoint - Ensure all tests pass






  - Ensure all tests pass, ask the user if questions arise.


- [x] 24. Admin Panel for Chat Owners (Private Messages)



  - [x] 24.1 Create AdminPanelService for chat owners


    - Create AdminMenuCategory enum (Protection, Notifications, Games, Dailies, Quotes, Advanced)
    - Implement get_owner_chats() to get chats where user is creator
    - Implement build_main_menu(), build_category_menu()
    - Implement handle_callback(), verify_ownership()
    - Note: Existing admin_dashboard.py is for bot owner only; this is for chat owners
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 16.8, 16.9, 16.10, 16.11, 16.12_

  - [x] 24.2 Update /admin command handler for chat owners

    - Show chat list for chat owner (not just bot owner)
    - Redirect to PM if used in group with message
    - _Requirements: 16.1, 16.12_

  - [x] 24.3 Implement Protection category menu
    - DEFCON level buttons (1, 2, 3)
    - Feature toggles (anti-spam, profanity filter, sticker limit, forward block)

    - _Requirements: 16.3_
  - [x] 24.4 Implement Notifications category menu
    - Toggles for each notification type (raid alerts, ban notifications, toxicity warnings, daily tips)

    - Show current status for each toggle
    - _Requirements: 16.4_
  - [x] 24.5 Implement Games category menu

    - Enable/disable game commands (/grow, /pvp, /roulette)
    - Enable/disable tournament participation
    - _Requirements: 16.5_
  - [x] 24.6 Implement Dailies category menu

    - Toggles for morning summary, evening quote, daily stats
    - Time configuration options
    - _Requirements: 16.6_
  - [x] 24.7 Implement Quotes category menu

    - Theme selection (dark/light/auto)
    - Golden Fund participation toggle
    - Sticker pack management
    - _Requirements: 16.7_
  - [x] 24.8 Implement Advanced Settings menu

    - Toxicity threshold slider
    - Mute durations configuration
    - Custom banned words management
    - _Requirements: 16.10_


- [x] 25. Worker Process Setup (Arq)






  - [x] 25.1 Set up Arq worker with Redis

    - Create app/worker.py with Arq worker configuration
    - Configure Redis connection for task queue
    - Create task queue infrastructure with proper settings
    - Update requirements.txt/pyproject.toml with arq dependency
    - _Requirements: 14.1, 14.2, 14.3_

  - [x] 25.2 Implement TTS worker task

    - Create tts_task() function in worker
    - Update TTSService.queue_tts_task() to enqueue to Arq
    - Handle task completion and send result to chat
    - _Requirements: 14.1_

  - [x] 25.3 Implement quote rendering worker task

    - Create quote_render_task() function in worker
    - Queue heavy quote rendering operations
    - Handle task completion and send result to chat
    - _Requirements: 14.2_

  - [x] 25.4 Implement GIF analysis worker task

    - Create gif_analysis_task() function in worker
    - Update GIFPatrolService.queue_analysis() to enqueue to Arq
    - Handle task completion and apply moderation action
    - _Requirements: 14.3_


  - [x] 25.5 Implement task completion notification
    - Create callback mechanism for completed tasks
    - Notify main bot process when task completes
    - Send results to appropriate chat/user

    - _Requirements: 14.4_
  - [x] 25.6 Implement retry logic with exponential backoff

    - Configure Arq retry settings (max_tries=3)
    - Implement exponential backoff between retries
    - Log failures and notify on final failure
    - _Requirements: 14.5_

  - [x] 25.7 Implement queue monitoring

    - Create queue_monitor_task() to check queue size
    - Log warning when queue exceeds 100 pending tasks
    - Optionally notify administrators
    - _Requirements: 14.6_

- [x] 26. Checkpoint - Ensure all tests pass






  - Ensure all tests pass, ask the user if questions arise.


- [x] 27. Documentation and README



  - [x] 27.1 Update README.md with v6.0 Fortress Update features


    - Update version from 5.0 to 6.0 in header
    - Add "What's new in 6.0" section with all Fortress Update features
    - Document new commands (/defcon, /советы, /tips, /tournament, /say, /tl;dr, /summary, /q, /qs, /qd)
    - Add DEFCON levels comparison table (Level 1/2/3 features)
    - Update badges if needed
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.9, 18.10_

  - [x] 27.2 Document Admin Panel for chat owners
    - Add section explaining /admin command in PM
    - Include menu structure description (Protection, Notifications, Games, Dailies, Quotes, Advanced)
    - Explain each category's options

    - _Requirements: 18.5_
  - [x] 27.3 Add Security section to README
    - Document security features (input sanitization, rate limiting, HMAC callbacks)
    - Include best practices for bot deployment
    - Mention DEFCON system for chat protection
    - _Requirements: 18.6_
  - [x] 27.4 Update CHANGELOG.md with v6.0 changes


    - Add [6.0.0] section with current date
    - Document all new features (Citadel, Neuro-Moderation, GIF Patrol, Reputation, TTS, etc.)
    - Follow Keep a Changelog format
    - _Requirements: 18.7_
  - [x] 27.5 Create git commit


    - Stage all changes
    - Commit with message "feat: OLEG v6.0 Fortress Update"
    - _Requirements: 18.8_

- [ ] 28. Final Checkpoint - Ensure all tests pass


  - Ensure all tests pass, ask the user if questions arise.

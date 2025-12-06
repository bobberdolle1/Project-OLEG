# Implementation Plan

## Phase 1: Database Models and Migrations

- [x] 1. Create database models and migration
  - [x] 1.1 Add UserEnergy model to app/database/models.py
    - Fields: id, user_id, chat_id, energy (default 3), last_request, cooldown_until
    - UniqueConstraint on (user_id, chat_id)
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  - [x] 1.2 Add ChatRateLimitConfig model to app/database/models.py
    - Fields: id, chat_id (unique), llm_requests_per_minute (default 20), updated_at
    - _Requirements: 2.1, 2.3_
  - [x] 1.3 Add ProtectionProfileConfig model to app/database/models.py
    - Fields: id, chat_id (unique), profile, all custom settings fields, updated_at
    - _Requirements: 10.1, 10.2, 10.3, 10.4_
  - [x] 1.4 Add SilentBan model to app/database/models.py
    - Fields: id, user_id, chat_id, reason, captcha_answer, created_at, expires_at
    - UniqueConstraint on (user_id, chat_id)
    - _Requirements: 9.4, 9.5_
  - [x] 1.5 Create Alembic migration for new tables
    - _Requirements: 1.1, 2.1, 9.4, 10.1_


## Phase 2: Energy Limiter Service

- [x] 2. Implement Energy Limiter Service


  - [x] 2.1 Create app/services/energy_limiter.py with EnergyLimiterService class
    - Implement check_energy(), consume_energy(), reset_energy(), get_cooldown_remaining()
    - Use Redis for fast access with DB fallback
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  - [x] 2.2 Write property test for energy decrement


    - Add test function to tests/property/test_energy_limiter_props.py
    - Test that energy decrements by exactly 1 on rapid requests (within 10 seconds)
    - Use the existing EnergyLimiterService test class in the file
    - **Property 1: Energy Decrement on Rapid Requests**
    - **Validates: Requirements 1.1**

  - [x] 2.3 Write property test for cooldown message





    - Add test function to tests/property/test_energy_limiter_props.py
    - Test that cooldown message contains user mention and 60-second wait instruction
    - **Property 2: Cooldown Message Contains Required Elements**

    - **Validates: Requirements 1.2**

  - [x] 2.4 Write property test for energy reset




    - Add test function to tests/property/test_energy_limiter_props.py
    - Test that energy resets to 3 after 60+ seconds of inactivity

    - **Property 3: Energy Reset After Inactivity**
    - **Validates: Requirements 1.3**

  - [x] 2.5 Write property test for energy allows processing








    - Add test function to tests/property/test_energy_limiter_props.py
    - Test that users with energy > 0 can proceed with requests
    - **Property 4: Energy Allows Processing**
    - **Validates: Requirements 1.4**

- [x] 3. Checkpoint - Ensure all tests pass


  - Ensure all tests pass, ask the user if questions arise.

## Phase 3: Global Rate Limiter Service

- [x] 4. Implement Global Rate Limiter Service

  - [x] 4.1 Create app/services/global_rate_limiter.py with GlobalRateLimiterService class


    - Implement check_chat_limit(), increment_chat_counter(), set_chat_limit(), get_chat_limit()
    - Use Redis with 60-second TTL for counters
    - Use ChatRateLimitConfig model for persistent configuration
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  - [x] 4.2 Write property test for global limit exceeded behavior


    - Create tests/property/test_global_rate_limit_props.py
    - Test that requests are rejected when limit exceeded and response is "Занят."
    - **Property 5: Global Limit Exceeded Behavior**
    - **Validates: Requirements 2.1, 2.2**


  - [x] 4.3 Write property test for rate limit window reset









    - Test that counter resets to 0 after 60-second window expires
    - **Property 6: Rate Limit Window Reset**
    - **Validates: Requirements 2.4**

## Phase 4: Status Notification Manager

- [x] 5. Implement Status Notification Manager

  - [x] 5.1 Create app/services/status_manager.py with StatusManager class


    - Implement start_processing(), add_pending_reaction(), finish_processing(), is_processing()
    - Track processing state per chat in Redis/memory
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 5.2 Write property test for processing state triggers reaction

    - Create tests/property/test_status_manager_props.py
    - Test that new messages get ⏳ reaction while chat is processing
    - **Property 7: Processing State Triggers Reaction**
    - **Validates: Requirements 3.1**


  - [x] 5.3 Write property test for first request triggers notification









    - Test that first request in idle chat triggers exactly one notification
    - **Property 8: First Request Triggers Notification**
    - **Validates: Requirements 3.2**


- [x] 6. Checkpoint - Ensure all tests pass

  - Ensure all tests pass, ask the user if questions arise.


## Phase 5: RAG Temporal Memory Extensions

- [x] 7. Extend RAG with Temporal Memory


  - [x] 7.1 Add timestamp methods to app/services/vector_db.py


    - Implement add_fact_with_timestamp() ensuring created_at in ISO 8601
    - Implement search_facts_with_age() returning age_days field
    - Extend existing VectorDB class (already has add_fact, search_facts methods)
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 7.2 Write property test for RAG fact timestamp presence

    - Create tests/property/test_rag_temporal_props.py
    - Test that all saved facts have valid ISO 8601 created_at metadata
    - **Property 9: RAG Fact Timestamp Presence**
    - **Validates: Requirements 4.1**
  - [x] 7.3 Write property test for RAG prompt contains datetime

    - Test that generated prompts include "СЕГОДНЯ: YYYY-MM-DD HH:MM" format
    - **Property 10: RAG Prompt Contains Current DateTime**
    - **Validates: Requirements 4.2**


  - [x] 7.4 Write property test for RAG fact prioritization




    - Test that newer facts are prioritized over older conflicting facts
    - **Property 11: RAG Fact Prioritization by Recency**
    - **Validates: Requirements 4.3**



  - [x] 7.5 Add memory management methods to app/services/vector_db.py



    - Implement delete_all_chat_facts(), delete_old_facts(), delete_user_facts()
    - Return count of deleted facts
    - _Requirements: 5.1, 5.2, 5.3, 5.4_


  - [x] 7.6 Write property test for memory deletion completeness - all facts




    - Test that delete_all_chat_facts() leaves exactly 0 facts for that chat
    - **Property 12: Memory Deletion Completeness - All Facts**


    - **Validates: Requirements 5.1**

  - [x] 7.7 Write property test for memory deletion completeness - old facts



    - Test that delete_old_facts() removes all facts older than 90 days

    - **Property 13: Memory Deletion Completeness - Old Facts**
    - **Validates: Requirements 5.2**
  - [x] 7.8 Write property test for memory deletion completeness - user facts

    - Test that delete_user_facts() removes all facts for specified user_id
    - **Property 14: Memory Deletion Completeness - User Facts**
    - **Validates: Requirements 5.3**

  - [x] 7.9 Write property test for deletion count accuracy



    - Test that returned count equals actual number of deleted facts
    - **Property 15: Deletion Count Accuracy**
    - **Validates: Requirements 5.4**


- [x] 8. Checkpoint - Ensure all tests pass


  - Ensure all tests pass, ask the user if questions arise.

## Phase 6: Panic Mode Controller

- [-] 9. Implement Panic Mode Controller

  - [x] 9.1 Create app/services/panic_mode.py with PanicModeController class




    - Implement check_join_trigger() with 10 joins/10 seconds threshold
    - Implement check_message_trigger() with 20 messages/second threshold
    - Implement activate_panic_mode(), deactivate_panic_mode()
    - Integrate with existing CitadelService for raid detection
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 9.2 Write property test for panic mode activation on mass join




    - Create tests/property/test_panic_mode_props.py
    - Test that 10+ joins in 10 seconds activates panic mode
    - **Property 16: Panic Mode Activation on Mass Join**
    - **Validates: Requirements 6.1**

  - [x] 9.3 Write property test for panic mode activation on message flood




    - Test that 20+ messages/second from different users activates panic mode
    - **Property 17: Panic Mode Activation on Message Flood**
    - **Validates: Requirements 6.2**


  - [x] 9.4 Write property test for panic mode silences welcome messages



    - Test that no welcome messages are sent while panic mode is active
    - **Property 18: Panic Mode Silences Welcome Messages**
    - **Validates: Requirements 6.3**

  - [x] 9.5 Write property test for panic mode restricts recent users




    - Test that users joined within 24 hours get 30-minute RO status
    - **Property 19: Panic Mode Restricts Recent Users**
    - **Validates: Requirements 6.4**
  - [x] 9.6 Implement hard captcha generation and verification





    - Generate math problems (e.g., "12 + 7 = ?")
    - Store expected answer in SilentBan.captcha_answer
    - _Requirements: 6.5_


## Phase 7: Permission Checker Service

- [ ] 10. Implement Permission Checker Service


  - [x] 10.1 Create app/services/permission_checker.py with PermissionChecker class



    - Implement check_permissions() with 60-second cache
    - Implement can_perform_action() checking specific permission
    - Implement report_missing_permission() for silent admin notification
    - Use get_chat_member API for permission verification
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 10.2 Write property test for permission check before moderation




    - Create tests/property/test_permission_checker_props.py
    - Test that permissions are verified before any moderation action
    - **Property 20: Permission Check Before Moderation**

    - **Validates: Requirements 7.1**

  - [x] 10.3 Write property test for missing permission silent report



    - Test that missing permissions trigger silent admin notification
    - **Property 21: Missing Permission Silent Report**
    - **Validates: Requirements 7.2**

  - [x] 10.4 Write property test for no threats without permissions




    - Test that no threatening messages are sent when bot lacks permissions
    - **Property 22: No Threats Without Permissions**
    - **Validates: Requirements 7.3**

- [ ] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 8: Spam Classifier Service

- [ ] 12. Implement Spam Classifier Service
  - [x] 12.1 Create app/services/spam_classifier.py with SpamClassifier class





    - Define SPAM_PATTERNS dict with categories: selling, crypto, job_offer, collaboration
    - Implement classify() returning SpamClassification with confidence
    - Use combination of regex, keywords, and scoring
    - _Requirements: 8.1, 8.2, 8.3, 8.4_
  - [x] 12.2 Write property test for spam detection triggers delete and ban





    - Create tests/property/test_spam_classifier_props.py
    - Test that spam messages trigger both deletion and ban
    - **Property 23: Spam Detection Triggers Delete and Ban**
    - **Validates: Requirements 8.1, 8.2**
  - [x] 12.3 Write property test for spam classification logging





    - Test that spam logs contain message hash and confidence score
    - **Property 24: Spam Classification Logging**
    - **Validates: Requirements 8.4**

## Phase 9: User Scanner Service

- [-] 13. Implement User Scanner Service

  - [x] 13.1 Create app/services/user_scanner.py with UserScanner class




    - Implement scan_user() checking avatar, name patterns, premium status
    - Implement calculate_score() returning 0.0-1.0 suspicion score
    - Check for RTL characters, hieroglyphics, spam words in username
    - Use SilentBan model for storing silent ban records
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  - [x] 13.2 Write property test for new user scan checks all factors





    - Create tests/property/test_user_scanner_props.py
    - Test that scan checks avatar, username patterns, and premium status
    - **Property 25: New User Scan Checks All Factors**
    - **Validates: Requirements 9.1, 9.2, 9.3**

  - [x] 13.3 Write property test for high suspicion score triggers silent ban




    - Test that no avatar + suspicious name triggers silent ban
    - **Property 26: High Suspicion Score Triggers Silent Ban**
    - **Validates: Requirements 9.4**

  - [x] 13.4 Write property test for silent ban deletes messages silently




    - Test that messages from silent-banned users are deleted without notification
    - **Property 27: Silent Ban Deletes Messages Silently**
    - **Validates: Requirements 9.5**

- [ ] 14. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Phase 10: Protection Profiles Manager


- [x] 15. Implement Protection Profiles Manager






  - [x] 15.1 Create app/services/protection_profiles.py with ProtectionProfileManager class














    - Define ProtectionProfile enum (STANDARD, STRICT, BUNKER, CUSTOM)
    - Define PROFILE_PRESETS dict with default settings for each profile
    - Implement get_profile(), set_profile(), set_custom_settings(), get_settings()
    - Use ProtectionProfileConfig model for persistence
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 15.2 Write property test for protection profile applies correct settings






    - Create tests/property/test_protection_profiles_props.py
    - Test Standard: anti_spam_links=true, captcha_type="button", profanity_allowed=true
    - Test Strict: neural_ad_filter=true, block_forwards=true, sticker_limit=3
    - Test Bunker: mute_newcomers=true, block_media_non_admin=true, aggressive_profanity=true
    - **Property 28: Protection Profile Applies Correct Settings**
    - **Validates: Requirements 10.1, 10.2, 10.3**

## Phase 11: RAG Serialization Round-Trip

- [-] 16. Implement RAG Fact Metadata Serialization


  - [x] 16.1 Add RAGFactMetadata dataclass to app/services/vector_db.py



    - Implement to_dict() and from_dict() methods
    - Fields: chat_id, user_id, username, topic_id, message_id, created_at
    - Ensure all metadata fields are preserved through serialization
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 16.2 Write property test for RAG fact serialization round-trip




    - Create tests/property/test_rag_serialization_props.py
    - Test that serialize(deserialize(fact)) == fact for all valid facts
    - **Property 29: RAG Fact Serialization Round-Trip**
    - **Validates: Requirements 11.1, 11.2**


  - [x] 16.3 Write property test for Unicode preservation in serialization



    - Test that Cyrillic, emoji, and special symbols are preserved
    - **Property 30: Unicode Preservation in Serialization**
    - **Validates: Requirements 11.3**



- [x] 17. Final Checkpoint - Ensure all tests pass



  - Ensure all tests pass, ask the user if questions arise.

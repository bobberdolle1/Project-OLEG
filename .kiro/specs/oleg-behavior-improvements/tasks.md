# Implementation Plan

- [x] 1. Отключение автоматических ответов на изображения





  - [x] 1.1 Добавить функцию should_process_image в vision.py


    - Создать функцию проверки упоминания бота в caption
    - Проверять reply на сообщение бота
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.2 Обновить handle_image_message для использования фильтра

    - Добавить вызов should_process_image в начало обработчика
    - Возвращать early если фильтр не прошёл
    - _Requirements: 1.1, 1.4_
  - [x] 1.3 Написать property тест для фильтрации изображений


    - **Property 1: Image filtering without explicit mention**
    - **Property 2: Image processing with explicit mention**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4**


- [x] 2. Улучшение системы авто-ответов





  - [x] 2.1 Обновить константы вероятности в auto_reply.py

    - BASE_PROBABILITY_MIN = 0.02 (было 0.15)
    - BASE_PROBABILITY_MAX = 0.05 (было 0.25)
    - MAX_PROBABILITY = 0.15 (было 0.40)
    - _Requirements: 2.1, 2.4_
  - [x] 2.2 Добавить фильтр по длине сообщения

    - MIN_MESSAGE_LENGTH = 15
    - Проверять len(text) >= MIN_MESSAGE_LENGTH
    - _Requirements: 2.2_

  - [x] 2.3 Добавить блоклист коротких фраз

    - Создать BLOCKED_SHORT_PHRASES set
    - Проверять text.lower().strip() not in BLOCKED_SHORT_PHRASES
    - _Requirements: 2.3_


  - [x] 2.4 Обновить метод should_reply с новыми фильтрами
    - Добавить проверки длины и блоклиста перед расчётом вероятности
    - _Requirements: 2.2, 2.3_
  - [x] 2.5 Обновить property тесты для auto_reply


    - **Property 3: Short message rejection**
    - **Property 4: Probability bounds**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**


- [x] 3. Checkpoint - Проверка тестов




  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Переработка промпта Олега





  - [x] 4.1 Упростить секцию "Базовые черты характера"


    - Убрать литературные обороты
    - Использовать простые формулировки
    - Добавить "используется в тему, не постоянно" для мата/юмора
    - _Requirements: 4.8, 4.9, 4.10_

  - [x] 4.2 Упростить секцию "Стиль общения"

    - Убрать "из токсичного чата" → просто "как живой человек"
    - Убрать "без форсирования техно-отсылок" → "отвечай по теме"
    - Убрать "растекаешься мыслью по древу"
    - _Requirements: 4.11, 4.12, 4.13_
  - [x] 4.3 Переработать секцию "Длина ответов"


    - Явно указать: 1-3 коротких предложения максимум
    - Запретить списки и структурированные ответы
    - Запретить фразы "рад помочь", "надеюсь помог"
    - _Requirements: 4.1, 4.3, 4.6, 4.7_
  - [x] 4.4 Вынести примеры диалогов в отдельную секцию


    - Убрать примеры из середины инструкций
    - Разместить примеры в конце промпта
    - Убрать конкретные фразы для входа в диалог
    - _Requirements: 4.14, 4.15_
  - [x] 4.5 Написать unit тест для проверки структуры промпта


    - Проверить отсутствие запрещённых фраз
    - Проверить наличие ключевых инструкций
    - _Requirements: 4.1-4.15_


- [x] 5. Обновление qna.py для согласованности




  - [x] 5.1 Проверить что явные вызовы всегда срабатывают


    - Убедиться что @mention и "олег" проверяются до авто-ответа
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  - [x] 5.2 Написать property тесты для явных вызовов


    - **Property 5: Explicit mention always triggers response**
    - **Property 6: Private chat always triggers response**
    - **Validates: Requirements 5.1, 5.2, 5.4**


- [x] 6. Checkpoint - Финальная проверка




  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Обновление документации

  - [x] 7.1 Обновить CHANGELOG.md
    - Добавить секцию для версии 6.6
    - Описать все изменения
    - _Requirements: 6.1_
  - [x] 7.2 Обновить README.md при необходимости
    - Проверить актуальность описания функций
    - _Requirements: 6.2_
  - [x] 7.3 Создать git commit
    - Сообщение: "v6.6: Improve Oleg behavior - disable auto image replies, tune auto-reply system, refine prompt"
    - _Requirements: 6.3_

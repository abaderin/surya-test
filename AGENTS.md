# Project Goal
The project goal is to implement web tool which provides useful way to process books with surya and introspect processing
results.
It consists of frontend (SPA) and backend (API).
Typical usage flow is:
- user uploads pdf or djvu file
- backend should validate it, process and prepare data for visualization
- user can look on the result

Each page has a left side menu, which could be collapsed.
Menu has sections - Files and Tasks for the beginning.
Application main page - Files. It provides to user a way to upload files and lists already uploaded files.
Each Files page list element contains informations which been updated in process of processing - like pages count, processing
progress (amount of procedeed tasks / total amount of tasks), book icon (first page).
This file element is clickable and leads to file page. If book still being procedeed this file page shows message about it and
shows progress. If processing failed the transient link is not active and file element shows failed task link to follow and look.
If processing has been finished and succeded then file page shows primary view - page splitted into two columns, left used for
original pages and blocks recognized by layout and on right side - content of this blocks: cutted image for image blocks, OCRed text for text blocks, latex code for formulas, etc. File page has a pagination and amount of pages displayd could be changes using
corresponding control element which provides options of 10, 20, 50 book pages at once.
On left column above original book page image all recognized blocks marked with rectangular svg blocks with hover tooltip which
contains (shows) original surya response corresponding this block. Each type of block has its own color. Textual - blue, Header - red, etc. Right columns contains blocks list, for which additional processing has been performed (OCR for example). Each block contains result of that processing. Each block on left side connected by line of corresponding color with block on right side (marked with that color too).
Tasks page shows list of all tasks performed timely ordered. Also task status must be shown.
Click on tasks page element leads to task page where input and output params could be discovered.

## File processing states:
- New
- Validation
- Validation Failed
- In Progress
- Failed
- Done

## Task states:
- New
- In Progress
- Failed
- Done

## Task types
- Layout
- OCR
- Image Extraction
- Meta Extraction (page number, chapter name, etc)

## Backend stack
- Python 3.14
- FastAPI
- DI контейнер - встроенный в FastAPI
- uvicorn
- asyncio
- APScheduler
- SQLAlchemy 2.x
- asyncpg
- PostgreSQL
- Redis (websocket + redis as event bus for notifications and status updates)

## Frontend stack
- TypeScript
- React
- Vite
- Mantine
- Zustand
- TanStack Query
- Websocket

## Rules
- Technical stack changes disallowed
- Tests are required for every task if they could be added. Task is not counted finished until tests are not implemented
- Tests must succeed after task implementation, otherwise task is not counted as finished.
- Tests logic must mirror busyness logic, dont adjust to the solution - it is disallowed
- Unused code must be removed
- After every change do commit and push into current branch

# UAE Seeker

Рабочий прототип ежедневного мониторинга вакансий **Frontend Developer / Frontend Engineer** уровня **Senior → Staff → Principal → Lead → Tech Lead** для:

- UAE
- Saudi Arabia
- Southeast Asia
- Cyprus

Прототип уже умеет:

- читать реестр источников из YAML;
- собирать вакансии из sample-источника, RSS и публичных ATS/job APIs;
- фильтровать junior/middle/нерелевантные вакансии;
- определять seniority и frontend relevance score;
- вытаскивать стек: React, TypeScript, Next.js, Angular, Vue, GraphQL и т.д.;
- дедуплицировать вакансии;
- сохранять результат в SQLite;
- генерировать Markdown digest;
- запускаться ежедневно через GitHub Actions.

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
python -m job_monitor collect --config config/sources.example.yaml --db data/jobs.sqlite --digest out/digest.md
```

После запуска digest будет в:

```text
out/digest.md
```

Посмотреть последние записи из SQLite:

```bash
python -m job_monitor show --db data/jobs.sqlite --limit 20
```

Запустить тесты:

```bash
pytest
```

## Как добавлять источники

Источники лежат в `config/sources.example.yaml`. Каждый источник имеет `type`:

- `sample` — демо-данные, чтобы прототип работал без API-ключей;
- `rss` — RSS/Atom feed;
- `jsearch` — job-search API через RapidAPI-style JSearch;
- `greenhouse` — публичные job boards Greenhouse;
- `lever` — публичные job postings Lever;
- `ashby` — публичный job board Ashby.

Пример Greenhouse:

```yaml
- name: example-greenhouse
  type: greenhouse
  enabled: true
  region: uae
  country: UAE
  board_token: examplecompany
```

Пример Lever:

```yaml
- name: example-lever
  type: lever
  enabled: true
  region: cyprus
  country: Cyprus
  site: examplecompany
```

Пример JSearch:

```yaml
- name: jsearch-uae
  type: jsearch
  enabled: true
  region: uae
  country: UAE
  queries:
    - Senior Frontend Developer Dubai
    - Lead Frontend Engineer UAE
```

Для JSearch нужен `.env`:

```bash
JSEARCH_API_KEY=...
JSEARCH_API_HOST=jsearch.p.rapidapi.com
```

Если ключа нет, источник будет пропущен, а остальные продолжат работать.

## Daily run через GitHub Actions

Workflow находится в `.github/workflows/frontend-job-monitor.yml`. Он запускается по расписанию и вручную.

Для реального прод-режима надо добавить repository secret:

```text
JSEARCH_API_KEY
```

Артефакты после запуска:

- `digest.md`
- `jobs.sqlite`

## Что ещё добавить на следующем этапе

- Telegram/Slack/email delivery;
- отдельный web dashboard;
- LLM-классификатор для `visa / relocation / remote / compensation`;
- pgvector или embeddings для более сильной дедупликации;
- список target-компаний по UAE, Saudi, SEA и Cyprus;
- ingestion из email alerts для LinkedIn/Indeed/JobStreet/Bayt.

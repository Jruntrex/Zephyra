# Mentorly — Платформа управління навчальним процесом

**Mentorly** — головна платформа для автоматизації академічного обліку. Кожен навчальний заклад розгортає власний екземпляр Mentorly зі своїм брендингом — у даному репозиторії це заклад **MyBosco**.

Назва та логотип закладу налаштовуються через `InstitutionSettings` (singleton-модель) і автоматично відображаються в інтерфейсі через `context_processors`.

---

## Можливості

### Адміністратор
- CRUD для студентів, викладачів та адміністраторів (з фото профілю)
- Управління групами, предметами та аудиторіями
- Призначення викладачів на дисципліни для конкретних груп (`TeachingAssignment`)
- Редактор тижневого розкладу з підтримкою чисельник/знаменник
- CSV-імпорт та експорт для користувачів, груп, предметів, аудиторій
- Налаштування закладу (назва, слоган, логотип, фавікон)
- Налаштування шкал оцінювання та правил переведення балів (`GradingScale`, `GradeRule`)
- Звіти: академічний рейтинг, пропуски, "студенти під ризиком", домашні завдання

### Викладач
- Журнал оцінок та відвідуваності для закріплених груп
- Зважена система оцінювання: кожен тип заняття (лекція, практика, екзамен тощо) має власний відсотковий коефіцієнт (`EvaluationType`)
- Часова шкала занять з можливістю редагування тем і матеріалів
- Завантаження вкладень до занять
- Перегляд, оцінювання та коментування домашніх завдань студентів
- Сканування студентських карток (апаратна інтеграція через `CARD_SCAN_API_KEY`)

### Студент
- Особистий залік з деталізацією по предметах і коментарями викладачів
- Облік відвідуваності (поважні та неповажні пропуски)
- Подача домашніх завдань з файловими вкладеннями
- Перегляд розкладу занять
- Просунуті фільтри: за датою, предметом, балом, пошуковим запитом

---

## Технологічний стек

| Рівень | Технологія |
|---|---|
| Backend | Python 3.12+ / Django 5.2.7 |
| Database | MySQL (через `mysqlclient`) |
| Frontend | Tailwind CSS 3.4, Vanilla JS (AJAX / Fetch API) |
| Сповіщення | Twilio SMS |
| Зображення | Pillow |
| Async HTTP | aiohttp |
| Конфігурація | python-dotenv |

---

## Встановлення

### 1. Клонування та віртуальне середовище
```bash
git clone <url_репозиторію>
cd MyBosco
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Файл `.env`
Створіть `.env` у корені проекту (`MyBosco/`):
```env
SECRET_KEY=ваш_секретний_ключ
DEBUG=True

DB_ENGINE=django.db.backends.mysql
DB_NAME=mybosco_db
DB_USER=root
DB_PASSWORD=ваш_пароль
DB_HOST=localhost
DB_PORT=3306

# Опційно — SMS через Twilio
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=

# Опційно — сканування карток
CARD_SCAN_API_KEY=
```

### 3. База даних та міграції
```bash
# Створіть БД у MySQL
mysql -u root -p -e "CREATE DATABASE mybosco_db CHARACTER SET utf8mb4;"

python manage.py migrate
python manage.py createsuperuser
```

### 4. Збірка CSS (Tailwind)
```bash
npm install
npm run build:css
# або для розробки:
npm run watch:css
```

### 5. Запуск
```bash
python manage.py runserver
```

---

## Management Commands

```bash
# Наповнення бази тестовими даними
python manage.py reset_and_seed
python manage.py seed_rich_content

# Заповнення деталей занять (теми, типи)
python manage.py fill_lesson_details
```

---

## Структура проекту

```
MyBosco/
├── main/
│   ├── models.py              # Всі моделі (User, Group, Subject, Lesson, Grade…)
│   ├── views.py               # Views та REST-like API endpoints
│   ├── urls.py
│   ├── forms.py
│   ├── selectors.py           # Запити до БД (read-side)
│   ├── context_processors.py  # Глобальний контекст (InstitutionSettings)
│   ├── middleware.py          # NoCacheAuthMiddleware
│   ├── services/
│   │   ├── grading_service.py   # Логіка зваженого рейтингу
│   │   ├── schedule_service.py  # Генерація занять із шаблонів
│   │   └── sms_service.py       # Twilio SMS
│   ├── templatetags/
│   │   ├── journal_filters.py
│   │   └── math_filters.py
│   ├── management/commands/     # Seed-команди
│   ├── static/                  # CSS (Tailwind output), JS
│   └── templates/
├── mybosco_project/
│   ├── settings.py
│   └── urls.py
├── requirements.txt
├── package.json                 # Tailwind / PostCSS
└── manage.py
```

---

## Безпека

- Паролі хешуються через PBKDF2 (стандарт Django)
- Рольовий доступ (Admin / Teacher / Student) через декоратор `role_required`
- Django ORM захищає від SQL Injection
- `NoCacheAuthMiddleware` запобігає кешуванню сторінок авторизованих користувачів
- Секрети зберігаються у `.env`, а не в коді

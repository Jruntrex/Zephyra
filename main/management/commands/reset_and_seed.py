"""
Management command: reset_and_seed

Очищає під нуль: оцінки, пропуски, розклад, матеріали уроків.
Заново заповнює дані з 2026-03-09 по 2026-04-09:
  - Оцінки та пропуски: до 2026-03-20 включно
  - Розклад (уроки): весь діапазон

Уроки заповнюються детальним контентом (конспект, ДЗ, матеріали),
щоб студент, який пропустив заняття, зміг самостійно опанувати тему.
"""

import random
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from main.models import (
    AbsenceReason,
    Classroom,
    EvaluationType,
    HomeworkSubmission,
    Lesson,
    LessonAttachment,
    PrivateComment,
    ScheduleTemplate,
    StudentPerformance,
    StudyGroup,
    SubmissionAttachment,
    TeachingAssignment,
    User,
)

# ─── Dates ────────────────────────────────────────────────────────────────────
START_DATE = date(2026, 3, 9)
END_DATE = date(2026, 4, 9)
GRADES_CUTOFF = date(2026, 3, 20)  # grades + absences only up to this date

# ─── Schedule plan ────────────────────────────────────────────────────────────
# (day_of_week 1=Пн … 5=Пт, lesson_number 1-5, subject_slot_idx)
# subject_slot_idx cycles modulo len(group subjects)
SCHEDULE_SLOTS = [
    (1, 1, 0),
    (1, 2, 1),
    (1, 3, 2),
    (1, 4, 3),  # Пн – 4 пари
    (2, 1, 4),
    (2, 2, 5),
    (2, 3, 6),
    (2, 4, 0),  # Вт – 4 пари
    (3, 1, 1),
    (3, 2, 2),
    (3, 3, 3),  # Ср – 3 пари
    (4, 1, 4),
    (4, 2, 5),
    (4, 3, 6),
    (4, 4, 1),  # Чт – 4 пари
    (5, 1, 0),
    (5, 2, 2),
    (5, 3, 3),  # Пт – 3 пари
]

TIME_MAP = {
    1: (time(8, 30), time(9, 50)),
    2: (time(10, 5), time(11, 25)),
    3: (time(11, 40), time(13, 0)),
    4: (time(13, 30), time(14, 50)),
    5: (time(15, 5), time(16, 25)),
}

# For each subject, cycle through these lesson types
LESSON_TYPE_CYCLE = ["lecture", "practical", "lab", "lecture", "practical"]

# ─── Topics by subject ────────────────────────────────────────────────────────
TOPICS = {
    "Вища математика": [
        "Визначений інтеграл та його застосування",
        "Невизначений інтеграл. Методи інтегрування",
        "Диференціальні рівняння першого порядку",
        "Числові ряди. Ознаки збіжності",
        "Функції кількох змінних. Часткові похідні",
        "Подвійний інтеграл та його застосування",
        "Степеневі ряди. Ряд Тейлора та Маклорена",
        "Криволінійні інтеграли",
        "Поверхневі інтеграли",
        "Елементи теорії поля",
    ],
    "Об'єктно-орієнтоване програмування": [
        "Інкапсуляція, наслідування, поліморфізм",
        "Патерни проектування: Singleton, Factory, Observer",
        "Абстрактні класи та інтерфейси",
        "Виняткові ситуації та їх обробка",
        "Узагальнені типи (Generics)",
        "Патерни проектування: Strategy, Command, Decorator",
        "SOLID-принципи проектування",
        "Рефакторинг коду. Code Smells",
        "Unit-тестування. TDD",
        "UML-діаграми. Моделювання систем",
    ],
    "Бази даних": [
        "Реляційна модель даних. Нормальні форми",
        "SQL: складні запити, підзапити, JOIN",
        "Транзакції та рівні ізоляції",
        "Індекси та оптимізація запитів",
        "Збережені процедури та тригери",
        "NoSQL-бази даних: MongoDB, Redis",
        "Проектування баз даних. ER-діаграми",
        "Реплікація та шардинг",
        "ORM: принципи та практика",
        "Безпека баз даних",
    ],
    "Веб-технології": [
        "HTTP/HTTPS протокол. REST API",
        "JavaScript: асинхронність, Promise, async/await",
        "React: компоненти, хуки, стан",
        "CSS Flexbox та Grid Layout",
        "Автентифікація та авторизація у веб-додатках",
        "WebSockets та реал-тайм комунікація",
        "Django: моделі, представлення, шаблони",
        "GraphQL. Порівняння з REST",
        "PWA та Service Workers",
        "Мікрофронтенд архітектура",
    ],
    "Алгоритми та структури даних": [
        "Сортування: merge sort, quick sort, heap sort",
        "Бінарні дерева пошуку. AVL-дерева",
        "Графи: алгоритми BFS та DFS",
        "Алгоритм Дейкстри та A*",
        "Динамічне програмування",
        "Хеш-таблиці. Методи вирішення колізій",
        "Черги з пріоритетом. Купа (Heap)",
        "Жадібні алгоритми",
        "Алгоритми рядків: KMP, Boyer-Moore",
        "NP-повні задачі. Апроксимаційні алгоритми",
    ],
    "Комп'ютерні мережі": [
        "Модель OSI та стек протоколів TCP/IP",
        "Мережевий рівень. IP-адресація та маршрутизація",
        "Транспортний рівень. TCP vs UDP",
        "DNS, DHCP, NAT",
        "Мережева безпека. Брандмауери та VPN",
        "Бездротові мережі: Wi-Fi стандарти",
        "HTTP/2, HTTP/3 та оптимізація веб-трафіку",
        "SDN та NFV",
        "IPv6: перехід та особливості",
        "Мережевий моніторинг та діагностика",
    ],
    "Комп'ютерна архітектура": [
        "Архітектура процесора. Конвеєризація",
        "Пам'ять: ієрархія, кеш, віртуальна пам'ять",
        "Паралелізм на рівні інструкцій",
        "Багатоядерні процесори. SIMD",
        "Введення/Виведення. Переривання",
        "Периферійні пристрої. Шини",
        "Архітектура GPU",
    ],
    "Операційні системи": [
        "Управління процесами та потоками",
        "Синхронізація: м'ютекси, семафори, монітори",
        "Управління пам'яттю. Сторінкова організація",
        "Файлові системи: FAT, NTFS, ext4",
        "Планування процесів: FCFS, SJF, Round Robin",
        "Системні виклики Unix/Linux",
        "Deadlock: умови виникнення та методи запобігання",
        "Безпека ОС. Права доступу",
        "Контейнеризація. Docker",
        "Ядро Linux: архітектура та модулі",
    ],
    "Дискретна математика": [
        "Теорія множин. Відношення та функції",
        "Математична логіка. Нормальні форми",
        "Теорія графів. Основні поняття та задачі",
        "Комбінаторика: перестановки, розміщення, комбінації",
        "Булева алгебра та логічні схеми",
        "Рекурентні співвідношення",
        "Теорія автоматів і формальних мов",
        "Теорія кодування",
        "Теорія ймовірностей: дискретний випадок",
        "Математична індукція та рекурсія",
    ],
    "Програмування мовою Python": [
        "Декоратори та генератори",
        "Об'єктно-орієнтоване програмування в Python",
        "Робота з файлами, JSON, CSV",
        "Мережеве програмування: requests, aiohttp",
        "NumPy та Pandas: основи аналізу даних",
        "Тестування: unittest, pytest",
        "Паралельне програмування: threading, multiprocessing, asyncio",
        "Розробка API: FastAPI, Flask",
        "Робота з базами даних: SQLAlchemy",
        "Автоматизація: скрипти та CLI",
    ],
    "Штучний інтелект та МН": [
        "Машинне навчання: класифікація та регресія",
        "Нейронні мережі: перцептрон та багатошарові мережі",
        "Згорткові нейронні мережі (CNN)",
        "Рекурентні нейронні мережі (RNN, LSTM)",
        "Навчання з підкріпленням",
        "Трансформери та увага (Attention Mechanism)",
        "Генеративні моделі: GAN, VAE",
    ],
    "Мобільна розробка": [
        "Архітектура мобільних додатків",
        "Flutter: основи та State Management",
        "Нативний Android: Kotlin основи",
        "iOS розробка: Swift та SwiftUI",
        "Робота з API та локальним сховищем",
        "Push-сповіщення та фонові задачі",
        "Публікація в App Store та Google Play",
    ],
    "Безпека інформаційних систем": [
        "Криптографія: симетричне та асиметричне шифрування",
        "Атаки на веб-додатки: XSS, SQL Injection, CSRF",
        "PKI та цифровий підпис",
        "Мережеві атаки та методи захисту",
        "Аутентифікація: паролі, MFA, OAuth 2.0",
        "Пентестинг: методологія та інструменти",
        "OWASP Top 10: огляд вразливостей",
    ],
    "Теорія ймовірностей та статистика": [
        "Ймовірнісний простір. Аксіоми Колмогорова",
        "Умовна ймовірність. Формула Байєса",
        "Випадкові величини та їх розподіли",
        "Математичне очікування та дисперсія",
        "Закон великих чисел",
        "Центральна гранична теорема",
        "Статистичне оцінювання параметрів",
        "Перевірка статистичних гіпотез",
        "Регресійний аналіз",
        "Кореляційний аналіз",
    ],
    "Системне програмування": [
        "Системні виклики POSIX: процеси",
        "Міжпроцесна взаємодія: pipes, FIFO",
        "Сокети та мережеве програмування",
        "Потоки (pthreads) та синхронізація",
        "Динамічне завантаження бібліотек",
        "Сигнали в Unix/Linux",
        "Розробка модулів ядра Linux",
    ],
    "ВЕБ-технології": [
        "HTTP/HTTPS протокол. REST API",
        "HTML5 та семантична розмітка",
        "CSS3: сучасні можливості",
        "JavaScript ES2022+",
        "React: сучасна розробка SPA",
        "Node.js та серверний JavaScript",
        "DevOps: CI/CD для веб-додатків",
    ],
}

DEFAULT_TOPICS = [
    "Введення в тему. Основні поняття",
    "Теоретичні основи розділу",
    "Практичне застосування теорії",
    "Розбір типових задач та прикладів",
    "Узагальнення та систематизація знань",
    "Лабораторна робота за темою",
    "Контрольне заняття",
    "Самостійна робота та аналіз",
]

# ─── Rich HTML content for lectures ──────────────────────────────────────────


def _make_lecture_html(topic, subject=""):
    """Генерує детальний HTML-конспект лекції для студентів."""
    return f"""<h2>{topic}</h2>

<h3>1. Мета та завдання теми</h3>
<p>На цьому занятті розглядається тема <strong>{topic}</strong>. Після вивчення матеріалу студент повинен:</p>
<ul>
  <li>знати основні визначення та поняття теми;</li>
  <li>розуміти теоретичні основи та принципи;</li>
  <li>вміти застосовувати отримані знання на практиці;</li>
  <li>аналізувати типові задачі та знаходити оптимальні рішення.</li>
</ul>

<h3>2. Теоретична частина</h3>
<p>Тема <strong>{topic}</strong> є важливою складовою курсу <em>{subject}</em>. Розглянемо ключові аспекти:</p>

<h4>2.1. Основні визначення</h4>
<p>Перш за все, необхідно засвоїти базову термінологію та поняття, що використовуються в даній темі. Всі визначення наведені у відповідному розділі підручника та у слайдах презентації.</p>

<h4>2.2. Теоретичні основи</h4>
<p>Теоретична база теми ґрунтується на фундаментальних принципах, що вивчалися раніше. Важливо розуміти взаємозв'язок між поточним матеріалом і попередніми темами курсу.</p>

<h4>2.3. Ключові алгоритми та методи</h4>
<p>Для розв'язання задач за даною темою використовуються такі підходи:</p>
<ol>
  <li><strong>Аналіз задачі</strong> — визначення вхідних даних, умов та очікуваного результату.</li>
  <li><strong>Вибір методу</strong> — застосування відповідного алгоритму чи формули.</li>
  <li><strong>Реалізація</strong> — покрокове виконання алгоритму.</li>
  <li><strong>Перевірка результату</strong> — верифікація отриманої відповіді.</li>
</ol>

<h3>3. Практичні приклади</h3>
<p>Розглянемо кілька типових прикладів за темою <strong>{topic}</strong>:</p>

<blockquote>
  <p><strong>Приклад 1.</strong> Типова задача початкового рівня. Застосовуємо базові поняття теми та отримуємо результат, використовуючи стандартний алгоритм.</p>
</blockquote>

<blockquote>
  <p><strong>Приклад 2.</strong> Задача середнього рівня складності. Потребує комбінування кількох методів та уважного аналізу умови задачі.</p>
</blockquote>

<blockquote>
  <p><strong>Приклад 3.</strong> Задача підвищеної складності. Розглядає нестандартний підхід та використовує весь арсенал знань з теми.</p>
</blockquote>

<h3>4. Типові помилки та як їх уникнути</h3>
<ul>
  <li>Неуважне читання умови задачі — завжди перевіряйте вхідні дані.</li>
  <li>Пропуск граничних випадків — враховуйте крайні значення діапазону.</li>
  <li>Неправильне застосування формул — звертайтесь до конспекту та підручника.</li>
  <li>Відсутність перевірки результату — завжди верифікуйте отримані відповіді.</li>
</ul>

<h3>5. Зв'язок з іншими темами курсу</h3>
<p>Матеріал теми <strong>{topic}</strong> безпосередньо пов'язаний з попередніми та наступними розділами курсу. Рекомендується повторити відповідні теми для кращого розуміння.</p>

<h3>6. Питання для самоперевірки</h3>
<ol>
  <li>Сформулюйте основне визначення теми своїми словами.</li>
  <li>Яке практичне значення має дана тема?</li>
  <li>Наведіть два-три приклади застосування матеріалу.</li>
  <li>Які є типові помилки при розв'язанні задач за цією темою?</li>
  <li>Як дана тема пов'язана з іншими розділами курсу?</li>
</ol>

<h3>7. Рекомендована література</h3>
<p>Детальний перелік літератури та посилання на матеріали розміщені у розділі «Матеріали» до цього заняття.</p>"""


def _make_practical_html(topic, subject=""):
    """HTML для практичного заняття."""
    return f"""<h2>Практичне заняття: {topic}</h2>

<h3>Мета заняття</h3>
<p>Закріплення теоретичного матеріалу з теми <strong>{topic}</strong> шляхом розв'язання практичних задач.</p>

<h3>Теоретичний мінімум (повторення)</h3>
<p>Перед виконанням практичних завдань переконайтесь, що ви пам'ятаєте:</p>
<ul>
  <li>основні визначення та поняття теми;</li>
  <li>ключові формули та алгоритми;</li>
  <li>типові підходи до розв'язання задач.</li>
</ul>
<p>Якщо потрібно — повторіть конспект лекції перед виконанням завдань.</p>

<h3>Завдання для виконання на занятті</h3>

<h4>Задача 1 (обов'язкова, базовий рівень)</h4>
<p>Розв'язати задачу, застосовуючи стандартний алгоритм із лекції. Задача перевіряє базове розуміння теми.</p>
<p><em>Варіант задачі надається викладачем на початку заняття (або вказується у роздатковому матеріалі).</em></p>

<h4>Задача 2 (обов'язкова, середній рівень)</h4>
<p>Задача вимагає комбінування кількох методів та більш глибокого аналізу.</p>
<p><em>Виконати самостійно, після чого порівняти з розбором на дошці.</em></p>

<h4>Задача 3 (підвищений рівень, для тих, хто виконав перші дві)</h4>
<p>Нестандартна задача, що розвиває творче мислення. Виконання не обов'язкове, але заохочується додатковими балами.</p>

<h3>Порядок роботи</h3>
<ol>
  <li>Уважно прочитати умову задачі.</li>
  <li>Записати що дано та що потрібно знайти.</li>
  <li>Вибрати та записати відповідну формулу/алгоритм.</li>
  <li>Виконати розв'язання.</li>
  <li>Перевірити та оформити відповідь.</li>
</ol>

<h3>Критерії оцінювання</h3>
<ul>
  <li><strong>12 балів</strong> — всі задачі виконані правильно, чисте оформлення.</li>
  <li><strong>9-11 балів</strong> — перші дві задачі виконані правильно.</li>
  <li><strong>6-8 балів</strong> — перша задача виконана правильно, в другій є незначні помилки.</li>
  <li><strong>4-5 балів</strong> — часткове виконання з суттєвими помилками.</li>
  <li><strong>1-3 бали</strong> — робота розпочата, але не завершена.</li>
</ul>

<h3>Домашнє завдання</h3>
<p>Детальне домашнє завдання наведено у відповідному розділі цієї сторінки.</p>"""


def _make_lab_html(topic, subject=""):
    """HTML для лабораторної роботи."""
    return f"""<h2>Лабораторна робота: {topic}</h2>

<h3>Мета роботи</h3>
<p>Набуття практичних навичок роботи з інструментами та методами за темою <strong>{topic}</strong>. Студент повинен самостійно виконати завдання та оформити звіт.</p>

<h3>Теоретичні відомості</h3>
<p>Перед виконанням лабораторної роботи необхідно ознайомитись із теоретичним матеріалом лекції на тему <strong>{topic}</strong>. Конспект лекції доступний на цій сторінці у попередніх заняттях.</p>

<p>Ключові поняття, що використовуються в роботі:</p>
<ul>
  <li>Основні визначення та термінологія теми.</li>
  <li>Алгоритм виконання основних операцій.</li>
  <li>Інструменти та середовища, що використовуються в роботі.</li>
</ul>

<h3>Хід виконання</h3>

<h4>Крок 1. Підготовка</h4>
<p>Налаштуйте робоче середовище відповідно до інструкцій у методичних вказівках. Переконайтеся, що всі необхідні інструменти встановлені та працюють.</p>

<h4>Крок 2. Виконання основного завдання</h4>
<p>Виконайте завдання відповідно до свого варіанту (список варіантів у Teams або на стенді кафедри). Фіксуйте всі кроки для подальшого включення у звіт.</p>

<h4>Крок 3. Тестування та перевірка</h4>
<p>Перевірте коректність виконання роботи на тестових прикладах. Переконайтесь, що результати відповідають очікуваним.</p>

<h4>Крок 4. Оформлення звіту</h4>
<p>Оформіть звіт за встановленим шаблоном (шаблон у Teams). Звіт повинен містити:</p>
<ol>
  <li>Тему та мету роботи.</li>
  <li>Теоретичні відомості (стисло).</li>
  <li>Хід виконання з скріншотами/кодом.</li>
  <li>Результати та їх аналіз.</li>
  <li>Висновки.</li>
</ol>

<h3>Контрольні питання для захисту</h3>
<ol>
  <li>Поясніть мету та основні принципи лабораторної роботи.</li>
  <li>Які інструменти використовувалися і чому?</li>
  <li>Опишіть алгоритм виконання основного завдання.</li>
  <li>Які труднощі виникли і як ви їх вирішили?</li>
  <li>Як можна покращити або розширити виконану роботу?</li>
</ol>

<h3>Термін здачі</h3>
<p>Звіт завантажити у Moodle або надіслати викладачу на email до зазначеного дедлайну (вказано у розділі «Домашнє завдання»).</p>"""


# ─── Materials templates ──────────────────────────────────────────────────────
MATERIALS = {
    "Вища математика": (
        "Підручник: Кузьменко І.М. «Вища математика», відповідний розділ.\n"
        "Презентація до лекції у Microsoft Teams → Матеріали.\n"
        "https://www.wolframalpha.com — онлайн обчислення.\n"
        "https://brilliant.org/courses/calculus — відеорозбір тем.\n"
        "Таблиця інтегралів і похідних — роздруківка видана на парі."
    ),
    "Об'єктно-орієнтоване програмування": (
        "Лекційні слайди у Teams → ООП → Лекції.\n"
        "https://refactoring.guru/uk/design-patterns — патерни проектування.\n"
        "Документація Java: https://docs.oracle.com/javase/tutorial/\n"
        "Репозиторій з прикладами коду — GitHub Classroom (посилання в Teams).\n"
        "Відеолекція: https://www.youtube.com/playlist?list=PLtv_xO-rBbmGE5E4I_rOQlkLhClqkFoNf"
    ),
    "Бази даних": (
        "Слайди у Teams → БД → Лекції.\n"
        "Документація MySQL: https://dev.mysql.com/doc/\n"
        "Інтерактивний тренажер SQL: https://sqlbolt.com\n"
        "ERD-діаграми з лекції — Teams.\n"
        "Підручник: Ульман Дж. «Основи баз даних», відповідна глава."
    ),
    "Веб-технології": (
        "MDN Web Docs: https://developer.mozilla.org/uk/\n"
        "Слайди лекції — Moodle → Веб-технології.\n"
        "Документація React: https://react.dev/\n"
        "Документація Django: https://docs.djangoproject.com/uk/\n"
        "CSS Tricks: https://css-tricks.com\n"
        "Roadmap: https://roadmap.sh/frontend"
    ),
    "Алгоритми та структури даних": (
        "Підручник: Кормен Т. «Алгоритми: побудова і аналіз», відповідна глава.\n"
        "https://visualgo.net/uk — візуалізація алгоритмів.\n"
        "LeetCode: https://leetcode.com — задачі за темою.\n"
        "https://www.cs.usfca.edu/~galles/visualization/ — анімації структур даних.\n"
        "Слайди — Teams → АСД → Лекції."
    ),
    "Комп'ютерні мережі": (
        "Підручник: Таненбаум Е. «Комп'ютерні мережі», відповідна глава.\n"
        "Cisco Networking Academy: https://www.netacad.com\n"
        "Wireshark Tutorial: https://www.wireshark.org/docs/\n"
        "RFC-документи: https://www.rfc-editor.org\n"
        "Слайди — Teams → Мережі → Лекції."
    ),
    "Операційні системи": (
        "Підручник: Таненбаум Е. «Сучасні операційні системи», відповідна глава.\n"
        "Linux man-pages: https://man7.org/linux/man-pages/\n"
        "The Linux Command Line: https://linuxcommand.org/tlcl.php\n"
        "Слайди — Teams → ОС → Лекції.\n"
        "https://os.phil-opp.com — написання ОС на Rust (додатково)."
    ),
    "Програмування мовою Python": (
        "Документація Python: https://docs.python.org/uk/3/\n"
        "https://realpython.com — підручники та статті.\n"
        "Книга: Lutz M. «Learning Python», відповідна глава.\n"
        "https://www.codecademy.com/learn/learn-python-3 — інтерактивний курс.\n"
        "Код із пари — GitHub Classroom (посилання в Teams)."
    ),
    "Дискретна математика": (
        "Підручник: Яблонський С.В. «Дискретна математика», відповідна глава.\n"
        "Слайди — Teams → ДМ → Лекції.\n"
        "https://brilliant.org/courses/discrete-mathematics/\n"
        "https://www.wolframalpha.com — перевірка логічних виразів.\n"
        "Таблиця логічних еквівалентностей — видана на парі."
    ),
    "Безпека інформаційних систем": (
        "OWASP Top 10: https://owasp.org/Top10/\n"
        "PortSwigger Web Academy: https://portswigger.net/web-security\n"
        "Підручник: Stallings W. «Cryptography and Network Security», відповідна глава.\n"
        "CTFtime.org: https://ctftime.org — змагання з кібербезпеки.\n"
        "Слайди — Teams → Безпека → Лекції."
    ),
    "Штучний інтелект та МН": (
        "Курс fast.ai: https://www.fast.ai\n"
        "Документація TensorFlow: https://www.tensorflow.org/tutorials?hl=uk\n"
        "https://playground.tensorflow.org — інтерактивна нейронна мережа.\n"
        "Підручник: Goodfellow I. «Deep Learning», відповідна глава.\n"
        "Kaggle: https://www.kaggle.com — датасети та змагання."
    ),
    "Мобільна розробка": (
        "Документація Flutter: https://flutter.dev/docs\n"
        "Android Developers: https://developer.android.com/docs\n"
        "Apple Developer Docs: https://developer.apple.com/documentation/\n"
        "https://pub.dev — пакети для Flutter.\n"
        "Слайди — Teams → МР → Лекції."
    ),
    "Теорія ймовірностей та статистика": (
        "Підручник: Гмурман В.Є. «Теорія ймовірностей», відповідна глава.\n"
        "https://seeing-theory.brown.edu/uk.html — інтерактивний підручник.\n"
        "Відеокурс: StatQuest (youtube.com/c/joshstarmer).\n"
        "https://www.khanacademy.org/math/statistics-probability\n"
        "Таблиці розподілів — видані на парі."
    ),
    "Системне програмування": (
        "Книга: Stevens W.R. «Advanced Programming in the UNIX Environment».\n"
        "Документація POSIX: https://pubs.opengroup.org/onlinepubs/9699919799/\n"
        "GNU C Library: https://www.gnu.org/software/libc/manual/\n"
        "man-pages Linux: https://man7.org/linux/man-pages/\n"
        "Слайди — Teams → СП → Лекції."
    ),
}

DEFAULT_MATERIALS = (
    "Слайди лекції розміщені у Microsoft Teams → Матеріали.\n"
    "Конспект доступний у Moodle після авторизації.\n"
    "Додаткова literatura у бібліотеці кафедри (3 поверх, читальна зала).\n"
    "https://scholar.google.com — наукові статті за темою."
)

# ─── Homework templates ───────────────────────────────────────────────────────


def _hw_lecture(topic):
    options = [
        (
            f"1. Опрацювати конспект лекції з теми «{topic}». "
            "Повторити ключові визначення та формули.\n"
            "2. Прочитати відповідний розділ підручника (вказано у матеріалах).\n"
            "3. Виписати у зошит: 5 ключових термінів з визначеннями та 3 ключові формули/правила.\n"
            "4. Підготувати 2–3 запитання до наступного заняття за незрозумілими моментами."
        ),
        (
            f"1. Переглянути презентацію у Teams, доповнити конспект лекції «{topic}».\n"
            "2. Підготуватися до усного опитування на початку наступної пари "
            "(5 хвилин, 3–5 запитань за матеріалом лекції).\n"
            "3. Виконати завдання для самоперевірки зі слайдів (позначені зірочкою ★).\n"
            "4. Ознайомитися з додатковими матеріалами за посиланнями у розділі «Матеріали»."
        ),
        (
            f"1. Повторити матеріал попередніх тем, що пов'язані з «{topic}».\n"
            "2. Прочитати розділ підручника, виконати задачі/приклади зі слайдів.\n"
            "3. Скласти короткий план-конспект теми (1 сторінка А4) для підготовки до заліку.\n"
            "4. Підготуватися до тесту на наступному занятті."
        ),
    ]
    return random.choice(options)


def _hw_practical(topic):
    deadline = (date.today() + timedelta(days=random.choice([3, 5, 7]))).strftime(
        "%d.%m.%Y"
    )
    options = [
        (
            f"1. Доробити практичне завдання з пари за темою «{topic}» (якщо не завершено на занятті).\n"
            "2. Перевірити правильність розв'язання всіх задач, виправити помилки.\n"
            "3. Оформити розв'язання у зошиті або у файлі Word/PDF.\n"
            f"4. Здати на перевірку до {deadline} (кинути у відповідне завдання в Moodle або показати викладачу)."
        ),
        (
            f"1. Завершити практичну роботу за темою «{topic}».\n"
            "2. Випробувати всі варіанти вхідних даних, переконатися у коректності результатів.\n"
            "3. Записати висновки: що вдалося, що викликало труднощі.\n"
            f"4. Підготуватися до захисту — вміти пояснити кожен крок розв'язання. Дедлайн: {deadline}."
        ),
    ]
    return random.choice(options)


def _hw_lab(topic):
    deadline = (date.today() + timedelta(days=random.choice([5, 7, 10]))).strftime(
        "%d.%m.%Y"
    )
    options = [
        (
            f"1. Завершити виконання лабораторної роботи з теми «{topic}».\n"
            "2. Підготувати звіт за встановленим шаблоном (шаблон у Teams → Шаблони звітів).\n"
            "3. Звіт завантажити у Moodle або надіслати на email викладача до {deadline}.\n"
            "4. Підготуватися до захисту: знати відповіді на контрольні питання (перелік у конспекті)."
        ).format(deadline=deadline),
        (
            f"1. Дооформити лабораторну роботу «{topic}», перевірити відповідність вимогам.\n"
            "2. Переконатися, що звіт містить: мету, теоретичні відомості, хід роботи, результати, висновки.\n"
            "3. Підготувати демонстрацію виконаної роботи для захисту на наступному занятті.\n"
            f"4. Дедлайн здачі звіту: {deadline}."
        ),
    ]
    return random.choice(options)


# ─── Helper functions ─────────────────────────────────────────────────────────


def _get_materials(subject_name):
    return MATERIALS.get(subject_name, DEFAULT_MATERIALS)


def _get_homework(lesson_type, topic):
    if lesson_type == "lecture":
        return _hw_lecture(topic)
    elif lesson_type == "practical":
        return _hw_practical(topic)
    else:
        return _hw_lab(topic)


def _get_notes(lesson_type, topic, subject_name=""):
    if lesson_type == "lecture":
        return _make_lecture_html(topic, subject_name)
    elif lesson_type == "practical":
        return _make_practical_html(topic, subject_name)
    else:
        return _make_lab_html(topic, subject_name)


def _get_eval_type(ta, lesson_type):
    """Повертає EvaluationType за типом заняття.
    Лекція=50%, Лабораторна=30% non-HW, Практична=20% non-HW."""
    non_hw = list(
        ta.evaluation_types.filter(is_homework_type=False).order_by("-weight_percent")
    )
    if not non_hw:
        return None
    weight_map = {et.weight_percent: et for et in non_hw}
    from decimal import Decimal

    if lesson_type == "lecture":
        # Highest weight = Lecture (50%)
        return non_hw[0]
    elif lesson_type == "lab":
        # Look for 30% non-HW (Lab)
        et_30 = weight_map.get(Decimal("30.00"))
        return et_30 if et_30 else (non_hw[1] if len(non_hw) > 1 else non_hw[0])
    else:
        # Practical = lowest weight (20%)
        return non_hw[-1]


# ─── Main command ─────────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = (
        "Очищає оцінки, пропуски, розклад, матеріали уроків та заново "
        "заповнює дані з 2026-03-09 по 2026-04-09."
    )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("=" * 60))
        self.stdout.write(self.style.WARNING("  RESET AND SEED - Zephyra"))
        self.stdout.write(self.style.WARNING("=" * 60))

        self._clear_data()
        templates_info = self._create_templates()
        self._create_lessons(templates_info)
        self._create_grades()

        self.stdout.write(self.style.SUCCESS("\nGotovo! Dani uspishno perezapovneni."))

    # ── Step 1: clear ─────────────────────────────────────────────────────────

    def _clear_data(self):
        self.stdout.write("\n[1/4] Clearing data...")

        counts = {
            "PrivateComment": PrivateComment.objects.all().delete()[0],
            "SubmissionAttachment": SubmissionAttachment.objects.all().delete()[0],
            "HomeworkSubmission": HomeworkSubmission.objects.all().delete()[0],
            "StudentPerformance": StudentPerformance.objects.all().delete()[0],
            "LessonAttachment": LessonAttachment.objects.all().delete()[0],
            "Lesson": Lesson.objects.all().delete()[0],
            "ScheduleTemplate": ScheduleTemplate.objects.all().delete()[0],
        }

        for model, cnt in counts.items():
            if cnt:
                self.stdout.write(f"  Deleted {model}: {cnt}")

        self.stdout.write(self.style.SUCCESS("  OK: Cleared"))

    # ── Step 2: schedule templates ────────────────────────────────────────────

    def _create_templates(self):
        """Створює ScheduleTemplate для кожної групи.
        Повертає dict: group_id -> list[(template, ta, subject_slot_idx)]."""
        self.stdout.write("\n[2/4] Creating schedule templates...")

        classrooms = list(Classroom.objects.filter(is_active=True))
        templates_info = {}  # group_id -> [(template, ta)]

        for group in StudyGroup.objects.filter(is_active=True).order_by("name"):
            tas = list(
                TeachingAssignment.objects.filter(group=group, is_active=True)
                .select_related("subject", "teacher")
                .order_by("id")
            )
            if not tas:
                self.stdout.write(f"  Skipping {group.name} (no TeachingAssignment)")
                continue

            n = len(tas)
            group_templates = []

            for day, lesson_num, subj_idx in SCHEDULE_SLOTS:
                ta = tas[subj_idx % n]
                classroom = random.choice(classrooms) if classrooms else None
                start_t, end_t = TIME_MAP[lesson_num]
                duration = (
                    end_t.hour * 60 + end_t.minute - start_t.hour * 60 - start_t.minute
                )

                try:
                    tmpl = ScheduleTemplate.objects.create(
                        group=group,
                        subject=ta.subject,
                        teacher=ta.teacher,
                        teaching_assignment=ta,
                        day_of_week=day,
                        lesson_number=lesson_num,
                        start_time=start_t,
                        duration_minutes=duration,
                        classroom=classroom,
                        is_active=True,
                    )
                    group_templates.append((tmpl, ta))
                except Exception as exc:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  Template error {group.name} day={day} "
                            f"lesson={lesson_num}: {exc}"
                        )
                    )

            templates_info[group.id] = group_templates
            self.stdout.write(
                f"  {group.name}: {len(group_templates)} templates " f"({n} subjects)"
            )

        self.stdout.write(self.style.SUCCESS("  OK: Templates created"))
        return templates_info

    # ── Step 3: lessons ───────────────────────────────────────────────────────

    def _create_lessons(self, templates_info):
        """Генерує уроки з START_DATE по END_DATE на основі шаблонів."""
        self.stdout.write("\n[3/4] Creating lessons...")

        # topic_counters[(group_id, subj_id)] = next topic index
        topic_counters = {}
        # type_counters[(group_id, subj_id)] = next lesson type index
        type_counters = {}

        lessons_to_create = []

        current = START_DATE
        while current <= END_DATE:
            dow = current.isoweekday()  # 1=Пн … 7=Нд
            if dow <= 5:  # тільки будні
                for group_id, group_templates in templates_info.items():
                    for tmpl, ta in group_templates:
                        if tmpl.day_of_week != dow:
                            continue

                        subj_id = ta.subject.id
                        key = (group_id, subj_id)

                        # Topic (sequential)
                        topic_list = TOPICS.get(ta.subject.name, DEFAULT_TOPICS)
                        t_idx = topic_counters.get(key, 0)
                        topic = topic_list[t_idx % len(topic_list)]
                        topic_counters[key] = t_idx + 1

                        # Lesson type (cycles: lecture→practical→lab→lecture…)
                        l_idx = type_counters.get(key, 0)
                        lesson_type = LESSON_TYPE_CYCLE[l_idx % len(LESSON_TYPE_CYCLE)]
                        type_counters[key] = l_idx + 1

                        eval_type = _get_eval_type(ta, lesson_type)
                        start_t, end_t = TIME_MAP[tmpl.lesson_number]
                        subj_name = ta.subject.name

                        lessons_to_create.append(
                            Lesson(
                                group=tmpl.group,
                                subject=ta.subject,
                                teacher=ta.teacher,
                                date=current,
                                start_time=start_t,
                                end_time=end_t,
                                topic=topic,
                                classroom=tmpl.classroom,
                                max_points=12,
                                evaluation_type=eval_type,
                                template_source=tmpl,
                                notes=_get_notes(lesson_type, topic, subj_name),
                                homework=_get_homework(lesson_type, topic),
                                materials=_get_materials(subj_name),
                            )
                        )

            current += timedelta(days=1)

        # Bulk insert (skip conflicts — shouldn't happen, but just in case)
        created = Lesson.objects.bulk_create(lessons_to_create, ignore_conflicts=True)
        self.stdout.write(
            f"  Created {len(created)} lessons ({START_DATE} to {END_DATE})"
        )
        self.stdout.write(self.style.SUCCESS("  OK: Lessons created"))

    # ── Step 4: grades + absences ─────────────────────────────────────────────

    def _create_grades(self):
        """Виставляє оцінки та пропуски для уроків до GRADES_CUTOFF."""
        self.stdout.write(
            f"\n[4/4] Creating grades + absences (up to {GRADES_CUTOFF})..."
        )

        lessons = list(
            Lesson.objects.filter(
                date__gte=START_DATE,
                date__lte=GRADES_CUTOFF,
            ).select_related("group", "subject")
        )

        absence_reasons = list(AbsenceReason.objects.filter(is_active=True))
        # Weights for realistic grade distribution (1..12)
        # Mostly 7-12, few low scores
        grade_weights = [1, 1, 2, 3, 4, 5, 8, 10, 12, 12, 10, 8]

        perf_to_create = []
        total_absent = 0

        for lesson in lessons:
            students = list(
                User.objects.filter(
                    group=lesson.group,
                    role="student",
                    is_active=True,
                )
            )
            for student in students:
                if random.random() < 0.10 and absence_reasons:
                    # 10% chance of absence
                    absence = random.choice(absence_reasons)
                    perf_to_create.append(
                        StudentPerformance(
                            lesson=lesson,
                            student=student,
                            absence=absence,
                            earned_points=None,
                        )
                    )
                    total_absent += 1
                else:
                    pts = random.choices(range(1, 13), weights=grade_weights)[0]
                    perf_to_create.append(
                        StudentPerformance(
                            lesson=lesson,
                            student=student,
                            absence=None,
                            earned_points=pts,
                        )
                    )

        StudentPerformance.objects.bulk_create(perf_to_create, ignore_conflicts=True)

        self.stdout.write(
            f"  Performance records: {len(perf_to_create)} "
            f"(absences: {total_absent})"
        )
        self.stdout.write(self.style.SUCCESS("  OK: Grades and absences filled"))

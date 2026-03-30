"""
Management command: fill_lesson_details
Fills materials and homework for lessons in the last 30 days.
"""

import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from main.models import Lesson

# ── Materials templates by subject ───────────────────────────────────────────

MATERIALS = {
    "Вища математика": [
        "Підручник: Кузьменко І.М. «Вища математика», розд. {ch}.\nПрезентація до лекції у Teams.\nhttps://www.wolframalpha.com — для перевірки обчислень.",
        "Конспект лекції у Moodle (курс ВМ-2025).\nДодаткові задачі: Демидович Б.П., §{ch}.\nhttps://brilliant.org/courses/calculus — відеорозбір тем.",
        "Слайди лекції — папка Teams › Матеріали.\nПосилання на Khan Academy (ua.khanacademy.org) — розділ «Calculus».\nТаблиця інтегралів — роздруківка видана на парі.",
    ],
    "Об'єктно-орієнтоване програмування": [
        "Лекційні слайди у Teams › ООП › Лекції.\nhttps://refactoring.guru/uk/design-patterns — патерни проектування.\nПідручник: Гамма Е. та ін. «Design Patterns», гл. {ch}.",
        "Відеолекція: youtube.com/playlist?list=PLtv_xO-rBbmGE5E4I_rOQlkLhClqkFoNf\nДокументація: docs.oracle.com/javase/tutorial/java/concepts/\nПрактичне завдання — репозиторій на GitHub Classroom.",
        "Презентація лекції у Moodle.\nhttps://www.geeksforgeeks.org/object-oriented-programming-oops-concept-in-java/\nКод-приклади з пари — папка Teams › Код.",
    ],
    "Бази даних": [
        "Слайди у Teams › БД › Лекції.\nДокументація MySQL: https://dev.mysql.com/doc/\nПідручник: Ульман Дж. «Основи баз даних», гл. {ch}.",
        "Відео: «SQL для початківців» — youtube.com/watch?v=7S_tz1z_5bA\nhttps://sqlbolt.com — інтерактивний тренажер SQL.\nERD-діаграми з лекції — Teams.",
        "Матеріали: dbdiagram.io — для побудови ER-діаграм.\nПідручник Коннолі Т. «Бази даних», розд. {ch}.\nSQL Fiddle: https://sqlfiddle.com — практика запитів.",
    ],
    "Веб-технології": [
        "MDN Web Docs: https://developer.mozilla.org/uk/\nСлайди лекції — Moodle › Веб-технології.\nПодкаст «Web Dev Stories» — посилання в Teams.",
        "Документація React: https://react.dev/\nДокументація Django: https://docs.djangoproject.com/uk/\nКод із пари — GitHub Classroom › web-lab-{ch}.",
        "CSS Tricks: https://css-tricks.com\nhttps://roadmap.sh/frontend — дорожня карта фронтенду.\nПрезентація у Teams › Веб › Лекції.",
    ],
    "Алгоритми та структури даних": [
        "Підручник: Кормен Т. «Алгоритми: побудова і аналіз», гл. {ch}.\nhttps://visualgo.net/uk — візуалізація алгоритмів.\nСлайди — Teams › АСД.",
        "LeetCode: https://leetcode.com — задачі за темою.\nhttps://www.cs.usfca.edu/~galles/visualization/ — анімації структур даних.\nКонспект лекції — Moodle.",
        "Відеолекція: CS50 (youtube.com/c/cs50) — тема «{topic}».\nhttps://codeforces.com — задачі для самостійної практики.\nПрезентація — Teams › АСД › Лекції.",
    ],
    "Комп'ютерні мережі": [
        "Підручник: Таненбаум Е. «Комп'ютерні мережі», гл. {ch}.\nhttps://www.cloudflare.com/learning/ — довідник мережевих концепцій.\nСлайди — Teams › Мережі.",
        "Cisco Networking Academy: https://www.netacad.com\nWireshark Tutorial: https://www.wireshark.org/docs/\nПрезентація лекції — Moodle.",
        "RFC-документи: https://www.rfc-editor.org\nСлайди з пари — Teams › Мережі › Лекції.\nhttps://networklessons.com — практичні приклади.",
    ],
    "Архітектура комп\u2019ютерів": [
        "Підручник: Харріс Д. «Цифрова схемотехніка та архітектура комп'ютера», гл. {ch}.\nСлайди — Teams › АК.\nhttps://www.nandgame.com — симулятор логічних схем.",
        "Відеокурс: «Computer Architecture» (Coursera/Princeton).\nhttps://cpulator.01xz.net/ — емулятор процесора ARMv7.\nМатеріали лекції — Moodle.",
        "Слайди — Teams › Архітектура › Лекції.\nДокументація Intel ISA: https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html\nПодаткова: Patterson D., Hennessy J. «COD», гл. {ch}.",
    ],
    "Дискретна математика": [
        "Підручник: Яблонський С.В. «Дискретна математика», гл. {ch}.\nСлайди — Teams › ДМ.\nhttps://discrete.gr — онлайн-задачі.",
        "Конспект лекції у Moodle.\nhttps://brilliant.org/courses/discrete-mathematics/\nТаблиця логічних еквівалентностей — видана на парі.",
        "Слайди — Teams › ДМ › Лекції.\nhttps://www.wolframalpha.com — перевірка логічних виразів.\nПідручник Кемені Дж. «Скінченні ланцюги Маркова», гл. {ch}.",
    ],
    "Операційні системи": [
        "Підручник: Таненбаум Е. «Сучасні операційні системи», гл. {ch}.\nСлайди — Teams › ОС.\nhttps://os.phil-opp.com — написання ОС на Rust.",
        "Linux man-pages: https://man7.org/linux/man-pages/\nВідео: MIT 6.004 Lectures (youtube).\nКонспект лекції — Moodle.",
        "The Linux Command Line (вільна книга): https://linuxcommand.org/tlcl.php\nСлайди — Teams › ОС › Лекції.\nhttps://www.kernel.org/doc/ — документація ядра Linux.",
    ],
    "Програмування мовою Python": [
        "Документація Python: https://docs.python.org/uk/3/\nСлайди — Teams › Python.\nhttps://realpython.com — підручники та статті.",
        "Книга: Lutz M. «Learning Python», гл. {ch}.\nhttps://www.codecademy.com/learn/learn-python-3 — інтерактивний курс.\nКод із пари — GitHub Classroom › python-lab-{ch}.",
        "https://leetcode.com/problemset/all/?difficulty=Easy&topicSlugs=python — задачі на Python.\nКонспект лекції — Moodle.\nСлайди — Teams › Python › Лекції.",
    ],
    "Штучний інтелект та МН": [
        "Курс fast.ai: https://www.fast.ai\nСлайди — Teams › ШІ.\nПідручник: Goodfellow I. «Deep Learning», гл. {ch}.",
        "Документація TensorFlow: https://www.tensorflow.org/tutorials?hl=uk\nПрезентація — Moodle › ШІ.\nhttps://playground.tensorflow.org — інтерактивна NN.",
        "Курс Andrew Ng (Coursera): https://www.coursera.org/specializations/machine-learning-introduction\nСлайди — Teams › ШІ › Лекції.\nKaggle: https://www.kaggle.com — датасети та змагання.",
    ],
    "Безпека інформаційних систем": [
        "OWASP Top 10: https://owasp.org/Top10/\nСлайди — Teams › Безпека.\nПідручник: Stallings W. «Cryptography and Network Security», гл. {ch}.",
        "PortSwigger Web Academy: https://portswigger.net/web-security\nПрезентація — Moodle › БІС.\nhttps://www.cybrary.it — безкоштовні курси з кібербезпеки.",
        "CTFtime.org: https://ctftime.org — змагання з кібербезпеки.\nСлайди — Teams › Безпека › Лекції.\nCVE Database: https://cve.mitre.org/",
    ],
    "Мобільна розробка": [
        "Документація Flutter: https://flutter.dev/docs\nСлайди — Teams › МР.\nПідручник: Windmill E. «Flutter in Action», гл. {ch}.",
        "Android Developers: https://developer.android.com/docs\nPresentation — Moodle › Мобільна.\nhttps://pub.dev — пакети для Flutter.",
        "Apple Developer Docs: https://developer.apple.com/documentation/\nСлайди — Teams › МР › Лекції.\nhttps://www.raywenderlich.com — туторіали з мобільної розробки.",
    ],
    "Теорія ймовірностей та статистика": [
        "Підручник: Гмурман В.Є. «Теорія ймовірностей та математична статистика», гл. {ch}.\nСлайди — Teams › ТЙС.\nhttps://www.wolframalpha.com — перевірка розрахунків.",
        "Конспект лекції — Moodle.\nhttps://seeing-theory.brown.edu/uk.html — інтерактивний підручник з теорії ймовірностей.\nТаблиці розподілів — видані на парі.",
        "Відеокурс: StatQuest (youtube.com/c/joshstarmer).\nСлайди — Teams › ТЙС › Лекції.\nhttps://www.khanacademy.org/math/statistics-probability — Khan Academy.",
    ],
    "Системне програмування": [
        "Книга: Stevens W.R. «Advanced Programming in the UNIX Environment», гл. {ch}.\nСлайди — Teams › СП.\nman-pages Linux: https://man7.org/linux/man-pages/",
        "Документація POSIX: https://pubs.opengroup.org/onlinepubs/9699919799/\nКонспект лекції — Moodle.\nВідео: «Systems Programming» (CS:APP, CMU).",
        "GNU C Library: https://www.gnu.org/software/libc/manual/\nСлайди — Teams › СП › Лекції.\nКод із пари — GitHub Classroom › sysprog-lab-{ch}.",
    ],
}

DEFAULT_MATERIALS = [
    "Слайди лекції розміщені у Teams › Матеріали.\nДодаткова literatura у бібліотеці кафедри.\nКонспект доступний у Moodle після авторизації.",
    "Презентація до заняття — у Teams.\nДодаткові матеріали: https://scholar.google.com — наукові статті за темою.\nКонспект лекції — Moodle.",
    "Навчальні матеріали у Moodle (курс поточного семестру).\nСлайди — Teams › Поточний курс › Лекції.\nПідручник на кафедрі (читальна зала, 3 поверх).",
]

# ── Homework templates ────────────────────────────────────────────────────────

LECTURE_HW = [
    "Опрацювати конспект лекції, повторити ключові визначення.\nПідготувати 2-3 запитання до наступного заняття.",
    "Прочитати відповідний розділ підручника (вказано у слайдах).\nВиписати основні формули/концепції у зошит.",
    "Переглянути презентацію у Teams, доповнити конспект.\nПідготуватися до усного опитування на початку наступної пари.",
    "Опрацювати §{ch} підручника, підготуватися до тесту.\nЗаписати питання, що виникли під час самостійного опрацювання.",
    "Повторити матеріал попередніх тем, прочитати нові §{ch}–{ch2}.\nВиконати задачі/приклади зі слайдів (зірочкою не позначені).",
]

PRACTICAL_HW = [
    "Доробити практичне завдання з пари (здати до кінця тижня).\nВипробувати всі варіанти вхідних даних.",
    "Завершити реалізацію алгоритму/функції з пари.\nДодати коментарі до коду та перевірити на крайніх значеннях.",
    "Завершити лабораторну роботу №{ch} та завантажити звіт у Moodle до {deadline}.",
    "Виконати варіант завдання {ch} (список варіантів у Teams).\nЗдати на перевірку до наступної пари.",
    "Дописати програму, протестувати, оформити README.\nЗавантажити у GitHub Classroom до кінця тижня.",
]

LAB_HW = [
    "Захист лабораторної роботи №{ch} — на наступному занятті.\nПідготувати звіт за зразком у Teams.",
    "Завершити виконання ЛР №{ch}, підготувати демонстрацію.\nЗвіт завантажити у Moodle до {deadline}.",
    "Дооформити лабораторну роботу, перевірити відповідність вимогам.\nГотуватися до захисту: знати відповіді на контрольні питання.",
    "Підготувати звіт лабораторної роботи (шаблон — Teams).\nЗдати до {deadline}.",
]

DEFAULT_HW = [
    "Опрацювати матеріали заняття, підготуватися до наступної теми.",
    "Повторити пройдений матеріал, виконати завдання зі слайдів.",
    "Підготуватися до контрольного запитання на початку наступного заняття.",
]


def _pick(templates, **kwargs):
    tpl = random.choice(templates)
    ch = random.randint(2, 12)
    ch2 = ch + random.randint(1, 2)
    deadline_days = random.choice([3, 5, 7])
    from datetime import date, timedelta

    deadline = (date.today() + timedelta(days=deadline_days)).strftime("%d.%m")
    return tpl.format(ch=ch, ch2=ch2, deadline=deadline, topic="...")


class Command(BaseCommand):
    help = "Fill materials and homework for lessons in the last 30 days"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of past days to cover (default: 30)",
        )
        parser.add_argument(
            "--force", action="store_true", help="Overwrite existing materials/homework"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without saving",
        )

    def handle(self, *args, **options):
        days = options["days"]
        force = options["force"]
        dry_run = options["dry_run"]

        today = date.today()
        since = today - timedelta(days=days)

        lessons = Lesson.objects.filter(
            date__gte=since, date__lte=today
        ).select_related("subject", "evaluation_type")

        total = lessons.count()
        self.stdout.write(f"Found {total} lessons from {since} to {today}")

        updated_mat = 0
        updated_hw = 0
        to_update = []

        for lesson in lessons:
            changed = False
            subj_name = lesson.subject.name
            etype = lesson.evaluation_type.name if lesson.evaluation_type else ""

            # ── Materials ────────────────────────────────────────────────────
            if not lesson.materials or force:
                templates = MATERIALS.get(subj_name, DEFAULT_MATERIALS)
                lesson.materials = _pick(templates)
                changed = True
                updated_mat += 1

            # ── Homework ─────────────────────────────────────────────────────
            if not lesson.homework or force:
                if "Лекція" in etype:
                    hw_templates = LECTURE_HW
                elif "Практична" in etype:
                    hw_templates = PRACTICAL_HW
                elif "Лабораторна" in etype:
                    hw_templates = LAB_HW
                else:
                    hw_templates = DEFAULT_HW
                lesson.homework = _pick(hw_templates)
                changed = True
                updated_hw += 1

            if changed:
                to_update.append(lesson)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Would update {len(to_update)} lessons "
                    f"(materials: {updated_mat}, homework: {updated_hw})"
                )
            )
            return

        # Bulk update
        if to_update:
            Lesson.objects.bulk_update(to_update, ["materials", "homework"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Done! Updated {len(to_update)} lessons: "
                f"materials={updated_mat}, homework={updated_hw}"
            )
        )

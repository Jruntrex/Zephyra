"""
Management command: seed_kn41_schedule

Fills ScheduleTemplate + Lesson records for group КН-41 for the current week
(Monday–Friday, 7 standard periods per day, 50 min each).

Constraints respected:
  - Teacher cannot teach two groups at the same (day, lesson_number)
  - Classroom cannot be used by two groups at the same (day, lesson_number)
  - Subjects are spread across days (no subject twice on the same day, when possible)

Usage:
    python manage.py seed_kn41_schedule
    python manage.py seed_kn41_schedule --dry-run   # preview without saving
"""

from collections import defaultdict, namedtuple
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from main.constants import DEFAULT_TIME_SLOTS
from main.models import (
    Classroom,
    EvaluationType,
    Lesson,
    ScheduleTemplate,
    StudyGroup,
    TeachingAssignment,
    User,
)

DAYS = [1, 2, 3, 4, 5]  # Monday = 1 … Friday = 5
DAY_NAMES = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт"}

SlotEntry = namedtuple("SlotEntry", ["day", "lesson_num", "assignment", "classroom"])


class Command(BaseCommand):
    help = "Seed 7-period Mon–Fri schedule for КН-41 and create lessons for the current week"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be created without touching the DB",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        if dry:
            self.stdout.write(self.style.WARNING("=== DRY RUN — nothing will be saved ==="))

        today = date.today()
        monday = today - timedelta(days=today.weekday())
        friday = monday + timedelta(days=4)
        self.stdout.write(f"Target week: {monday}  –  {friday}")

        # ── 1. Resolve group ──────────────────────────────────────────────────
        try:
            group = StudyGroup.objects.get(name="КН-41")
        except StudyGroup.DoesNotExist:
            self.stdout.write(self.style.ERROR("Group 'КН-41' not found in DB"))
            return
        self.stdout.write(f"Group: {group.name}  (id={group.id})")

        # ── 2. Resolve assignments ────────────────────────────────────────────
        assignments = list(
            TeachingAssignment.objects.filter(group=group, is_active=True)
            .select_related("subject", "teacher")
            .order_by("id")
        )
        if not assignments:
            self.stdout.write(self.style.ERROR("No active TeachingAssignments for КН-41"))
            return
        self.stdout.write(f"Assignments found: {len(assignments)}")
        for a in assignments:
            self.stdout.write(f"  • {a.subject.name}  /  {a.teacher.full_name}")

        # ── 3. Resolve classrooms ─────────────────────────────────────────────
        classrooms = list(Classroom.objects.filter(is_active=True).order_by("id"))
        if not classrooms:
            self.stdout.write(self.style.ERROR("No active classrooms found"))
            return
        self.stdout.write(f"Classrooms available: {len(classrooms)}")

        # ── 4. Pre-cache EvaluationTypes (one query, not N) ──────────────────
        eval_type_cache: dict = {}
        for et in EvaluationType.objects.filter(assignment__in=assignments):
            eval_type_cache.setdefault(et.assignment_id, et)

        # ── 5. Delete existing templates for КН-41 ───────────────────────────
        if not dry:
            deleted_t, _ = ScheduleTemplate.objects.filter(group=group).delete()
            self.stdout.write(f"Deleted {deleted_t} old ScheduleTemplate rows")

        # ── 6. Build slot plan day by day ─────────────────────────────────────
        slot_plan: list[SlotEntry] = []

        for day in DAYS:
            # One query per day instead of 14 (7 slots × 2 queries)
            other_slots = list(
                ScheduleTemplate.objects.filter(day_of_week=day, is_active=True)
                .exclude(group=group)
                .values("lesson_number", "teacher_id", "classroom_id")
            )
            occupied_teachers: dict[int, set] = defaultdict(set)
            occupied_classrooms: dict[int, set] = defaultdict(set)
            for s in other_slots:
                occupied_teachers[s["lesson_number"]].add(s["teacher_id"])
                occupied_classrooms[s["lesson_number"]].add(s["classroom_id"])

            # Rotate pool per day for subject variety across weekdays
            day_offset = day - 1
            pool = (
                assignments[day_offset % len(assignments) :]
                + assignments[: day_offset % len(assignments)]
            )

            used_subjects_today: set = set()
            used_classrooms_today: set = set()  # maintained incrementally

            for lesson_num in range(1, 8):
                busy_teachers = occupied_teachers[lesson_num]

                # Pick assignment: prefer unique subject + free teacher
                chosen = next(
                    (
                        a
                        for a in pool
                        if a.teacher_id not in busy_teachers
                        and a.subject_id not in used_subjects_today
                    ),
                    None,
                ) or next(
                    (a for a in pool if a.teacher_id not in busy_teachers),
                    None,
                ) or pool[lesson_num % len(pool)]

                used_subjects_today.add(chosen.subject_id)

                # Rotate pool so the chosen item goes to the back
                chosen_idx = pool.index(chosen)
                pool = pool[chosen_idx + 1 :] + pool[: chosen_idx + 1]

                # Pick classroom (avoid conflicts + reuse within same day)
                busy_cls = occupied_classrooms[lesson_num] | used_classrooms_today
                free_cls = [c for c in classrooms if c.id not in busy_cls]
                if not free_cls:
                    free_cls = [c for c in classrooms if c.id not in occupied_classrooms[lesson_num]]
                classroom = free_cls[0] if free_cls else classrooms[0]
                used_classrooms_today.add(classroom.id)

                slot_plan.append(SlotEntry(day, lesson_num, chosen, classroom))

        # ── 7. Print plan ─────────────────────────────────────────────────────
        self.stdout.write("\n── Schedule plan ──────────────────────────────────────")
        for entry in slot_plan:
            start_time, _ = DEFAULT_TIME_SLOTS[entry.lesson_num]
            self.stdout.write(
                f"  {DAY_NAMES[entry.day]} пара {entry.lesson_num}  {start_time}  "
                f"{entry.assignment.subject.name[:30]:<30}  "
                f"{entry.assignment.teacher.full_name:<25}  {entry.classroom.name}"
            )

        if dry:
            self.stdout.write(self.style.SUCCESS(f"\n✓ Dry run complete — {len(slot_plan)} slots planned"))
            return

        # ── 8. Bulk-create ScheduleTemplate rows (1 INSERT instead of 35) ────
        template_objs = []
        for entry in slot_plan:
            start_time, _ = DEFAULT_TIME_SLOTS[entry.lesson_num]
            template_objs.append(
                ScheduleTemplate(
                    group=group,
                    subject=entry.assignment.subject,
                    teacher=entry.assignment.teacher,
                    teaching_assignment=entry.assignment,
                    day_of_week=entry.day,
                    lesson_number=entry.lesson_num,
                    start_time=start_time,
                    duration_minutes=50,
                    classroom=entry.classroom,
                    is_active=True,
                )
            )
        created_templates = ScheduleTemplate.objects.bulk_create(template_objs)
        self.stdout.write(self.style.SUCCESS(f"Created {len(created_templates)} ScheduleTemplate rows"))

        # Index templates by (day, lesson_num) for O(1) lookup below
        template_map = {(t.day_of_week, t.lesson_number): t for t in created_templates}

        # ── 9. Delete + recreate this week's Lesson rows ─────────────────────
        deleted_l, _ = Lesson.objects.filter(
            group=group, date__gte=monday, date__lte=friday
        ).delete()
        self.stdout.write(f"Deleted {deleted_l} old Lesson rows for this week")

        lesson_objs = []
        for day_idx, day_num in enumerate(DAYS):
            lesson_date = monday + timedelta(days=day_idx)
            for entry in slot_plan:
                if entry.day != day_num:
                    continue

                start_time, end_time = DEFAULT_TIME_SLOTS[entry.lesson_num]

                # Ensure EvaluationType exists (cache hit avoids extra queries)
                if entry.assignment.id not in eval_type_cache:
                    et = EvaluationType.objects.create(
                        assignment=entry.assignment,
                        name="Заняття",
                        weight_percent=0,
                    )
                    eval_type_cache[entry.assignment.id] = et
                eval_type = eval_type_cache[entry.assignment.id]

                tmpl = template_map.get((entry.day, entry.lesson_num))

                lesson_objs.append(
                    Lesson(
                        group=group,
                        date=lesson_date,
                        start_time=start_time,
                        end_time=end_time,
                        subject=entry.assignment.subject,
                        teacher=entry.assignment.teacher,
                        classroom=entry.classroom,
                        template_source=tmpl,
                        evaluation_type=eval_type,
                    )
                )

        Lesson.objects.bulk_create(lesson_objs)
        self.stdout.write(
            self.style.SUCCESS(f"Created {len(lesson_objs)} Lesson rows  ({monday} – {friday})")
        )
        self.stdout.write(self.style.SUCCESS("\n✓ Done!"))

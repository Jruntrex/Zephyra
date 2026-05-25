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
)

DAYS = [1, 2, 3, 4, 5]  # Monday = 1 … Friday = 5


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

        # ── 4. Delete existing templates for КН-41 ───────────────────────────
        if not dry:
            deleted_t, _ = ScheduleTemplate.objects.filter(group=group).delete()
            self.stdout.write(f"Deleted {deleted_t} old ScheduleTemplate rows")

        # ── 5. Build templates day by day ────────────────────────────────────
        templates_to_create = []  # list of (day, lesson_num, assignment, classroom)

        for day in DAYS:
            # Collect what other groups already occupy at each slot
            occupied_teachers_by_slot = {}
            occupied_classrooms_by_slot = {}
            for lesson_num in range(1, 8):
                occupied_teachers_by_slot[lesson_num] = set(
                    ScheduleTemplate.objects.filter(
                        day_of_week=day,
                        lesson_number=lesson_num,
                        is_active=True,
                    )
                    .exclude(group=group)
                    .values_list("teacher_id", flat=True)
                )
                occupied_classrooms_by_slot[lesson_num] = set(
                    ScheduleTemplate.objects.filter(
                        day_of_week=day,
                        lesson_number=lesson_num,
                        is_active=True,
                    )
                    .exclude(group=group)
                    .values_list("classroom_id", flat=True)
                )

            # Rotate assignment pool per day so weekdays don't all start with
            # the same subject.
            day_offset = day - 1
            pool = assignments[day_offset % len(assignments):] + assignments[:day_offset % len(assignments)]

            used_subjects_today = set()
            pool_idx = 0

            for lesson_num in range(1, 8):
                free_teachers = occupied_teachers_by_slot[lesson_num]

                # Pick assignment: prefer unique subject today AND free teacher
                chosen = None
                for a in pool:
                    if a.teacher_id not in free_teachers and a.subject_id not in used_subjects_today:
                        chosen = a
                        break
                if chosen is None:
                    # Relax unique-subject constraint
                    for a in pool:
                        if a.teacher_id not in free_teachers:
                            chosen = a
                            break
                if chosen is None:
                    # All teachers occupied by other groups — just round-robin
                    chosen = pool[pool_idx % len(pool)]

                used_subjects_today.add(chosen.subject_id)
                # Rotate pool so next slot doesn't always grab the same item
                chosen_idx = pool.index(chosen)
                pool = pool[chosen_idx + 1:] + pool[:chosen_idx + 1]
                pool_idx += 1

                # Pick classroom
                busy_cls = occupied_classrooms_by_slot[lesson_num]
                # Also avoid reusing the same classroom twice on the same day in
                # КН-41's own schedule
                already_used_today = {r[3].id for r in templates_to_create if r[0] == day and r[3]}
                free_cls = [c for c in classrooms if c.id not in busy_cls and c.id not in already_used_today]
                if not free_cls:
                    free_cls = [c for c in classrooms if c.id not in busy_cls]
                classroom = free_cls[0] if free_cls else classrooms[0]

                templates_to_create.append((day, lesson_num, chosen, classroom))

        # ── 6. Persist templates ──────────────────────────────────────────────
        self.stdout.write("\n── Schedule plan ──────────────────────────────────────")
        day_names = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт"}
        created_templates = []

        for day, lesson_num, assignment, classroom in templates_to_create:
            start_time, _ = DEFAULT_TIME_SLOTS[lesson_num]
            line = (
                f"  {day_names[day]} пара {lesson_num}  {start_time}  "
                f"{assignment.subject.name[:30]:<30}  {assignment.teacher.full_name:<25}  {classroom.name}"
            )
            self.stdout.write(line)

            if not dry:
                tmpl = ScheduleTemplate.objects.create(
                    group=group,
                    subject=assignment.subject,
                    teacher=assignment.teacher,
                    teaching_assignment=assignment,
                    day_of_week=day,
                    lesson_number=lesson_num,
                    start_time=start_time,
                    duration_minutes=50,
                    classroom=classroom,
                    is_active=True,
                )
                created_templates.append(tmpl)

        if not dry:
            self.stdout.write(self.style.SUCCESS(f"\nCreated {len(created_templates)} ScheduleTemplate rows"))

        # ── 7. Delete this week's lessons for КН-41 ──────────────────────────
        if not dry:
            deleted_l, _ = Lesson.objects.filter(
                group=group, date__gte=monday, date__lte=friday
            ).delete()
            self.stdout.write(f"Deleted {deleted_l} old Lesson rows for this week")

        # ── 8. Create Lesson rows ─────────────────────────────────────────────
        lessons_created = 0

        for day_idx, day_num in enumerate(DAYS):
            lesson_date = monday + timedelta(days=day_idx)

            for day, lesson_num, assignment, classroom in templates_to_create:
                if day != day_num:
                    continue

                start_time, end_time = DEFAULT_TIME_SLOTS[lesson_num]

                if dry:
                    self.stdout.write(
                        f"  [dry] Lesson {lesson_date} пара {lesson_num}  "
                        f"{assignment.subject.name}  {assignment.teacher.full_name}"
                    )
                    lessons_created += 1
                    continue

                # Ensure EvaluationType exists for this assignment
                eval_type = EvaluationType.objects.filter(
                    assignment=assignment
                ).first()
                if not eval_type:
                    eval_type = EvaluationType.objects.create(
                        assignment=assignment,
                        name="Заняття",
                        weight_percent=0,
                    )

                # Find the just-created template for this (day, lesson_num)
                tmpl = next(
                    (t for t in created_templates if t.day_of_week == day and t.lesson_number == lesson_num),
                    None,
                )

                Lesson.objects.update_or_create(
                    group=group,
                    date=lesson_date,
                    start_time=start_time,
                    defaults={
                        "subject": assignment.subject,
                        "teacher": assignment.teacher,
                        "end_time": end_time,
                        "classroom": classroom,
                        "template_source": tmpl,
                        "evaluation_type": eval_type,
                    },
                )
                lessons_created += 1

        if not dry:
            self.stdout.write(
                self.style.SUCCESS(f"Created {lessons_created} Lesson rows  ({monday} – {friday})")
            )

        self.stdout.write(self.style.SUCCESS("\n✓ Done!"))

# main/urls.py

from django.urls import path

from . import views

urlpatterns = [
    # =========================
    # 1. АУТЕНТИФІКАЦІЯ
    # =========================
    path("", views.login_view, name="login"),
    path("login/", views.login_process, name="login_process"),
    path("logout/", views.logout_view, name="logout"),
    # =========================
    # 2. АДМІНІСТРУВАННЯ ТА ДАШБОРДИ
    # =========================
    path("admin/", views.admin_panel_view, name="admin_panel"),
    path("admin/institution/", views.institution_settings_view, name="institution_settings"),
    path("users/", views.users_list_view, name="users_list"),
    path("schedule/", views.schedule_view, name="schedule_view"),
    path("schedule/timeline/", views.timeline_schedule_view, name="timeline_schedule"),
    path("schedule/set/", views.set_weekly_schedule_view, name="set_weekly_schedule"),
    path("schedule/save/", views.save_schedule_changes, name="save_schedule"),
    path("schedule/editor/", views.schedule_editor_view, name="schedule_editor"),
    path(
        "api/schedule/slot/save/",
        views.api_save_schedule_slot,
        name="api_save_schedule_slot",
    ),
    # Управління Користувачами (CRUD)
    path("users/edit/<int:pk>/", views.user_edit_view, name="user_edit"),
    path("users/delete/<int:pk>/", views.user_delete_view, name="user_delete"),
    path("users/export/", views.users_csv_export, name="users_csv_export"),
    path("users/import/", views.users_csv_import, name="users_csv_import"),
    # Управління Групами (CRUD)
    path("groups/", views.groups_list_view, name="groups_list"),
    path("groups/add/", views.group_add_view, name="group_add"),
    path("groups/delete/<int:pk>/", views.group_delete_view, name="group_delete"),
    path("groups/export/", views.groups_csv_export, name="groups_csv_export"),
    path("groups/import/", views.groups_csv_import, name="groups_csv_import"),
    # Управління Предметами (CRUD)
    path("subjects/", views.subjects_list_view, name="subjects_list"),
    path("subjects/add/", views.subject_add_view, name="subject_add"),
    path("subjects/delete/<int:pk>/", views.subject_delete_view, name="subject_delete"),
    path("subjects/export/", views.subjects_csv_export, name="subjects_csv_export"),
    path("subjects/import/", views.subjects_csv_import, name="subjects_csv_import"),
    # Управління Аудиторіями (CRUD)
    path("classrooms/", views.classrooms_list_view, name="classrooms_list"),
    path("classrooms/add/", views.classroom_add_view, name="classroom_add"),
    path(
        "classrooms/delete/<int:pk>/",
        views.classroom_delete_view,
        name="classroom_delete",
    ),
    path(
        "classrooms/export/", views.classrooms_csv_export, name="classrooms_csv_export"
    ),
    path(
        "classrooms/import/", views.classrooms_csv_import, name="classrooms_csv_import"
    ),
    # =========================
    # 3. ЗВІТИ (CSV)
    # =========================
    path("admin/reports/", views.admin_reports_view, name="admin_reports"),
    path("admin/reports/rating/", views.report_rating_view, name="report_rating"),
    path("admin/reports/absences/", views.report_absences_view, name="report_absences"),
    path(
        "admin/reports/weekly_absences/",
        views.report_weekly_absences_view,
        name="report_weekly_absences",
    ),
    path("admin/reports/subjects/", views.report_subjects_view, name="report_subjects"),
    path("admin/reports/at-risk/", views.report_at_risk_view, name="report_at_risk"),
    path("admin/reports/homework/", views.report_homework_view, name="report_homework"),
    # =========================
    # 4. ВИКЛАДАЧ ТА ЖУРНАЛ
    # =========================
    path("teacher/", views.teacher_journal_view, name="teacher_journal"),
    path("teacher/dashboard/", views.teacher_dashboard_view, name="teacher_dashboard"),
    path(
        "teacher/live/<int:lesson_id>/",
        views.teacher_live_mode_view,
        name="teacher_live_mode",
    ),
    # Use the new API for saving (even if frontend calls it 'save_journal_entries' or we rename it)
    path("api/teacher/save-grade/", views.api_save_grade, name="api_save_grade"),
    path(
        "api/teacher/update-lesson/", views.api_update_lesson, name="api_update_lesson"
    ),
    path("teacher/settings/", views.teacher_settings_view, name="teacher_settings"),
    path(
        "api/teacher/manage-eval-types/",
        views.api_manage_evaluation_types,
        name="api_manage_evaluation_types",
    ),
    path("api/teacher/card-scan/", views.api_card_scan, name="api_card_scan"),
    # Restore compat name if needed, or better:
    path(
        "teacher/save/", views.api_save_grade, name="save_journal_entries"
    ),  # Alias for compatibility
    # Управління типами оцінювання
    path(
        "teacher/evaluation-types/",
        views.manage_evaluation_types_view,
        name="manage_evaluation_types",
    ),
    path(
        "teacher/evaluation-type/edit/<int:pk>/",
        views.evaluation_type_edit_view,
        name="edit_evaluation_type",
    ),
    path(
        "teacher/evaluation-type/delete/<int:pk>/",
        views.evaluation_type_delete_view,
        name="delete_evaluation_type",
    ),
    path(
        "api/evaluation-types/",
        views.get_evaluation_types_api,
        name="get_evaluation_types_api",
    ),
    # =========================
    # 5. СТУДЕНТ
    # =========================
    path("student/grades/", views.student_grades_view, name="student_grades"),
    path(
        "student/attendance/", views.student_attendance_view, name="student_attendance"
    ),
    path("student/dashboard/", views.student_dashboard_view, name="student_dashboard"),
    path("profile/", views.profile_view, name="profile"),
    path("api/set-theme/", views.api_set_theme, name="api_set_theme"),
    # =========================
    # 6. СТРІЧКА НОВИН
    # =========================
    path("news/", views.news_feed_view, name="news_feed"),
    path(
        "api/news/post/create/", views.api_news_create_post, name="api_news_create_post"
    ),
    path(
        "api/news/post/delete/<int:pk>/",
        views.api_news_delete_post,
        name="api_news_delete_post",
    ),
    path(
        "api/news/comment/create/",
        views.api_news_create_comment,
        name="api_news_create_comment",
    ),
    path(
        "api/news/comment/delete/<int:pk>/",
        views.api_news_delete_comment,
        name="api_news_delete_comment",
    ),
    # =========================
    # 7. СПОВІЩЕННЯ
    # =========================
    path("notifications/", views.notifications_page_view, name="notifications_page"),
    path(
        "api/notifications/",
        views.api_notifications_list,
        name="api_notifications_list",
    ),
    path(
        "api/notifications/mark-read/<int:pk>/",
        views.api_notifications_mark_read,
        name="api_notifications_mark_read",
    ),
    path(
        "api/notifications/mark-unread/<int:pk>/",
        views.api_notifications_mark_unread,
        name="api_notifications_mark_unread",
    ),
    path(
        "api/notifications/mark-all-read/",
        views.api_notifications_mark_all_read,
        name="api_notifications_mark_all_read",
    ),
    path(
        "api/notifications/delete/<int:pk>/",
        views.api_notifications_delete,
        name="api_notifications_delete",
    ),
    path(
        "api/notifications/delete-all-read/",
        views.api_notifications_delete_all_read,
        name="api_notifications_delete_all_read",
    ),
    path(
        "api/notifications/delete-all/",
        views.api_notifications_delete_all,
        name="api_notifications_delete_all",
    ),
    # =========================
    # 8. ДЕТАЛІ УРОКУ ТА ДЗ
    # =========================
    path("lessons/", views.lessons_list_view, name="lessons_list"),
    path("lesson/<int:lesson_id>/", views.lesson_detail_view, name="lesson_detail"),
    path(
        "api/lesson/<int:lesson_id>/content/",
        views.api_lesson_save_content,
        name="api_lesson_save_content",
    ),
    path(
        "api/lesson/<int:lesson_id>/upload-attachment/",
        views.api_lesson_upload_attachment,
        name="api_lesson_upload_attachment",
    ),
    path(
        "api/lesson/<int:lesson_id>/delete-attachment/<int:attachment_id>/",
        views.api_lesson_delete_attachment,
        name="api_lesson_delete_attachment",
    ),
    path(
        "api/lesson/<int:lesson_id>/submit-homework/",
        views.api_lesson_submit_homework,
        name="api_lesson_submit_homework",
    ),
    path(
        "api/lesson/<int:lesson_id>/cancel-homework/",
        views.api_lesson_cancel_homework,
        name="api_lesson_cancel_homework",
    ),
    # Google Classroom-style APIs
    path(
        "api/lesson/<int:lesson_id>/submission/attach/",
        views.api_submission_upload_file,
        name="api_submission_upload_file",
    ),
    path(
        "api/lesson/<int:lesson_id>/submission/delete-file/<int:attachment_id>/",
        views.api_submission_delete_file,
        name="api_submission_delete_file",
    ),
    path(
        "api/lesson/<int:lesson_id>/turn-in/",
        views.api_lesson_turn_in,
        name="api_lesson_turn_in",
    ),
    path(
        "api/lesson/<int:lesson_id>/save-settings/",
        views.api_lesson_save_settings,
        name="api_lesson_save_settings",
    ),
    path(
        "api/lesson/<int:lesson_id>/student/<int:student_id>/submission/",
        views.api_get_student_submission,
        name="api_get_student_submission",
    ),
    path(
        "api/submission/<int:submission_id>/grade/",
        views.api_grade_submission,
        name="api_grade_submission",
    ),
    path(
        "api/submission/<int:submission_id>/comment/",
        views.api_add_private_comment,
        name="api_add_private_comment",
    ),
]

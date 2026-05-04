from .models import InstitutionSettings, Specialty, TeachingAssignment


def institution_settings(request):
    """
    Inject InstitutionSettings singleton into every template context.
    Falls back gracefully if no record exists or table is missing.
    """
    try:
        institution = InstitutionSettings.get_instance()
    except Exception:
        institution = None
    return {"institution": institution}


def global_context(request):
    """
    Inject the active course/specialty context (stored in session) into
    every template. Also exposes the list of specialties for the switcher,
    filtered by user role and permissions.
    """
    ctx = {
        "ctx_course": None,
        "ctx_specialty": None,
        "ctx_specialties": [],
        "ctx_courses": [],
        "show_context_switcher": False,
    }

    if not request.user.is_authenticated or request.user.role == "student":
        return ctx

    try:
        # 1. Determine allowed context options
        if request.user.role == "admin":
            ctx["ctx_specialties"] = list(Specialty.objects.filter(is_active=True))
            ctx["ctx_courses"] = list(range(1, 7))
            ctx["show_context_switcher"] = True
        elif request.user.role == "teacher":
            # For teachers, specialty is not needed as per request
            ctx["ctx_specialties"] = []

            # Teachers get full course selection (1-6) just like admins
            ctx["ctx_courses"] = list(range(1, 7))
            ctx["show_context_switcher"] = True

        # 2. Get current active context from session
        ctx["ctx_course"] = request.session.get("global_course")
        specialty_id = request.session.get("global_specialty_id")

        if specialty_id:
            # Verify teacher still has access to this specialty if they switched roles or assignments
            if (
                request.user.role == "admin"
                or Specialty.objects.filter(
                    id=specialty_id, id__in=[s.id for s in ctx["ctx_specialties"]]
                ).exists()
            ):
                ctx["ctx_specialty"] = Specialty.objects.filter(pk=specialty_id).first()
            else:
                # Reset invalid context
                request.session["global_specialty_id"] = None
                ctx["ctx_specialty"] = None

        if ctx["ctx_course"] and ctx["ctx_course"] not in ctx["ctx_courses"]:
            # Reset invalid course context
            request.session["global_course"] = None
            ctx["ctx_course"] = None

    except Exception:
        pass

    return ctx

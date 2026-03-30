from .models import InstitutionSettings


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

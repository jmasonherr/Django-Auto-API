
def _superadmin(request):
    """ Detect if the user is a superadmin, let them do whatever if so """
    return request.user.is_superuser or request.DATA.get('key', '') == 'secretkeythatallowsyousuperadminaccess'


def _permission(request, model, method):
    """ 
        Convenience method to check if the user has permission to take an action
        Takes a Django model or instance, and an permission method stored on the model like 'has_PUT_permission'
    """
    if _superadmin(request):
        return True
    try:
        return getattr(model, method)(request)
    except TypeError:
        return getattr(model(), method)(request)
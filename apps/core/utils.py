from apps.core.models import SystemSetting


def get_setting(key, default=None):
    try:
        return SystemSetting.objects.get(
            key=key
        ).value
    except SystemSetting.DoesNotExist:
        return default


def get_int_setting(key, default):
    try:
        value = get_setting(
            key,
            default
        )
        return int(value)
    except (TypeError, ValueError):
        return default

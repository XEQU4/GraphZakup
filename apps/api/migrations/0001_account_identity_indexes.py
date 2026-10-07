"""Preserve accounts while enforcing case-insensitive registration identities."""
from django.db import migrations
from django.db.models import Count
from django.db.models.functions import Lower

INDEXES = {'username': 'api_auth_username_ci', 'email': 'api_auth_email_ci'}


def add_indexes(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    alias = schema_editor.connection.alias
    for field in INDEXES:
        duplicates = (User.objects.using(alias).exclude(**{field: ''})
            .annotate(identity=Lower(field)).values('identity').annotate(n=Count('pk')).filter(n__gt=1))
        if duplicates.exists():
            raise RuntimeError('Account identity indexes require unique nonempty values for ' + field +
                '; existing account rows were not changed.')
    quote = schema_editor.quote_name
    table = quote(User._meta.db_table)
    for field, index in INDEXES.items():
        column = quote(User._meta.get_field(field).column)
        condition = " WHERE " + column + " <> ''" if field == 'email' else ''
        schema_editor.execute('CREATE UNIQUE INDEX ' + quote(index) + ' ON ' + table +
            ' (LOWER(' + column + '))' + condition)


def remove_indexes(apps, schema_editor):
    for index in INDEXES.values():
        schema_editor.execute('DROP INDEX ' + schema_editor.quote_name(index))


class Migration(migrations.Migration):
    dependencies = [('auth', '0012_alter_user_first_name_max_length')]
    operations = [migrations.RunPython(add_indexes, remove_indexes)]

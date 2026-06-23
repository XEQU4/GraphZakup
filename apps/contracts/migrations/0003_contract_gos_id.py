from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0002_alter_contract_tender_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='contract_gos_id',
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
    ]

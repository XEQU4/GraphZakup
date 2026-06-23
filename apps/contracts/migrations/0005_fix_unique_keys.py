from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0004_contract_contract_number'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contract',
            name='tender_id',
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='contract',
            name='contract_number',
            field=models.CharField(db_index=True, max_length=255, unique=True),
        ),
    ]

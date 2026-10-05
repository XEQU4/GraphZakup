from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("graph", "0002_alter_connection_connection_type")]

    operations = [
        migrations.AddField(
            model_name="riskcluster", name="is_active",
            field=models.BooleanField(default=True, db_index=True),
        ),
        migrations.AddField(
            model_name="riskcluster", name="analysis_fingerprint",
            field=models.CharField(max_length=64, blank=True),
        ),
        migrations.AddField(
            model_name="riskcluster", name="explanation_stale",
            field=models.BooleanField(default=True),
        ),
    ]

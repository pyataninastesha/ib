from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0013_organization_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailymenu',
            name='planned_breakfast_portions',
            field=models.PositiveIntegerField(default=0, verbose_name='План порций (утро)'),
        ),
        migrations.AddField(
            model_name='dailymenu',
            name='planned_lunch_portions',
            field=models.PositiveIntegerField(default=0, verbose_name='План порций (день)'),
        ),
    ]

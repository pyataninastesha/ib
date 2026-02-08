from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_organization_and_purchase_org'),
        ('users', '0009_mealrequest_stock_deducted'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='users', to='core.organization', verbose_name='Организация'),
        ),
        migrations.AddField(
            model_name='subscription',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='subscriptions', to='core.organization', verbose_name='Организация'),
        ),
        migrations.AddField(
            model_name='mealreceipt',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='meal_receipts', to='core.organization', verbose_name='Организация'),
        ),
        migrations.AddField(
            model_name='mealrequest',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='meal_requests', to='core.organization', verbose_name='Организация'),
        ),
    ]

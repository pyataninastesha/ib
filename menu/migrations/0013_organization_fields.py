from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_organization_and_purchase_org'),
        ('menu', '0012_normalize_products_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='products', to='core.organization', verbose_name='Организация'),
        ),
        migrations.AlterField(
            model_name='product',
            name='name',
            field=models.CharField(max_length=200),
        ),
        migrations.AddConstraint(
            model_name='product',
            constraint=models.UniqueConstraint(fields=('organization', 'name'), name='uniq_product_org_name'),
        ),
        migrations.AddField(
            model_name='dailymenu',
            name='organization',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='daily_menus', to='core.organization', verbose_name='Организация'),
        ),
        migrations.AlterField(
            model_name='dailymenu',
            name='date',
            field=models.DateField(),
        ),
        migrations.AddConstraint(
            model_name='dailymenu',
            constraint=models.UniqueConstraint(fields=('organization', 'date'), name='uniq_dailymenu_org_date'),
        ),
    ]

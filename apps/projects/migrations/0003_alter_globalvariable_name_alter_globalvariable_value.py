# Generated by Django 4.2.20 on 2025-04-20 21:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_globalvariable'),
    ]

    operations = [
        migrations.AlterField(
            model_name='globalvariable',
            name='name',
            field=models.CharField(help_text='变量名称', max_length=16, verbose_name='变量名称'),
        ),
        migrations.AlterField(
            model_name='globalvariable',
            name='value',
            field=models.CharField(help_text='变量值', max_length=16, verbose_name='变量值'),
        ),
    ]

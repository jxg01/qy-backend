# Generated by Django 4.2.20 on 2025-05-01 19:06

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0003_alter_globalvariable_name_alter_globalvariable_value'),
    ]

    operations = [
        migrations.CreateModel(
            name='InterFace',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=30, verbose_name='接口名称')),
                ('url', models.CharField(max_length=500, verbose_name='接口路径')),
                ('method', models.CharField(choices=[('GET', 'GET'), ('POST', 'POST'), ('PUT', 'PUT'), ('DELETE', 'DELETE'), ('PATCH', 'PATCH')], max_length=10, verbose_name='请求方式')),
                ('headers', models.JSONField(default=dict, verbose_name='请求头')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='projects.projects', verbose_name='所属项目')),
                ('updated_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': '接口用例',
                'verbose_name_plural': '接口用例',
                'db_table': 'qy_interface',
            },
        ),
        migrations.CreateModel(
            name='TestCase',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=30, verbose_name='用例名称')),
                ('description', models.CharField(max_length=100, null=True, verbose_name='用例描述')),
                ('body', models.JSONField(default=dict, verbose_name='请求参数')),
                ('assertions', models.JSONField(default=list, verbose_name='断言规则')),
                ('variable_extract', models.JSONField(default=list, verbose_name='变量提取规则')),
                ('enabled', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('interface', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='jk_case.interface', verbose_name='接口')),
                ('updated_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': '测试用例',
                'verbose_name_plural': '测试用例',
                'db_table': 'qy_test_case',
            },
        ),
        migrations.CreateModel(
            name='TestSuite',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(help_text='套件名称', max_length=30, unique=True, verbose_name='套件名称')),
                ('description', models.CharField(help_text='套件描述', max_length=100, null=True, verbose_name='套件描述')),
                ('cases', models.ManyToManyField(help_text='用例', to='jk_case.testcase', verbose_name='用例')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(help_text='项目名称', on_delete=django.db.models.deletion.CASCADE, to='projects.projects', verbose_name='项目名称')),
                ('updated_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': '测试套件',
                'verbose_name_plural': '测试套件',
                'db_table': 'qy_suite',
            },
        ),
        migrations.CreateModel(
            name='TestExecution',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', '未开始'), ('running', '执行中'), ('passed', '成功'), ('failed', '失败')], default='pending', max_length=20)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('ended_at', models.DateTimeField(null=True)),
                ('duration', models.FloatField(null=True)),
                ('executed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('suite', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='jk_case.testsuite', verbose_name='测试套件')),
            ],
            options={
                'db_table': 'qy_test_execution',
            },
        ),
        migrations.CreateModel(
            name='CaseExecution',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', '未开始'), ('running', '执行中'), ('passed', '成功'), ('failed', '失败')], max_length=20)),
                ('request_data', models.JSONField()),
                ('response_data', models.JSONField()),
                ('assertions_result', models.JSONField()),
                ('extracted_vars', models.JSONField()),
                ('duration', models.FloatField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('case', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='jk_case.testcase')),
                ('execution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cases', to='jk_case.testexecution')),
            ],
            options={
                'db_table': 'qy_case_execution',
            },
        ),
        migrations.CreateModel(
            name='SuiteCaseRelation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='执行顺序')),
                ('case', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='jk_case.testcase')),
                ('suite', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='jk_case.testsuite')),
            ],
            options={
                'db_table': 'qy_suite_case_relation',
                'ordering': ['order'],
                'unique_together': {('suite', 'case')},
            },
        ),
    ]

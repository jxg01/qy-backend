import django_filters
from jk_case.models import TestCase, TestSuite
from projects.models import Projects


class TestCaseFilter(django_filters.FilterSet):
    """ 定义字段，搜索方式：模糊搜索 """
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')

    class Meta:
        model = TestCase
        fields = ['name']


class SuiteFilter(django_filters.FilterSet):
    """ 定义字段，搜索方式：模糊搜索 """
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    project = django_filters.ModelChoiceFilter(queryset=Projects.objects.all())
    # 或者使用下面这种方式通过project的name字段过滤
    # project__name = django_filters.CharFilter(field_name='project__name', lookup_expr='icontains')

    class Meta:
        model = TestSuite
        fields = ['name', 'project']


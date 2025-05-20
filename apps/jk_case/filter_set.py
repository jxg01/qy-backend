import django_filters
from jk_case.models import TestCase


class TestCaseFilter(django_filters.FilterSet):
    """ 定义字段，搜索方式：模糊搜索 """
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')

    class Meta:
        model = TestCase
        fields = ['name']



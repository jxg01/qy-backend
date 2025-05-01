from django.contrib import admin
from django.apps import apps


all_model = apps.get_app_config('jk_case').get_models()

admin.site.register(all_model)

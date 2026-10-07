from django.contrib import admin
from django.urls import include, path, re_path

from apps.core.views import health_live, health_ready
from apps.frontend import views as frontend_views

urlpatterns = [
    path('', frontend_views.home, name='frontend-home'),
    path('app/', frontend_views.index, name='frontend-app'),
    re_path(r'^app/(?P<path>.*)$', frontend_views.index, name='frontend-route'),
    path('legacy/', include('apps.dashboard.urls')),
    path('api/v1/', include('apps.api.urls')),
    path('analysis/', include('apps.ai.urls')),
    path('health/live/', health_live, name='health-live'),
    path('health/ready/', health_ready, name='health-ready'),
    path('admin/', admin.site.urls),
    path('clusters/', include('apps.graph.urls')),
    path('companies/', include('apps.companies.urls')),
    path('owners/', include('apps.owners.urls')),
]

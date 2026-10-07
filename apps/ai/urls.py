from django.urls import path
from .views import start_analysis, job_status, analysis_data

app_name = 'ai'
urlpatterns = [
    path('jobs/<uuid:uuid>/', job_status, name='job_status'),
    path('<uuid:uuid>/start/', start_analysis, name='start'),
    path('<uuid:uuid>/', analysis_data, name='data'),
]

from django.contrib import admin
from django.urls import include
from django.urls import path
from apps.core.views import health_live, health_ready

urlpatterns = [
    path("health/live/", health_live, name="health-live"),
    path("health/ready/", health_ready, name="health-ready"),

    path(
        "admin/",
        admin.site.urls
    ),

    path(
        "",
        include(
            "apps.dashboard.urls"
        )
    ),

    path(
        "clusters/",
        include(
            "apps.graph.urls"
        )
    ),

    path(
        "companies/",
        include(
            "apps.companies.urls"
        )
    ),

    path(
        "owners/",
        include(
            "apps.owners.urls"
        )
    ),

]

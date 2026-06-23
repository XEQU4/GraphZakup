from django.contrib import admin
from django.urls import include
from django.urls import path

urlpatterns = [

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

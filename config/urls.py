from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from worklog import views


router = DefaultRouter()
router.register("projects", views.ProjectViewSet, basename="projects")
router.register("worklogs", views.WorklogViewSet, basename="worklogs")

urlpatterns = [
    path("health/", views.health, name="health"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/token/", views.LoginView.as_view(), name="login"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("api/members/", views.MemberListView.as_view(), name="members"),
    path("api/", include(router.urls)),
]

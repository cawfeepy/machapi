"""api URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from drf_spectacular.renderers import OpenApiJsonRenderer

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include([
        path('', include('machtms.backend.auth.urls')),
        path('', include('machtms.backend.loads.urls')),
        path('', include('machtms.backend.legs.urls')),
        path('', include('machtms.backend.routes.urls')),
        path('', include('machtms.backend.carriers.urls')),
        path('', include('machtms.backend.customers.urls')),
        path('', include('machtms.backend.addresses.urls')),
        # TODO: Uncomment when financials module is implemented
        # path('', include('machtms.backend.financials.urls')),
        path('', include('machtms.backend.DocumentManager.urls')),
        path('', include('machtms.backend.GmailAPI.urls')),
    ])),
    path("api/schema/", SpectacularAPIView.as_view(renderer_classes=[OpenApiJsonRenderer]), name='api^schema'),
    path("api/docs/", SpectacularSwaggerView.as_view(), name='api^docs'),
]

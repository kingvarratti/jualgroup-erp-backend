from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/core/', include('core.urls')),
    path('api/sales/', include('sales.urls')),
    path('api/procurement/', include('procurement.urls')),
    path('api/production/', include('production.urls')),
    path('api/finance/', include('finance.urls')),
    path('api/hr/', include('hr.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
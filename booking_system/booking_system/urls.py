from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def health(request):
    """Liveness probe for container orchestrators."""
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('bookings.urls', namespace='bookings')),
    path('healthz/', health, name='health'),
]

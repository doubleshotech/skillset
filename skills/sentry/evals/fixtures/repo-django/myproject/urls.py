from django.urls import path, include

urlpatterns = [
    path('widgets/', include('widgets.urls')),
]

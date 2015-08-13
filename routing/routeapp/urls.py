from django.conf.urls import url
from . import views

urlpatterns = [
url(r'^search/$', views.search, name='search'),
url(r'^elevation.geojson/$', views.elevationgeojson, name='elevationgeojson'),
url(r'^route.geojson/$', views.routegeojson, name='routegeojson'),
url(r'^$', views.homepage, name='homepage'),


]
from django.contrib import admin
from django.urls import path
from clientes.views import hola_mundo, saludoNombre, index, vistas, guardar_cliente, busqueda_clientes
from productos.views import guardar_producto, busqueda_productos

urlpatterns = [
    path('admin/', admin.site.urls),
    path('saludo/', hola_mundo),
    path('saludo/<str:nombre>/<int:edad>', saludoNombre),
    path('', index),
    path('vistas/<str:form>/', vistas),
    path('guardar_cliente/', guardar_cliente),
    path('busqueda_clientes/', busqueda_clientes),
    path('guardar_producto/', guardar_producto),
    path('busqueda_productos/', busqueda_productos),
    
]

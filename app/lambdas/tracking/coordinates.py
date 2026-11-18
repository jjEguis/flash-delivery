"""Coordenadas de pedido: cobertura local explícita y almacenamiento entero E6."""
import math
import os
from lambdas.shared.exceptions import ValidationError


def coordinate(value):
    if not isinstance(value, dict) or set(value) != {'latitude', 'longitude'}:
        raise ValidationError('Cada punto requiere latitude y longitude')
    for name, bound in [('latitude', 90), ('longitude', 180)]:
        number = value[name]
        if type(number) not in (int, float) or abs(number) > bound or not math.isfinite(number):
            raise ValidationError('Coordenadas inválidas')
    west, south, east, north = map(float, os.getenv('ROUTING_BBOX', '-74.28,11.12,-74.05,11.36').split(','))
    if not west <= value['longitude'] <= east or not south <= value['latitude'] <= north:
        raise ValidationError('El punto está fuera de la cobertura de Santa Marta')
    return {name+'E6': round(value[name]*1_000_000) for name in ('latitude', 'longitude')}


def degrees(value):
    return {name: value[name+'E6']/1_000_000 for name in ('latitude', 'longitude')}

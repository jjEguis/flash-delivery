"""Proyección local en metros, continuidad en cruces y ETA por segmentos OSRM."""
import math
import os


def project(route, point, previous=None):
    coords = route['geometry']['coordinates']
    p = [point['longitude'], point['latitude']]
    cos = math.cos(math.radians(p[1]))
    candidates, accumulated = [], 0.
    for i, (a, b) in enumerate(zip(coords, coords[1:])):
        ax, ay = (a[0]-p[0])*111195*cos, (a[1]-p[1])*111195
        dx, dy = (b[0]-a[0])*111195*cos, (b[1]-a[1])*111195
        segment = math.hypot(dx, dy)
        fraction = max(0., min(1., -(ax*dx+ay*dy)/(segment*segment))) if segment else 0.
        gap = math.hypot(ax+fraction*dx, ay+fraction*dy)
        candidates.append((gap, accumulated+fraction*segment, i, fraction))
        accumulated += segment
    if previous and previous.get('sampleEpoch'):
        advance = max(80, min(500, max(0, point['epoch']-previous['sampleEpoch'])*40))
        nearby = [c for c in candidates if previous['progressMeters']-25 <= c[1] <= previous['progressMeters']+advance]
        if nearby:
            candidates = nearby
    gap, progress, index, fraction = min(candidates, key=lambda c: c[0])
    threshold = max(float(os.getenv('ROUTE_DEVIATION_METERS', '50')), min(200, point.get('accuracyMeters', 0)))
    off_route = gap > threshold
    if off_route and previous:
        progress = previous.get('progressMeters', 0)
        remaining = previous.get('remainingMeters', route['distanceMeters'])
        eta = None
    else:
        remaining = sum(route['segmentDistances'][index+1:]) + route['segmentDistances'][index]*(1-fraction)
        eta = sum(route['segmentDurations'][index+1:]) + route['segmentDurations'][index]*(1-fraction)
    return {'progressMeters':progress, 'remainingMeters':remaining, 'etaSeconds':eta if not off_route else None,
            'segmentIndex':index, 'segmentFraction':fraction, 'distanceToRouteMeters':gap,
            'offRoute':off_route, 'sampleEpoch':point['epoch'],
            'deviationCount':(previous.get('deviationCount', 0) if previous else 0)+1 if off_route else 0}

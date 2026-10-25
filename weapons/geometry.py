"""Non-mutating swept circle queries; times are fractions of the movement."""
import math

def circle_time(start, delta, center, radius):
    x, y = start[0]-center[0], start[1]-center[1]
    a = delta[0]**2 + delta[1]**2
    c = x*x+y*y-radius*radius
    if c <= 0:
        return 0.0
    if a < 1e-12:
        return None
    b = x*delta[0]+y*delta[1]
    disc = b*b-a*c
    if disc < 0:
        return None
    t = (-b-math.sqrt(disc))/a
    return t if 0 <= t <= 1 else None

def segment_contact(start, delta, a, b, radius):
    dx, dy = b[0]-a[0], b[1]-a[1]
    length = math.hypot(dx,dy)
    candidates = []
    for endpoint in (a,b):
        t = circle_time(start, delta, endpoint, radius)
        if t is not None:
            nx, ny = start[0]+delta[0]*t-endpoint[0], start[1]+delta[1]*t-endpoint[1]
            norm = math.hypot(nx,ny)
            if norm > 1e-9 and (t > 1e-9 or delta[0]*nx+delta[1]*ny < 0):
                candidates.append((t,(nx/norm,ny/norm)))
    if length > 1e-9:
        nx,ny = -dy/length,dx/length
        distance = (start[0]-a[0])*nx+(start[1]-a[1])*ny
        velocity = delta[0]*nx+delta[1]*ny
        for side in (-1,1):
            t = (side*radius-distance)/velocity if abs(velocity)>1e-12 else -1
            if abs(distance) <= radius:
                t = 0.0
                side = 1 if distance >= 0 else -1
            if 0 <= t <= 1:
                px,py = start[0]+delta[0]*t-a[0],start[1]+delta[1]*t-a[1]
                along = (px*dx+py*dy)/length
                if 0 <= along <= length and velocity*side < 0:
                    candidates.append((t,(nx*side,ny*side)))
    return min(candidates,key=lambda item:item[0]) if candidates else None

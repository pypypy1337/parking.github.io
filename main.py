from parking import Parking
from camera import Camera
from object import Object

park = Parking("A1")
print(park.parking_stage)
print(park.check_occupancy())

cam = Camera("Camera 1", 100, 100, 200, 200)
print(cam.name)
print(cam.get_coordinates())

cam.monitor_parking(park)

car1 = Object("Audi", "Black", "М512УХ")
print(car1.name)
print(car1.color)
print(car1.number)

car1.park_car(park)

cam.monitor_parking(park)

car2 = Object("BMW", "White", "А695КА")
car2.park_car(park)

car1.leave_parking(park)

car2.park_car(park)

cam.monitor_parking(park)
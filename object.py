class Object:
    def __init__(self, name, color, number):
        self.name = name
        self.color = color
        self.number = number
        print("Заезжает машина: ")

    def park_car(self, parking):
        if not parking.is_occupied:
            parking.occupy()
            print(f"{self.color} {self.name} {self.number} припарковалась на месте '{parking.parking_stage}'")
        else:
            print(f"Место '{parking.parking_stage}' уже занято! {self.color} {self.name} {self.number} не может припарковаться")

    def leave_parking(self, parking):
        if parking.is_occupied:
            parking.free()
            print(f"{self.color} {self.name} {self.number} уехала с места '{parking.parking_stage}'")
        else:
            print(f"Место '{parking.parking_stage}' и так свободно")
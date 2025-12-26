class Parking:
    def __init__(self, parking_stage):
        self.parking_stage = parking_stage
        self.is_occupied = False
        print("Создается парковочное место: ")

    def check_occupancy(self):
        if self.is_occupied:
            return f"Место '{self.parking_stage}' занято"
        else:
            return f"Место '{self.parking_stage}' свободно"

    def occupy(self):
        self.is_occupied = True
        print(f"Место '{self.parking_stage}' теперь занято")

    def free(self):
        self.is_occupied = False
        print(f"Место '{self.parking_stage}' теперь свободно")
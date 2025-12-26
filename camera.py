class Camera:
    def __init__(self, name, x1, y1, x2, y2):
        self.name = name
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        print(f"Создается камера: ")

    def monitor_parking(self, parking):
        status = parking.check_occupancy()
        print(f"Камера '{self.name}': {status}")

    def get_coordinates(self):
        return f"'{self.name}' следит за областью: ({self.x1}, {self.y1}, {self.x2}, {self.y2})"
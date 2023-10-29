
# the parking minimum is effectively 2 everywhere for all housing types
PARKING_MINIMUM = 2.0

class Zone(dict):
    def __init__(self, name, front_setback, side_setback, rear_setback, height, stories, far, max_lot_coverage, min_open_space, lot_area, max_dua, lot_frontage):
        self.name = name
        self.front_setback = front_setback
        self.side_setback = side_setback
        self.rear_setback = rear_setback
        self.height = height
        self.stories = stories
        self.far = far
        self.max_lot_coverage = max_lot_coverage
        self.min_open_space = min_open_space
        self.lot_area = lot_area
        self.max_dua = max_dua
        self.lot_frontage = lot_frontage
        
        self.district_parking_ratio = PARKING_MINIMUM
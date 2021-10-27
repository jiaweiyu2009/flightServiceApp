class Flight:
    def __init__(self, fid=-1, dayOfMonth=0, carrierId=0, flightNum=0, originCity="", destCity="", time=0, capacity=0, price=0):
        self.fid = fid
        self.dayOfMonth = dayOfMonth
        self.carrierId = carrierId
        self.flightNum = flightNum
        self.originCity = originCity
        self.destCity = destCity
        self.time = time
        self.capacity = capacity
        self.price = price

    def toString(self):
        return "ID: {} Day: {} Carrier: {} Number: {} Origin: {} Dest: {} Duration: {} Capacity: {} Price: {}\n".format(
            self.fid, self.dayOfMonth, self.carrierId, self.flightNum, self.originCity, self.destCity, self.time, self.capacity, self.price)


class Itinerary:
    # one-hop flight
    def __init__(self,  time, flight1, flight2=Flight()):  # the second one could be empty flight
        self.flights = []
        self.flights.append(flight1)
        self.flights.append(flight2)
        self.time = time

    def itineraryPrice(self):
        price = 0
        for f in self.flights:
            price += f.price
        return price

    def numFlights(self):
        if(self.flights[1].fid == -1):
            return 1
        else:
            return 2

    def dayOfItinerary(self):
        return self.flights[0].dayOfMonth

    def getFlight1(self):
        return self.flights[0]

    def getFlight2(self):
        return self.flights[1]


def main():
    a = Flight(12, 54, 67, 23, "o", "d", 25, 30, 22)
    b = Flight()
    c = Itinerary(a.time, a)
    print(c.getFlight2().fid)


if __name__ == "__main__":
    main()

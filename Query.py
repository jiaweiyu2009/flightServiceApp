import sqlite3
import operator
import subprocess
import os
import csv
import apsw
import time
import threading
##################################################################################################################
DB_NAME = "example.db"

# A class to store flight information.


class Flight:
    def __init__(self, fid=-1, dayOfMonth=0, carrierId=0, flightNum=0, originCity="", destCity="", time=0, capacity=-1, price=0):
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

    def getTime(self):
        return self.time


class Query:
    CREATE_CUSTOMER_SQL = "INSERT INTO Customers VALUES('{}', '{}', {})"

    CHECK_FLIGHT_DAY = "SELECT * FROM Reservations r, Flights f WHERE r.username = '{}' AND f.day_of_month = {} AND r.fid1 = f.fid"
    CHECK_FLIGHT_CAPACITY = "SELECT capacity FROM Flights WHERE fid = {}"
    CHECK_BOOKED_SEATS = "SELECT COUNT(*) AS cnt FROM Reservations WHERE fid = {}"
    CLEAR_DB_SQL1 = "DELETE FROM Reservations;"
    CLEAR_DB_SQL2 = "DELETE FROM Customers;"
    CLEAR_DB_SQL3 = "UPDATE ReservationsId SET rid = 1;"

    GET_PASSWORD_FROM_USERNAME = "SELECT password FROM Customers WHERE username = '{}'"
    SEARCH_DIRECT_FLIGHT = "SELECT fid, day_of_month, carrier_id, flight_num, origin_city, dest_city, actual_time, capacity, price FROM Flights WHERE origin_city = '{}' AND dest_city = '{}' AND day_of_month = {} AND actual_time != 0 ORDER BY actual_time ASC LIMIT {}"
    SEARCH_HOP_FLIGHT = "SELECT F1.fid, F1.day_of_month, F1.carrier_id, F1.flight_num, F1.origin_city, F1.dest_city, F1.actual_time, F1.capacity, F1.price, F2.fid, F2.day_of_month, F2.carrier_id, F2.flight_num, F2.origin_city, F2.dest_city, F2.actual_time, F2.capacity, F2.price FROM Flights AS F1, Flights AS F2 WHERE F1.origin_city = '{}' AND F2.dest_city = '{}' AND F1.dest_city = F2.origin_city AND F1.day_of_month = {} AND F2.day_of_month = F1.day_of_month AND F1.canceled != 1 AND F2.canceled != 1 ORDER BY F1.actual_time + F2.actual_time ASC LIMIT {}"
    INSERT_RESERVATIONS_TABLE = "INSERT INTO Reservations VALUES({}, {}, {}, {}, {}, {}, '{}', {})"
    GET_LAST_RESERVE_ID = "SELECT rid FROM Reservations WHERE username = '{}' ORDER BY rid DESC LIMIT 1 "
    TARGET_RESERVATION_PRICE = "SELECT price FROM Reservations WHERE rid = {}"
    TARGET_RESERVATION_USERNAME = "SELECT username FROM Reservations WHERE rid = {}"
    TARGET_RESERVATION_PAID = "SELECT paid FROM Reservations WHERE rid = {}"
    TARGET_RESERVATION_CANCELED = "SELECT canceled FROM Reservations WHERE rid = {}"
    GET_CUSTOMER_BALANCE = "SELECT balance FROM Customers WHERE username = '{}'"
    UPDATE_CUSTOMER_BALANCE = "UPDATE Customers SET balance = {} WHERE username = '{}'"
    UPDATE_RESERVATIONS_PAID = "UPDATE Reservations SET paid = 1 WHERE rid = {} AND username = '{}'"
    GET_ALL_RESERVATIONS = "SELECT * FROM Reservations WHERE username = '{}' AND canceled != 1"
    GET_FLIGHT_FROM_FID = "SELECT fid, day_of_month, carrier_id, flight_num, origin_city, dest_city, actual_time, capacity, price FROM Flights WHERE fid = {}"
    UPDATE_RESERVATIONS_CANCELED = "UPDATE Reservations SET canceled = 1 WHERE rid = {} AND username = '{}'"
    username = None
    lastItineraries = []
    sortedItinerary = []
    newReserveId = 1
    last_reserveId = -1
    currentBalance = -1

    def __init__(self):
        self.db_name = DB_NAME
        self.conn = apsw.Connection(self.db_name, statementcachesize=0)
        self.conn.setbusytimeout(5000)

    def startConnection(self):
        self.conn = apsw.Connection(self.db_name, statementcachesize=0)

    def closeConnection(self):
        self.conn.close()

##################################################################################################################################
    '''
    * Clear the data in any custom tables created. and reload the Carriers, Flights, Weekdays and Months tables.
    *
    * WARNING! Do not drop any tables and do not clear the flights table.
    '''

    def clearTables(self):
        try:
            os.remove(DB_NAME)
            open(DB_NAME, 'w').close()
            os.system("chmod 777 {}".format(DB_NAME))
            # remove old db file

            # I have to reconstruct the db before each test
            self.conn = apsw.Connection(self.db_name, statementcachesize=0)

            self.conn.cursor().execute("PRAGMA foreign_keys=ON;")
            self.conn.cursor().execute(" PRAGMA serializable = true;")
            self.conn.cursor().execute(
                "CREATE TABLE Carriers (cid VARCHAR(7) PRIMARY KEY, name VARCHAR(83))")
            self.conn.cursor().execute("""
                    CREATE TABLE Months (
                        mid INT PRIMARY KEY,
                        month VARCHAR(9)
                    );""")

            self.conn.cursor().execute("""
                    CREATE TABLE Weekdays(
                        did INT PRIMARY KEY,
                        day_of_week VARCHAR(9)
                    );""")
            self.conn.cursor().execute("""
                    CREATE TABLE Flights (
                        fid INT PRIMARY KEY,
                        month_id INT,        -- 1-12
                        day_of_month INT,    -- 1-31
                        day_of_week_id INT,  -- 1-7, 1 = Monday, 2 = Tuesday, etc
                        carrier_id VARCHAR(7),
                        flight_num INT,
                        origin_city VARCHAR(34),
                        origin_state VARCHAR(47),
                        dest_city VARCHAR(34),
                        dest_state VARCHAR(46),
                        departure_delay INT, -- in mins
                        taxi_out INT,        -- in mins
                        arrival_delay INT,   -- in mins
                        canceled INT,        -- 1 means canceled
                        actual_time INT,     -- in mins
                        distance INT,        -- in miles
                        capacity INT,
                        price INT,           -- in $
                        FOREIGN KEY (carrier_id) REFERENCES Carriers(cid),
                        FOREIGN KEY (month_id) REFERENCES Months(mid),
                        FOREIGN KEY (day_of_week_id) REFERENCES Weekdays(did)
                    );""")
            self.conn.cursor().execute("""
                    CREATE TABLE Customers(
                        username VARCHAR(256),
                        password VARCHAR(256),
                        balance INT,
                        PRIMARY KEY (username)
                    );""")
            self.conn.cursor().execute("""
                    CREATE TABLE Itineraries(
                        direct INT, -- 1 or 0 stands for direct or one-hop flights
                        fid1 INT,
                        fid2 INT -- -1 means that this is a direct flight and has no second flight
                    );""")
            self.conn.cursor().execute("""
                    CREATE TABLE Reservations(
                        rid INT,
                        price INT,
                        fid1 INT,
                        fid2 INT,
                        paid INT,
                        canceled INT,
                        username VARCHAR(256),
                        day_of_month INT,
                        PRIMARY KEY (rid)
                    );""")
            self.conn.cursor().execute("""
                    CREATE TABLE ReservationsId(
                        rid INT
                    );""")

            self.conn.cursor().execute("INSERT INTO ReservationsId VALUES (1);")

            # reload db file for next tests

            with open("carriers.csv") as carriers:
                carriers_data = csv.reader(carriers)
                self.conn.cursor().executemany("INSERT INTO Carriers VALUES (?, ?)", carriers_data)

            with open("months.csv") as months:
                months_data = csv.reader(months)
                self.conn.cursor().executemany("INSERT INTO Months VALUES (?, ?)", months_data)

            with open("weekdays.csv") as weekdays:
                weekdays_data = csv.reader(weekdays)
                self.conn.cursor().executemany("INSERT INTO Weekdays VALUES (?, ?)", weekdays_data)

            # conn.cursor().executemany() is too slow to load largecsv files... so i use the command line instead for flights.csv
            subprocess.run(['sqlite3',
                            "example.db",
                            '-cmd',
                            '.mode csv',
                            '.import flights-small.csv Flights'])

        except sqlite3.Error:
            print("clear table SQL execution meets Error")

###################################################################################################################################
    '''
   * Implement the create user function.
   *
   * @param username   new user's username. User names are unique the system.
   * @param password   new user's password.
   * @param initAmount initial amount to deposit into the user's account, should be >= 0 (failure
   *                   otherwise).
   *
   * @return either "Created user `username`\n" or "Failed to create user\n" if failed.
    '''

    def transactionCreateCustomer(self, username, password, initAmount):
        # this is an example function.
        response = ""
        try:
            if(initAmount >= 0):
                self.conn.cursor().execute(
                    self.CREATE_CUSTOMER_SQL.format(username, password, initAmount))
                response = "Created user {}\n".format(username)
            else:
                response = "Failed to create user\n"
        except apsw.ConstraintError:
            # we already have this customer. we can not create it again
            # print("create user meets apsw.ConstraintError")
            response = "Failed to create user\n"

        except apsw.BusyError:
            self.conn.setbusytimeout(5000)
        return response

    '''
   * Takes a user's username and password and attempts to log the user in.
   *
   * @param username user's username
   * @param password user's password
   *
   * @return If someone has already logged in, then return "User already logged in\n" For all other
   *         errors, return "Login failed\n". Otherwise, return "Logged in as [username]\n".
    '''

    def transactionLogin(self, username, password):
        # TODO your code here
        response = ""
        try:
            if(self.username is not None):
                response += "User already logged in\n"
            else:
                pswd = (self.conn.cursor().execute(
                    self.GET_PASSWORD_FROM_USERNAME.format(username))).fetchone()[0]
                if(pswd == password):
                    self.username = username
                    response += "Logged in as {}\n".format(username)
                else:
                    response += "Login failed\n"

        except apsw.ConstraintError:
            response += "Login failed\n"
        except apsw.BusyError:
            self.conn.setbusytimeout(5000)
        return response
    '''
   * Implement the search function.
   *
   * Searches for flights from the given origin city to the given destination city, on the given day
   * of the month. If {@code directFlight} is true, it only searches for direct flights, otherwise
   * is searches for direct flights and flights with two "hops." Only searches for up to the number
   * of itineraries given by {@code numberOfItineraries}.
   *
   * The results are sorted based on total flight time.
   *
   * @param originCity
   * @param destinationCity
   * @param directFlight        if true, then only search for direct flights, otherwise include
   *                            indirect flights as well
   * @param dayOfMonth
   * @param numberOfItineraries number of itineraries to return
   *
   * @return If no itineraries were found, return "No flights match your selection\n". If an error
   *         occurs, then return "Failed to search\n".
   *
   *         Otherwise, the sorted itineraries printed in the following format:
   *
   *         Itinerary [itinerary number]: [number of flights] flight(s), [total flight time]
   *         minutes\n [first flight in itinerary]\n ... [last flight in itinerary]\n
   *
   *         Each flight should be printed using the same format as in the {@code Flight} class.
   *         Itinerary numbers in each search should always start from 0 and increase by 1.
   *
   * @see Flight#toString()
   '''

    def transactionSearch(self, originCity, destCity, directFlight, dayOfMonth, numberOfItineraries):
        # TODO your code here
        response = ""
        self.lastItineraries.clear()
        try:
            if(directFlight == 1):
                result = self.conn.cursor().execute(self.SEARCH_DIRECT_FLIGHT.format(
                    originCity, destCity, dayOfMonth, numberOfItineraries)).fetchall()

                if not result:
                    response += "No flights match your selection\n"
                else:
                    for x in range(len(result)):
                        f1 = Flight(result[x][0], result[x][1], result[x][2], result[x][3], result[x]
                                    [4], result[x][5], result[x][6], result[x][7], result[x][8])
                        self.lastItineraries.append(Itinerary(f1.time, f1))
                        response += "Itinerary {}: 1 flight(s), {} minutes\n".format(
                            x, self.lastItineraries[x].time)
                        response += f1.toString()

            else:
                result1 = self.conn.cursor().execute(self.SEARCH_DIRECT_FLIGHT.format(
                    originCity, destCity, dayOfMonth, numberOfItineraries)).fetchall()
                if(len(result1) > 0):
                    for x in range(len(result1)):
                        f1 = Flight(result1[x][0], result1[x][1], result1[x][2], result1[x][3], result1[x]
                                    [4], result1[x][5], result1[x][6], result1[x][7], result1[x][8])
                        self.lastItineraries.append(Itinerary(f1.time, f1))
                else:
                    response += ""

                if(len(result1) < numberOfItineraries):
                    result2 = self.conn.cursor().execute(self.SEARCH_HOP_FLIGHT.format(
                        originCity, destCity, dayOfMonth, numberOfItineraries - len(result1))).fetchall()
                    if(len(result1+result2) == 0):
                        response += "No flights match your selection\n"
                        return response
                    else:
                        for x in range(len(result2)):
                            f1 = Flight(result2[x][0], result2[x][1], result2[x][2], result2[x][3], result2[x]
                                        [4], result2[x][5], result2[x][6], result2[x][7], result2[x][8])
                            f2 = Flight(result2[x][9], result2[x][10], result2[x][11], result2[x][12], result2[x]
                                        [13], result2[x][14], result2[x][15], result2[x][16], result2[x][17])
                            a = Itinerary(f1.time + f2.time, f1, f2)
                            self.lastItineraries.append(a)
                else:
                    response += ""
                self.sorted_Itinerary = sorted(
                    self.lastItineraries, key=lambda x: x.time)
                self.lastItineraries.clear()
                for i in self.sorted_Itinerary:
                    self.lastItineraries.append(i)
                self.sorted_Itinerary.clear()
                for x in range(len(self.lastItineraries)):
                    response += "Itinerary {}: {} flight(s), {} minutes\n".format(
                        x, self.lastItineraries[x].numFlights(), self.lastItineraries[x].time)
                    response += self.lastItineraries[x].getFlight1().toString()
                    if(self.lastItineraries[x].getFlight2().fid != -1):
                        response += self.lastItineraries[x].getFlight2().toString()
                    else:
                        response += ""

        except apsw.ConstraintError:
            response = "Failed to search\n"
        except apsw.BusyError:
            self.conn.setbusytimeout(5000)
        return response

    '''
   * Implements the book itinerary function.
   *
   * @param itineraryId ID of the itinerary to book. This must be one that is returned by search in
   *                    the current session.
   *
   * @return If the user is not logged in, then return "Cannot book reservations, not logged in\n".
   *         If the user is trying to book an itinerary with an invalid ID or without having done a
   *         search, then return "No such itinerary {@code itineraryId}\n". If the user already has
   *         a reservation on the same day as the one that they are trying to book now, then return
   *         "You cannot book two flights in the same day\n". For all other errors, return "Booking
   *         failed\n".
   *
   *         And if booking succeeded, return "Booked flight(s), reservation ID: [reservationId]\n"
   *         where reservationId is a unique number in the reservation system that starts from 1 and
   *         increments by 1 each time a successful reservation is made by any user in the system.
    '''

    def transactionBook(self, itineraryId):
        # TODO your code here
        response = ""
        try:
            if (self.username is None):
                response += "Cannot book reservations, not logged in\n"
                return response
            else:
                if (not self.lastItineraries or (itineraryId < 0 or itineraryId >= len(self.lastItineraries))):
                    response += "No such itinerary {}\n".format(itineraryId)
                    return response
                else:
                    if (self.lastItineraries[itineraryId].getFlight1().capacity == 0 or self.lastItineraries[itineraryId].getFlight2().capacity == 0):
                        response += "Booking failed\n"
                        return response
                    elif (self.checkFlightSameDay(self.username, self.lastItineraries[itineraryId].dayOfItinerary()) == True):
                        response += "You cannot book two flights in the same day\n"
                        return response
                    else:
                        if(len((self.conn.cursor().execute(self.GET_LAST_RESERVE_ID.format(self.username))).fetchall()) == 0):
                            self.newReserveId = 1
                        else:
                            self.newReserveId = (self.conn.cursor().execute(
                                self.GET_LAST_RESERVE_ID.format(self.username))).fetchone()[0] + 1

                        self.conn.cursor().execute(self.INSERT_RESERVATIONS_TABLE.format(self.newReserveId, self.lastItineraries[itineraryId].itineraryPrice(), self.lastItineraries[itineraryId].getFlight1(
                        ).fid, self.lastItineraries[itineraryId].getFlight2().fid, 0, 0, self.username, self.lastItineraries[itineraryId].getFlight1().dayOfMonth))
                        response += "Booked flight(s), reservation ID: {}\n".format(
                            self.newReserveId)

        except apsw.ConstraintError:
            response = "Booking failed\n"
        except apsw.BusyError:
            self.conn.setbusytimeout(5000)
        return response

    '''
   * Implements the pay function.
   *
   * @param reservationId the reservation to pay for.
   *
   * @return If no user has logged in, then return "Cannot pay, not logged in\n" If the reservation
   *         is not found / not under the logged in user's name, then return "Cannot find unpaid
   *         reservation [reservationId] under user: [username]\n" If the user does not have enough
   *         money in their account, then return "User has only [balance] in account but itinerary
   *         costs [cost]\n" For all other errors, return "Failed to pay for reservation
   *         [reservationId]\n"
   *
   *         If successful, return "Paid reservation: [reservationId] remaining balance:
   *         [balance]\n" where [balance] is the remaining balance in the user's account.
    '''

    def transactionPay(self, reservationId):
        # TODO your code here
        response = ""
        try:
            self.last_reserveId = (self.conn.cursor().execute(
                self.GET_LAST_RESERVE_ID.format(self.username))).fetchone()

            if (self.username is None):
                response += "Cannot pay, not logged in\n"
            else:
                self.currentBalance = (self.conn.cursor().execute(
                    self.GET_CUSTOMER_BALANCE.format(self.username))).fetchone()[0]

                if (self.last_reserveId is None or reservationId < 1 or reservationId > self.last_reserveId[0]):
                    response += "Cannot find unpaid reservation {} under user: {}\n".format(
                        reservationId, self.username)
                else:
                    targetReservationPrice = (self.conn.cursor().execute(
                        self.TARGET_RESERVATION_PRICE.format(reservationId))).fetchone()[0]
                    targetReservationUsername = (self.conn.cursor().execute(
                        self.TARGET_RESERVATION_USERNAME.format(reservationId))).fetchone()[0]
                    targetReservationPaid = (self.conn.cursor().execute(
                        self.TARGET_RESERVATION_PAID.format(reservationId))).fetchone()[0]

                    if (self.username != targetReservationUsername or targetReservationPaid == 1):
                        response += "Cannot find unpaid reservation {} under user: {}\n".format(
                            reservationId, self.username)
                    elif (self.currentBalance < targetReservationPrice):
                        response += "User has only {} in account but itinerary costs {}\n".format(
                            self.currentBalance, targetReservationPrice)
                    else:
                        self.conn.cursor().execute(self.UPDATE_CUSTOMER_BALANCE.format(
                            (self.currentBalance - targetReservationPrice), self.username))
                        self.currentBalance = self.currentBalance-targetReservationPrice
                        self.conn.cursor().execute(
                            self.UPDATE_RESERVATIONS_PAID.format(reservationId, self.username))
                        response += "Paid reservation: {} remaining balance: {}\n".format(
                            reservationId, self.currentBalance)
        except apsw.ConstraintError:
            response = "Failed to pay for reservation {}\n".format(
                reservationId)
        except apsw.BusyError:
            self.conn.setbusytimeout(5000)

        return response

    '''
   * Implements the reservations function.
   *
   * @return If no user has logged in, then return "Cannot view reservations, not logged in\n" If
   *         the user has no reservations, then return "No reservations found\n" For all other
   *         errors, return "Failed to retrieve reservations\n"
   *
   *         Otherwise return the reservations in the following format:
   *
   *         Reservation [reservation ID] paid: [true or false]:\n [flight 1 under the
   *         reservation]\n [flight 2 under the reservation]\n Reservation [reservation ID] paid:
   *         [true or false]:\n [flight 1 under the reservation]\n [flight 2 under the
   *         reservation]\n ...
   *
   *         Each flight should be printed using the same format as in the {@code Flight} class.
   *
   * @see Flight#toString()
    '''

    def transactionReservation(self):
        # TODO your code here
        response = ""
        try:
            if (self.username is None):
                response += "Cannot view reservations, not logged in\n"
            else:
                self.last_reserveId = (self.conn.cursor().execute(
                    self.GET_LAST_RESERVE_ID.format(self.username))).fetchone()
                if (self.last_reserveId is None):
                    response += "No reservations found\n"
                else:
                    reservation_result = (self.conn.cursor().execute(
                        self.GET_ALL_RESERVATIONS.format(self.username))).fetchall()
                    for x in range(len(reservation_result)):
                        if(reservation_result[x][4] == 1):
                            paid = "true"
                        else:
                            paid = "false"
                        response += "Reservation {} paid: {}:\n".format(
                            x+1, paid)
                        f1 = (self.conn.cursor().execute(
                            self.GET_FLIGHT_FROM_FID.format(reservation_result[x][2]))).fetchone()
                        flight1 = Flight(
                            f1[0], f1[1], f1[2], f1[3], f1[4], f1[5], f1[6], f1[7], f1[8])
                        response += flight1.toString()
                        if (reservation_result[x][3] != -1):
                            f2 = (self.conn.cursor().execute(
                                self.GET_FLIGHT_FROM_FID.format(reservation_result[x][3]))).fetchone()
                            flight2 = Flight(
                                f2[0], f2[1], f2[2], f2[3], f2[4], f2[5], f2[6], f2[7], f2[8])
                            response += flight2.toString()
                        else:
                            response += ""

        except apsw.ConstraintError:
            response = "Failed to retrieve reservations\n".format(
                reservationId)
        except apsw.BusyError:
            self.conn.setbusytimeout(5000)

        return response

    '''
   * Implements the cancel operation.
   *
   * @param reservationId the reservation ID to cancel
   *
   * @return If no user has logged in, then return "Cannot cancel reservations, not logged in\n" For
   *         all other errors, return "Failed to cancel reservation [reservationId]\n"
   *
   *         If successful, return "Canceled reservation [reservationId]\n"
   *
   *         Even though a reservation has been canceled, its ID should not be reused by the system.
    '''

    def transactionCancel(self, reservationId):
        # TODO your code here
        response = ""
        try:
            if (self.username is None):
                response += "Cannot view reservations, not logged in\n"

            else:
                if (len((self.conn.cursor().execute(self.GET_LAST_RESERVE_ID.format(self.username))).fetchall()) == 0):
                    response += "Failed to cancel reservation {}\n".format(
                        reservationId)
                else:
                    last_rid = (self.conn.cursor().execute(
                        self.GET_LAST_RESERVE_ID.format(self.username))).fetchone()[0]
                    if (reservationId < 1 or reservationId > last_rid):
                        response += "Failed to cancel reservation {}\n".format(
                            reservationId)
                    elif ((self.conn.cursor().execute(
                            self.TARGET_RESERVATION_CANCELED.format(reservationId))).fetchone()[0] == 1):
                        response += "Failed to cancel reservation {}\n".format(
                            reservationId)
                    else:
                        self.conn.cursor().execute(
                            self.UPDATE_RESERVATIONS_CANCELED.format(reservationId, self.username))
                        current_balance = (self.conn.cursor().execute(
                            self.GET_CUSTOMER_BALANCE.format(self.username))).fetchone()[0]
                        target_reservation_price = (self.conn.cursor().execute(
                            self.TARGET_RESERVATION_PRICE.format(reservationId))).fetchone()[0]
                        self.conn.cursor().execute(
                            self.UPDATE_CUSTOMER_BALANCE.format(current_balance + target_reservation_price, self.username))
                        response += "Canceled reservation {}\n".format(
                            reservationId)

        except apsw.ConstraintError:
            response = "Failed to cancel reservation {}\n".format(
                reservationId)
        except apsw.BusyError:
            self.conn.setbusytimeout(5000)

        return response

    '''
    Example utility function that uses prepared statements
    '''

    def checkFlightCapacity(self, fid):
        # a helper function that you will use to implement previous functions
        result = self.conn.cursor().execute(
            self.CHECK_FLIGHT_CAPACITY.format(fid)).fetchone()
        if(result != None):
            return result[16]
        else:
            return 0

    def checkFlightIsFull(self, fid):
        # a helper function that you will use to implement previous functions

        capacity = self.conn.cursor().execute(
            self.CHECK_FLIGHT_CAPACITY.format(fid)).fetchone()[0]
        booked_seats = self.conn.cursor().execute(
            self.CHECK_BOOKED_SEATS.format(fid)).fetchone()[0]
        # print("Checking booked/capacity {}/{}".format(booked_seats, capacity))
        return booked_seats >= capacity

    def checkFlightSameDay(self, username, dayOfMonth):
        # TODO your code here
        result = self.conn.cursor().execute(
            self.CHECK_FLIGHT_DAY.format(username, dayOfMonth)).fetchall()
        if(len(result) == 0):
            # have not found there are multiple flights on the specific day by current user.
            return False
        else:
            return True

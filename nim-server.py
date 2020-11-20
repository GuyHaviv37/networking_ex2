#!/usr/bin/python3
import socket
import struct
import sys
import errno

UTF = 'utf-8'

# Sends all of bytesData to conn
def mySendall(conn, bytesData):
    try:
        while (len(bytesData) != 0):
            ret = conn.send(bytesData)
            bytesData = bytesData[ret:]
    except OSError as error:
        print(error.strerror)
        return False
    return True

# Recieves MSGLEN bytes of data from socket 'conn'
# Returns bytes object - that can be unpacked into tuple
def myRecvall(conn,MSGLEN):
    STRUCT_SIZE = 33
    bytesLeft = 0
    chunks = []
    while bytesLeft < MSGLEN:
        try:
            data = conn.recv(1024) # to be changed later
        except OSError as error:
            if(error.errno == errno.ECONNREFUSED):
                # disconnected from socket
                return b'Q\x00\x00\x00\x00'
        if data == b'':
            # disconnected from socket
            return b'Q\x00\x00\x00\x00'
        bytesLeft += sys.getsizeof(data)-STRUCT_SIZE
        chunks.append(data)
    return b''.join(chunks)

# Preforms shutdown to the socket - i.e. checks for 'leftover' data on recv buffer
def shutdownSocket(conn):
    conn.shutdown(socket.SHUT_WR)
    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break
        except OSError as error:
            break
    conn.close()

# Gets command line input
# returns - N_a,N_b,N_c[,PORT]
# TESTED
def getConsoleInput():
    inputLen = len(sys.argv)
    if not(inputLen == 4  or inputLen==5) :
        print("Invalid number of arguements for nim-server")
        print("Should be 3/4 : heapA heapB heapC [PORT]")
        sys.exit(0)
    na = int(sys.argv[1])
    nb = int(sys.argv[2])
    nc = int(sys.argv[3])
    if(inputLen == 5): # can add check to viable PORT number , i.e. > 1024
        if sys.argv[4].isdigit():
            port = int(sys.argv[4])
        else:
            print("Error: PORT number specified is invalid.")
            sys.exit(0) 
    else:
        port = 6444
    return na,nb,nc,port

# Gets char as heapId
# 'A'/'B'/'C' returns 0,1,2 respectivly.
# 'Q' return 3
# Any other heapId (invalid) returns -1 
def parseHeapId(heapId):
    return {
        'A' : 0,
        'B' : 1,
        'C' : 2,
        'Q' : 3
    }.get(heapId,-1)

# Client input parser
# param - a bytes object
# Returns heaps array index to look for , or invalid index for quit / invalid move
# Returns amount of die to remove if heapIndex is valid
def parseRecvInput(bytesRecv):
    dataRecv = struct.unpack(">ci",bytesRecv)
    heapId , amount = dataRecv
    heapId = heapId.decode(UTF)
    heapIndex = parseHeapId(heapId)
    return heapIndex,amount

# Checks if current client move is valid
# 0 <= heapIndex <=2 && heaps[heapIndex] >= amount
# returns boolean
# TESTED
def checkValid(heaps,heapIndex,amount):
    if(heapIndex < 0 or heapIndex > 2):
        return False
    if amount <= 0:
        return False
    if(heaps[heapIndex] < amount):
        return False
    else:
        return True
    
# Makes server game move
# Looks for biggest heap and removes 1 from it
# TESTED
def updateHeapsServer(heaps):
    maxNum = max(heaps)
    for i in range(3):
        if heaps[i] == maxNum:
            heaps[i] -= 1
            break

# Makes client game move
# available only if checkValid returns True on params
# TESTED
def updateHeapsClient(heaps,heapIndex,amount):
    heaps[heapIndex] -= amount

# Checks if game was won
# TESTED
def checkForWin(heaps):
    return True if sum(heaps) <= 0 else False

# Main server function
def server(na,nb,nc,PORT):
    try:
        listenSocket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        listenSocket.bind(('',PORT))
        listenSocket.listen(1)
    except OSError as error:
        print('An error occured establishing a server:')
        print(error.strerror)
        if(listenSocket.fileno() >= 0):
            listenSocket.close()
        sys.exit(0)

    while True:
        try:
            conn , addr = listenSocket.accept()
        except OSError as err:
            print('Failed to accept an incoming connection... ')
            print(err.strerror)
            break
        #Initialize game
        init = True
        gameOver = False
        heaps = [na,nb,nc]
        messageTag = 'i'
        dataSent = struct.pack(">ciii",messageTag.encode(UTF),heaps[0],heaps[1],heaps[2])
        while(not gameOver): #can be changed to while True
            # Send message to client
            print(messageTag)
            if init == True: # send with 'i' tag
                init = False
            else: # send with messageTag
                dataSent = struct.pack(">ciii",messageTag.encode(UTF),heaps[0],heaps[1],heaps[2])

            if not mySendall(conn,dataSent):
                break # Quit current game

            # Receive message from client
            bytesRecv = myRecvall(conn,5)
            heapIndex, amount = parseRecvInput(bytesRecv)
            # Make game move and set messageTag:
            if(heapIndex >= 3): # Quit current game
                break
            print(checkValid(heaps,heapIndex,amount))
            if(not checkValid(heaps,heapIndex,amount)):
                messageTag = 'x'
                updateHeapsServer(heaps)
                if(checkForWin(heaps)):
                    # server wins - last client move was invalid
                    messageTag = 't'
            else:
                messageTag = 'g'
                updateHeapsClient(heaps,heapIndex,amount)
                if(checkForWin(heaps)):
                    # client wins - last client move was valid
                    messageTag = 'c'
                else:
                    updateHeapsServer(heaps)
                    if(checkForWin(heaps)):
                        # server wins - last client move was valid
                        messageTag = 's'
            #continue program with loop
        if(conn.fileno() >= 0):
            shutdownSocket(conn)
            #conn.close()
    listenSocket.close()

#Main function for the program
def main():
    na,nb,nc,PORT = getConsoleInput()
    server(na,nb,nc,PORT)


def test():
    #test_basicGame(5,5,5)
    #recv = test_Recvall()
    heapIndex , amount = parseRecvInput(b'X\x00\x00\x00\x00')
    print(heapIndex,amount)

    

def test_Recvall():
    sent = struct.pack(">ci",b'A',999)
    print(f"message to send: {sent}")
    MSGLEN = struct.calcsize(">ci")
    STRUCT_SIZE = 33
    bytesLeft = 0
    chunks = []
    while bytesLeft < MSGLEN:
        data = sent[0:2]
        if data == b'':
            print("disconnect")
            return
        else:
            bytesLeft += sys.getsizeof(data)-STRUCT_SIZE
            chunks.append(data)
        sent = sent[2:]
    print("message recieved fully")
    print(f"message : {b''.join(chunks)}")
    return b''.join(chunks)
        



def test_basicGame(na,nb,nc):
    heaps = [na,nb,nc]
    while(True):
        print(heaps)
        index = int(input())
        amount = int(input())
        if(checkValid(heaps,index,amount)):
            updateHeapsClient(heaps,index,amount)
        if(checkForWin(heaps)):
            print("Client won")
            break
        updateHeapsServer(heaps)
        if(checkForWin(heaps)):
            print("Server won")
            break

DEBUG = False
func = main if not DEBUG else test
func()
